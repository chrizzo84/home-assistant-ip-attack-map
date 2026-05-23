# IP Attack Map

A [Home Assistant](https://www.home-assistant.io/) custom integration (install via [HACS](https://hacs.xyz/)) that visualizes failed HTTP logins and IP bans from Home Assistant’s built-in HTTP integration on a **Lovelace dashboard** — with stats, an attack table, and a world map.

**Versioning:** `0.x.x` means early development (not a stable 1.0 API yet).

## What it does

Home Assistant can log failed login attempts and ban abusive IPs when you enable IP banning on the HTTP integration. IP Attack Map listens for those events, enriches each IP with geolocation, and exposes:

- **Sensors** — attempts today, active bans, last attacker, tracked IP count  
- **`geo_location` entities** — one marker per attacker (for the native Map card)  
- **Custom Lovelace card** — summary tiles plus a sortable attack table  
- **Import of existing bans** — reads `ip_bans.yaml` on startup and uses each entry’s `banned_at` timestamp  

No separate log parser or external database is required.

## Features

| Feature | Description |
|--------|-------------|
| Login capture | Subscribes to HA persistent notifications (`http-login`, `ip-ban`) |
| Ban import | Loads `/config/ip_bans.yaml` and preserves real ban dates |
| GeoIP | **MaxMind GeoLite2** (local, recommended) or **cloud** (ip-api.com / ipinfo.io) |
| Map markers | `geo_location` source `ip_attack_map` for the standard Map card |
| Custom card | Built-in `ip-attack-map-card` — no manual `www/` copy |
| Auto Lovelace resource | Registers and updates `/local/ip_attack_map/ip-attack-map-card.js?v=…` on startup |
| Filtering | IP whitelist, hide private IPs, external-only map, retention days |
| Privacy-friendly defaults | Private IPs hidden; MaxMind keeps lookups on your host |

## Requirements

- Home Assistant **2023.1** or newer (see `hacs.json`)  
- [HACS](https://hacs.xyz/) for the recommended install path  
- HTTP integration with **IP banning** enabled  

### Enable HTTP login banning

In `configuration.yaml` (or via the HTTP integration UI):

```yaml
http:
  ip_ban_enabled: true
  login_attempts_threshold: 5
```

Adjust the threshold to taste. Failed logins are counted; when the limit is reached, HA bans the IP and writes it to `ip_bans.yaml`.

### Reverse proxy (Nginx, Traefik, Cloudflare, …)

To record the **real client IP** instead of the proxy:

```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 192.168.1.0/24   # your proxy/LAN
```

Add every hop that terminates TLS in front of Home Assistant.

## Installation

### HACS (recommended)

1. Open **HACS** → **Integrations** → **⋮** → **Custom repositories**  
2. Add repository: `https://github.com/chrizzo84/home-assistant-ip-attack-map`  
3. Category: **Integration**  
4. Install **IP Attack Map**  
5. **Restart Home Assistant** (full restart, not only reload)  
6. Go to **Settings** → **Devices & services** → **Add integration** → **IP Attack Map**  
7. Complete the setup wizard (geolocation + options)

After updates, use **HACS** → **IP Attack Map** → **Redownload**, then restart HA again so Python and the Lovelace card reload.

### Manual install

Copy the folder `custom_components/ip_attack_map` into your config directory:

```text
config/
  custom_components/
    ip_attack_map/
      ...
```

Restart Home Assistant and add the integration from **Devices & services**.

## Configuration

The config flow has two main steps.

### 1. Geolocation provider

**MaxMind GeoLite2 (recommended, local)**

1. Create a free account at [MaxMind](https://www.maxmind.com/en/geolite2/signup)  
2. Download **GeoLite2 City** (`.mmdb`)  
3. Copy the file to your HA host (e.g. `/config/GeoLite2-City.mmdb`)  
4. Enter the full path in the integration setup  

IPs are **not** sent to third parties. The `geoip2` package is installed automatically when you choose MaxMind.

**Cloud**

| Provider | Notes |
|----------|--------|
| **ip-api.com** | Free tier; respect rate limits |
| **ipinfo.io** | Optional API token for higher limits |

Client IPs are sent to the selected provider for lookup.

### 2. Options

| Option | Default | Description |
|--------|---------|-------------|
| **IP whitelist** | empty | Comma-separated IPs or CIDR ranges to ignore (LAN, Docker, reverse proxy) |
| **Hide private IPs** | on | Do not track RFC1918 / local addresses |
| **Only external IPs on map** | on | Map markers only for public IPs |
| **Retention (days)** | 30 | Remove old **non-banned** attack records after N days |

**Banned IPs** from `ip_bans.yaml` are kept until Home Assistant removes the ban, regardless of retention.

You can change options later via **Configure** on the integration card.

## Dashboard setup

The integration ships a **custom Lovelace card** and registers it automatically. You do **not** need to add a manual resource or copy files into `www/` (unless you use Lovelace entirely in YAML mode — see troubleshooting).

After the Lovelace resource loads, the card appears under **Community cards** in the card picker (German UI: **Community-Karten**). That list is built from `window.customCards` in the card script — it is not the separate HACS **Frontend** plugin catalog.

### Recommended layout: vertical stack

Use two cards: **IP Attack Map** (stats + table) and the native **Map** card (world map). This avoids Leaflet issues in some browsers when editing stacked cards.

**Option A — UI:** Edit dashboard → **Add card** → search for **IP Attack Map**.

**Option B — YAML:** Add a **Manual** card and paste the example from [`docs/dashboard-stack.yaml`](docs/dashboard-stack.yaml):

```yaml
type: vertical-stack
cards:
  - type: custom:ip-attack-map-card
    title: Login attacks
    show_list: true
    show_map_hint: false
    max_list_items: 50
  - type: map
    title: Attacks on the map
    geo_location_sources:
      - ip_attack_map
    entities:
      - zone.home
    default_zoom: 2
    aspect_ratio: "16:9"
```

### Custom card columns

| Column | Content |
|--------|---------|
| IP / Host | Attacker IP; hostname when known |
| Origin | City, region, country, ISP/org |
| Attempts | Failed login count for this IP |
| Status | **Banned** or **Active** |
| Date | Ban time from `ip_bans.yaml` (`banned_at`), or last login attempt for active IPs |

### Stat tiles

| Tile | Meaning |
|------|---------|
| **Today** | Failed login attempts today (sensor + live data) |
| **Bans** | IPs currently marked banned |
| **IPs** | Tracked attacker IPs |
| **On map** | `geo_location` entities shown on the map |

### Card options (YAML / UI editor)

| Key | Default | Description |
|-----|---------|-------------|
| `title` | Login attacks | Card header |
| `show_list` | `true` | Show attack table |
| `show_map_hint` | `false` | Show hint to add a Map card below |
| `max_list_items` | `30` | Max table rows (5–100) |

## Entities

### Sensors (diagnostic)

Linked to the **IP Attack Map** device. Entity IDs depend on your instance (e.g. `sensor.ip_attack_map_attempts_today`).

| Sensor | Description |
|--------|-------------|
| **Attempts today** | Failed HTTP logins since midnight |
| **Active bans** | Banned IPs in the registry |
| **Last attacker** | Most recent attacker (IP · city · country) |
| **Tracked IPs** | Number of IPs in the registry |

### Map (`geo_location`)

One entity per external attacker IP, source **`ip_attack_map`**. These entities are **hidden from the default entity list** by design (they exist for the Map card). Use **Settings** → **Entities** → **Hidden** if you need to inspect them.

Attributes include `ip`, `country`, `city`, `attempt_count`, `banned`, `banned_at`, `last_seen`, and more.

## How data flows

```text
Failed login / IP ban
        ↓
HA HTTP integration → persistent notification
        ↓
IP Attack Map listener → coordinator registry
        ↓
GeoIP lookup (MaxMind or cloud) + storage cache
        ↓
geo_location entities + sensors + Lovelace card
```

On startup, existing entries in **`/config/ip_bans.yaml`** are imported. The **`banned_at`** field from YAML is used for display and sorting, not the time of the last HA restart.

## Privacy & data storage

- Attack records are stored locally in Home Assistant storage (`.storage/ip_attack_map_cache_*`)  
- Cloud GeoIP sends IPs to the provider you choose  
- MaxMind lookups run entirely on your system  
- No telemetry is sent to the integration author  

## Troubleshooting

### Custom element doesn’t exist (`ip-attack-map-card`)

1. Install **0.3.0+** via HACS and **restart Home Assistant**  
2. Hard-refresh the browser (e.g. Cmd+Shift+R)  
3. Check logs for:  
   - `Published IP Attack Map card for Lovelace`  
   - `Updated IP Attack Map Lovelace resource` or `Registered IP Attack Map Lovelace resource`  
4. **Settings** → **Dashboards** → **Resources** — you should have **one** entry:  
   `/local/ip_attack_map/ip-attack-map-card.js?v=0.3.0`  
   Type: **JavaScript module**  
   From **0.3.0**, the URL is updated automatically on startup (including fixing old typo URLs like `ip_attack_map-card.js`). Remove duplicate or `/api/...` entries if any remain.  
5. Red preview **only in the card editor?** Save the dashboard and open it in normal view — the editor sometimes loads resources late.

### Lovelace resources in YAML mode

If `resource_mode` is **yaml**, automatic registration is skipped. Add once to `configuration.yaml` or `ui-lovelace.yaml`:

```yaml
lovelace:
  mode: storage
  resources:
    - url: /local/ip_attack_map/ip-attack-map-card.js?v=0.3.0
      type: module
```

Restart HA after changing resources.

### Map / Safari (`_leaflet_pos` errors)

This usually affects the **native Map card** in the **dashboard editor preview**, not the custom IP Attack Map card. Save the dashboard, hard-refresh, or edit in Chrome/Firefox. Test the Map card alone if a vertical stack misbehaves in Safari.

### Stats show dashes but the table works

Reload the integration or restart HA. The card falls back to `geo_location` data when sensors are unavailable; **Today** uses the attempts sensor when present.

### Wrong “today” counts or ban dates

Ensure you are on **0.3.0+**. Old bans must use `banned_at` in `ip_bans.yaml`:

```yaml
203.0.113.10:
  banned_at: "2025-07-02T22:55:39.820955+00:00"
```

Reload the integration after editing the ban file.

### Verify installed version (SSH / Terminal add-on)

```bash
grep version /config/custom_components/ip_attack_map/manifest.json
```

Expected: `"version": "0.3.0"` (or newer).

If HACS did not update:

```bash
rm -rf /config/custom_components/ip_attack_map
```

Then copy fresh files from [GitHub](https://github.com/chrizzo84/home-assistant-ip-attack-map/tree/main/custom_components/ip_attack_map) and restart.

### Stale config flow / `TextSelector` errors in logs

That means an old copy of the integration is still on disk. Redownload via HACS, remove the folder manually if needed, and **fully restart** Home Assistant (the config flow is loaded at startup).

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-test.txt
pytest tests/
```

## License

MIT — see [LICENSE](LICENSE).

## Links

- [GitHub repository](https://github.com/chrizzo84/home-assistant-ip-attack-map)  
- [Issue tracker](https://github.com/chrizzo84/home-assistant-ip-attack-map/issues)
