import logging
from dataclasses import dataclass
from typing import NamedTuple


@dataclass
class ReaderSyncConfig():
    """Specify configuration for how a reader should find sync events and align to a reference clock."""

    is_reference: str = False
    """Whether the reader represents the canonical, reference clock to which others readers will be aligned."""

    buffer_name: str = None
    """The name of the reader result or extra buffer that will contain sync events."""

    event_value: int | float = None
    """The event value to look for to identify sync events within the named event buffer."""

    event_value_index: int = 0
    """The event value index to use when looking for event_value within the named event buffer."""

    reader_name: str = None
    """The name of the reader to act as when aligning data within trials.

    Usually reader_name would be the name of the reader itself.
    Or it may be the name of a different reader so that one reader may reuse sync info from another.
    """

    init_event_count: int = 1
    """How many initial sync events Pyramid should to try to read for this reader, before delimiting trials."""

    init_max_reads: int = 10
    """How many times Pyramid should keep trying to read when waiting for initial sync events."""

    pairing_strategy: str = "closest"
    """How to pair up event keys between readers: "closest", "max", or "last equal"."""


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

    # TODO: accept keys selected by caller.
    def record_event(self, reader_name: str, event_time: float) -> None:
        """Record a sync event as seen by the named reader."""
        events = self.reader_events.get(reader_name, [])
        events.append(SyncEvent(timestamp=event_time, key=event_time))
        self.reader_events[reader_name] = events

    def find_events(self, reader_name: str, end_time: float = None) -> list[float]:
        """Find sync events for the given reader, at or before the given end time.

        If end_time is before the first sync event, return the first sync event.
        """
        events = self.reader_events.get(reader_name, [])
        if not events:
            return []

        if end_time is None:
            return events

        filtered_events = [event for event in events if event.timestamp <= end_time]
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

        # How far is each reference key from the last reader key?
        reader_last = reader_events[-1]
        distances_from_reader_last = [reader_last.key - reference_event.key for reference_event in reference_events]
        min_distance_from_reader_last = min(distances_from_reader_last, key=abs)

        # How far is each reader key from the last reference key?
        reference_last = reference_events[-1]
        distances_from_reference_last = [reader_event.key - reference_last.key for reader_event in reader_events]
        min_distance_from_reference_last = min(distances_from_reference_last, key=abs)

        # Compute the timestamp offset at the closest pair of keys.
        if abs(min_distance_from_reader_last) < abs(min_distance_from_reference_last):
            reference_event = reference_events[distances_from_reader_last.index(min_distance_from_reader_last)]
            return reader_last.timestamp - reference_event.timestamp
        else:
            reader_event = reader_events[distances_from_reference_last.index(min_distance_from_reference_last)]
            return reader_event.timestamp - reference_last.timestamp

    def compute_offset(
        self,
        reader_name: str,
        pairing_strategy: str,
        reference_end_time: float = None,
        reader_end_time: float = None
    ) -> float:
        """Estimate clock drift between the named reader and the reference, based on events marked for each reader."""
        reference_events = self.find_events(self.reference_reader_name, reference_end_time)
        reader_events = self.find_events(reader_name, reader_end_time)
        if pairing_strategy == "closest":
            return self.offset_from_closest_keys(reference_events, reader_events)
        else:  # pragma: no cover
            logging.error(f'Unknown sync event pairing strategy <{pairing_strategy}>, defaulting to "closest".')
            return self.offset_from_closest_keys(reference_events, reader_events)
