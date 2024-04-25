from typing import Any, Self
from dataclasses import dataclass
import numpy as np

from pyramid.model.model import BufferData


@dataclass
class NumericEventList(BufferData):
    """Wrap a 2D array listing one event per row: [timestamp, value [, value ...]]."""

    event_data: np.ndarray
    """2D array backing the event list.

    event_data must have shape (n, m>=2) where:
     - n is the number of events (one event per row)
     - m is at least 2 (timestamps and values in columns):
       - column 0 holds the event timestamps
       - columns 1+ hold one or more values per event
    """

    def __eq__(self, other: object) -> bool:
        """Compare event_data arrays as-a-whole instead of element-wise."""
        if isinstance(other, self.__class__):
            return (self.event_data.size == 0 and other.event_data.size == 0) or np.array_equal(self.event_data, other.event_data)
        else:
            return False

    def copy(self) -> Self:
        """Implementing BufferData superclass."""
        return NumericEventList(self.event_data.copy())

    def get_time_selector(self, start_time: float, end_time: float) -> np.ndarray:
        if start_time is None:
            tail_selector = np.repeat(True, self.event_data.shape[0])
        else:
            tail_selector = self.event_data[:, 0] >= start_time

        if end_time is None:
            head_selector = np.repeat(True, self.event_data.shape[0])
        else:
            head_selector = self.event_data[:, 0] < end_time

        return tail_selector & head_selector

    def copy_time_range(self, start_time: float = None, end_time: float = None) -> Self:
        """Implementing BufferData superclass."""
        rows_in_range = self.get_time_selector(start_time, end_time)
        range_event_data = self.event_data[rows_in_range, :]
        return NumericEventList(range_event_data)

    def append(self, other: Self) -> None:
        """Implementing BufferData superclass."""
        self.event_data = np.concatenate([self.event_data, other.event_data])

    def discard_before(self, start_time: float) -> None:
        """Implementing BufferData superclass."""
        rows_to_keep = self.event_data[:, 0] >= start_time
        self.event_data = self.event_data[rows_to_keep, :]

    def shift_times(self, shift: float) -> None:
        """Implementing BufferData superclass."""
        if self.event_data.size > 0:
            self.event_data[:, 0] += shift

    def get_end_time(self) -> float:
        """Implementing BufferData superclass."""
        if self.event_count():
            return self.event_data[:, 0].max()
        else:
            return None

    def get_times_of(
        self,
        event_value: float,
        value_index: int = 0,
        start_time: float = None,
        end_time: float = None
    ) -> np.ndarray:
        """Get times of any events matching the given event_value.

        By default this searches the first value per event.
        Pass in value_index>0 to use a different value per event.

        By default this searches all events in the list.
        Pass in start_time restrict to events at or after start_time.
        Pass in end_time restrict to events strictly before end_time.
        """
        rows_in_range = self.get_time_selector(start_time, end_time)
        value_column = value_index + 1
        matching_rows = (self.event_data[:, value_column] == event_value)
        return self.event_data[rows_in_range & matching_rows, 0]

    def apply_offset_then_gain(self, offset: float = 0, gain: float = 1, value_index: int = 0) -> None:
        """Transform all event data by a constant gain and offset.

        Uses a convention of applying offset first, then gain.
        This comes from ecodes where we might want to subtract an arbitrary baseline then scale to a fixed precision.

        By default this modifies the first value per event.
        Pass in value_index>0 to use a different value per event.

        This modifies the event_data of this object, in place.
        """
        value_column = value_index + 1
        self.event_data[:, value_column] += offset
        self.event_data[:, value_column] *= gain

    def get_times(self) -> np.ndarray:
        """Get just the event times, ignoring event values."""
        return self.event_data[:, 0]

    def event_count(self) -> int:
        """Get the number of events in the list.

        Event timestamps are in event_data[:,0].
        So, the number of events is event_data.shape[0].
        """
        return self.event_data.shape[0]

    def values_per_event(self) -> int:
        """Get the number of values per event.

        Event values are in event_data[:,1].
        Optional additional event values may be in event_data[:,2], event_data[:,3], etc.
        So, the number of values per event is (event_data.shape[1] - 1).
        """
        return self.event_data.shape[1] - 1

    def get_values(self, start_time: float = None, end_time: float = None, value_index: int = 0) -> np.ndarray:
        """Get just the event values, ignoring event times.

        By default this gets only the first value per event.
        Pass in value_index>0 to get a different value.
        """
        rows_in_range = self.get_time_selector(start_time, end_time)
        value_column = value_index + 1
        return self.event_data[rows_in_range, value_column]

    def copy_value_range(self, min: float = None, max: float = None, value_index: int = 0) -> Self:
        """Make a new list containing only events with values in half open interval [min, max).

        Omit min to copy all events with value strictly less than max.
        Omit max to copy all events with value greater than or equal to min.

        By default min and max apply to the first value per event.
        Pass in value_index>0 to use a different value per event.

        This returns a new NumericEventList with a copy of events in the requested range.
        """
        value_column = value_index + 1
        if min is None:
            top_selector = True
        else:
            top_selector = self.event_data[:, value_column] >= min

        if max is None:
            bottom_selector = True
        else:
            bottom_selector = self.event_data[:, value_column] < max

        rows_in_range = top_selector & bottom_selector
        range_event_data = self.event_data[rows_in_range, :]
        return NumericEventList(range_event_data)


@dataclass
class TextEventList(BufferData):
    """Wrap an array of timestamps and an array of text data.

    Although the timestamps and text are stored as separate arrays, with different data types,
    we can think of TextEventList as a 2D array with shape (n,2) where the rows look like:
        [timestamp, text],
        [timestamp, text],
        [timestamp, text],
        ...
    """

    timestamp_data: np.ndarray
    """1D array backing the event times.

    timestamp_data must have shape (n,), where n is the number of events.
    It should have a numeric data type, like numpy.float32 or numpy.float64.
    """

    text_data: np.ndarray
    """1D array backing the event text.

    text_data must have shape (n,), where n is the number of events.
    It should have a unicode string data type from numpy.str_, for example "<U16", "<U64", "<U256", etc.
    """

    def __eq__(self, other: object) -> bool:
        """Compare data arrays as-a-whole instead of element-wise."""
        if isinstance(other, self.__class__):
            if (self.timestamp_data.size == 0 and other.timestamp_data.size == 0 and self.text_data.size == 0 and other.text_data.size == 0):
                return True
            else:
                return np.array_equal(self.timestamp_data, other.timestamp_data) and np.array_equal(self.text_data, other.text_data)
        else:
            return False

    def copy(self) -> Self:
        """Implementing BufferData superclass."""
        return TextEventList(self.timestamp_data.copy(), self.text_data.copy())

    def get_time_selector(self, start_time: float, end_time: float) -> np.ndarray:
        if start_time is None:
            tail_selector = np.repeat(True, self.timestamp_data.shape[0])
        else:
            tail_selector = self.timestamp_data >= start_time

        if end_time is None:
            head_selector = np.repeat(True, self.timestamp_data.shape[0])
        else:
            head_selector = self.timestamp_data < end_time

        return tail_selector & head_selector

    def copy_time_range(self, start_time: float = None, end_time: float = None) -> Self:
        """Implementing BufferData superclass."""
        rows_in_range = self.get_time_selector(start_time, end_time)
        range_timestamp_data = self.timestamp_data[rows_in_range]
        range_text_data = self.text_data[rows_in_range]
        return TextEventList(range_timestamp_data, range_text_data)

    def append(self, other: Self) -> None:
        """Implementing BufferData superclass."""
        self.timestamp_data = np.concatenate([self.timestamp_data, other.timestamp_data])
        self.text_data = np.concatenate([self.text_data, other.text_data])

    def discard_before(self, start_time: float) -> None:
        """Implementing BufferData superclass."""
        rows_to_keep = self.timestamp_data >= start_time
        self.timestamp_data = self.timestamp_data[rows_to_keep]
        self.text_data = self.text_data[rows_to_keep]

    def shift_times(self, shift: float) -> None:
        """Implementing BufferData superclass."""
        if self.timestamp_data.size > 0:
            self.timestamp_data += shift

    def get_end_time(self) -> float:
        """Implementing BufferData superclass."""
        if self.event_count():
            return self.timestamp_data.max()
        else:
            return None

    def event_count(self) -> int:
        """Get the number of events in the list -- the length of the text event data."""
        return self.text_data.size

    def get_times_of(
        self,
        event_value: str,
        value_index: int = 0,
        start_time: float = None,
        end_time: float = None
    ) -> np.ndarray:
        """Get times of any events matching the given event_value.

        This ignores value_index and always searches the text_data array.

        By default this searches all events in the list.
        Pass in start_time restrict to events at or after start_time.
        Pass in end_time restrict to events strictly before end_time.
        """
        rows_in_range = self.get_time_selector(start_time, end_time)
        matching_rows = (self.text_data == event_value)
        return self.timestamp_data[rows_in_range & matching_rows]

    def get_values(self, start_time: float = None, end_time: float = None) -> np.ndarray:
        """Get just the event text values, ignoring event times."""
        rows_in_range = self.get_time_selector(start_time, end_time)
        return self.text_data[rows_in_range]
