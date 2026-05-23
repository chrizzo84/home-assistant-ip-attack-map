# IP Attack Map

Home-Assistant-Custom-Integration (HACS), die fehlgeschlagene Logins und IP-Bans aus der nativen HTTP-Integration auf einer Karte anzeigt.

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
2. Repository-URL: `https://github.com/DEIN_USER/home-assistant-ip-attack-map`  
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

## Karte einrichten

Lovelace-Beispiel (siehe auch [`docs/dashboard-map-card.yaml`](docs/dashboard-map-card.yaml)):

```yaml
type: map
geo_location_sources:
  - ip_attack_map
entities:
  - zone.home
default_zoom: 2
aspect_ratio: "16:9"
```

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

## Entwicklung

```bash
python -m pytest tests/
```

## Lizenz

MIT
