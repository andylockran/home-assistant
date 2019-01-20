"""
Support for the PRT Heatmiser themostats using the V3 protocol.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.heatmiser/
"""
import logging
import time
import voluptuous as vol

from homeassistant.components.climate import (
    ClimateDevice, PLATFORM_SCHEMA, SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import (
    TEMP_CELSIUS, ATTR_TEMPERATURE, CONF_PORT, CONF_NAME, CONF_ID, PRECISION_WHOLE)
    
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['heatmiserV3==1.1.8']

_LOGGER = logging.getLogger(__name__)

CONF_IPADDRESS = 'ipaddress'
CONF_PORT = 'port'
CONF_TSTATS = 'tstats'

# TSTATS_SCHEMA = vol.Schema({
#     vol.Required(CONF_ID): cv.string,
#     vol.Required(CONF_NAME): cv.string,
# })

# PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
#     vol.Required(CONF_IPADDRESS): cv.string,
#     vol.Required(CONF_PORT): cv.port,
#     vol.Required(CONF_TSTATS, default=[]):
#         vol.Schema({cv.string: TSTATS_SCHEMA}),
# })


DOMAIN = 'heatmiser_uh1'
ATTR_NAME = 'name'
DEFAULT_NAME = 'uh1'

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the heatmiser thermostat."""
    from heatmiserV3 import heatmiser, connection

    ipaddress = config.get(CONF_IPADDRESS)
    port = str(config.get(CONF_PORT))
    tstats = config.get(CONF_TSTATS)

    uh1 = connection.HeatmiserUH1(ipaddress, port)
    add_entities([HeatmiserUH1(uh1)])

    for tstat in tstats:
        room = tstat.get('room')
        therm_id = tstat.get('id')
        model = tstat.get('model')
        thermostat = heatmiser.HeatmiserThermostat(therm_id, model, uh1)
        add_entities([
            HeatmiserV3Thermostat(
            thermostat, room)
        ])
        time.sleep(3)


class HeatmiserUH1(ClimateDevice):
    def __init__(self, uh1):
        self.uh1 = uh1

    def temperature_unit(self):
        return TEMP_CELSIUS
    
    def supported_features(self):
        return None

class HeatmiserV3Thermostat(ClimateDevice):
    """Representation of a HeatmiserV3 thermostat."""

    def __init__(self, thermostat, name):
        """Initialize the thermostat."""
        self.thermostat = thermostat
        self.thermostat.read_dcb()
        self._current_temperature = self.thermostat.get_floor_temp()
        self._name = name

    @property
    def precision(self):
        return PRECISION_WHOLE

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.thermostat.get_floor_temp()

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.thermostat.get_target_temp()

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        _LOGGER.info("Setting temperature to {}".format(int(temperature)))
        if temperature is None:
            return
        self.thermostat.set_target_temp(int(temperature))

    def update(self):
        """Get the latest data."""
        self.dcb = self.thermostat.read_dcb()
        self._target_temperature = int(self.thermostat.get_target_temp())
        _LOGGER.info("Target temperature for {} is {}".format(self._name, self._target_temperature))

