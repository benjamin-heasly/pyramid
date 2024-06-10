import sys
from importlib import import_module
from typing import Any, Self, Iterator
from inspect import signature

import numpy as np

from pyramid.file_finder import FileFinder

class DynamicImport():
    """Utility for creating class instances from a dynamically imported module and class.

    Document optional file_finder, injected by context, or None
    """

    @classmethod
    def from_dynamic_import(
        cls,
        import_spec: str,
        file_finder: FileFinder,
        external_package_path: str = None,
        **kwargs
    ) -> Self:
        """Create a class instance from a dynamically imported module and class.

        The given import_spec should be of the form "package.subpackage.module.ClassName".
        The "package.subpackage.module" will be imported dynamically via importlib.
        Then "ClassName" from the imported module will be invoked as a class constructor.

        This should be equivalent to the static statement "from package.subpackage.module import ClassName",
        followed by instance = ClassName(**kwargs)

        Returns a new instance of the imported class.

        Provide external_package_path in order to import a class from a module that was not
        already installed by the usual means, eg conda or pip.  The external_package_path will
        be added temporarily to the Python import search path, then removed when done here.
        """
        last_dot = import_spec.rfind(".")
        module_spec = import_spec[0:last_dot]

        try:
            original_sys_path = sys.path
            if external_package_path:
                sys.path = original_sys_path.copy()
                path_to_add = file_finder.find(external_package_path)
                sys.path.append(path_to_add)
            imported_module = import_module(module_spec, package=None)
        finally:
            sys.path = original_sys_path

        class_name = import_spec[last_dot+1:]
        imported_class = getattr(imported_module, class_name)

        # Does the class constructor want to have a "file_finder" helper injected?
        constructor_signature = signature(imported_class)
        if "file_finder" in constructor_signature.parameters.keys():
            instance = imported_class(file_finder=file_finder, **kwargs)
        else:
            instance = imported_class(**kwargs)

        # Remember the kwargs this instance was constructed with, for audit/visualization.
        instance.kwargs = kwargs

        return instance


class BufferData():
    """An interface to tell us what Pyramid data types must have in common in order to flow from Reader to Trial."""

    def copy(self) -> Self:
        """Create a new, independent copy of the data -- allows reusing raw data along multuple routes/buffers."""
        raise NotImplementedError  # pragma: no cover

    def copy_time_range(self, start_time: float = None, end_time: float = None) -> Self:
        """Copy subset of data in half-open interval [start_time, end_time) -- allows selecting data into trials.

        Omit start_time to copy all events strictly before end_time.
        Omit end_time to copy all events at and after start_time.
        """
        raise NotImplementedError  # pragma: no cover

    def append(self, other: Self) -> None:
        """Append data from the given object to this object, in place -- this is the main buffering operation."""
        raise NotImplementedError  # pragma: no cover

    def discard_before(self, start_time: float) -> None:
        """Discard data strictly before the given start_time -- to prevent buffers from consuming unlimited memory."""
        raise NotImplementedError  # pragma: no cover

    def shift_times(self, shift: float) -> None:
        """Shift data times, in place -- allows Trial "wrt" alignment and Reader clock adjustments."""
        raise NotImplementedError  # pragma: no cover

    def start(self) -> float:
        """Get the time of the first data item still in the buffer."""
        raise NotImplementedError  # pragma: no cover

    def end(self) -> float:
        """Get the time of the latest data item still in the buffer."""
        raise NotImplementedError  # pragma: no cover

    def times(
        self,
        value: Any = None,
        value_index: int = 0,
        start_time: float = None,
        end_time: float = None
    ) -> np.ndarray:
        """Get an array of times for buffered values.

        By default returns times for all buffered values.
        If value is provided, returns the times when value occurred, if any.
        Implementations that store non-scalar values can use value_index to pick from one column/channel/etc.

        By default returns the full range of buffered times.
        If start_time is provided, returns only times at or after start_time.
        If end_time is provided, returns only times strictly before end_time.
        """
        raise NotImplementedError  # pragma: no cover

    def first(self, value_index: int = 0):
        """Get the first buffered value.

        Implementations that store non-scalar values can use value_index to pick from one column/channel/etc.
        """
        raise NotImplementedError  # pragma: no cover

    def last(self, value_index: int = 0):
        """Get the last buffered value.

        Implementations that store non-scalar values can use value_index to pick from one column/channel/etc.
        """
        raise NotImplementedError  # pragma: no cover

    def values(
        self,
        value_index: int = 0,
        start_time: float = None,
        end_time: float = None
    ) -> np.ndarray:
        """Get an array of buffered values.

        Implementations that store non-scalar values can use value_index to pick from one column/channel/etc.

        By default returns the full range of buffered values.
        If start_time is provided, returns only values at or after start_time.
        If end_time is provided, returns only values from strictly before end_time.
        """
        raise NotImplementedError  # pragma: no cover

    def at(
        self,
        time: float = 0.0,
        value_index: int = 0,
    ) -> Any:
        """Get the first value at or after the given time.

        Implementations that store non-scalar values can use value_index to pick from one column/channel/etc.
        """
        raise NotImplementedError  # pragma: no cover

    def each(self) -> Iterator[tuple[float, Any]]:
        """Return an iterator over events or samples in this buffer, with each presented as a tuple: (timestamp, value)."""
        raise NotImplementedError  # pragma: no cover


class Buffer():
    """Hold data in a sliding window of time, smoothing any timing mismatch between Readers and Trials.

    In addition to the actual buffer data, holds a clock drift estimate that may change over time.
    Reader routers can update this offset as they calibrate themselves over time,
    and Trials can include this offset querying and aligning data.
    """

    def __init__(
        self,
        initial_data: BufferData,
        initial_clock_drift: float = 0.0
    ) -> None:
        self.data = initial_data
        self.clock_drift = initial_clock_drift
        self.sync_events = []

    def __eq__(self, other: object) -> bool:
        """Compare buffers field-wise, to support use of this class in tests."""
        if isinstance(other, self.__class__):
            return (
                self.data == other.data
                and self.clock_drift == other.clock_drift
            )
        else:  # pragma: no cover
            return False

    def snap_to_sync_time(self, raw_time: float, snap_threshold: float = 0.0001) -> float:
        """If the given raw time is close to a known sync time, snap to the known sync time.

        This is to avoid floating point rounding error on computed raw times.
        This ususally won't matter.
        But if a raw time falls near a trial boundary, even tiny rounding errors can cause
        data to show up in the wrong trial.
        """
        if not self.sync_events:
            return raw_time

        differences = [abs(raw_time - event.timestamp) for event in self.sync_events]
        min_difference = min(differences)
        if min_difference < snap_threshold:
            min_index = differences.index(min_difference)
            return self.sync_events[min_index].timestamp
        else:
            return raw_time

    def raw_time_to_reference(self, raw_time: float) -> float:
        """Convert a time from the buffer's own raw clock to align with the Pyramid reference clock."""
        return self.snap_to_sync_time(raw_time) - self.clock_drift

    def reference_time_to_raw(self, reference_time: float) -> float:
        """Convert a time Pyramid's reference clock to align with the buffer's own raw clock."""
        if reference_time is None:
            return None
        else:
            return self.snap_to_sync_time(reference_time + self.clock_drift)
