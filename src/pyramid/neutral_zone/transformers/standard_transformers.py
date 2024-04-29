import logging

import numpy as np

from pyramid.model.model import BufferData
from pyramid.model.events import NumericEventList, TextEventList
from pyramid.model.signals import SignalChunk
from pyramid.neutral_zone.transformers.transformers import Transformer


class OffsetThenGain(Transformer):
    """Apply an offset, then gain, to values in a Pyramid BufferData type."""

    def __init__(self, offset: float = 0.0, gain: float = 1.0, value_id: int | str = 0, **kwargs) -> None:
        self.offset = offset
        self.gain = gain
        self.value_id = value_id

    def __eq__(self, other: object) -> bool:
        """Compare transformers field-wise, to support use of this class in tests."""
        if isinstance(other, self.__class__):
            return (
                self.offset == other.offset
                and self.gain == other.gain
                and self.value_id == other.value_id
            )
        else:  # pragma: no cover
            return False

    def transform(self, data: BufferData) -> BufferData:
        if isinstance(data, NumericEventList):
            data.apply_offset_then_gain(self.offset, self.gain, self.value_id)
        elif isinstance(data, SignalChunk):
            data.apply_offset_then_gain(self.offset, self.gain)
        else:  # pragma: no cover
            logging.warning(f"OffsetThenGain doesn't know how to apply to {data.__class__.__name__}")
        return data


class FilterRange(Transformer):
    """Filter values, taking only those in the half open interval [min, max), from a Pyramid type like NumericEventList."""

    def __init__(self, min: float = None, max: float = None, value_index: int = 0, **kwargs) -> None:
        self.min = min
        self.max = max
        self.value_index = value_index

    def transform(self, data: BufferData) -> BufferData:
        if isinstance(data, NumericEventList):
            return data.copy_value_range(self.min, self.max, self.value_index)
        else:  # pragma: no cover
            logging.warning(f"FilterRange doesn't know how to apply to {data.__class__.__name__}")
            return data


class SmashCase(Transformer):
    """Filter text event values, transforming them to all UPPER or all lower case."""

    def __init__(self, upper_case: bool = True, **kwargs) -> None:
        self.upper_case = upper_case

    def transform(self, data: BufferData):
        if isinstance(data, TextEventList):
            if (self.upper_case):
                return TextEventList(data.timestamp_data, np.char.upper(data.text_data))
            else:
                return TextEventList(data.timestamp_data, np.char.lower(data.text_data))
        else:  # pragma: no cover
            logging.warning(f"SmashCase doesn't know how to apply to {data.__class__.__name__}")
            return data
