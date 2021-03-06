"""Alexa message handlers."""
import logging
import math

from homeassistant import core as ha
from homeassistant.components import cover, fan, group, light, media_player
from homeassistant.components.climate import const as climate
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    STATE_ALARM_DISARMED,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_DISARM,
    SERVICE_LOCK,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_SET_COVER_POSITION,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_UNLOCK,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
import homeassistant.util.color as color_util
import homeassistant.util.dt as dt_util
from homeassistant.util.decorator import Registry
from homeassistant.util.temperature import convert as convert_temperature

from .const import (
    API_TEMP_UNITS,
    API_THERMOSTAT_MODES_CUSTOM,
    API_THERMOSTAT_MODES,
    API_THERMOSTAT_PRESETS,
    Cause,
    PERCENTAGE_FAN_MAP,
    RANGE_FAN_MAP,
    SPEED_FAN_MAP,
)
from .entities import async_get_entities
from .errors import (
    AlexaInvalidDirectiveError,
    AlexaInvalidValueError,
    AlexaSecurityPanelAuthorizationRequired,
    AlexaSecurityPanelUnauthorizedError,
    AlexaTempRangeError,
    AlexaUnsupportedThermostatModeError,
    AlexaVideoActionNotPermittedForContentError,
)
from .state_report import async_enable_proactive_mode

_LOGGER = logging.getLogger(__name__)
HANDLERS = Registry()


@HANDLERS.register(("Alexa.Discovery", "Discover"))
async def async_api_discovery(hass, config, directive, context):
    """Create a API formatted discovery response.

    Async friendly.
    """
    discovery_endpoints = [
        alexa_entity.serialize_discovery()
        for alexa_entity in async_get_entities(hass, config)
        if config.should_expose(alexa_entity.entity_id)
    ]

    return directive.response(
        name="Discover.Response",
        namespace="Alexa.Discovery",
        payload={"endpoints": discovery_endpoints},
    )


@HANDLERS.register(("Alexa.Authorization", "AcceptGrant"))
async def async_api_accept_grant(hass, config, directive, context):
    """Create a API formatted AcceptGrant response.

    Async friendly.
    """
    auth_code = directive.payload["grant"]["code"]
    _LOGGER.debug("AcceptGrant code: %s", auth_code)

    if config.supports_auth:
        await config.async_accept_grant(auth_code)

        if config.should_report_state:
            await async_enable_proactive_mode(hass, config)

    return directive.response(
        name="AcceptGrant.Response", namespace="Alexa.Authorization", payload={}
    )


@HANDLERS.register(("Alexa.PowerController", "TurnOn"))
async def async_api_turn_on(hass, config, directive, context):
    """Process a turn on request."""
    entity = directive.entity
    domain = entity.domain
    if domain == group.DOMAIN:
        domain = ha.DOMAIN

    service = SERVICE_TURN_ON
    if domain == cover.DOMAIN:
        service = cover.SERVICE_OPEN_COVER
    elif domain == media_player.DOMAIN:
        supported = entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        power_features = media_player.SUPPORT_TURN_ON | media_player.SUPPORT_TURN_OFF
        if not supported & power_features:
            service = media_player.SERVICE_MEDIA_PLAY

    await hass.services.async_call(
        domain,
        service,
        {ATTR_ENTITY_ID: entity.entity_id},
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.PowerController", "TurnOff"))
async def async_api_turn_off(hass, config, directive, context):
    """Process a turn off request."""
    entity = directive.entity
    domain = entity.domain
    if entity.domain == group.DOMAIN:
        domain = ha.DOMAIN

    service = SERVICE_TURN_OFF
    if entity.domain == cover.DOMAIN:
        service = cover.SERVICE_CLOSE_COVER
    elif domain == media_player.DOMAIN:
        supported = entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        power_features = media_player.SUPPORT_TURN_ON | media_player.SUPPORT_TURN_OFF
        if not supported & power_features:
            service = media_player.SERVICE_MEDIA_STOP

    await hass.services.async_call(
        domain,
        service,
        {ATTR_ENTITY_ID: entity.entity_id},
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.BrightnessController", "SetBrightness"))
async def async_api_set_brightness(hass, config, directive, context):
    """Process a set brightness request."""
    entity = directive.entity
    brightness = int(directive.payload["brightness"])

    await hass.services.async_call(
        entity.domain,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity.entity_id, light.ATTR_BRIGHTNESS_PCT: brightness},
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.BrightnessController", "AdjustBrightness"))
async def async_api_adjust_brightness(hass, config, directive, context):
    """Process an adjust brightness request."""
    entity = directive.entity
    brightness_delta = int(directive.payload["brightnessDelta"])

    # read current state
    try:
        current = math.floor(
            int(entity.attributes.get(light.ATTR_BRIGHTNESS)) / 255 * 100
        )
    except ZeroDivisionError:
        current = 0

    # set brightness
    brightness = max(0, brightness_delta + current)
    await hass.services.async_call(
        entity.domain,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity.entity_id, light.ATTR_BRIGHTNESS_PCT: brightness},
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.ColorController", "SetColor"))
async def async_api_set_color(hass, config, directive, context):
    """Process a set color request."""
    entity = directive.entity
    rgb = color_util.color_hsb_to_RGB(
        float(directive.payload["color"]["hue"]),
        float(directive.payload["color"]["saturation"]),
        float(directive.payload["color"]["brightness"]),
    )

    await hass.services.async_call(
        entity.domain,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity.entity_id, light.ATTR_RGB_COLOR: rgb},
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.ColorTemperatureController", "SetColorTemperature"))
async def async_api_set_color_temperature(hass, config, directive, context):
    """Process a set color temperature request."""
    entity = directive.entity
    kelvin = int(directive.payload["colorTemperatureInKelvin"])

    await hass.services.async_call(
        entity.domain,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity.entity_id, light.ATTR_KELVIN: kelvin},
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.ColorTemperatureController", "DecreaseColorTemperature"))
async def async_api_decrease_color_temp(hass, config, directive, context):
    """Process a decrease color temperature request."""
    entity = directive.entity
    current = int(entity.attributes.get(light.ATTR_COLOR_TEMP))
    max_mireds = int(entity.attributes.get(light.ATTR_MAX_MIREDS))

    value = min(max_mireds, current + 50)
    await hass.services.async_call(
        entity.domain,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity.entity_id, light.ATTR_COLOR_TEMP: value},
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.ColorTemperatureController", "IncreaseColorTemperature"))
async def async_api_increase_color_temp(hass, config, directive, context):
    """Process an increase color temperature request."""
    entity = directive.entity
    current = int(entity.attributes.get(light.ATTR_COLOR_TEMP))
    min_mireds = int(entity.attributes.get(light.ATTR_MIN_MIREDS))

    value = max(min_mireds, current - 50)
    await hass.services.async_call(
        entity.domain,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity.entity_id, light.ATTR_COLOR_TEMP: value},
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.SceneController", "Activate"))
async def async_api_activate(hass, config, directive, context):
    """Process an activate request."""
    entity = directive.entity
    domain = entity.domain

    await hass.services.async_call(
        domain,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity.entity_id},
        blocking=False,
        context=context,
    )

    payload = {
        "cause": {"type": Cause.VOICE_INTERACTION},
        "timestamp": f"{dt_util.utcnow().replace(tzinfo=None).isoformat()}Z",
    }

    return directive.response(
        name="ActivationStarted", namespace="Alexa.SceneController", payload=payload
    )


@HANDLERS.register(("Alexa.SceneController", "Deactivate"))
async def async_api_deactivate(hass, config, directive, context):
    """Process a deactivate request."""
    entity = directive.entity
    domain = entity.domain

    await hass.services.async_call(
        domain,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity.entity_id},
        blocking=False,
        context=context,
    )

    payload = {
        "cause": {"type": Cause.VOICE_INTERACTION},
        "timestamp": f"{dt_util.utcnow().replace(tzinfo=None).isoformat()}Z",
    }

    return directive.response(
        name="DeactivationStarted", namespace="Alexa.SceneController", payload=payload
    )


@HANDLERS.register(("Alexa.PercentageController", "SetPercentage"))
async def async_api_set_percentage(hass, config, directive, context):
    """Process a set percentage request."""
    entity = directive.entity
    percentage = int(directive.payload["percentage"])
    service = None
    data = {ATTR_ENTITY_ID: entity.entity_id}

    if entity.domain == fan.DOMAIN:
        service = fan.SERVICE_SET_SPEED
        speed = "off"

        if percentage <= 33:
            speed = "low"
        elif percentage <= 66:
            speed = "medium"
        elif percentage <= 100:
            speed = "high"
        data[fan.ATTR_SPEED] = speed

    elif entity.domain == cover.DOMAIN:
        service = SERVICE_SET_COVER_POSITION
        data[cover.ATTR_POSITION] = percentage

    await hass.services.async_call(
        entity.domain, service, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.PercentageController", "AdjustPercentage"))
async def async_api_adjust_percentage(hass, config, directive, context):
    """Process an adjust percentage request."""
    entity = directive.entity
    percentage_delta = int(directive.payload["percentageDelta"])
    service = None
    data = {ATTR_ENTITY_ID: entity.entity_id}

    if entity.domain == fan.DOMAIN:
        service = fan.SERVICE_SET_SPEED
        speed = entity.attributes.get(fan.ATTR_SPEED)
        current = PERCENTAGE_FAN_MAP.get(speed, 100)

        # set percentage
        percentage = max(0, percentage_delta + current)
        speed = "off"

        if percentage <= 33:
            speed = "low"
        elif percentage <= 66:
            speed = "medium"
        elif percentage <= 100:
            speed = "high"

        data[fan.ATTR_SPEED] = speed

    elif entity.domain == cover.DOMAIN:
        service = SERVICE_SET_COVER_POSITION

        current = entity.attributes.get(cover.ATTR_POSITION)

        data[cover.ATTR_POSITION] = max(0, percentage_delta + current)

    await hass.services.async_call(
        entity.domain, service, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.LockController", "Lock"))
async def async_api_lock(hass, config, directive, context):
    """Process a lock request."""
    entity = directive.entity
    await hass.services.async_call(
        entity.domain,
        SERVICE_LOCK,
        {ATTR_ENTITY_ID: entity.entity_id},
        blocking=False,
        context=context,
    )

    response = directive.response()
    response.add_context_property(
        {"name": "lockState", "namespace": "Alexa.LockController", "value": "LOCKED"}
    )
    return response


@HANDLERS.register(("Alexa.LockController", "Unlock"))
async def async_api_unlock(hass, config, directive, context):
    """Process an unlock request."""
    entity = directive.entity
    await hass.services.async_call(
        entity.domain,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: entity.entity_id},
        blocking=False,
        context=context,
    )

    response = directive.response()
    response.add_context_property(
        {"namespace": "Alexa.LockController", "name": "lockState", "value": "UNLOCKED"}
    )

    return response


@HANDLERS.register(("Alexa.Speaker", "SetVolume"))
async def async_api_set_volume(hass, config, directive, context):
    """Process a set volume request."""
    volume = round(float(directive.payload["volume"] / 100), 2)
    entity = directive.entity

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        media_player.const.ATTR_MEDIA_VOLUME_LEVEL: volume,
    }

    await hass.services.async_call(
        entity.domain, SERVICE_VOLUME_SET, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.InputController", "SelectInput"))
async def async_api_select_input(hass, config, directive, context):
    """Process a set input request."""
    media_input = directive.payload["input"]
    entity = directive.entity

    # attempt to map the ALL UPPERCASE payload name to a source
    source_list = entity.attributes[media_player.const.ATTR_INPUT_SOURCE_LIST] or []
    for source in source_list:
        # response will always be space separated, so format the source in the
        # most likely way to find a match
        formatted_source = source.lower().replace("-", " ").replace("_", " ")
        if formatted_source in media_input.lower():
            media_input = source
            break
    else:
        msg = "failed to map input {} to a media source on {}".format(
            media_input, entity.entity_id
        )
        raise AlexaInvalidValueError(msg)

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        media_player.const.ATTR_INPUT_SOURCE: media_input,
    }

    await hass.services.async_call(
        entity.domain,
        media_player.SERVICE_SELECT_SOURCE,
        data,
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.Speaker", "AdjustVolume"))
async def async_api_adjust_volume(hass, config, directive, context):
    """Process an adjust volume request."""
    volume_delta = int(directive.payload["volume"])

    entity = directive.entity
    current_level = entity.attributes.get(media_player.const.ATTR_MEDIA_VOLUME_LEVEL)

    # read current state
    try:
        current = math.floor(int(current_level * 100))
    except ZeroDivisionError:
        current = 0

    volume = float(max(0, volume_delta + current) / 100)

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        media_player.const.ATTR_MEDIA_VOLUME_LEVEL: volume,
    }

    await hass.services.async_call(
        entity.domain, SERVICE_VOLUME_SET, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.StepSpeaker", "AdjustVolume"))
async def async_api_adjust_volume_step(hass, config, directive, context):
    """Process an adjust volume step request."""
    # media_player volume up/down service does not support specifying steps
    # each component handles it differently e.g. via config.
    # This workaround will simply call the volume up/Volume down the amount of steps asked for
    # When no steps are called in the request, Alexa sends a default of 10 steps which for most
    # purposes is too high. The default  is set 1 in this case.
    entity = directive.entity
    volume_int = int(directive.payload["volumeSteps"])
    is_default = bool(directive.payload["volumeStepsDefault"])
    default_steps = 1

    if volume_int < 0:
        service_volume = SERVICE_VOLUME_DOWN
        if is_default:
            volume_int = -default_steps
    else:
        service_volume = SERVICE_VOLUME_UP
        if is_default:
            volume_int = default_steps

    data = {ATTR_ENTITY_ID: entity.entity_id}

    for _ in range(0, abs(volume_int)):
        await hass.services.async_call(
            entity.domain, service_volume, data, blocking=False, context=context
        )

    return directive.response()


@HANDLERS.register(("Alexa.StepSpeaker", "SetMute"))
@HANDLERS.register(("Alexa.Speaker", "SetMute"))
async def async_api_set_mute(hass, config, directive, context):
    """Process a set mute request."""
    mute = bool(directive.payload["mute"])
    entity = directive.entity
    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        media_player.const.ATTR_MEDIA_VOLUME_MUTED: mute,
    }

    await hass.services.async_call(
        entity.domain, SERVICE_VOLUME_MUTE, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.PlaybackController", "Play"))
async def async_api_play(hass, config, directive, context):
    """Process a play request."""
    entity = directive.entity
    data = {ATTR_ENTITY_ID: entity.entity_id}

    await hass.services.async_call(
        entity.domain, SERVICE_MEDIA_PLAY, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.PlaybackController", "Pause"))
async def async_api_pause(hass, config, directive, context):
    """Process a pause request."""
    entity = directive.entity
    data = {ATTR_ENTITY_ID: entity.entity_id}

    await hass.services.async_call(
        entity.domain, SERVICE_MEDIA_PAUSE, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.PlaybackController", "Stop"))
async def async_api_stop(hass, config, directive, context):
    """Process a stop request."""
    entity = directive.entity
    data = {ATTR_ENTITY_ID: entity.entity_id}

    await hass.services.async_call(
        entity.domain, SERVICE_MEDIA_STOP, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.PlaybackController", "Next"))
async def async_api_next(hass, config, directive, context):
    """Process a next request."""
    entity = directive.entity
    data = {ATTR_ENTITY_ID: entity.entity_id}

    await hass.services.async_call(
        entity.domain, SERVICE_MEDIA_NEXT_TRACK, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.PlaybackController", "Previous"))
async def async_api_previous(hass, config, directive, context):
    """Process a previous request."""
    entity = directive.entity
    data = {ATTR_ENTITY_ID: entity.entity_id}

    await hass.services.async_call(
        entity.domain,
        SERVICE_MEDIA_PREVIOUS_TRACK,
        data,
        blocking=False,
        context=context,
    )

    return directive.response()


def temperature_from_object(hass, temp_obj, interval=False):
    """Get temperature from Temperature object in requested unit."""
    to_unit = hass.config.units.temperature_unit
    from_unit = TEMP_CELSIUS
    temp = float(temp_obj["value"])

    if temp_obj["scale"] == "FAHRENHEIT":
        from_unit = TEMP_FAHRENHEIT
    elif temp_obj["scale"] == "KELVIN":
        # convert to Celsius if absolute temperature
        if not interval:
            temp -= 273.15

    return convert_temperature(temp, from_unit, to_unit, interval)


@HANDLERS.register(("Alexa.ThermostatController", "SetTargetTemperature"))
async def async_api_set_target_temp(hass, config, directive, context):
    """Process a set target temperature request."""
    entity = directive.entity
    min_temp = entity.attributes.get(climate.ATTR_MIN_TEMP)
    max_temp = entity.attributes.get(climate.ATTR_MAX_TEMP)
    unit = hass.config.units.temperature_unit

    data = {ATTR_ENTITY_ID: entity.entity_id}

    payload = directive.payload
    response = directive.response()
    if "targetSetpoint" in payload:
        temp = temperature_from_object(hass, payload["targetSetpoint"])
        if temp < min_temp or temp > max_temp:
            raise AlexaTempRangeError(hass, temp, min_temp, max_temp)
        data[ATTR_TEMPERATURE] = temp
        response.add_context_property(
            {
                "name": "targetSetpoint",
                "namespace": "Alexa.ThermostatController",
                "value": {"value": temp, "scale": API_TEMP_UNITS[unit]},
            }
        )
    if "lowerSetpoint" in payload:
        temp_low = temperature_from_object(hass, payload["lowerSetpoint"])
        if temp_low < min_temp or temp_low > max_temp:
            raise AlexaTempRangeError(hass, temp_low, min_temp, max_temp)
        data[climate.ATTR_TARGET_TEMP_LOW] = temp_low
        response.add_context_property(
            {
                "name": "lowerSetpoint",
                "namespace": "Alexa.ThermostatController",
                "value": {"value": temp_low, "scale": API_TEMP_UNITS[unit]},
            }
        )
    if "upperSetpoint" in payload:
        temp_high = temperature_from_object(hass, payload["upperSetpoint"])
        if temp_high < min_temp or temp_high > max_temp:
            raise AlexaTempRangeError(hass, temp_high, min_temp, max_temp)
        data[climate.ATTR_TARGET_TEMP_HIGH] = temp_high
        response.add_context_property(
            {
                "name": "upperSetpoint",
                "namespace": "Alexa.ThermostatController",
                "value": {"value": temp_high, "scale": API_TEMP_UNITS[unit]},
            }
        )

    await hass.services.async_call(
        entity.domain,
        climate.SERVICE_SET_TEMPERATURE,
        data,
        blocking=False,
        context=context,
    )

    return response


@HANDLERS.register(("Alexa.ThermostatController", "AdjustTargetTemperature"))
async def async_api_adjust_target_temp(hass, config, directive, context):
    """Process an adjust target temperature request."""
    entity = directive.entity
    min_temp = entity.attributes.get(climate.ATTR_MIN_TEMP)
    max_temp = entity.attributes.get(climate.ATTR_MAX_TEMP)
    unit = hass.config.units.temperature_unit

    temp_delta = temperature_from_object(
        hass, directive.payload["targetSetpointDelta"], interval=True
    )
    target_temp = float(entity.attributes.get(ATTR_TEMPERATURE)) + temp_delta

    if target_temp < min_temp or target_temp > max_temp:
        raise AlexaTempRangeError(hass, target_temp, min_temp, max_temp)

    data = {ATTR_ENTITY_ID: entity.entity_id, ATTR_TEMPERATURE: target_temp}

    response = directive.response()
    await hass.services.async_call(
        entity.domain,
        climate.SERVICE_SET_TEMPERATURE,
        data,
        blocking=False,
        context=context,
    )
    response.add_context_property(
        {
            "name": "targetSetpoint",
            "namespace": "Alexa.ThermostatController",
            "value": {"value": target_temp, "scale": API_TEMP_UNITS[unit]},
        }
    )

    return response


@HANDLERS.register(("Alexa.ThermostatController", "SetThermostatMode"))
async def async_api_set_thermostat_mode(hass, config, directive, context):
    """Process a set thermostat mode request."""
    entity = directive.entity
    mode = directive.payload["thermostatMode"]
    mode = mode if isinstance(mode, str) else mode["value"]

    data = {ATTR_ENTITY_ID: entity.entity_id}

    ha_preset = next((k for k, v in API_THERMOSTAT_PRESETS.items() if v == mode), None)

    if ha_preset:
        presets = entity.attributes.get(climate.ATTR_PRESET_MODES, [])

        if ha_preset not in presets:
            msg = f"The requested thermostat mode {ha_preset} is not supported"
            raise AlexaUnsupportedThermostatModeError(msg)

        service = climate.SERVICE_SET_PRESET_MODE
        data[climate.ATTR_PRESET_MODE] = ha_preset

    elif mode == "CUSTOM":
        operation_list = entity.attributes.get(climate.ATTR_HVAC_MODES)
        custom_mode = directive.payload["thermostatMode"]["customName"]
        custom_mode = next(
            (k for k, v in API_THERMOSTAT_MODES_CUSTOM.items() if v == custom_mode),
            None,
        )
        if custom_mode not in operation_list:
            msg = (
                f"The requested thermostat mode {mode}: {custom_mode} is not supported"
            )
            raise AlexaUnsupportedThermostatModeError(msg)

        service = climate.SERVICE_SET_HVAC_MODE
        data[climate.ATTR_HVAC_MODE] = custom_mode

    else:
        operation_list = entity.attributes.get(climate.ATTR_HVAC_MODES)
        ha_modes = {k: v for k, v in API_THERMOSTAT_MODES.items() if v == mode}
        ha_mode = next(iter(set(ha_modes).intersection(operation_list)), None)
        if ha_mode not in operation_list:
            msg = f"The requested thermostat mode {mode} is not supported"
            raise AlexaUnsupportedThermostatModeError(msg)

        service = climate.SERVICE_SET_HVAC_MODE
        data[climate.ATTR_HVAC_MODE] = ha_mode

    response = directive.response()
    await hass.services.async_call(
        climate.DOMAIN, service, data, blocking=False, context=context
    )
    response.add_context_property(
        {
            "name": "thermostatMode",
            "namespace": "Alexa.ThermostatController",
            "value": mode,
        }
    )

    return response


@HANDLERS.register(("Alexa", "ReportState"))
async def async_api_reportstate(hass, config, directive, context):
    """Process a ReportState request."""
    return directive.response(name="StateReport")


@HANDLERS.register(("Alexa.PowerLevelController", "SetPowerLevel"))
async def async_api_set_power_level(hass, config, directive, context):
    """Process a SetPowerLevel request."""
    entity = directive.entity
    percentage = int(directive.payload["powerLevel"])
    service = None
    data = {ATTR_ENTITY_ID: entity.entity_id}

    if entity.domain == fan.DOMAIN:
        service = fan.SERVICE_SET_SPEED
        speed = "off"

        if percentage <= 33:
            speed = "low"
        elif percentage <= 66:
            speed = "medium"
        else:
            speed = "high"

        data[fan.ATTR_SPEED] = speed

    await hass.services.async_call(
        entity.domain, service, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.PowerLevelController", "AdjustPowerLevel"))
async def async_api_adjust_power_level(hass, config, directive, context):
    """Process an AdjustPowerLevel request."""
    entity = directive.entity
    percentage_delta = int(directive.payload["powerLevelDelta"])
    service = None
    data = {ATTR_ENTITY_ID: entity.entity_id}

    if entity.domain == fan.DOMAIN:
        service = fan.SERVICE_SET_SPEED
        speed = entity.attributes.get(fan.ATTR_SPEED)
        current = PERCENTAGE_FAN_MAP.get(speed, 100)

        # set percentage
        percentage = max(0, percentage_delta + current)
        speed = "off"

        if percentage <= 33:
            speed = "low"
        elif percentage <= 66:
            speed = "medium"
        else:
            speed = "high"

        data[fan.ATTR_SPEED] = speed

    await hass.services.async_call(
        entity.domain, service, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.SecurityPanelController", "Arm"))
async def async_api_arm(hass, config, directive, context):
    """Process a Security Panel Arm request."""
    entity = directive.entity
    service = None
    arm_state = directive.payload["armState"]
    data = {ATTR_ENTITY_ID: entity.entity_id}

    if entity.state != STATE_ALARM_DISARMED:
        msg = "You must disarm the system before you can set the requested arm state."
        raise AlexaSecurityPanelAuthorizationRequired(msg)

    if arm_state == "ARMED_AWAY":
        service = SERVICE_ALARM_ARM_AWAY
    if arm_state == "ARMED_STAY":
        service = SERVICE_ALARM_ARM_HOME
    if arm_state == "ARMED_NIGHT":
        service = SERVICE_ALARM_ARM_NIGHT

    await hass.services.async_call(
        entity.domain, service, data, blocking=False, context=context
    )

    response = directive.response(
        name="Arm.Response", namespace="Alexa.SecurityPanelController"
    )

    response.add_context_property(
        {
            "name": "armState",
            "namespace": "Alexa.SecurityPanelController",
            "value": arm_state,
        }
    )

    return response


@HANDLERS.register(("Alexa.SecurityPanelController", "Disarm"))
async def async_api_disarm(hass, config, directive, context):
    """Process a Security Panel Disarm request."""
    entity = directive.entity
    data = {ATTR_ENTITY_ID: entity.entity_id}

    payload = directive.payload
    if "authorization" in payload:
        value = payload["authorization"]["value"]
        if payload["authorization"]["type"] == "FOUR_DIGIT_PIN":
            data["code"] = value

    if not await hass.services.async_call(
        entity.domain, SERVICE_ALARM_DISARM, data, blocking=True, context=context
    ):
        msg = "Invalid Code"
        raise AlexaSecurityPanelUnauthorizedError(msg)

    response = directive.response()
    response.add_context_property(
        {
            "name": "armState",
            "namespace": "Alexa.SecurityPanelController",
            "value": "DISARMED",
        }
    )

    return response


@HANDLERS.register(("Alexa.ModeController", "SetMode"))
async def async_api_set_mode(hass, config, directive, context):
    """Process a next request."""
    entity = directive.entity
    instance = directive.instance
    domain = entity.domain
    service = None
    data = {ATTR_ENTITY_ID: entity.entity_id}
    mode = directive.payload["mode"]

    if domain != fan.DOMAIN:
        msg = "Entity does not support directive"
        raise AlexaInvalidDirectiveError(msg)

    if instance == f"{fan.DOMAIN}.{fan.ATTR_DIRECTION}":
        mode, direction = mode.split(".")
        if direction in [fan.DIRECTION_REVERSE, fan.DIRECTION_FORWARD]:
            service = fan.SERVICE_SET_DIRECTION
            data[fan.ATTR_DIRECTION] = direction

    await hass.services.async_call(
        domain, service, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.ModeController", "AdjustMode"))
async def async_api_adjust_mode(hass, config, directive, context):
    """Process a AdjustMode request.

    Requires modeResources to be ordered.
    Only modes that are ordered support the adjustMode directive.
    """
    entity = directive.entity
    instance = directive.instance
    domain = entity.domain

    if domain != fan.DOMAIN:
        msg = "Entity does not support directive"
        raise AlexaInvalidDirectiveError(msg)

    if instance is None:
        msg = "Entity does not support directive"
        raise AlexaInvalidDirectiveError(msg)

    # No modeResources are currently ordered to support this request.

    return directive.response()


@HANDLERS.register(("Alexa.ToggleController", "TurnOn"))
async def async_api_toggle_on(hass, config, directive, context):
    """Process a toggle on request."""
    entity = directive.entity
    instance = directive.instance
    domain = entity.domain
    service = None
    data = {ATTR_ENTITY_ID: entity.entity_id}

    if domain != fan.DOMAIN:
        msg = "Entity does not support directive"
        raise AlexaInvalidDirectiveError(msg)

    if instance == f"{fan.DOMAIN}.{fan.ATTR_OSCILLATING}":
        service = fan.SERVICE_OSCILLATE
        data[fan.ATTR_OSCILLATING] = True

    await hass.services.async_call(
        domain, service, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.ToggleController", "TurnOff"))
async def async_api_toggle_off(hass, config, directive, context):
    """Process a toggle off request."""
    entity = directive.entity
    instance = directive.instance
    domain = entity.domain
    service = None
    data = {ATTR_ENTITY_ID: entity.entity_id}

    if domain != fan.DOMAIN:
        msg = "Entity does not support directive"
        raise AlexaInvalidDirectiveError(msg)

    if instance == f"{fan.DOMAIN}.{fan.ATTR_OSCILLATING}":
        service = fan.SERVICE_OSCILLATE
        data[fan.ATTR_OSCILLATING] = False

    await hass.services.async_call(
        domain, service, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.RangeController", "SetRangeValue"))
async def async_api_set_range(hass, config, directive, context):
    """Process a next request."""
    entity = directive.entity
    instance = directive.instance
    domain = entity.domain
    service = None
    data = {ATTR_ENTITY_ID: entity.entity_id}
    range_value = int(directive.payload["rangeValue"])

    if domain != fan.DOMAIN:
        msg = "Entity does not support directive"
        raise AlexaInvalidDirectiveError(msg)

    if instance == f"{fan.DOMAIN}.{fan.ATTR_SPEED}":
        service = fan.SERVICE_SET_SPEED
        speed = SPEED_FAN_MAP.get(range_value, None)

        if not speed:
            msg = "Entity does not support value"
            raise AlexaInvalidValueError(msg)

        if speed == fan.SPEED_OFF:
            service = fan.SERVICE_TURN_OFF

        data[fan.ATTR_SPEED] = speed

    await hass.services.async_call(
        domain, service, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.RangeController", "AdjustRangeValue"))
async def async_api_adjust_range(hass, config, directive, context):
    """Process a next request."""
    entity = directive.entity
    instance = directive.instance
    domain = entity.domain
    service = None
    data = {ATTR_ENTITY_ID: entity.entity_id}
    range_delta = int(directive.payload["rangeValueDelta"])

    if instance == f"{fan.DOMAIN}.{fan.ATTR_SPEED}":
        service = fan.SERVICE_SET_SPEED

        # adjust range
        current_range = RANGE_FAN_MAP.get(entity.attributes.get(fan.ATTR_SPEED), 0)
        speed = SPEED_FAN_MAP.get(max(0, range_delta + current_range), fan.SPEED_OFF)

        if speed == fan.SPEED_OFF:
            service = fan.SERVICE_TURN_OFF

        data[fan.ATTR_SPEED] = speed

    await hass.services.async_call(
        domain, service, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.ChannelController", "ChangeChannel"))
async def async_api_changechannel(hass, config, directive, context):
    """Process a change channel request."""
    channel = "0"
    entity = directive.entity
    payload = directive.payload["channel"]
    payload_name = "number"

    if "number" in payload:
        channel = payload["number"]
        payload_name = "number"
    elif "callSign" in payload:
        channel = payload["callSign"]
        payload_name = "callSign"
    elif "affiliateCallSign" in payload:
        channel = payload["affiliateCallSign"]
        payload_name = "affiliateCallSign"
    elif "uri" in payload:
        channel = payload["uri"]
        payload_name = "uri"

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        media_player.const.ATTR_MEDIA_CONTENT_ID: channel,
        media_player.const.ATTR_MEDIA_CONTENT_TYPE: media_player.const.MEDIA_TYPE_CHANNEL,
    }

    await hass.services.async_call(
        entity.domain,
        media_player.const.SERVICE_PLAY_MEDIA,
        data,
        blocking=False,
        context=context,
    )

    response = directive.response()

    response.add_context_property(
        {
            "namespace": "Alexa.ChannelController",
            "name": "channel",
            "value": {payload_name: channel},
        }
    )

    return response


@HANDLERS.register(("Alexa.ChannelController", "SkipChannels"))
async def async_api_skipchannel(hass, config, directive, context):
    """Process a skipchannel request."""
    channel = int(directive.payload["channelCount"])
    entity = directive.entity

    data = {ATTR_ENTITY_ID: entity.entity_id}

    if channel < 0:
        service_media = SERVICE_MEDIA_PREVIOUS_TRACK
    else:
        service_media = SERVICE_MEDIA_NEXT_TRACK

    for _ in range(0, abs(channel)):
        await hass.services.async_call(
            entity.domain, service_media, data, blocking=False, context=context
        )

    response = directive.response()

    response.add_context_property(
        {
            "namespace": "Alexa.ChannelController",
            "name": "channel",
            "value": {"number": ""},
        }
    )

    return response


@HANDLERS.register(("Alexa.SeekController", "AdjustSeekPosition"))
async def async_api_seek(hass, config, directive, context):
    """Process a seek request."""
    entity = directive.entity
    position_delta = int(directive.payload["deltaPositionMilliseconds"])

    current_position = entity.attributes.get(media_player.ATTR_MEDIA_POSITION)
    if not current_position:
        msg = f"{entity} did not return the current media position."
        raise AlexaVideoActionNotPermittedForContentError(msg)

    seek_position = int(current_position) + int(position_delta / 1000)

    if seek_position < 0:
        seek_position = 0

    media_duration = entity.attributes.get(media_player.ATTR_MEDIA_DURATION)
    if media_duration and 0 < int(media_duration) < seek_position:
        seek_position = media_duration

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        media_player.ATTR_MEDIA_SEEK_POSITION: seek_position,
    }

    await hass.services.async_call(
        media_player.DOMAIN,
        media_player.SERVICE_MEDIA_SEEK,
        data,
        blocking=False,
        context=context,
    )

    # convert seconds to milliseconds for StateReport.
    seek_position = int(seek_position * 1000)

    payload = {"properties": [{"name": "positionMilliseconds", "value": seek_position}]}
    return directive.response(
        name="StateReport", namespace="Alexa.SeekController", payload=payload
    )
