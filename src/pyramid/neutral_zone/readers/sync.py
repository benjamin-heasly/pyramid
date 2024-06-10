import logging
from dataclasses import dataclass
from typing import NamedTuple, Any
from operator import itemgetter


@dataclass
class ReaderSyncConfig():
    """Specify configuration for how a reader should find sync events and align to a reference clock."""

    is_reference: str = False
    """Whether the reader represents the canonical, reference clock to which others readers will be aligned."""

    buffer_name: str = None
    """The name of the reader result or extra buffer that will contain sync events."""

    filter: str = None
    """Expression to evaluate and select events from the named buffer.

    The filter expression is evaluated once per event, with the following local variables available:
        "timestamp" the original timestamp of the incoming event
        "value"     the numeric or text value of the incoming event
        "count"     the overall count of sync events recorded for the reader, so far

    Only events where filter_expression returns True (or truthy) will be recorded as new sync events.
    The default filter is None, meaning record all incoming events as sync events.

    For numeric events, "value" will be a list of zero or more values per event.  To record only numeric
    events where the second value is 42, use a filter expression like this one:

        value[1] == 42

    For text events, "value" will be the event's text string.  To record only only text events that start
    with the prefix "Sync", use a filter expression like this one:

        value.startswith("Sync")

    Filter expressions can combine the timestamp, value, and event count as needed,  For example:

        timestmp > 0 and value[2] = 42 and count < 1000
    """

    timestamps: str = None
    """Expression to evaluate for each event, to obtain a sync event timestamp.

    The timestamps expression is evaluated once for each event that passes the filter expression with the
    following local variables available:
        "timestamp" the original timestamp of the incoming event
        "value"     the numeric or text value of the incoming event
        "count"     the overall count of sync events recorded for the reader, so far

    The expression should return a float value to use as the sync event's timestamp.
    The default timestamps expression is None, meaning use the original event's timestamp as the sync timestamp.

    For numeric events, "value" will be an array with zero or more values per event.  A timestamps expression
    like this one could substitute an event value for the orginal event timestamp:

        value[0]

    For text events, "value" will be the event's text string.  A timestamps expression like this one could
    parse a value out of a string like "Sync@123.45" and use the result to replace the original timestamp:

        float(value.split("@")[-1])

    The timestamps expresion can combine the timestamp, value, and event count as needed.  An expression like
    this one could conditionally replace the fracitonal part of the original event timestamp.

        timestamp if count < 100 else int(timestamp) + value[0] / 1000
    """

    keys: str = None
    """Expression to evaluate for each event, to obtain a sync event key.

    The keys expression is evaluated once for each event that passes the filter expression, with the
    following local variables available:
        "timestamp" the original timestamp of the incoming event
        "value"     the numeric or text value of the incoming event
        "count"     the overall count of sync events recorded for the reader, so far

    The expression should return a float value to use as the sync event's key.
    The default keys expression is None, meaning reuse the result of the timetamps expression as the sync event key.

    For numeric events, "value" will be an array with zero or more values per event.  A keys expression
    like this one could take the second value per event as they sync event key:

        value[1]

    For text events, "value" will be the event's text string.  A keys expression like this one could
    parse a key out of a string like "Sync@123.45=001":

        int(value.split("=")[-1])

    The keys expression can combine the timestamp, value, and event count as needed.  An expression like
    this one could choose a key conditionally based on all of these.

        value[0] if timestamp < 100 else count + value[1] / 1000
    """

    reader_name: str = None
    """The name of the reader to act as when aligning data within trials.

    Usually reader_name would be the name of the reader itself.
    Or it may be the name of a different reader so that one reader may reuse sync info from another.
    """

    init_event_count: int = 1
    """How many initial sync events Pyramid should to try to read for this reader, before delimiting trials."""

    init_max_reads: int = 100
    """How many times Pyramid should keep trying to read when waiting for initial sync events."""

    pairing_strategy: str = "closest"
    """How to pair up event keys between readers: "closest", "max", or "last equal"."""

    pairing_padding: float = 0.01
    """Padding to use when searching for timstamps to pair up.

    Add some padding (10ms by default) to queries for reader sync events near a trial end time.
    This should allow us to use the most up-to-date sync events we have on hand when estimating
    clock offsets between reader, even when sync events have some jitter, or we encounter floating
    point rounding errors.

    The basic intuition for this is: when looking at sync events up to time 3.0, don't exclude
    events with times like 3.00000001.
    """

    def __post_init__(self):
        """Compile callback expressoins for use in methods below."""
        if self.filter is None:
            self.compiled_filter = None
        else:
            self.compiled_filter = compile(self.filter, '<string>', 'eval')

        if self.timestamps is None:
            self.compiled_timestamps = None
        else:
            self.compiled_timestamps = compile(self.timestamps, '<string>', 'eval')

        if self.keys is None:
            self.compiled_keys = None
        else:
            self.compiled_keys = compile(self.keys, '<string>', 'eval')

    def filter_event(self, timestamp: float, value: Any, count: int) -> bool:
        """Apply the filter expression to the given timestamp and value and return the True/False result."""
        if self.compiled_filter is None:
            return True
        else:
            locals = {
                "timestamp": timestamp,
                "value": value,
                "count": count
            }
            filter_result = eval(self.compiled_filter, {}, locals)
            return bool(filter_result)

    def sync_timestamp(self, timestamp: float, value: Any, count: int, default: float) -> float:
        """Apply the timestamps expression to the given timestamp and value and return the numeric result."""
        if self.compiled_timestamps is None:
            return default
        else:
            locals = {
                "timestamp": timestamp,
                "value": value,
                "count": count
            }
            timestamp_result = eval(self.compiled_timestamps, {}, locals)
            return float(timestamp_result)

    def sync_key(self, timestamp: float, value: Any, count: int, default: float) -> float:
        """Apply the keys expression to the given timestamp and value and return the numeric result."""
        if self.compiled_keys is None:
            return default
        else:
            locals = {
                "timestamp": timestamp,
                "value": value,
                "count": count
            }
            keys_result = eval(self.compiled_keys, {}, locals)
            return float(keys_result)


class SyncEvent(NamedTuple):
    """Record a sync event as a pair of timestamp (used for alignment) and key (used to pair up corresponding events)."""

    timestamp: float
    """When a real-world sync event occurred, according to a particular reader and its clock."""

    key: float
    """Key used to match up sync events that represent the same real-world event, as seen by different readers."""


class ReaderSyncRegistry():
    """Keep track of sync events as seen by different readers and compute clock offsets compared to a reference reader."""

    def __init__(
        self,
        reference_reader_name: str
    ) -> None:
        self.reference_reader_name = reference_reader_name
        self.reader_events: dict[str, list[SyncEvent]] = {}

    def __eq__(self, other: object) -> bool:
        """Compare registry field-wise, to support use of this class in tests."""
        if isinstance(other, self.__class__):
            return (
                self.reference_reader_name == other.reference_reader_name
                and self.reader_events == other.reader_events
            )
        else:  # pragma: no cover
            return False

    def event_count(self, reader_name: str) -> int:
        events = self.reader_events.get(reader_name, [])
        return len(events)

    def record_event(self, reader_name: str, event_time: float, event_key: float = None) -> None:
        """Record a sync event as seen by the named reader."""
        if event_key is None:
            event_key = event_time
        events = self.reader_events.get(reader_name, [])
        events.append(SyncEvent(timestamp=event_time, key=event_key))
        self.reader_events[reader_name] = events
        logging.info(f"Recorded sync for {reader_name} at time {event_time} with key {event_key} ({len(events)} total).")

    def find_events(self, reader_name: str, end_time: float = None, end_padding: float = 0.0) -> list[float]:
        """Find sync events for the given reader, at or before the given end time.

        If end_time is before the first sync event, return the first sync event.

        If padding is provided, allow sync events at or before (end_time + end_padding).
        """
        events = self.reader_events.get(reader_name, [])
        if not events:
            return []

        if end_time is None:
            return events

        padded_end_time = end_time + end_padding
        filtered_events = [event for event in events if event.timestamp <= padded_end_time]
        if not filtered_events and events:
            # We have sync data but it's after the requested end time.
            # Return the first event we have, as the best match for end_time.
            return [events[0]]

        # Return times at or before the requested end_time.
        return filtered_events

    def offset_from_closest_keys(
        self,
        reference_events: list[SyncEvent],
        reader_events: list[SyncEvent]
    ) -> float:
        """Choose a pair of sync events that are close together in time.

        This pairs up sync events based on how close their keys are to each other
        and computes a clock offset from the pair with the closest keys.

        In general, we could compare all m X n pairs of keys from the given reference_events X reader_events.
        This seems excessive, though.  Instead this considers m + n pairings:
            - the last reference event vs each reader event
            - the last reader event vs each reference event

        This pairing strategy should be robust in case reference_events and reader_events contain different
        numbers of events, or have missing events somewhere in the middle.
        """

        if not reference_events or not reader_events:
            return 0.0

        # Which reference event has the closest key to the last reader event?
        reader_last = reader_events[-1]
        reference_closest = min(reference_events, key=lambda event: abs(reader_last.key - event.key))

        # Which reader event has the closest key to the last reference event?
        reference_last = reference_events[-1]
        reader_closest = min(reader_events, key=lambda event: abs(event.key - reference_last.key))

        # Of those two candidate pairings, which is the closest?
        reader_last_distance = abs(reader_last.key - reference_closest.key)
        reference_last_distance = abs(reader_closest.key - reference_last.key)
        if reader_last_distance < reference_last_distance:
            logging.info(f"offset {reader_last.timestamp} - {reference_closest.timestamp} = {reader_last.timestamp - reference_closest.timestamp}")
            return reader_last.timestamp - reference_closest.timestamp
        else:
            logging.info(f"offset {reader_closest.timestamp} - {reference_last.timestamp} = {reader_closest.timestamp - reference_last.timestamp}")
            return reader_closest.timestamp - reference_last.timestamp

    def offset_from_max_keys(
        self,
        reference_events: list[SyncEvent],
        reader_events: list[SyncEvent]
    ) -> float:
        """Compute a clock offset from the pair of sync events with the greatest key from each reader."""

        if not reference_events or not reader_events:
            return 0.0

        # Compare events by value at index 1, ie key.
        reference_max_by_key = max(reference_events, key=itemgetter(1))
        reader_max_by_key = max(reader_events, key=itemgetter(1))
        return reader_max_by_key.timestamp - reference_max_by_key.timestamp

    def offset_from_last_equal_keys(
        self,
        reference_events: list[SyncEvent],
        reader_events: list[SyncEvent]
    ) -> float:
        """Compute a clock offset from the last pair of sync events that share the same key."""

        if not reference_events or not reader_events:
            return 0.0

        # Walk the lists backwards, stopping at the first key match.
        # In the worst case with no match this will do m X n comparisons, which is lame.
        # In practice it ought to find a match near the array ends and short-circuit well before that.
        for reference_event in reversed(reference_events):
            for reader_event in reversed(reader_events):
                if reference_event.key == reader_event.key:
                    return reader_event.timestamp - reference_event.timestamp

        # We compared all the events and never found matching keys!
        return 0.0

    def compute_offset(
        self,
        reader_name: str,
        pairing_strategy: str,
        reference_end_time: float = None,
        reader_end_time: float = None,
        reader_pairing_padding: float = 0.0
    ) -> float:
        """Estimate clock drift between the named reader and the reference, based on events marked for each reader."""
        logging.info(f"{reader_name} offset up to {reference_end_time} AKA {reader_end_time}")
        reference_events = self.find_events(self.reference_reader_name, reference_end_time)
        reader_events = self.find_events(reader_name, reader_end_time, reader_pairing_padding)
        if pairing_strategy == "closest":
            return self.offset_from_closest_keys(reference_events, reader_events)
        elif pairing_strategy == "max":
            return self.offset_from_max_keys(reference_events, reader_events)
        elif pairing_strategy == "last_equal":
            return self.offset_from_last_equal_keys(reference_events, reader_events)
        else:  # pragma: no cover
            logging.error(f'Unknown sync event pairing strategy <{pairing_strategy}>, defaulting to "closest".')
            return self.offset_from_closest_keys(reference_events, reader_events)
