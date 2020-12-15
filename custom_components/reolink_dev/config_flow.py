"""Config flow for the Reolink camera component."""
import logging

import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .base import ReolinkBase
from .const import (
    BASE,
    CONF_CHANNEL,
    CONF_MOTION_OFF_DELAY,
    CONF_PROTOCOL,
    CONF_STREAM,
    DEFAULT_MOTION_OFF_DELAY,
    DEFAULT_STREAM,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ReolinkFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Reolink camera's."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    CHANNELS = 1
    MAC_ADDRESS = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return ReolinkOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self.data = user_input

            try:
                self.info = await self.validate_input(self.hass, user_input)

                if self.CHANNELS > 1:
                    return await self.async_step_nvr()

                self.data["channel"] = 1
                await self.async_set_unique_id(f"{self.MAC_ADDRESS}{user_input[CONF_CHANNEL]}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=self.info["title"], data=self.data)

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                errors["host"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=80): cv.positive_int,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_nvr(self, user_input=None):
        """Configure a NVR with multiple channels."""
        errors = {}
        if user_input is not None:
            self.data.update(user_input)

            await self.async_set_unique_id(f"{self.MAC_ADDRESS}{user_input[CONF_CHANNEL]}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=self.info["title"], data=self.data)

        return self.async_show_form(
            step_id="nvr",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CHANNEL): vol.All(vol.Coerce(int), vol.Range(min=1, max=self.CHANNELS)),
                }
            ),
            errors=errors,
        )

    async def validate_input(self, hass: core.HomeAssistant, user_input: dict):
        """Validate the user input allows us to connect."""
        base = ReolinkBase(
            hass,
            user_input,
            []
        )

        if not await base.connect_api():
            raise CannotConnect

        title = base.api.name
        self.CHANNELS = base.api._device_info["value"]["DevInfo"]["channelNum"]
        self.MAC_ADDRESS = base.api.mac_address
        base.disconnect_api()
        return {"title": title}


class ReolinkOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Reolink options."""

    def __init__(self, config_entry):
        """Initialize Reolink options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):  # pylint: disable=unused-argument
        """Manage the Reolink options."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STREAM, 
                    default=self.config_entry.options.get(
                            CONF_STREAM, DEFAULT_STREAM
                        ),): vol.In(
                        ["main", "sub"]
                    ),
                    vol.Required(
                        CONF_MOTION_OFF_DELAY,
                        default=self.config_entry.options.get(
                            CONF_MOTION_OFF_DELAY, DEFAULT_MOTION_OFF_DELAY
                        ),
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_TIMEOUT,
                        default=self.config_entry.options.get(
                            CONF_TIMEOUT, DEFAULT_TIMEOUT
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                }
            ),
        )


class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate device is already configured."""

class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""