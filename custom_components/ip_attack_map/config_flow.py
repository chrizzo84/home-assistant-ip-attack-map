"""Config flow for IP Attack Map."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_CLOUD_API_KEY,
    CONF_CLOUD_PROVIDER,
    CONF_GEO_PROVIDER,
    CONF_HIDE_PRIVATE_IPS,
    CONF_MAXMIND_DB_PATH,
    CONF_ONLY_EXTERNAL_ON_MAP,
    CONF_RETENTION_DAYS,
    CONF_WHITELIST,
    CLOUD_PROVIDER_IP_API,
    CLOUD_PROVIDER_IPINFO,
    DEFAULT_HIDE_PRIVATE_IPS,
    DEFAULT_ONLY_EXTERNAL_ON_MAP,
    DEFAULT_RETENTION_DAYS,
    DOMAIN,
    GEO_PROVIDER_CLOUD,
    GEO_PROVIDER_MAXMIND,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_GEO_PROVIDER): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(
                        value=GEO_PROVIDER_MAXMIND,
                        label="MaxMind GeoLite2 (local)",
                    ),
                    selector.SelectOptionDict(
                        value=GEO_PROVIDER_CLOUD,
                        label="Cloud API",
                    ),
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)


class IpAttackMapConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IP Attack Map."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> IpAttackMapOptionsFlow:
        """Return options flow handler."""
        return IpAttackMapOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        if user_input[CONF_GEO_PROVIDER] == GEO_PROVIDER_MAXMIND:
            return await self.async_step_maxmind()
        return await self.async_step_cloud()

    async def async_step_maxmind(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure MaxMind database path."""
        schema = vol.Schema(
            {
                vol.Required(CONF_MAXMIND_DB_PATH): str,
                vol.Optional(
                    CONF_WHITELIST,
                    default=[],
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        multiline=True,
                        placeholder="192.168.0.0/16\n10.0.0.1",
                    )
                ),
                vol.Optional(
                    CONF_HIDE_PRIVATE_IPS, default=DEFAULT_HIDE_PRIVATE_IPS
                ): bool,
                vol.Optional(
                    CONF_ONLY_EXTERNAL_ON_MAP,
                    default=DEFAULT_ONLY_EXTERNAL_ON_MAP,
                ): bool,
                vol.Optional(
                    CONF_RETENTION_DAYS, default=DEFAULT_RETENTION_DAYS
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=365)),
            }
        )
        if user_input is None:
            return self.async_show_form(step_id="maxmind", data_schema=schema)

        whitelist = _parse_whitelist(user_input.get(CONF_WHITELIST, []))
        return self.async_create_entry(
            title="IP Attack Map",
            data={
                CONF_GEO_PROVIDER: GEO_PROVIDER_MAXMIND,
                CONF_MAXMIND_DB_PATH: user_input[CONF_MAXMIND_DB_PATH],
                CONF_WHITELIST: whitelist,
                CONF_HIDE_PRIVATE_IPS: user_input.get(
                    CONF_HIDE_PRIVATE_IPS, DEFAULT_HIDE_PRIVATE_IPS
                ),
                CONF_ONLY_EXTERNAL_ON_MAP: user_input.get(
                    CONF_ONLY_EXTERNAL_ON_MAP, DEFAULT_ONLY_EXTERNAL_ON_MAP
                ),
                CONF_RETENTION_DAYS: user_input.get(
                    CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS
                ),
            },
        )

    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure cloud GeoIP provider."""
        schema = vol.Schema(
            {
                vol.Required(CONF_CLOUD_PROVIDER): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=CLOUD_PROVIDER_IP_API,
                                label="ip-api.com (free)",
                            ),
                            selector.SelectOptionDict(
                                value=CLOUD_PROVIDER_IPINFO,
                                label="ipinfo.io",
                            ),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_CLOUD_API_KEY): str,
                vol.Optional(
                    CONF_WHITELIST,
                    default=[],
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        multiline=True,
                        placeholder="192.168.0.0/16",
                    )
                ),
                vol.Optional(
                    CONF_HIDE_PRIVATE_IPS, default=DEFAULT_HIDE_PRIVATE_IPS
                ): bool,
                vol.Optional(
                    CONF_ONLY_EXTERNAL_ON_MAP,
                    default=DEFAULT_ONLY_EXTERNAL_ON_MAP,
                ): bool,
                vol.Optional(
                    CONF_RETENTION_DAYS, default=DEFAULT_RETENTION_DAYS
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=365)),
            }
        )
        if user_input is None:
            return self.async_show_form(step_id="cloud", data_schema=schema)

        whitelist = _parse_whitelist(user_input.get(CONF_WHITELIST, []))
        return self.async_create_entry(
            title="IP Attack Map",
            data={
                CONF_GEO_PROVIDER: GEO_PROVIDER_CLOUD,
                CONF_CLOUD_PROVIDER: user_input[CONF_CLOUD_PROVIDER],
                CONF_CLOUD_API_KEY: user_input.get(CONF_CLOUD_API_KEY) or None,
                CONF_WHITELIST: whitelist,
                CONF_HIDE_PRIVATE_IPS: user_input.get(
                    CONF_HIDE_PRIVATE_IPS, DEFAULT_HIDE_PRIVATE_IPS
                ),
                CONF_ONLY_EXTERNAL_ON_MAP: user_input.get(
                    CONF_ONLY_EXTERNAL_ON_MAP, DEFAULT_ONLY_EXTERNAL_ON_MAP
                ),
                CONF_RETENTION_DAYS: user_input.get(
                    CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS
                ),
            },
        )


class IpAttackMapOptionsFlow(config_entries.OptionsFlow):
    """Handle options for IP Attack Map."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_WHITELIST,
                    default="\n".join(self._entry.data.get(CONF_WHITELIST, [])),
                ): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)
                ),
                vol.Optional(
                    CONF_HIDE_PRIVATE_IPS,
                    default=self._entry.data.get(
                        CONF_HIDE_PRIVATE_IPS, DEFAULT_HIDE_PRIVATE_IPS
                    ),
                ): bool,
                vol.Optional(
                    CONF_ONLY_EXTERNAL_ON_MAP,
                    default=self._entry.data.get(
                        CONF_ONLY_EXTERNAL_ON_MAP, DEFAULT_ONLY_EXTERNAL_ON_MAP
                    ),
                ): bool,
                vol.Optional(
                    CONF_RETENTION_DAYS,
                    default=self._entry.data.get(
                        CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=365)),
            }
        )
        if user_input is None:
            return self.async_show_form(step_id="init", data_schema=schema)

        data = dict(self._entry.data)
        data[CONF_WHITELIST] = _parse_whitelist(user_input.get(CONF_WHITELIST, ""))
        data[CONF_HIDE_PRIVATE_IPS] = user_input[CONF_HIDE_PRIVATE_IPS]
        data[CONF_ONLY_EXTERNAL_ON_MAP] = user_input[CONF_ONLY_EXTERNAL_ON_MAP]
        data[CONF_RETENTION_DAYS] = user_input[CONF_RETENTION_DAYS]

        self.hass.config_entries.async_update_entry(self._entry, data=data)
        return self.async_create_entry(title="", data={})


def _parse_whitelist(value: str | list[str]) -> list[str]:
    """Parse whitelist from multiline string or list."""
    if isinstance(value, list):
        lines = value
    else:
        lines = str(value or "").splitlines()
    return [line.strip() for line in lines if line.strip()]
