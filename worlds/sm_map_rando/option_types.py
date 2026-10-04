"""
Option types used to expose Map Rando's settings as Archipelago options.

Map Rando settings are organized in categories (skill assumptions, item progression, quality of life, ...), each
with presets. As on the maprando.com website, a preset is chosen for each category, and individual settings can then
be changed from the preset's value. Individual setting options default to "preset", meaning: use the value from the
selected preset.
"""
from __future__ import annotations

import math
from typing import Any, ClassVar, Dict, Optional, Tuple

from Options import Choice, FreeText, NamedRange, OptionDict, OptionError


class MapRandoSetting:
    """Mixin for options corresponding to a Map Rando setting at a JSON path."""
    path: ClassVar[str] = ""

    def setting_value(self) -> Any:
        """The JSON value for the setting, or None to keep the value from the preset."""
        raise NotImplementedError


class PresetChoice(Choice, MapRandoSetting):
    """A Map Rando enum setting. The first choice, 'preset', keeps the value from the selected preset."""
    option_preset = 0
    default = 0
    # Map from option value to the JSON value in Map Rando's settings
    json_values: ClassVar[Dict[int, Any]] = {}

    def setting_value(self) -> Any:
        if self.value == self.option_preset:
            return None
        return self.json_values[self.value]


class PlainChoice(Choice, MapRandoSetting):
    """A Map Rando enum setting without a preset (it always sets the value)."""
    json_values: ClassVar[Dict[int, Any]] = {}

    def setting_value(self) -> Any:
        return self.json_values[self.value]


class PresetToggle(Choice, MapRandoSetting):
    """A Map Rando on/off setting. 'preset' keeps the value from the selected preset."""
    option_preset = 0
    option_false = 1
    option_true = 2
    alias_off = 1
    alias_no = 1
    alias_on = 2
    alias_yes = 2
    default = 0

    def setting_value(self) -> Any:
        if self.value == self.option_preset:
            return None
        return self.value == self.option_true


class PresetRange(NamedRange, MapRandoSetting):
    """A Map Rando integer setting. 'preset' (-1) keeps the value from the selected preset."""
    range_start = -1
    range_end = 100
    default = -1
    special_range_names = {"preset": -1}

    def setting_value(self) -> Any:
        if self.value == -1:
            return None
        return self.value

    @classmethod
    def get_option_name(cls, value: int) -> str:
        return "preset" if value == -1 else str(value)


class PresetFloat(FreeText, MapRandoSetting):
    """
    A Map Rando decimal number setting. 'preset' keeps the value from the selected preset; otherwise a number
    (decimals allowed).
    """
    default = "preset"
    min_value: ClassVar[Optional[float]] = None
    max_value: ClassVar[Optional[float]] = None

    def __init__(self, value: Any):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = repr(value)
        value = str(value).strip()
        if value.lower() != "preset":
            number = self.parse(value)
            if self.min_value is not None and number < self.min_value:
                raise OptionError(f"{self.__class__.__name__}: {value} is below the minimum {self.min_value}")
            if self.max_value is not None and number > self.max_value:
                raise OptionError(f"{self.__class__.__name__}: {value} is above the maximum {self.max_value}")
        else:
            value = "preset"
        super().__init__(value)

    @classmethod
    def parse(cls, value: str) -> float:
        try:
            number = float(value)
        except ValueError:
            raise OptionError(f"{cls.__name__}: expected 'preset' or a number, got {value!r}")
        if not math.isfinite(number):
            raise OptionError(f"{cls.__name__}: expected a finite number, got {value!r}")
        return number

    @classmethod
    def from_any(cls, data: Any) -> "PresetFloat":
        return cls(data)

    def setting_value(self) -> Any:
        if self.value == "preset":
            return None
        number = self.parse(self.value)
        return int(number) if number.is_integer() and self.integer_valued else number

    integer_valued: ClassVar[bool] = False

    @classmethod
    def get_option_name(cls, value: str) -> str:
        return value


class ChoiceMapping(OptionDict):
    """A mapping of keys (e.g. items) to one of a set of allowed values."""
    allowed_values: ClassVar[Tuple[str, ...]] = ()

    def verify_keys(self) -> None:
        super().verify_keys()
        for key, value in self.value.items():
            if value not in self.allowed_values:
                raise OptionError(f"{self.__class__.__name__}: invalid value {value!r} for {key!r}; "
                                  f"allowed values: {', '.join(self.allowed_values)}")
