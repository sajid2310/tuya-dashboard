const $ = (sel) => document.querySelector(sel);

// ---------------------------------------------------------------------
// Icons (inline SVG, feather-style — no external font/icon CDN so this
// keeps working fully offline on your LAN).
// ---------------------------------------------------------------------
const ICONS = {
  search: `<svg class="i" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>`,
  sync: `<svg class="i" viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>`,
  moon: `<svg class="i" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`,
  sun: `<svg class="i" viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`,
  grid: `<svg class="i" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>`,
  list: `<svg class="i" viewBox="0 0 24 24"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>`,
  cloud: `<svg class="i" viewBox="0 0 24 24"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/></svg>`,
  external: `<svg class="i" viewBox="0 0 24 24"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>`,
  edit: `<svg class="i" viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`,
  refresh: `<svg class="i" viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4-4.64 4.36A9 9 0 0 1 3.51 15"/></svg>`,
  eye: `<svg class="i" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`,
  eyeOff: `<svg class="i" viewBox="0 0 24 24"><path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`,
  copy: `<svg class="i" viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`,
  x: `<svg class="i" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
  chevronDown: `<svg class="i" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"/></svg>`,
  chevronUp: `<svg class="i" viewBox="0 0 24 24"><polyline points="18 15 12 9 6 15"/></svg>`,
  plug: `<svg class="i" viewBox="0 0 24 24"><path d="M9 2v4M15 2v4M6 8h12a1 1 0 0 1 1 1v3a7 7 0 0 1-14 0V9a1 1 0 0 1 1-1z"/><path d="M12 19v3"/></svg>`,
  toggleSwitch: `<svg class="i" viewBox="0 0 24 24"><rect x="1" y="5" width="22" height="14" rx="7"/><circle cx="16" cy="12" r="3"/></svg>`,
  bulb: `<svg class="i" viewBox="0 0 24 24"><path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.2 1 2.05V17h6v-.25c0-.85.4-1.55 1-2.05A7 7 0 0 0 12 2z"/></svg>`,
  boxes: `<svg class="i xl" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>`,
};

function icon(name, extraClass) {
  const svg = ICONS[name] || "";
  return extraClass ? svg.replace('class="i"', `class="i ${extraClass}"`) : svg;
}

function mountIcons(root) {
  root.querySelectorAll("[data-icon]").forEach((el) => {
    el.innerHTML = icon(el.getAttribute("data-icon"));
  });
  root.querySelectorAll("[data-icon-prefix]").forEach((el) => {
    if (el.querySelector("svg.i")) return;
    el.insertAdjacentHTML("afterbegin", icon(el.getAttribute("data-icon-prefix")));
  });
}

function categoryIcon(cat) {
  if (cat === "kg") return "toggleSwitch";
  if (cat === "dj") return "bulb";
  return "plug";
}

// ---------------------------------------------------------------------
// State
// ---------------------------------------------------------------------
let devices = [];
let revealed = new Set();
let pollTimer = null;
let state = {
  search: "",
  filter: "all",
  sortKey: "name",
  sortDir: "asc",
  view: localStorage.getItem("tuya_dashboard_view") || "table",
};

function toast(msg, kind) {
  const el = $("#toast");
  el.innerHTML = "";
  const span = document.createElement("span");
  span.textContent = msg;
  el.appendChild(span);
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

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function relativeTime(ts) {
  if (!ts) return null;
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return "just now";
  if (diff < 3600) return Math.floor(diff / 60) + "m ago";
  if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
  return Math.floor(diff / 86400) + "d ago";
}

// ---------------------------------------------------------------------
// Filtering / sorting
// ---------------------------------------------------------------------
function applyFilters(list) {
  let out = list;
  const q = state.search.trim().toLowerCase();
  if (q) {
    out = out.filter((d) =>
      (d.name || "").toLowerCase().includes(q) ||
      (d.ip || "").toLowerCase().includes(q) ||
      (d.id || "").toLowerCase().includes(q) ||
      (d.category || "").toLowerCase().includes(q) ||
      (d.product_name || "").toLowerCase().includes(q)
    );
  }
  if (state.filter === "online") out = out.filter((d) => d.online);
  else if (state.filter === "offline") out = out.filter((d) => !d.online);
  else if (state.filter === "nokey") out = out.filter((d) => !d.key);

  const key = state.sortKey;
  const dir = state.sortDir === "asc" ? 1 : -1;
  out = [...out].sort((a, b) => {
    let av = a[key], bv = b[key];
    if (key === "online") { av = a.online ? 1 : 0; bv = b.online ? 1 : 0; }
    av = av === undefined || av === null ? "" : av;
    bv = bv === undefined || bv === null ? "" : bv;
    if (typeof av === "string") av = av.toLowerCase();
    if (typeof bv === "string") bv = bv.toLowerCase();
    if (av < bv) return -1 * dir;
    if (av > bv) return 1 * dir;
    return 0;
  });
  return out;
}

// ---------------------------------------------------------------------
// Stats
// ---------------------------------------------------------------------
function renderStats(all) {
  const total = all.length;
  const online = all.filter((d) => d.online).length;
  const offline = total - online;
  const noKey = all.filter((d) => !d.key).length;

  const cards = [
    { icon: "boxes", cls: "accent", value: total, label: "Total devices" },
    { icon: "toggleSwitch", cls: "green", value: online, label: "Online" },
    { icon: "eyeOff", cls: "red", value: offline, label: "Offline" },
    { icon: "eye", cls: "yellow", value: noKey, label: "Missing local key" },
  ];
  $("#statsGrid").innerHTML = cards.map((c) => `
    <div class="stat-card">
      <div class="stat-icon ${c.cls}">${icon(c.icon)}</div>
      <div>
        <div class="stat-value">${c.value}</div>
        <div class="stat-label">${c.label}</div>
      </div>
    </div>
  `).join("");
}

// ---------------------------------------------------------------------
// Table / grid rendering
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
    ${key ? `<button data-reveal="${d.id}" title="${shown ? "Hide" : "Show"}">${icon(shown ? "eyeOff" : "eye")}</button>` : ""}
    ${key ? `<button data-copy="${escapeHtml(key)}" title="Copy">${icon("copy")}</button>` : ""}
  </div>`;
}

function controlToggle(d) {
  const dp = d.switch_dp || "1";
  const dps = d.last_dps || {};
  const on = dps[dp] === true;
  const disabled = !(d.ip && d.key) ? "disabled" : "";
  return `<button class="toggle ${on ? "on" : ""}" ${disabled}
            data-toggle="${d.id}" data-dp="${dp}"
            title="${d.ip && d.key ? "Toggle switch" : "Missing IP/local key"}"></button>`;
}

function nameCell(d, size) {
  return `<div class="name-cell">
    <span class="avatar" style="${size ? `width:${size}px;height:${size}px` : ""}">${icon(categoryIcon(d.category))}</span>
    <div class="name-text">
      <span class="primary">${escapeHtml(d.name || d.id)}</span>
      <span class="secondary mono">${escapeHtml(d.id)}</span>
    </div>
  </div>`;
}

function renderTable(list) {
  const tbody = $("#deviceTableBody");
  tbody.innerHTML = list.map((d) => `
    <tr data-row="${d.id}">
      <td>${nameCell(d)}</td>
      <td>${statusPill(d)}</td>
      <td class="mono">${escapeHtml(d.ip || "—")}</td>
      <td class="mono">${escapeHtml(d.id)}</td>
      <td>${keyCell(d)}</td>
      <td>${d.version ? `<span class="badge">${escapeHtml(d.version)}</span>` : "—"}</td>
      <td>${escapeHtml(d.category || d.product_name || "—")}</td>
      <td>${controlToggle(d)}</td>
      <td>
        <div class="row-actions">
          <button class="icon-btn" data-edit="${d.id}" title="Edit">${icon("edit")}</button>
          <button class="icon-btn" data-refresh="${d.id}" title="Refresh status">${icon("refresh")}</button>
        </div>
      </td>
    </tr>
  `).join("");
}

function renderGrid(list) {
  const grid = $("#deviceGrid");
  grid.innerHTML = list.map((d) => `
    <div class="device-card" data-row="${d.id}">
      <div class="device-card-top">
        <div class="device-card-id">
          ${nameCell(d)}
        </div>
        ${statusPill(d)}
      </div>
      <div class="device-card-meta">
        <div class="row"><span>IP</span><span class="mono">${escapeHtml(d.ip || "—")}</span></div>
        <div class="row"><span>Version</span><span>${d.version ? `<span class="badge">${escapeHtml(d.version)}</span>` : "—"}</span></div>
        <div class="row"><span>Local key</span>${keyCell(d)}</div>
      </div>
      <div class="device-card-footer">
        <div class="row-actions">
          <button class="icon-btn" data-edit="${d.id}" title="Edit">${icon("edit")}</button>
          <button class="icon-btn" data-refresh="${d.id}" title="Refresh status">${icon("refresh")}</button>
        </div>
        ${controlToggle(d)}
      </div>
    </div>
  `).join("");
}

function renderEmptyState(hasAnyDevices) {
  const empty = $("#emptyState");
  if (hasAnyDevices) {
    empty.innerHTML = `
      <div class="empty-icon">${icon("search")}</div>
      <h3>No devices match</h3>
      <p>Try clearing the search box or switching filters.</p>
    `;
  } else {
    empty.innerHTML = `
      <div class="empty-icon">${icon("boxes")}</div>
      <h3>No devices yet</h3>
      <p>Click "Sync devices" to scan your LAN and (optionally) your Tuya Cloud account for switches.</p>
      <button class="btn primary" id="emptyStateSync">${icon("sync")}Sync devices</button>
    `;
    const btn = $("#emptyStateSync");
    if (btn) btn.addEventListener("click", startSync);
  }
}

function render() {
  renderStats(devices);
  const filtered = applyFilters(devices);
  $("#resultCount").textContent = devices.length
    ? `${filtered.length} of ${devices.length} device${devices.length === 1 ? "" : "s"}`
    : "";

  const tableView = $("#tableView");
  const gridView = $("#gridView");
  const empty = $("#emptyState");

  if (!filtered.length) {
    tableView.classList.add("hidden");
    gridView.classList.add("hidden");
    empty.classList.remove("hidden");
    renderEmptyState(devices.length > 0);
    return;
  }
  empty.classList.add("hidden");
  if (state.view === "grid") {
    tableView.classList.add("hidden");
    gridView.classList.remove("hidden");
    renderGrid(filtered);
  } else {
    gridView.classList.add("hidden");
    tableView.classList.remove("hidden");
    renderTable(filtered);
  }
}

async function loadDevices() {
  devices = await api("/api/devices");
  render();
  const lastSeen = devices.reduce((max, d) => Math.max(max, d.last_seen || 0), 0);
  $("#lastSynced").textContent = lastSeen ? `Last synced ${relativeTime(lastSeen)}` : "Not synced yet";
  return devices;
}

// ---------------------------------------------------------------------
// Scan / sync
// ---------------------------------------------------------------------
async function startSync() {
  $("#btnSync").disabled = true;
  const banner = $("#scanBanner");
  banner.className = "banner";
  banner.innerHTML = `${icon("sync", "spin")}<span>Starting scan...</span>`;
  banner.classList.remove("hidden");
  try {
    await api("/api/scan", { method: "POST", body: JSON.stringify({ scantime: 12, use_cloud: true, forcescan: true }) });
  } catch (e) {
    banner.className = "banner error";
    banner.innerHTML = `${icon("x")}<span>Failed to start scan: ${escapeHtml(e.message)}</span>`;
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
      banner.innerHTML = `${icon("sync", "spin")}<span>${escapeHtml(job.progress || "Scanning...")}</span>`;
    } else {
      clearInterval(pollTimer);
      $("#btnSync").disabled = false;
      if (job.error) {
        banner.className = "banner error";
        banner.innerHTML = `${icon("x")}<span>Scan failed: ${escapeHtml(job.error)}</span>`;
      } else {
        banner.className = "banner success";
        const r = job.result || {};
        let msg = `Sync complete — found ${r.found_on_lan || 0} device(s) on the LAN`;
        if (r.found_by_mac_sweep) msg += `, +${r.found_by_mac_sweep} more located by MAC/ARP sweep`;
        if (r.from_cloud) msg += `, matched against ${r.from_cloud} from your Tuya Cloud account`;
        if (job.cloud_error) msg += `. Cloud note: ${job.cloud_error}`;
        banner.innerHTML = `${icon("sync")}<span>${escapeHtml(msg)}</span>`;
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
function openEdit(id) {
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
// Theme + view persistence
// ---------------------------------------------------------------------
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("tuya_dashboard_theme", theme);
  const btn = $("#themeToggle");
  const label = $("#themeLabel");
  const svgHolder = btn.querySelector("svg.i");
  if (svgHolder) svgHolder.outerHTML = icon(theme === "dark" ? "moon" : "sun");
  if (label) label.textContent = theme === "dark" ? "Dark mode" : "Light mode";
}

function applyView(view) {
  state.view = view;
  localStorage.setItem("tuya_dashboard_view", view);
  document.querySelectorAll(".view-btn").forEach((b) => {
    b.classList.toggle("active", b.getAttribute("data-view") === view);
  });
  render();
}

// ---------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  mountIcons(document);

  const savedTheme = localStorage.getItem("tuya_dashboard_theme") || "dark";
  applyTheme(savedTheme);
  applyView(state.view);

  loadDevices().catch((e) => toast("Failed to load devices: " + e.message, "error"));

  $("#btnSync").addEventListener("click", startSync);
  $("#navCloudSettings").addEventListener("click", openSettings);
  $("#btnCfgSave").addEventListener("click", saveSettings);
  $("#btnCfgClear").addEventListener("click", clearSettings);
  $("#btnCfgCancel").addEventListener("click", () => $("#settingsModal").classList.add("hidden"));
  $("#btnCfgClose").addEventListener("click", () => $("#settingsModal").classList.add("hidden"));
  $("#btnEditSave").addEventListener("click", saveEdit);
  $("#btnEditCancel").addEventListener("click", () => $("#editModal").classList.add("hidden"));
  $("#btnEditClose").addEventListener("click", () => $("#editModal").classList.add("hidden"));
  $("#btnEditDelete").addEventListener("click", deleteEditingDevice);

  $("#themeToggle").addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme");
    applyTheme(cur === "dark" ? "light" : "dark");
  });

  document.querySelectorAll(".view-btn").forEach((b) => {
    b.addEventListener("click", () => applyView(b.getAttribute("data-view")));
  });

  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      state.filter = chip.getAttribute("data-filter");
      document.querySelectorAll(".chip").forEach((c) => c.classList.toggle("active", c === chip));
      render();
    });
  });

  let searchDebounce;
  $("#searchInput").addEventListener("input", (e) => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
      state.search = e.target.value;
      render();
    }, 120);
  });

  document.querySelectorAll("th.sortable").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.getAttribute("data-sort");
      if (state.sortKey === key) {
        state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = key;
        state.sortDir = "asc";
      }
      document.querySelectorAll("th.sortable svg.i").forEach((s) => {
        s.outerHTML = icon("chevronDown");
      });
      const activeSvg = th.querySelector("svg.i");
      if (activeSvg) activeSvg.outerHTML = icon(state.sortDir === "asc" ? "chevronUp" : "chevronDown");
      render();
    });
  });

  document.body.addEventListener("click", async (ev) => {
    const revealBtn = ev.target.closest("[data-reveal]");
    if (revealBtn) {
      const id = revealBtn.getAttribute("data-reveal");
      if (revealed.has(id)) revealed.delete(id); else revealed.add(id);
      render();
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
      openEdit(editBtn.getAttribute("data-edit"));
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
