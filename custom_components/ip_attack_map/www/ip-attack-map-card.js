/**
 * IP Attack Map Lovelace card: statistics + attack table.
 * Pair with a native "map" card (geo_location_sources: ip_attack_map) below.
 */
class IpAttackMapCard extends HTMLElement {
  constructor() {
    super();
    this._config = null;
    this._hass = null;
    this._initialized = false;
  }

  static getStubConfig() {
    return {
      title: "Login-Angriffe",
      show_list: true,
      show_map_hint: false,
      max_list_items: 30,
    };
  }

  static getConfigElement() {
    return document.createElement("ip-attack-map-card-editor");
  }

  setConfig(config) {
    this._config = {
      ...IpAttackMapCard.getStubConfig(),
      ...config,
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return this._config?.show_list === false ? 3 : 7;
  }

  _escape(text) {
    return String(text ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  _formatTime(iso) {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString(undefined, {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  }

  _ensureDom() {
    if (this._initialized) return;

    const style = document.createElement("style");
    style.textContent = `
      ip-attack-map-card { display: block; }
      ip-attack-map-card ha-card { overflow: hidden; }
      ip-attack-map-card .stats {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 8px;
        padding: 12px 16px 0;
      }
      ip-attack-map-card .stat {
        background: var(--secondary-background-color);
        border-radius: 8px;
        padding: 8px 10px;
        text-align: center;
      }
      ip-attack-map-card .stat-label { font-size: 0.75rem; opacity: 0.8; }
      ip-attack-map-card .stat-value {
        font-size: 1.25rem;
        font-weight: 600;
        margin-top: 2px;
      }
      ip-attack-map-card .list-header {
        padding: 12px 16px 4px;
        font-size: 0.95rem;
        font-weight: 600;
      }
      ip-attack-map-card .table-wrap {
        padding: 0 8px 16px;
        overflow-x: auto;
        max-height: 420px;
        overflow-y: auto;
      }
      ip-attack-map-card table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.82rem;
      }
      ip-attack-map-card th {
        text-align: left;
        padding: 8px 6px;
        border-bottom: 2px solid var(--divider-color);
        opacity: 0.85;
        font-weight: 600;
        white-space: nowrap;
        position: sticky;
        top: 0;
        background: var(--card-background-color, var(--ha-card-background));
        z-index: 1;
      }
      ip-attack-map-card td {
        padding: 8px 6px;
        border-bottom: 1px solid var(--divider-color);
        vertical-align: top;
      }
      ip-attack-map-card tr:hover td {
        background: var(--secondary-background-color);
      }
      ip-attack-map-card .ip-cell { font-weight: 600; font-family: monospace; }
      ip-attack-map-card .host-sub {
        font-size: 0.75rem;
        opacity: 0.75;
        font-weight: normal;
        font-family: inherit;
      }
      ip-attack-map-card .loc-sub {
        font-size: 0.75rem;
        opacity: 0.75;
      }
      ip-attack-map-card .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.72rem;
        font-weight: 600;
        white-space: nowrap;
      }
      ip-attack-map-card .badge-banned {
        background: rgba(var(--rgb-state-device-tracker-home, 76, 175, 80), 0.25);
        color: var(--state-device-tracker-home-color, #4caf50);
      }
      ip-attack-map-card .badge-open {
        background: rgba(var(--rgb-state-device-tracker-not_home, 244, 67, 54), 0.2);
        color: var(--error-color, #f44336);
      }
      ip-attack-map-card .map-hint {
        margin: 8px 16px 0;
        padding: 8px 12px;
        border-radius: 8px;
        background: var(--secondary-background-color);
        font-size: 0.82rem;
      }
      ip-attack-map-card .empty {
        padding: 12px 16px 16px;
        opacity: 0.75;
        font-size: 0.9rem;
      }
      @media (max-width: 700px) {
        ip-attack-map-card .stats { grid-template-columns: repeat(2, 1fr); }
        ip-attack-map-card .hide-mobile { display: none; }
      }
    `;
    this.appendChild(style);

    const card = document.createElement("ha-card");
    card.innerHTML = `
      <div class="stats"></div>
      <div class="map-hint" style="display:none"></div>
      <div class="list-header"></div>
      <div class="table-wrap"></div>
    `;
    this.appendChild(card);
    this._initialized = true;
  }

  _findOurSensor(suffix) {
    const matches = Object.values(this._hass.states).filter(
      (s) =>
        s.entity_id.startsWith("sensor.") &&
        s.entity_id.includes("ip_attack_map") &&
        (s.entity_id.endsWith(`_${suffix}`) ||
          s.entity_id === `sensor.ip_attack_map_${suffix}`),
    );
    return matches[0] || null;
  }

  _isToday(isoString) {
    if (!isoString) return false;
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return false;
    const now = new Date();
    return (
      date.getFullYear() === now.getFullYear() &&
      date.getMonth() === now.getMonth() &&
      date.getDate() === now.getDate()
    );
  }

  _sensorNumber(sensor) {
    if (!sensor) return null;
    const state = sensor.state;
    if (state === "unavailable" || state === "unknown" || state === "") {
      return null;
    }
    const value = Number(state);
    return Number.isFinite(value) ? value : null;
  }

  _countAttemptsToday(attacks) {
    /** Failed logins today — not "last_seen" (old bans get refreshed without new attempts). */
    let attemptsToday = 0;
    for (const a of attacks) {
      if (!this._isToday(a.attributes.last_seen)) continue;
      const count = Number(a.attributes.attempt_count) || 0;
      if (count <= 0) continue;
      attemptsToday += count;
    }
    return attemptsToday;
  }

  _statsFromAttacks(attacks) {
    let bans = 0;
    for (const a of attacks) {
      if (a.attributes.banned) bans += 1;
    }
    return {
      tracked: attacks.length,
      bans,
      attemptsToday: this._countAttemptsToday(attacks),
    };
  }

  _attackEntities() {
    return Object.values(this._hass.states)
      .filter(
        (s) =>
          s.entity_id.startsWith("geo_location.") &&
          s.attributes.source === "ip_attack_map",
      )
      .sort((a, b) => {
        const sortKey = (s) => {
          const attrs = s.attributes;
          return attrs.banned && attrs.banned_at
            ? attrs.banned_at
            : attrs.last_seen || "";
        };
        return sortKey(b).localeCompare(sortKey(a));
      });
  }

  _attackTableRow(state) {
    const a = state.attributes;
    const ip = a.ip || state.state;
    const hostname =
      a.hostname && a.hostname !== ip
        ? `<div class="host-sub">${this._escape(a.hostname)}</div>`
        : "";
    const locParts = [a.city, a.region, a.country].filter(Boolean);
    const loc = locParts.length
      ? `<div>${this._escape(locParts.join(", "))}</div>`
      : `<div>—</div>`;
    const org = a.org
      ? `<div class="loc-sub">${this._escape(a.org)}</div>`
      : "";
    const attempts = a.attempt_count != null ? String(a.attempt_count) : "—";
    const banned = a.banned
      ? `<span class="badge badge-banned">Gebannt</span>`
      : `<span class="badge badge-open">Aktiv</span>`;
    const timeIso =
      a.banned && a.banned_at ? a.banned_at : a.last_seen;
    const when = this._formatTime(timeIso);

    return `<tr>
      <td class="ip-cell">${this._escape(ip)}${hostname}</td>
      <td>${loc}${org}</td>
      <td style="text-align:center">${this._escape(attempts)}</td>
      <td>${banned}</td>
      <td class="hide-mobile">${this._escape(when)}</td>
    </tr>`;
  }

  _attemptsTodayValue(attacks) {
    const fromList = this._countAttemptsToday(attacks);
    const sensorAttempts = this._sensorNumber(
      this._findOurSensor("attempts_today"),
    );
    if (sensorAttempts != null) {
      return Math.max(sensorAttempts, fromList);
    }
    return fromList;
  }

  _render() {
    if (!this._config || !this._hass) return;

    this._ensureDom();
    const card = this.querySelector("ha-card");
    card.header = this._config.title || "Login-Angriffe";

    const attacks = this._attackEntities();
    const computed = this._statsFromAttacks(attacks);
    const maxItems = this._config.max_list_items ?? 30;

    const attemptsVal = this._attemptsTodayValue(attacks);
    const bansVal =
      this._sensorNumber(this._findOurSensor("active_bans")) ?? computed.bans;
    const trackedVal =
      this._sensorNumber(this._findOurSensor("tracked_ips")) ?? computed.tracked;

    card.querySelector(".stats").innerHTML = `
      <div class="stat" title="Fehlgeschlagene Logins heute (Sensor)"><div class="stat-label">Heute</div><div class="stat-value">${this._escape(attemptsVal)}</div></div>
      <div class="stat"><div class="stat-label">Bans</div><div class="stat-value">${this._escape(bansVal)}</div></div>
      <div class="stat"><div class="stat-label">IPs</div><div class="stat-value">${this._escape(trackedVal)}</div></div>
      <div class="stat"><div class="stat-label">Auf Karte</div><div class="stat-value">${attacks.length}</div></div>
    `;

    const hintEl = card.querySelector(".map-hint");
    if (this._config.show_map_hint) {
      hintEl.style.display = "";
      hintEl.innerHTML =
        "Weltkarte: normale <strong>Karte</strong>-Karte mit <code>geo_location_sources: ip_attack_map</code> darunter einfügen.";
    } else {
      hintEl.style.display = "none";
    }

    const listHeader = card.querySelector(".list-header");
    const tableWrap = card.querySelector(".table-wrap");

    if (this._config.show_list === false) {
      listHeader.textContent = "";
      tableWrap.innerHTML = "";
      return;
    }

    listHeader.textContent = `Angriffe (${Math.min(attacks.length, maxItems)} von ${attacks.length})`;

    if (!attacks.length) {
      tableWrap.innerHTML =
        '<div class="empty">Noch keine externen Angriffe erfasst.</div>';
      return;
    }

    const rows = attacks
      .slice(0, maxItems)
      .map((a) => this._attackTableRow(a))
      .join("");

    tableWrap.innerHTML = `
      <table>
        <thead>
          <tr>
            <th>IP / Host</th>
            <th>Herkunft</th>
            <th>Versuche</th>
            <th>Status</th>
            <th class="hide-mobile">Datum</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }
}

class IpAttackMapCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...IpAttackMapCard.getStubConfig(), ...config };
  }

  set hass(hass) {
    this._hass = hass;
  }

  _fire(config) {
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        bubbles: true,
        composed: true,
        detail: { config },
      }),
    );
  }

  connectedCallback() {
    const c = this._config || IpAttackMapCard.getStubConfig();
    this.innerHTML = `
      <div class="card-config" style="padding:8px;display:flex;flex-direction:column;gap:12px">
        <label>Titel<input name="title" type="text" value="${c.title || ""}"></label>
        <label><input name="show_list" type="checkbox" ${c.show_list !== false ? "checked" : ""}> Angriffstabelle anzeigen</label>
        <label>Max. Zeilen<input name="max_list_items" type="number" min="5" max="100" value="${c.max_list_items ?? 30}"></label>
      </div>
    `;
    this.querySelector('[name="title"]').addEventListener("change", (ev) => {
      this._fire({ ...this._config, title: ev.target.value });
    });
    this.querySelector('[name="show_list"]').addEventListener("change", (ev) => {
      this._fire({ ...this._config, show_list: ev.target.checked });
    });
    this.querySelector('[name="max_list_items"]').addEventListener("change", (ev) => {
      this._fire({
        ...this._config,
        max_list_items: parseInt(ev.target.value, 10) || 30,
      });
    });
  }
}

if (!customElements.get("ip-attack-map-card")) {
  customElements.define("ip-attack-map-card", IpAttackMapCard);
}
if (!customElements.get("ip-attack-map-card-editor")) {
  customElements.define("ip-attack-map-card-editor", IpAttackMapCardEditor);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "custom:ip-attack-map-card")) {
  window.customCards.push({
    type: "custom:ip-attack-map-card",
    name: "IP Attack Map",
    description: "Statistik und Angriffstabelle für fehlgeschlagene HA-Logins",
    preview: true,
    documentationURL:
      "https://github.com/chrizzo84/home-assistant-ip-attack-map#lovelace-karte",
  });
}
