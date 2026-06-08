import pytest
import sys
from types import ModuleType
from unittest.mock import MagicMock

# Stub homeassistant modules before loading frontend
for mod_name in [
    "homeassistant",
    "homeassistant.components",
    "homeassistant.components.frontend",
    "homeassistant.components.http",
    "homeassistant.components.lovelace",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.helpers",
    "homeassistant.helpers.event",
    "homeassistant.helpers.storage",
]:
    sys.modules[mod_name] = ModuleType(mod_name)

sys.modules["homeassistant.components"].frontend = sys.modules["homeassistant.components.frontend"]
sys.modules["homeassistant.components.frontend"].DATA_EXTRA_MODULE_URL = "frontend_extra_module_url"

class StaticPathConfig:
    def __init__(self, *args, **kwargs):
        pass
sys.modules["homeassistant.components.http"].StaticPathConfig = StaticPathConfig

sys.modules["homeassistant.components.lovelace"].DOMAIN = "lovelace"

sys.modules["homeassistant.const"].EVENT_HOMEASSISTANT_STARTED = "homeassistant_started"

class CoreState:
    running = "running"
sys.modules["homeassistant.core"].CoreState = CoreState
sys.modules["homeassistant.core"].HomeAssistant = MagicMock

def mock_callback(func):
    return func
sys.modules["homeassistant.core"].callback = mock_callback

sys.modules["homeassistant.helpers.event"].async_call_later = MagicMock()
sys.modules["homeassistant.helpers.storage"].Store = MagicMock

import importlib.util
from pathlib import Path

# Load const and frontend inside fake ip_attack_map package
ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "ip_attack_map"

const_spec = importlib.util.spec_from_file_location(
    "ip_attack_map.const",
    INTEGRATION / "const.py",
)
assert const_spec and const_spec.loader
const = importlib.util.module_from_spec(const_spec)
sys.modules["ip_attack_map.const"] = const
const_spec.loader.exec_module(const)

ip_attack_map = ModuleType("ip_attack_map")
ip_attack_map.const = const
sys.modules["ip_attack_map"] = ip_attack_map

frontend_spec = importlib.util.spec_from_file_location(
    "ip_attack_map.frontend",
    INTEGRATION / "frontend.py",
)
assert frontend_spec and frontend_spec.loader
frontend = importlib.util.module_from_spec(frontend_spec)
sys.modules["ip_attack_map.frontend"] = frontend
ip_attack_map.frontend = frontend
frontend_spec.loader.exec_module(frontend)

INTEGRATION_VERSION = const.INTEGRATION_VERSION
CARD_API_URL = frontend.CARD_API_URL
LOCAL_CARD_URL = frontend.LOCAL_CARD_URL
_async_maybe_await = frontend._async_maybe_await
_is_our_card_resource = frontend._is_our_card_resource
_resource_is_current = frontend._resource_is_current
_url_path = frontend._url_path
_url_version = frontend._url_version
card_module_url = frontend.card_module_url


@pytest.mark.asyncio
async def test_async_maybe_await_plain_value() -> None:
    assert await _async_maybe_await([{"id": "1"}]) == [{"id": "1"}]


@pytest.mark.asyncio
async def test_async_maybe_await_coroutine() -> None:
    async def _coro() -> str:
        return "ok"

    assert await _async_maybe_await(_coro()) == "ok"


def test_card_module_url_includes_version() -> None:
    url = card_module_url()
    assert url.startswith(LOCAL_CARD_URL)
    assert f"v={INTEGRATION_VERSION}" in url


def test_url_path_strips_query() -> None:
    assert _url_path("/api/foo.js?v=1") == "/api/foo.js"


def test_url_version() -> None:
    assert _url_version("/api/ip_attack_map/card/ip-attack-map-card.js?v=0.2.1") == "0.2.1"
    assert _url_version("/local/foo.js") is None


def test_is_our_card_resource() -> None:
    assert _is_our_card_resource(CARD_API_URL)
    assert _is_our_card_resource(f"{LOCAL_CARD_URL}?v=1")
    # Common manual typo (underscore instead of hyphen in filename).
    assert _is_our_card_resource("/local/ip_attack_map/ip_attack_map-card.js?v=0.2.5")
    assert _is_our_card_resource("/other/card.js") is False


def test_resource_is_current() -> None:
    assert _resource_is_current(f"{LOCAL_CARD_URL}?v={INTEGRATION_VERSION}") is True
    assert _resource_is_current(f"{CARD_API_URL}?v={INTEGRATION_VERSION}") is False


def test_card_module_url_uses_local_path() -> None:
    assert card_module_url().startswith(LOCAL_CARD_URL)


def test_extra_module_url_matches_lovelace_resource() -> None:
    card_extra_module_url = frontend.card_extra_module_url
    assert card_extra_module_url() == card_module_url()
