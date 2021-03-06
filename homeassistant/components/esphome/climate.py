"""Support for ESPHome climate devices."""
import logging
import math
from typing import TYPE_CHECKING, List, Optional

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_OPERATION_MODE, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW,
    STATE_AUTO, STATE_COOL, STATE_HEAT, SUPPORT_AWAY_MODE,
    SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_HIGH, SUPPORT_TARGET_TEMPERATURE_LOW)
from homeassistant.const import (
    ATTR_TEMPERATURE, PRECISION_HALVES, PRECISION_TENTHS, PRECISION_WHOLE,
    STATE_OFF, TEMP_CELSIUS)

from . import EsphomeEntity, platform_async_setup_entry

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from aioesphomeapi import ClimateInfo, ClimateState, ClimateMode  # noqa

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up ESPHome climate devices based on a config entry."""
    # pylint: disable=redefined-outer-name
    from aioesphomeapi import ClimateInfo, ClimateState  # noqa

    await platform_async_setup_entry(
        hass, entry, async_add_entities,
        component_key='climate',
        info_type=ClimateInfo, entity_type=EsphomeClimateDevice,
        state_type=ClimateState
    )


def _ha_climate_mode_to_esphome(mode: str) -> 'ClimateMode':
    # pylint: disable=redefined-outer-name
    from aioesphomeapi import ClimateMode  # noqa
    return {
        STATE_OFF: ClimateMode.OFF,
        STATE_AUTO: ClimateMode.AUTO,
        STATE_COOL: ClimateMode.COOL,
        STATE_HEAT: ClimateMode.HEAT,
    }[mode]


def _esphome_climate_mode_to_ha(mode: 'ClimateMode') -> str:
    # pylint: disable=redefined-outer-name
    from aioesphomeapi import ClimateMode  # noqa
    return {
        ClimateMode.OFF: STATE_OFF,
        ClimateMode.AUTO: STATE_AUTO,
        ClimateMode.COOL: STATE_COOL,
        ClimateMode.HEAT: STATE_HEAT,
    }[mode]


class EsphomeClimateDevice(EsphomeEntity, ClimateDevice):
    """A climate implementation for ESPHome."""

    @property
    def _static_info(self) -> 'ClimateInfo':
        return super()._static_info

    @property
    def _state(self) -> Optional['ClimateState']:
        return super()._state

    @property
    def precision(self) -> float:
        """Return the precision of the climate device."""
        precicions = [PRECISION_WHOLE, PRECISION_HALVES, PRECISION_TENTHS]
        for prec in precicions:
            if self._static_info.visual_temperature_step >= prec:
                return prec
        # Fall back to highest precision, tenths
        return PRECISION_TENTHS

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def operation_list(self) -> List[str]:
        """Return the list of available operation modes."""
        return [
            _esphome_climate_mode_to_ha(mode)
            for mode in self._static_info.supported_modes
        ]

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        # Round to one digit because of floating point math
        return round(self._static_info.visual_temperature_step, 1)

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._static_info.visual_min_temperature

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._static_info.visual_max_temperature

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        features = SUPPORT_OPERATION_MODE
        if self._static_info.supports_two_point_target_temperature:
            features |= (SUPPORT_TARGET_TEMPERATURE_LOW |
                         SUPPORT_TARGET_TEMPERATURE_HIGH)
        else:
            features |= SUPPORT_TARGET_TEMPERATURE
        if self._static_info.supports_away:
            features |= SUPPORT_AWAY_MODE
        return features

    @property
    def current_operation(self) -> Optional[str]:
        """Return current operation ie. heat, cool, idle."""
        if self._state is None:
            return None
        return _esphome_climate_mode_to_ha(self._state.mode)

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        if self._state is None:
            return None
        if math.isnan(self._state.current_temperature):
            return None
        return self._state.current_temperature

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        if self._state is None:
            return None
        if math.isnan(self._state.target_temperature):
            return None
        return self._state.target_temperature

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        if self._state is None:
            return None
        if math.isnan(self._state.target_temperature_low):
            return None
        return self._state.target_temperature_low

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        if self._state is None:
            return None
        if math.isnan(self._state.target_temperature_high):
            return None
        return self._state.target_temperature_high

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        if self._state is None:
            return None
        return self._state.away

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature (and operation mode if set)."""
        data = {'key': self._static_info.key}
        if ATTR_OPERATION_MODE in kwargs:
            data['mode'] = _ha_climate_mode_to_esphome(
                kwargs[ATTR_OPERATION_MODE])
        if ATTR_TEMPERATURE in kwargs:
            data['target_temperature'] = kwargs[ATTR_TEMPERATURE]
        if ATTR_TARGET_TEMP_LOW in kwargs:
            data['target_temperature_low'] = kwargs[ATTR_TARGET_TEMP_LOW]
        if ATTR_TARGET_TEMP_HIGH in kwargs:
            data['target_temperature_high'] = kwargs[ATTR_TARGET_TEMP_HIGH]
        await self._client.climate_command(**data)

    async def async_set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        await self._client.climate_command(
            key=self._static_info.key,
            mode=_ha_climate_mode_to_esphome(operation_mode),
        )

    async def async_turn_away_mode_on(self):
        """Turn away mode on."""
        await self._client.climate_command(key=self._static_info.key,
                                           away=True)

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        await self._client.climate_command(key=self._static_info.key,
                                           away=False)
