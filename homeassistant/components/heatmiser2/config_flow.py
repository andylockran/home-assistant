"""Config flow to configure ecobee."""
import voluptuous as vol

from heatmiserV3 import connection

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN


class HeatmiserFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an heatmiser config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the heatmiser flow."""
        self._uh1 = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            # Config entry already exists, only one allowed.
            return self.async_abort(reason="one_instance_only")

        errors = {}

        if user_input is not None:
            # Creates a temporary connection to the serial port to assure that this is valid.
            self._uh1 = connection.HeatmiserUH1(
                user_input[CONF_HOST], user_input[CONF_PORT]
            )
            config = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
            }
            return self.async_create_entry(title=DOMAIN, data=config)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST): str, vol.Required(CONF_PORT): str}
            ),
            errors=errors,
        )
