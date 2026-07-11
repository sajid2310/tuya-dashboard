const $ = (sel) => document.querySelector(sel);

let pollTimer = null;
let revealed = new Set();

function toast(msg, kind) {
  const el = $("#toast");
  el.textContent = msg;
  el.className = "toast" + (kind ? " " + kind : "");
  el.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add("hidden"), 4500);
}

async function api(path, opts) {
  const res = await fetch(path, Object.assign({
    headers: { "Content-Type": "application/json" },
  }, opts));
  let body = null;
  try { body = await res.json(); } catch (e) { /* no body */ }
  if (!res.ok) {
    const msg = (body && (body.error || body.cloud_error)) || res.statusText;
    throw new Error(msg);
  }
  return body;
}

// ---------------------------------------------------------------------
// Device table
// ---------------------------------------------------------------------
function statusPill(d) {
  if (d.online === true) return `<span class="pill online"><span class="dot"></span>Online</span>`;
  if (d.online === false) return `<span class="pill offline"><span class="dot"></span>Offline</span>`;
  return `<span class="pill unknown"><span class="dot"></span>Unknown</span>`;
}

function keyCell(d) {
  const shown = revealed.has(d.id);
  const key = d.key || "";
  const display = key ? (shown ? key : "•".repeat(Math.min(key.length, 16))) : "—";
  return `<div class="key-cell">
    <span class="mono">${escapeHtml(display)}</span>
    ${key ? `<button data-reveal="${d.id}" title="${shown ? 'Hide' : 'Show'}">${shown ? "🙈" : "👁"}</button>` : ""}
    ${key ? `<button data-copy="${escapeAttr(key)}" title="Copy">📋</button>` : ""}
  </div>`;
}

function controlCell(d) {
  const dp = d.switch_dp || "1";
  const dps = d.last_dps || {};
  const state = dps[dp];
  const disabled = !(d.ip && d.key) ? "disabled" : "";
  const on = state === true;
  return `<button class="toggle ${on ? "on" : ""}" ${disabled}
            data-toggle="${d.id}" data-dp="${dp}"
            title="${d.ip && d.key ? "Toggle switch" : "Missing IP/local key"}"></button>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function escapeAttr(s) { return escapeHtml(s); }

function renderDevices(devices) {
  const tbody = $("#deviceTableBody");
  if (!devices.length) {
    tbody.innerHTML = `<tr id="emptyRow"><td colspan="9" class="empty">No devices yet. Click "Sync devices" to scan your LAN and (optionally) your Tuya Cloud account.</td></tr>`;
    return;
  }
  tbody.innerHTML = devices.map((d) => `
    <tr data-row="${d.id}">
      <td>${escapeHtml(d.name || d.id)}</td>
      <td>${statusPill(d)}</td>
      <td class="mono">${escapeHtml(d.ip || "—")}</td>
      <td class="mono">${escapeHtml(d.id)}</td>
      <td>${keyCell(d)}</td>
      <td class="mono">${escapeHtml(d.version || "—")}</td>
      <td>${escapeHtml(d.category || d.product_name || "—")}</td>
      <td>${controlCell(d)}</td>
      <td>
        <div class="row-actions">
          <button class="icon-btn" data-edit="${d.id}" title="Edit">✎</button>
          <button class="icon-btn" data-refresh="${d.id}" title="Refresh status">⟳</button>
        </div>
      </td>
    </tr>
  `).join("");

  const summary = $("#summary");
  const onlineCount = devices.filter((d) => d.online).length;
  const withKeys = devices.filter((d) => d.key).length;
  summary.classList.remove("hidden");
  summary.innerHTML = `
    <div><b>${devices.length}</b> known device${devices.length === 1 ? "" : "s"}</div>
    <div><b>${onlineCount}</b> online</div>
    <div><b>${withKeys}</b> with local key</div>
  `;
}

async function loadDevices() {
  const devices = await api("/api/devices");
  renderDevices(devices);
  return devices;
}

// ---------------------------------------------------------------------
// Scan / sync
// ---------------------------------------------------------------------
async function startSync() {
  $("#btnSync").disabled = true;
  const banner = $("#scanBanner");
  banner.className = "banner";
  banner.textContent = "Starting scan...";
  banner.classList.remove("hidden");
  try {
    await api("/api/scan", { method: "POST", body: JSON.stringify({ scantime: 12, use_cloud: true, forcescan: true }) });
  } catch (e) {
    banner.className = "banner error";
    banner.textContent = "Failed to start scan: " + e.message;
    $("#btnSync").disabled = false;
    return;
  }
  pollScan();
}

function pollScan() {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    let job;
    try {
      job = await api("/api/scan/status");
    } catch (e) {
      return;
    }
    const banner = $("#scanBanner");
    banner.classList.remove("hidden");
    if (job.running) {
      banner.className = "banner";
      banner.textContent = job.progress || "Scanning...";
    } else {
      clearInterval(pollTimer);
      $("#btnSync").disabled = false;
      if (job.error) {
        banner.className = "banner error";
        banner.textContent = "Scan failed: " + job.error;
      } else {
        banner.className = "banner success";
        const r = job.result || {};
        let msg = `Sync complete — found ${r.found_on_lan || 0} device(s) on the LAN`;
        if (r.from_cloud) msg += `, matched against ${r.from_cloud} from your Tuya Cloud account`;
        if (job.cloud_error) msg += `. Cloud note: ${job.cloud_error}`;
        banner.textContent = msg;
        setTimeout(() => banner.classList.add("hidden"), 8000);
      }
      loadDevices();
    }
  }, 900);
}

// ---------------------------------------------------------------------
// Settings modal
// ---------------------------------------------------------------------
async function openSettings() {
  const cfg = await api("/api/config");
  const sel = $("#cfgRegion");
  sel.innerHTML = Object.entries(cfg.regions).map(([k, v]) => `<option value="${k}">${v} (${k})</option>`).join("");
  sel.value = cfg.region;
  $("#cfgAccessId").value = "";
  $("#cfgAccessSecret").value = "";
  $("#cfgAccessId").placeholder = cfg.access_id_masked ? "Current: " + cfg.access_id_masked : "e.g. abcd1234efgh5678";
  $("#cfgCurrent").textContent = cfg.configured
    ? "Cloud credentials are currently set. Leave fields blank to keep them, or enter new values to replace."
    : "No cloud credentials set yet — local network scanning will still work, but device names/local keys won't be filled in automatically.";
  $("#settingsModal").classList.remove("hidden");
}

async function saveSettings() {
  try {
    await api("/api/config", {
      method: "POST",
      body: JSON.stringify({
        access_id: $("#cfgAccessId").value.trim(),
        access_secret: $("#cfgAccessSecret").value.trim(),
        region: $("#cfgRegion").value,
      }),
    });
    toast("Saved cloud credentials.", "success");
    $("#settingsModal").classList.add("hidden");
  } catch (e) {
    toast("Failed to save: " + e.message, "error");
  }
}

async function clearSettings() {
  try {
    await api("/api/config", { method: "DELETE" });
    toast("Cleared cloud credentials.", "success");
    $("#settingsModal").classList.add("hidden");
  } catch (e) {
    toast("Failed: " + e.message, "error");
  }
}

// ---------------------------------------------------------------------
// Edit modal
// ---------------------------------------------------------------------
async function openEdit(id, devices) {
  const d = devices.find((x) => x.id === id);
  if (!d) return;
  $("#editId").value = d.id;
  $("#editName").value = d.name || "";
  $("#editIp").value = d.ip || "";
  $("#editKey").value = d.key || "";
  $("#editVersion").value = String(d.version || "3.3");
  $("#editDp").value = d.switch_dp || "1";
  $("#editModal").classList.remove("hidden");
}

async function saveEdit() {
  const id = $("#editId").value;
  try {
    await api(`/api/devices/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({
        name: $("#editName").value.trim(),
        ip: $("#editIp").value.trim(),
        key: $("#editKey").value.trim(),
        version: $("#editVersion").value,
        switch_dp: $("#editDp").value.trim() || "1",
      }),
    });
    $("#editModal").classList.add("hidden");
    toast("Device updated.", "success");
    await loadDevices();
  } catch (e) {
    toast("Failed to save: " + e.message, "error");
  }
}

async function deleteEditingDevice() {
  const id = $("#editId").value;
  if (!confirm("Remove this device from the dashboard? (Does not affect the physical device or your Tuya account.)")) return;
  try {
    await api(`/api/devices/${encodeURIComponent(id)}`, { method: "DELETE" });
    $("#editModal").classList.add("hidden");
    toast("Device removed.", "success");
    await loadDevices();
  } catch (e) {
    toast("Failed to delete: " + e.message, "error");
  }
}

// ---------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  loadDevices().catch((e) => toast("Failed to load devices: " + e.message, "error"));

  $("#btnSync").addEventListener("click", startSync);
  $("#btnSettings").addEventListener("click", openSettings);
  $("#btnCfgSave").addEventListener("click", saveSettings);
  $("#btnCfgClear").addEventListener("click", clearSettings);
  $("#btnCfgCancel").addEventListener("click", () => $("#settingsModal").classList.add("hidden"));
  $("#btnEditSave").addEventListener("click", saveEdit);
  $("#btnEditCancel").addEventListener("click", () => $("#editModal").classList.add("hidden"));
  $("#btnEditDelete").addEventListener("click", deleteEditingDevice);

  document.body.addEventListener("click", async (ev) => {
    const revealBtn = ev.target.closest("[data-reveal]");
    if (revealBtn) {
      const id = revealBtn.getAttribute("data-reveal");
      if (revealed.has(id)) revealed.delete(id); else revealed.add(id);
      loadDevices();
      return;
    }
    const copyBtn = ev.target.closest("[data-copy]");
    if (copyBtn) {
      const val = copyBtn.getAttribute("data-copy");
      try {
        await navigator.clipboard.writeText(val);
        toast("Copied to clipboard.", "success");
      } catch (e) {
        toast("Copy failed — select and copy manually.", "error");
      }
      return;
    }
    const editBtn = ev.target.closest("[data-edit]");
    if (editBtn) {
      const devices = await loadDevices();
      openEdit(editBtn.getAttribute("data-edit"), devices);
      return;
    }
    const refreshBtn = ev.target.closest("[data-refresh]");
    if (refreshBtn) {
      const id = refreshBtn.getAttribute("data-refresh");
      refreshBtn.disabled = true;
      try {
        await api(`/api/devices/${encodeURIComponent(id)}/status`);
        await loadDevices();
      } catch (e) {
        toast("Status check failed: " + e.message, "error");
      } finally {
        refreshBtn.disabled = false;
      }
      return;
    }
    const toggleBtn = ev.target.closest("[data-toggle]");
    if (toggleBtn && !toggleBtn.disabled) {
      const id = toggleBtn.getAttribute("data-toggle");
      const dp = toggleBtn.getAttribute("data-dp");
      toggleBtn.disabled = true;
      try {
        await api(`/api/devices/${encodeURIComponent(id)}/toggle`, {
          method: "POST",
          body: JSON.stringify({ dp }),
        });
        await loadDevices();
      } catch (e) {
        toast("Toggle failed: " + e.message, "error");
      } finally {
        toggleBtn.disabled = false;
      }
      return;
    }
  });
});
