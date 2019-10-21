"""The core heatmiser hub."""
from homeassistant.helpers.entity import Entity

from heatmiserV3 import connection
from .const import _LOGGER


class UH1Entity(Entity):
    """Basic UH1 Entity."""

    def __init__(self, host, port):
        """Set up device locally."""
        _LOGGER.info("Creating UH1 Device")
        self.uh1 = connection.HeatmiserUH1(host, port)
        _LOGGER.info("Creating UH1 Device")
