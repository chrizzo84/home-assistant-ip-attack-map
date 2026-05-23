/**
 * IP Attack Map Lovelace card (stats + attack list).
 * Use a separate built-in "map" card with geo_location_sources: ip_attack_map for the map
 * (embedding hui-map-card causes Leaflet errors in Safari / nested cards).
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
      max_list_items: 12,
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
    return 4;
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
      ip-attack-map-card .map-hint {
        margin: 12px 16px 0;
        padding: 10px 12px;
        border-radius: 8px;
        background: var(--secondary-background-color);
        font-size: 0.85rem;
        line-height: 1.4;
      }
      ip-attack-map-card .map-hint code {
        font-size: 0.8rem;
        word-break: break-all;
      }
      ip-attack-map-card .attack-list {
        padding: 8px 16px 16px;
        max-height: 220px;
        overflow-y: auto;
      }
      ip-attack-map-card .attack-row {
        display: flex;
        flex-wrap: wrap;
        gap: 4px 12px;
        padding: 6px 0;
        border-bottom: 1px solid var(--divider-color);
        font-size: 0.85rem;
      }
      ip-attack-map-card .attack-ip { font-weight: 600; }
      ip-attack-map-card .attack-meta { opacity: 0.85; }
      ip-attack-map-card .empty {
        padding: 8px 16px 16px;
        opacity: 0.75;
        font-size: 0.9rem;
      }
      ip-attack-map-card .last-attacker {
        padding: 0 16px 8px;
        font-size: 0.85rem;
        opacity: 0.9;
      }
      @media (max-width: 600px) {
        ip-attack-map-card .stats { grid-template-columns: repeat(2, 1fr); }
      }
    `;
    this.appendChild(style);

    const card = document.createElement("ha-card");
    card.innerHTML = `
      <div class="stats"></div>
      <div class="last-attacker"></div>
      <div class="map-hint"></div>
      <div class="attack-list"></div>
    `;
    this.appendChild(card);
    this._initialized = true;
  }

  _findSensor(suffix) {
    return Object.values(this._hass.states).find(
      (s) =>
        s.entity_id.startsWith("sensor.") &&
        s.entity_id.includes("ip_attack_map") &&
        s.entity_id.endsWith(suffix),
    );
  }

  _attackEntities() {
    return Object.values(this._hass.states)
      .filter(
        (s) =>
          s.entity_id.startsWith("geo_location.") &&
          s.attributes.source === "ip_attack_map",
      )
      .sort((a, b) => {
        const ta = a.attributes.last_seen || "";
        const tb = b.attributes.last_seen || "";
        return tb.localeCompare(ta);
      });
  }

  _attackRow(state) {
    const a = state.attributes;
    const loc = [a.city, a.country].filter(Boolean).join(", ");
    const banned = a.banned ? " · gebannt" : "";
    const count = a.attempt_count != null ? ` · ${a.attempt_count}×` : "";
    return `<div class="attack-row">
      <span class="attack-ip">${a.ip || state.state}</span>
      <span class="attack-meta">${loc}${banned}${count}</span>
    </div>`;
  }

  _render() {
    if (!this._config || !this._hass) return;

    this._ensureDom();
    const card = this.querySelector("ha-card");
    card.header = this._config.title || "Login-Angriffe";

    const attempts = this._findSensor("attempts_today");
    const bans = this._findSensor("active_bans");
    const tracked = this._findSensor("tracked_ips");
    const last = this._findSensor("last_attacker");
    const attacks = this._attackEntities();
    const lastLabel = last?.state && last.state !== "unknown" ? last.state : "—";
    const maxItems = this._config.max_list_items ?? 12;

    card.querySelector(".stats").innerHTML = `
      <div class="stat"><div class="stat-label">Heute</div><div class="stat-value">${attempts?.state ?? "—"}</div></div>
      <div class="stat"><div class="stat-label">Bans</div><div class="stat-value">${bans?.state ?? "—"}</div></div>
      <div class="stat"><div class="stat-label">IPs</div><div class="stat-value">${tracked?.state ?? "—"}</div></div>
      <div class="stat"><div class="stat-label">Marker</div><div class="stat-value">${attacks.length}</div></div>
    `;

    card.querySelector(".last-attacker").textContent = `Zuletzt: ${lastLabel}`;

    card.querySelector(".map-hint").innerHTML = `
      <strong>Weltkarte:</strong> Füge darunter eine normale
      <em>Karte</em>-Karte hinzu mit
      <code>geo_location_sources: ip_attack_map</code>
      (siehe README / docs/dashboard-stack.yaml).
    `;

    const listEl = card.querySelector(".attack-list");
    if (this._config.show_list === false) {
      listEl.innerHTML = "";
      listEl.style.display = "none";
    } else {
      listEl.style.display = "";
      listEl.innerHTML = attacks.length
        ? attacks
            .slice(0, maxItems)
            .map((a) => this._attackRow(a))
            .join("")
        : `<div class="empty">Noch keine externen Angriffe erfasst.</div>`;
    }
  }
}

class IpAttackMapCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
  }

  set hass(hass) {
    this._hass = hass;
  }

  _valueChanged(ev) {
    const field = ev.target.name;
    const value =
      ev.target.type === "checkbox" ? ev.target.checked : ev.target.value;
    const config = { ...this._config, [field]: value };
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        bubbles: true,
        composed: true,
        detail: { config },
      }),
    );
  }

  connectedCallback() {
    this.innerHTML = `
      <div class="card-config">
        <div>
          <label>Titel</label>
          <input name="title" type="text" value="${this._config?.title || "Login-Angriffe"}">
        </div>
      </div>
    `;
    this.querySelectorAll("input").forEach((el) => {
      el.addEventListener("change", (ev) => this._valueChanged(ev));
    });
  }
}

customElements.define("ip-attack-map-card", IpAttackMapCard);
customElements.define("ip-attack-map-card-editor", IpAttackMapCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "custom:ip-attack-map-card",
  name: "IP Attack Map",
  description: "Statistik und Angriffsliste für fehlgeschlagene HA-Logins",
  preview: true,
  documentationURL:
    "https://github.com/chrizzo84/home-assistant-ip-attack-map#lovelace-karte",
});
