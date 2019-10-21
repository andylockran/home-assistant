"""The HeatmiserV3Revisited integration."""
import asyncio
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, DATA_HEATMISER_CONFIG, HEATMISER_PLATFORMS
from .hub import UH1Entity


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): {
            vol.Required(CONF_HOST): cv.string,
            vol.Required(CONF_PORT): cv.port,
        }
    }
)


async def async_setup(hass, config):
    """Set up the HeatmiserV3Revisited integration."""

    hass.data[DATA_HEATMISER_CONFIG] = config.get(DOMAIN, {})

    if (
        not hass.config_entries.async_entries(DOMAIN)
        and hass.data[DATA_HEATMISER_CONFIG]
    ):
        # No config entry exists and configuration.yaml config exists, trigger the import flow.
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry for Heatmiser."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    UH1Entity(host, port)
    return True


async def async_unload_entry(hass, config_entry):
    """Unload the module."""
    hass.data.pop(DOMAIN)

    tasks = []
    for platform in HEATMISER_PLATFORMS:
        tasks.append(
            hass.config_entries.async_forward_entry_unload(config_entry, platform)
        )
    return all(await asyncio.gather(*tasks))
