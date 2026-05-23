# IP Attack Map

Home-Assistant-Custom-Integration (HACS), die fehlgeschlagene Logins und IP-Bans aus der nativen HTTP-Integration auf einer Karte anzeigt.

**Versionierung:** `0.x.x` = frühe Entwicklung (noch kein stabiles 1.0).

## Voraussetzungen

In `configuration.yaml` (oder über die UI beim HTTP-Integration-Setup) sollte IP-Banning aktiv sein:

```yaml
http:
  ip_ban_enabled: true
  login_attempts_threshold: 5
```

### Reverse Proxy (Nginx, Traefik, …)

Damit die **echte Client-IP** erfasst wird (nicht die Proxy-IP):

```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 192.168.1.0/24
```

## Installation (HACS)

1. HACS → Integrations → Custom repositories  
2. Repository-URL: `https://github.com/chrizzo84/home-assistant-ip-attack-map`  
3. Kategorie: **Integration**  
4. **IP Attack Map** installieren und Home Assistant neu starten  
5. Einstellungen → Geräte & Dienste → Integration hinzufügen → **IP Attack Map**

### Manuelle Installation

Kopiere `custom_components/ip_attack_map` nach `config/custom_components/` und starte Home Assistant neu.

## Geolocation

### MaxMind GeoLite2 (empfohlen, lokal)

1. Kostenlosen Account auf [MaxMind](https://www.maxmind.com/en/geolite2/signup) anlegen  
2. **GeoLite2-City** (`.mmdb`) herunterladen  
3. Datei auf den HA-Host legen (z. B. `/config/GeoLite2-City.mmdb`)  
4. Pfad im Config-Flow angeben  

Es werden **keine** IPs an Dritte gesendet.

### Cloud (ip-api.com / ipinfo.io)

- **ip-api.com**: kostenlos, Rate-Limit beachten  
- **ipinfo.io**: optional API-Token  

IPs werden zur Auflösung an den gewählten Anbieter übermittelt.

## Lovelace-Karte

Die Integration bringt die **Custom Card** mit und registriert sie **automatisch** — keine manuelle Ressource, kein Kopieren nach `www/`.

Nach Installation und Neustart:

1. Dashboard bearbeiten → **Karte hinzufügen** → **IP Attack Map** (oder Stapel-YAML unten)
2. Optional darunter eine normale **Karte** mit `geo_location_sources: ip_attack_map` (Weltkarte; vermeidet Leaflet-Probleme in Safari)

Die Karte liefert **Statistik + Angriffstabelle**; die Weltkarte ist eine separate HA-**Karte**.

### Dashboard aufbauen (empfohlen)

**Stapel** mit zwei Karten – siehe [`docs/dashboard-stack.yaml`](docs/dashboard-stack.yaml):

1. Dashboard bearbeiten → **Karte hinzufügen** → **Manuelle Karte** → YAML aus `dashboard-stack.yaml` einfügen  
   **oder** einzeln:
2. **IP Attack Map** (Custom Card) – Statistik + Liste  
3. Normale **Karte** mit `geo_location_sources: ip_attack_map`

```yaml
type: vertical-stack
cards:
  - type: custom:ip-attack-map-card
    title: Login-Angriffe
    show_list: true
    max_list_items: 50
  - type: map
    geo_location_sources:
      - ip_attack_map
    entities:
      - zone.home
    default_zoom: 2
```

Die Custom Card zeigt eine **Tabelle**: IP/Host, Herkunft (Stadt/Land/ISP), Versuche, **Gebannt** oder **Aktiv**, Zeitpunkt.

### Karte lädt nicht („Custom element doesn't exist“)

1. Integration auf **0.2.2+** aktualisieren (HACS) und **Home Assistant neu starten**
2. Einmal **hart neu laden** (Cmd+Shift+R), Dashboard neu öffnen
3. Im Log sollten erscheinen: `registered as frontend module` und/oder `Registered IP Attack Map Lovelace resource`
4. Alte manuelle Ressourcen unter **Einstellungen → Dashboards → Ressourcen** (z. B. `/local/ip_attack_map/...`) können **entfernt** werden — die Integration nutzt `/api/ip_attack_map/card/ip-attack-map-card.js`

Nur bei **Lovelace komplett in YAML** (selten): Ressource einmalig in `ui-lovelace.yaml` eintragen — URL wie oben, Typ `module`.

### Safari: `_leaflet_pos` in der Karten-Vorschau

Das betrifft die **normale HA-Karte** (Leaflet), oft in der **Bearbeitungsvorschau** eines Stapels — nicht die Custom Card. Nach **Speichern** und **Cmd+Shift+R** sollte die Karte im Dashboard laufen; im Editor kann Safari 26.x weiter zicken. Trenne die Karten testweise (nur Tabelle, nur Karte) oder nutze Chrome/Firefox zum Bearbeiten.

### Entitäten auf der Karte

`geo_location`-Marker pro Angreifer-IP sind **standardmäßig ausgeblendet** (nur für die Karte da, nicht in der Entitätenliste). Sichtbar bleiben die **Sensoren** (Attempts today, Active bans, …). Bereits angelegte Marker nach dem Update ggf. einmal unter Entitäten → Ausgeblendet prüfen oder Integration neu laden.

## Sensoren

| Entity | Bedeutung |
|--------|-----------|
| Attempts today | Fehlversuche heute |
| Active bans | Gebannte IPs in der Registry |
| Last attacker | Letzter Angreifer (IP · Stadt · Land) |
| Tracked IPs | Anzahl erfasster IPs |

## Optionen

- **IP-Whitelist**: LAN, Supervisor, Proxy (CIDR möglich)  
- **Private IPs ausblenden**: Standard `true`  
- **Nur externe IPs auf Karte**: Standard `true`  
- **Aufbewahrung**: alte Einträge werden nach X Tagen entfernt  

## Datenschutz

- Angriffs-IPs werden lokal in einer HA-Storage-Datei gespeichert  
- Bei Cloud-GeoIP werden IPs an den gewählten Anbieter gesendet  
- MaxMind verarbeitet alles lokal auf deinem System  

## Fehlerbehebung: `placeholder` / `TextSelector` im Log

Wenn im Log noch `selector.TextSelector` oder `placeholder` vorkommt, läuft auf deinem System **nicht** der aktuelle Code aus dem Repository – das hat nichts mit der Home-Assistant-Version zu tun.

**Prüfen (Terminal / SSH / „Terminal & SSH“-Add-on):**

```bash
grep -E 'TextSelector|placeholder' /config/custom_components/ip_attack_map/config_flow.py
cat /config/custom_components/ip_attack_map/manifest.json | grep version
```

- Erste Zeile: **keine Ausgabe** (gut)  
- Version: mindestens **`0.2.2`**

**Aktualisieren:**

1. HACS → **IP Attack Map** → Menü (⋮) → **Neu herunterladen** (oder deinstallieren + neu installieren)  
2. **Home Assistant vollständig neu starten** (wichtig – Python lädt den Config-Flow nur beim Start)  
3. Beim erneuten Öffnen des Setup-Dialogs im Log sollte stehen:  
   `IP Attack Map config flow started (version 0.2.2)`

**Manuell (falls HACS nicht aktualisiert):**

```bash
rm -rf /config/custom_components/ip_attack_map
```

Danach den Ordner `custom_components/ip_attack_map` aus dem [GitHub-Repository](https://github.com/chrizzo84/home-assistant-ip-attack-map/tree/main/custom_components/ip_attack_map) nach `/config/custom_components/` kopieren und HA neu starten.

## Entwicklung

```bash
python -m pytest tests/
```

## Lizenz

MIT
