"""Constants for the IP Attack Map integration."""

from __future__ import annotations

DOMAIN = "ip_attack_map"
SOURCE = "ip_attack_map"
INTEGRATION_VERSION = "0.2.5"

CONF_GEO_PROVIDER = "geo_provider"
CONF_MAXMIND_DB_PATH = "maxmind_db_path"
CONF_CLOUD_PROVIDER = "cloud_provider"
CONF_CLOUD_API_KEY = "cloud_api_key"
CONF_HIDE_PRIVATE_IPS = "hide_private_ips"
CONF_WHITELIST = "whitelist"
CONF_RETENTION_DAYS = "retention_days"
CONF_ONLY_EXTERNAL_ON_MAP = "only_external_on_map"

GEO_PROVIDER_MAXMIND = "maxmind"
GEO_PROVIDER_CLOUD = "cloud"

CLOUD_PROVIDER_IP_API = "ip_api"
CLOUD_PROVIDER_IPINFO = "ipinfo"

DEFAULT_RETENTION_DAYS = 30
DEFAULT_HIDE_PRIVATE_IPS = True
DEFAULT_ONLY_EXTERNAL_ON_MAP = True

IP_BANS_FILE = "ip_bans.yaml"

NOTIFICATION_ID_LOGIN = "http-login"
NOTIFICATION_ID_BAN = "ip-ban"

ATTR_IP = "ip"
ATTR_HOSTNAME = "hostname"
ATTR_COUNTRY = "country"
ATTR_CITY = "city"
ATTR_REGION = "region"
ATTR_ORG = "org"
ATTR_ATTEMPT_COUNT = "attempt_count"
ATTR_BANNED = "banned"
ATTR_BANNED_AT = "banned_at"
ATTR_LAST_SEEN = "last_seen"
ATTR_USER_AGENT = "user_agent"

STORAGE_VERSION = 1
STORAGE_KEY = "ip_attack_map_cache"

CLOUD_MIN_INTERVAL_SECONDS = 2.0
