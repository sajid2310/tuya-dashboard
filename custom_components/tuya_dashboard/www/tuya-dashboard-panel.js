/**
 * Tuya Dashboard - bundled Home Assistant sidebar panel.
 *
 * Self-contained on purpose: no bundler, no npm dependency, no external
 * card (e.g. flex-table-card). Plain ES module loaded directly by the
 * browser via panel_custom, styled with Home Assistant's own theme CSS
 * variables so it matches whatever theme the user has selected.
 *
 * Data comes from this integration's own services (tuya_dashboard.*),
 * called over the existing HA websocket connection - no separate REST
 * server, no separate auth.
 */

const REFRESH_MS = 30000;

function callService(hass, service, data) {
  return hass.connection.sendMessagePromise({
    type: "call_service",
    domain: "tuya_dashboard",
    service,
    service_data: data || {},
    return_response: true,
  });
}

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function relativeTime(ts) {
  if (!ts) return "never";
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return "just now";
  if (diff < 3600) return Math.floor(diff / 60) + "m ago";
  if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
  return Math.floor(diff / 86400) + "d ago";
}

const TYPE_LABELS = { switch: "Switch", plug: "Plug", light: "Light", fan: "Fan", other: "Other" };

class TuyaDashboardPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._devices = [];
    this._revealed = new Set();
    this._search = "";
    this._statusFilter = "all";
    this._typeFilter = "all";
    this._loading = true;
    this._error = null;
    this._diag = null; // { deviceId, name, loading, result }
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._render();
      this._refresh();
      this._timer = setInterval(() => this._refresh(), REFRESH_MS);
    }
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    if (this._hass) this._render();
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  async _refresh() {
    if (!this._hass) return;
    try {
      const msg = await callService(this._hass, "list_devices", {});
      this._devices = (msg.response && msg.response.devices) || [];
      this._error = null;
    } catch (e) {
      this._error = e.message || String(e);
    }
    this._loading = false;
    this._renderBody();
  }

  _filtered() {
    let out = this._devices;
    const q = this._search.trim().toLowerCase();
    if (q) {
      out = out.filter((d) =>
        (d.name || "").toLowerCase().includes(q) ||
        (d.ip || "").toLowerCase().includes(q) ||
        (d.device_id || "").toLowerCase().includes(q) ||
        (d.category || "").toLowerCase().includes(q)
      );
    }
    if (this._statusFilter === "online") out = out.filter((d) => d.status === "online");
    else if (this._statusFilter === "offline") out = out.filter((d) => d.status !== "online");
    else if (this._statusFilter === "nokey") out = out.filter((d) => !d.local_key);
    if (this._typeFilter !== "all") out = out.filter((d) => (d.type || "other") === this._typeFilter);
    return [...out].sort((a, b) => (a.name || "").localeCompare(b.name || ""));
  }

  async _setControl(deviceId, dp, value, btn) {
    if (btn) btn.disabled = true;
    try {
      const msg = await callService(this._hass, "set_control", { device_id: deviceId, dp, value });
      if (msg.response && msg.response.error) throw new Error(msg.response.error);
      await this._refresh();
    } catch (e) {
      this._toast("Control failed: " + (e.message || e));
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async _openDiagnose(deviceId, name) {
    this._diag = { deviceId, name, loading: true, result: null };
    this._renderBody();
    try {
      const msg = await callService(this._hass, "diagnose_device", { device_id: deviceId });
      this._diag = { deviceId, name, loading: false, result: msg.response };
    } catch (e) {
      this._diag = { deviceId, name, loading: false, result: { error: e.message || String(e) } };
    }
    this._renderBody();
  }

  _closeDiagnose() {
    this._diag = null;
    this._renderBody();
  }

  _toast(msg) {
    const el = this.shadowRoot.getElementById("toast");
    if (!el) return;
    el.textContent = msg;
    el.classList.add("show");
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => el.classList.remove("show"), 4000);
  }

  _controlsHtml(d) {
    const controls = (d.controls && d.controls.length) ? d.controls : [{ type: "toggle", dp: "1", label: "Power" }];
    const dps = d.last_dps || {};
    const reachable = !!(d.ip && d.local_key);
    return controls.map((c) => {
      if (c.type === "stepper") {
        const val = dps[c.dp];
        const shown = val === undefined || val === null ? "—" : escapeHtml(String(val));
        return `<span class="stepper" title="${escapeHtml(c.label)}">
          <button class="step-btn" data-step="-1" data-dp="${c.dp}" data-id="${d.device_id}" ${reachable ? "" : "disabled"}>-</button>
          <span class="step-val">${shown}</span>
          <button class="step-btn" data-step="1" data-dp="${c.dp}" data-id="${d.device_id}" ${reachable ? "" : "disabled"}>+</button>
        </span>`;
      }
      const on = dps[c.dp] === true;
      return `<button class="toggle ${on ? "on" : ""}" data-toggle data-dp="${c.dp}" data-id="${d.device_id}"
                data-val="${on ? "false" : "true"}" ${reachable ? "" : "disabled"}
                title="${reachable ? c.label : "Missing IP/local key"}"></button>`;
    }).join(" ");
  }

  _rowHtml(d) {
    const shown = this._revealed.has(d.device_id);
    const key = d.local_key || "";
    const keyDisplay = key ? (shown ? escapeHtml(key) : "•".repeat(Math.min(key.length, 14))) : "—";
    return `
      <tr>
        <td>${escapeHtml(d.name)}</td>
        <td><span class="pill ${d.status === "online" ? "online" : "offline"}">${d.status}</span></td>
        <td class="mono">${escapeHtml(d.ip || "—")}</td>
        <td class="mono small">${escapeHtml(d.device_id)}</td>
        <td class="mono key-cell">
          <span>${keyDisplay}</span>
          ${key ? `<button class="link-btn" data-reveal="${d.device_id}">${shown ? "hide" : "show"}</button>` : ""}
        </td>
        <td>${d.version ? `<span class="badge">${escapeHtml(d.version)}</span>` : "—"}</td>
        <td><span class="badge type-${d.type || "other"}">${TYPE_LABELS[d.type] || "Other"}</span> ${escapeHtml(d.category || "")}</td>
        <td>${this._controlsHtml(d)}</td>
        <td><button class="icon-btn" data-diagnose="${d.device_id}" data-name="${escapeHtml(d.name)}" title="Troubleshoot">&#9889;</button></td>
      </tr>`;
  }

  _diagHtml() {
    if (!this._diag) return "";
    const { name, loading, result } = this._diag;
    const side = (label, s) => {
      if (!s) return `<div class="diag-card"><div class="diag-head">${label}</div><div class="diag-status checking">Checking…</div></div>`;
      const cls = s.ok ? "ok" : "fail";
      return `<div class="diag-card">
        <div class="diag-head">${label}</div>
        <div class="diag-status ${cls}">${s.ok ? "Working" : "Not reachable"}</div>
        <div class="diag-detail">${escapeHtml(s.detail || "")}</div>
      </div>`;
    };
    const body = loading || !result
      ? side("Local (LAN)", null) + side("Tuya Cloud", null)
      : (result.error
          ? `<div class="diag-detail">${escapeHtml(result.error)}</div>`
          : side("Local (LAN)", result.local) + side("Tuya Cloud", result.cloud));
    const hint = (!loading && result && result.hint) ? `<div class="diag-hint">${escapeHtml(result.hint)}</div>` : "";
    return `
      <div class="modal-backdrop" id="diagBackdrop">
        <div class="modal">
          <div class="modal-head"><h3>Troubleshoot: ${escapeHtml(name)}</h3><button class="icon-btn" id="diagClose">✕</button></div>
          <div class="diag-grid">${body}</div>
          ${hint}
          <div class="modal-actions">
            <button class="btn" id="diagRerun">Run again</button>
            <button class="btn primary" id="diagCloseBtn">Close</button>
          </div>
        </div>
      </div>`;
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>${this._css()}</style>
      <div class="wrap">
        <div class="topbar">
          <h1>Tuya Devices</h1>
          <input id="search" type="text" placeholder="Search name, IP, ID…">
          <button class="btn" id="refreshBtn">Refresh</button>
        </div>
        <div class="chips" id="statusChips">
          <button class="chip active" data-status="all">All devices</button>
          <button class="chip" data-status="online">Online</button>
          <button class="chip" data-status="offline">Offline</button>
          <button class="chip" data-status="nokey">Missing key</button>
        </div>
        <div class="chips" id="typeChips">
          <button class="chip active" data-type="all">All types</button>
          <button class="chip" data-type="switch">Switches</button>
          <button class="chip" data-type="plug">Plugs</button>
          <button class="chip" data-type="light">Lights</button>
          <button class="chip" data-type="fan">Fans</button>
          <button class="chip" data-type="other">Other</button>
        </div>
        <div id="body"></div>
        <div id="toast" class="toast"></div>
      </div>`;

    const root = this.shadowRoot;
    root.getElementById("search").addEventListener("input", (e) => {
      this._search = e.target.value;
      this._renderBody();
    });
    root.getElementById("refreshBtn").addEventListener("click", () => this._refresh());
    root.getElementById("statusChips").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-status]");
      if (!btn) return;
      this._statusFilter = btn.getAttribute("data-status");
      root.querySelectorAll("#statusChips .chip").forEach((c) => c.classList.toggle("active", c === btn));
      this._renderBody();
    });
    root.getElementById("typeChips").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-type]");
      if (!btn) return;
      this._typeFilter = btn.getAttribute("data-type");
      root.querySelectorAll("#typeChips .chip").forEach((c) => c.classList.toggle("active", c === btn));
      this._renderBody();
    });
    // this.shadowRoot itself (unlike its children) is never recreated by
    // the innerHTML assignment above, so a listener attached to it here
    // would survive every call to _render(). Home Assistant's panel
    // loader can call connectedCallback - and therefore _render() - more
    // than once for the same element instance, so without this guard a
    // second listener would end up attached alongside the first. Any
    // click (e.g. the local-key "show" button) would then run
    // _handleBodyClick twice, toggling state on and back off in the same
    // click and making it look like nothing happened.
    if (!this._rootClickBound) {
      root.addEventListener("click", (e) => this._handleBodyClick(e));
      this._rootClickBound = true;
    }
    this._renderBody();
  }

  _handleBodyClick(e) {
    const revealBtn = e.target.closest("[data-reveal]");
    if (revealBtn) {
      const id = revealBtn.getAttribute("data-reveal");
      if (this._revealed.has(id)) this._revealed.delete(id); else this._revealed.add(id);
      this._renderBody();
      return;
    }
    const toggleBtn = e.target.closest("[data-toggle]");
    if (toggleBtn && !toggleBtn.disabled) {
      const id = toggleBtn.getAttribute("data-id");
      const dp = toggleBtn.getAttribute("data-dp");
      const val = toggleBtn.getAttribute("data-val") === "true";
      this._setControl(id, dp, val, toggleBtn);
      return;
    }
    const stepBtn = e.target.closest("[data-step]");
    if (stepBtn && !stepBtn.disabled) {
      const id = stepBtn.getAttribute("data-id");
      const dp = stepBtn.getAttribute("data-dp");
      const delta = parseInt(stepBtn.getAttribute("data-step"), 10);
      const device = this._devices.find((d) => d.device_id === id);
      const cur = device && device.last_dps ? device.last_dps[dp] : undefined;
      const curNum = typeof cur === "number" ? cur : parseInt(cur, 10);
      const next = !isNaN(curNum) ? Math.max(1, Math.min(100, curNum + delta)) : (delta > 0 ? 2 : 1);
      this._setControl(id, dp, next, stepBtn);
      return;
    }
    const diagBtn = e.target.closest("[data-diagnose]");
    if (diagBtn) {
      this._openDiagnose(diagBtn.getAttribute("data-diagnose"), diagBtn.getAttribute("data-name"));
      return;
    }
    if (e.target.id === "diagClose" || e.target.id === "diagCloseBtn" || e.target.id === "diagBackdrop") {
      this._closeDiagnose();
      return;
    }
    if (e.target.id === "diagRerun" && this._diag) {
      this._openDiagnose(this._diag.deviceId, this._diag.name);
      return;
    }
  }

  _renderBody() {
    const body = this.shadowRoot.getElementById("body");
    if (!body) return;

    if (this._loading) {
      body.innerHTML = `<p class="muted">Loading devices…</p>`;
      return;
    }
    if (this._error) {
      body.innerHTML = `<p class="error">Failed to load devices: ${escapeHtml(this._error)}</p>`;
      return;
    }
    const filtered = this._filtered();
    if (!filtered.length) {
      body.innerHTML = `<p class="muted">No devices match. ${this._devices.length ? "" : "Waiting for the first sync to complete…"}</p>${this._diagHtml()}`;
      return;
    }
    body.innerHTML = `
      <p class="muted">${filtered.length} of ${this._devices.length} device${this._devices.length === 1 ? "" : "s"}</p>
      <table>
        <thead>
          <tr>
            <th>Name</th><th>Status</th><th>IP</th><th>Device ID</th><th>Local Key</th>
            <th>Version</th><th>Category</th><th>Controls</th><th></th>
          </tr>
        </thead>
        <tbody>${filtered.map((d) => this._rowHtml(d)).join("")}</tbody>
      </table>
      ${this._diagHtml()}`;
  }

  _css() {
    return `
      :host { display: block; padding: 16px 24px 48px; font-family: var(--paper-font-body1_-_font-family, inherit); color: var(--primary-text-color); }
      .wrap { max-width: 1200px; margin: 0 auto; }
      .topbar { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
      .topbar h1 { font-size: 20px; font-weight: 500; margin: 0; flex-shrink: 0; }
      #search { flex: 1; max-width: 320px; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); }
      .btn { padding: 8px 14px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); cursor: pointer; }
      .btn.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: var(--primary-color); }
      .chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
      .chip { padding: 5px 12px; border-radius: 999px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--secondary-text-color); cursor: pointer; font-size: 12.5px; }
      .chip.active { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: var(--primary-color); }
      table { width: 100%; border-collapse: collapse; margin-top: 12px; background: var(--card-background-color); border-radius: 12px; overflow: hidden; }
      th { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: var(--secondary-text-color); padding: 10px 12px; border-bottom: 1px solid var(--divider-color); }
      td { padding: 10px 12px; border-bottom: 1px solid var(--divider-color); font-size: 13.5px; vertical-align: middle; }
      tr:last-child td { border-bottom: none; }
      .mono { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12px; }
      .small { font-size: 11px; opacity: .8; }
      .muted { color: var(--secondary-text-color); font-size: 13px; }
      .error { color: var(--error-color, #db4437); }
      .pill { padding: 3px 9px; border-radius: 999px; font-size: 11px; font-weight: 600; }
      .pill.online { background: rgba(76, 175, 80, .15); color: #4caf50; }
      .pill.offline { background: rgba(244, 67, 54, .15); color: #f44336; }
      .badge { display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; background: var(--secondary-background-color); border: 1px solid var(--divider-color); }
      .badge.type-fan { background: rgba(255, 193, 7, .15); color: #ffc107; border-color: #ffc107; }
      .badge.type-switch, .badge.type-plug { background: rgba(3, 169, 244, .15); color: #03a9f4; border-color: #03a9f4; }
      .badge.type-light { background: rgba(76, 175, 80, .15); color: #4caf50; border-color: #4caf50; }
      .key-cell { display: flex; align-items: center; gap: 6px; }
      .link-btn { background: none; border: none; color: var(--primary-color); cursor: pointer; font-size: 11px; padding: 0; }
      .icon-btn { background: none; border: 1px solid var(--divider-color); border-radius: 6px; width: 28px; height: 28px; cursor: pointer; color: var(--primary-text-color); }
      .toggle { width: 38px; height: 21px; border-radius: 999px; border: 1px solid var(--divider-color); background: var(--secondary-background-color); position: relative; cursor: pointer; }
      .toggle::after { content: ""; position: absolute; top: 2px; left: 2px; width: 15px; height: 15px; border-radius: 50%; background: var(--secondary-text-color); transition: transform .15s; }
      .toggle.on { background: rgba(76, 175, 80, .25); border-color: #4caf50; }
      .toggle.on::after { transform: translateX(17px); background: #4caf50; }
      .toggle:disabled { opacity: .4; cursor: default; }
      .stepper { display: inline-flex; align-items: center; gap: 6px; background: var(--secondary-background-color); border: 1px solid var(--divider-color); border-radius: 999px; padding: 2px 8px; }
      .step-btn { width: 18px; height: 18px; border-radius: 50%; border: 1px solid var(--divider-color); background: var(--card-background-color); cursor: pointer; color: var(--primary-text-color); font-size: 12px; line-height: 1; }
      .step-val { font-size: 11px; min-width: 16px; text-align: center; display: inline-block; }
      .modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.5); display: flex; align-items: center; justify-content: center; z-index: 10; }
      .modal { background: var(--card-background-color); border-radius: 12px; padding: 20px; width: 420px; max-width: 90vw; }
      .modal-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
      .modal-head h3 { margin: 0; font-size: 16px; }
      .diag-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
      .diag-card { background: var(--secondary-background-color); border-radius: 8px; padding: 10px 12px; }
      .diag-head { font-size: 11px; text-transform: uppercase; color: var(--secondary-text-color); margin-bottom: 6px; }
      .diag-status { font-weight: 700; font-size: 14px; }
      .diag-status.checking { color: var(--secondary-text-color); }
      .diag-status.ok { color: #4caf50; }
      .diag-status.fail { color: #f44336; }
      .diag-detail { font-size: 11px; color: var(--secondary-text-color); margin-top: 4px; }
      .diag-hint { margin-top: 12px; padding: 10px 12px; background: var(--secondary-background-color); border-radius: 8px; font-size: 12.5px; }
      .modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
      .toast { position: fixed; bottom: 20px; right: 20px; background: var(--card-background-color); border: 1px solid var(--divider-color); padding: 10px 16px; border-radius: 8px; font-size: 13px; opacity: 0; pointer-events: none; transition: opacity .2s; }
      .toast.show { opacity: 1; }
    `;
  }
}

customElements.define("tuya-dashboard-panel", TuyaDashboardPanel);
