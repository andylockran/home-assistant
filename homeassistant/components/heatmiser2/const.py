"""Constants for the HeatmiserV3Revisited integration."""
import logging
from datetime import timedelta

_LOGGER = logging.getLogger(__package__)

DOMAIN = "heatmiser2"
DATA_HEATMISER_CONFIG = "heatmiser2_config"
MIN_UPDATE_GAP = timedelta(seconds=2)

SUPPORTED_THERMOSTATS = ["prt"]
HEATMISER_PLATFORMS = ["climate"]
