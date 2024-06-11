from types import TracebackType
from typing import Any, ContextManager, Self
from dataclasses import dataclass, field
import logging

from pyramid.model.model import DynamicImport, BufferData, Buffer
from pyramid.neutral_zone.transformers.transformers import Transformer
from pyramid.neutral_zone.readers.sync import ReaderSyncConfig, ReaderSyncRegistry


class Reader(DynamicImport, ContextManager):
    """Interface for consuming data from arbitrary sources and converting to Pyramid BufferData types.

    Each reader implementation should:
     - Encapsulate the details of how to connect to a data source and get data from it.
     - Maintain internal state related to the data source, like a file handle and byte offset, a data block index,
       a socket descriptor, etc.
     - Implement read_next() to consume an increment of available data from the source, update internal state
       to reflect this, and return results as a dict of name - BufferData entries.
     - Implement __enter__() and __exit__() to confirm to Python's "context manager protocol"", which
       is how Pyramid manages acquisition and release of system and libarary resources.
       See: https://peps.python.org/pep-0343/#standard-terminology
     - Implement get_initial() to return a dictionary of name - BufferData entries, allowing users of the
       Reader to see the expected names and BufferData sub-types that the reader will produce.

    The focus of a reader implementation should be getting data out of the source incrementally and converting
    each increment into a dict of BufferData values.  From there, Pyramid takes the results of get_initial()
    and read_next() and handles how the data are copied into connected buffers, filtered and transformed into
    desired forms, and eventually assigned to trials.
    """

    def __enter__(self) -> Self:
        """Connect to a data source and acquire related system or library resources.

        Return an object that we can "read_next()" on -- probably return self.
        """
        raise NotImplementedError  # pragma: no cover

    def __exit__(
        self,
        __exc_type: type[BaseException] | None,
        __exc_value: BaseException | None,
        __traceback: TracebackType | None
    ) -> bool | None:
        """Release any resources acquired during __enter()__."""
        raise NotImplementedError  # pragma: no cover

    def read_next(self) -> dict[str, BufferData]:
        """Read/poll for new data at the connected source and convert available data to Pyramid BufferData types.

        This must not block when reading from its data source.
        Rather, it should read/poll for data once and just return None if no data are available yet.
        Pyramid will call read_next() again, soon, to get the next available data.
        This convention allows multiple concurrent readers to be interleaved,
        and for the readers to be interleaved with other tasks like interactive GUI user event handling.

        The implementation can choose its own read/poll strategy or timeout.
        Returning from read_next() within ~1 millisecond should be good.

        Return a dicitonary of any data consumed during the read increment, or None if no data available.
        Dictionary values must all be Pyramid BufferData types.
        Dictionary keys should suggest an interpretation of the interpretation, like "spikes", "event_codes", etc.
        """
        raise NotImplementedError  # pragma: no cover

    def get_initial(self) -> dict[str, BufferData]:
        """Create an initial dictionary of names and BufferData sub-types that Reader expects to produce.

        This is called before __enter__() or read_next().
        It's intended to inform Pyramid what result keys this Reader will produce, and the BufferData sub-types that it will use.
        These help setting up downstream components that receive the results of read_next().
        The initial dictionary returned here can (and should!) depend on the kwargs passed to the Reader's constructor. 
        """
        raise NotImplementedError  # pragma: no cover


@dataclass
class ReaderRoute():
    """Specify the mapping from a reader get_initial() or read_next() diciontary entry to a named buffer."""

    reader_result_name: str
    """How the reader named a result, like "spikes", "events", etc."""

    buffer_name: str
    """Name for the buffer that will receive the BufferData for "spikes", "ecodes", etc."""

    transformers: list[Transformer] = field(default_factory=list)
    """Optional data transformations between reader and buffer, applied in order."""


class ReaderRouter():
    """Get incremental results from a reader, copy and route the data into named buffers.

    If the reader throws an exception, it will be ignored going forward.
    This would apply equally to errors and orderly end-of-data situations.
    """

    def __init__(
        self,
        reader: Reader,
        routes: list[ReaderRoute],
        named_buffers: dict[str, Buffer],
        empty_reads_allowed: int = 3,
        sync_config: ReaderSyncConfig = None,
        sync_registry: ReaderSyncRegistry = None
    ) -> None:
        self.reader = reader
        self.routes = routes
        self.named_buffers = named_buffers
        self.empty_reads_allowed = empty_reads_allowed
        self.sync_config = sync_config
        self.sync_registry = sync_registry

        self.reader_exception = None
        self.max_buffer_time = 0.0
        self.clock_drift = 0.0

    def __eq__(self, other: object) -> bool:
        """Compare routers field-wise, to support use of this class in tests."""
        if isinstance(other, self.__class__):
            return (
                self.reader == other.reader
                and self.routes == other.routes
                and self.named_buffers == other.named_buffers
                and self.empty_reads_allowed == other.empty_reads_allowed
                and self.sync_config == other.sync_config
            )
        else:  # pragma: no cover
            return False

    def still_going(self) -> bool:
        return not self.reader_exception

    def route_next(self) -> bool:
        """Ask the reader to consume an increment of data, unconditoinally, and deal results into connected buffers."""
        if self.reader_exception:
            return False

        try:
            read_result = self.reader.read_next()
        except StopIteration as stop_iteration:
            self.reader_exception = stop_iteration
            logging.info(f"Reader {self.reader.__class__.__name__} is done (it raised StopIteration).")
            return False
        except Exception as exception:
            self.reader_exception = exception
            logging.warning(
                f"Reader {self.reader.__class__.__name__} is disabled (it raised an unexpected error):",
                exc_info=True
            )
            return False

        if not read_result:
            return False

        for route in self.routes:
            buffer = self.named_buffers.get(route.buffer_name, None)
            if not buffer:
                continue

            data = read_result.get(route.reader_result_name, None)
            if not data:
                continue

            data_copy = data.copy()
            if route.transformers:
                try:
                    for transformer in route.transformers:
                        data_copy = transformer.transform(data_copy)
                except Exception as exception:
                    logging.error(
                        f"Route transformer had an exception, skipping data for {route.reader_result_name} -> {route.buffer_name}:",
                        exc_info=True
                    )
                    continue

            try:
                buffer.data.append(data_copy)
            except Exception as exception:
                logging.error(
                    "Route buffer had exception appending data, skipping data for {route.reader_result_name} -> {route.buffer_name}:",
                    exc_info=True
                )
                continue

            # Add any new sync events to the sync registry.
            if self.sync_config is not None and self.sync_registry is not None and route.buffer_name == self.sync_config.buffer_name:
                # Iterate incoming, candidate sync events one at a time.
                for (timestamp, value) in data_copy.each():
                    # Check which incoming events pass a configured event filter.
                    count = self.sync_registry.event_count(self.sync_config.reader_name)
                    if self.sync_config.filter_event(timestamp, value, count):
                        # Get a default or custom sync timestamp and sync key from each event.
                        sync_timestamp = self.sync_config.sync_timestamp(timestamp, value, count, timestamp)
                        sync_key = self.sync_config.sync_key(timestamp, value, count, sync_timestamp)

                        # Record a new sync event for this reader.
                        self.sync_registry.record_event(self.sync_config.reader_name, sync_timestamp, sync_key)

        # Update the high water mark for the reader -- the latest timestamp seen so far.
        for buffer in self.named_buffers.values():
            buffer_end_time = buffer.data.end()
            if buffer_end_time and buffer_end_time > self.max_buffer_time:
                self.max_buffer_time = buffer_end_time

        return True

    def route_until(self, target_reference_time: float) -> float:
        """Ask the reader to read 0 or more times until catching up to the given reference time.

        This will convert the given target_reference_time into its own time frame, based on its
        current clock_drift estimate.  This is a target_reader_time.

        This will repeat reading until it sees some new data arrive with data_time_1 >= target_reader_time.

        This will continue reading until it sees some new data arive with data_time_2 > data_time_1.
        This last part is to ensure that any data with the same data_time_1 are treated as equivalent
        in time, and not split between trials or lost between trials.

        In case new data are not available, may return early, after exhausting empty_reads_allowed.

        Returns the latest timestamp seen, so far.
        """

        # Is the reader already caught up?
        target_reader_time = target_reference_time + self.clock_drift
        if self.max_buffer_time >= target_reader_time:
            return self.max_buffer_time

        # Catch up with at least one data item at or after the target time.
        empty_reads = 0
        while self.max_buffer_time < target_reader_time and empty_reads <= self.empty_reads_allowed:
            got_data = self.route_next()
            if got_data:
                empty_reads = 0
            else:
                empty_reads += 1

        # Continue reading data that have equal times, so that time-equal items are not split up.
        equal_item_time = self.max_buffer_time
        empty_reads = 0
        while self.max_buffer_time <= equal_item_time and empty_reads <= self.empty_reads_allowed:
            got_data = self.route_next()
            if got_data:
                empty_reads = 0
            else:
                empty_reads += 1

        return self.max_buffer_time

    def update_drift_estimate(self, reference_end_time: float = None) -> float:
        """Get a reader clock drift estimate from the sync registry and propagate it to all buffers.

        Return the current drift estimate.
        """
        if self.sync_config is None or self.sync_registry is None:
            return None

        if reference_end_time is None:
            reader_end_time = None
        else:
            reader_end_time = reference_end_time + self.clock_drift
        self.clock_drift = self.sync_registry.compute_offset(
            self.sync_config.reader_name,
            self.sync_config.pairing_strategy,
            reference_end_time,
            reader_end_time,
            self.sync_config.pairing_padding
        )
        for buffer in self.named_buffers.values():
            buffer.clock_drift = self.clock_drift
            buffer.sync_events = self.sync_registry.find_events(self.sync_config.reader_name)

        return self.clock_drift
