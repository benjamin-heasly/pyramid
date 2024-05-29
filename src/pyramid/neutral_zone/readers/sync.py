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


class SyncEvent(NamedTuple):
    """Record a sync event as a pair of timestamp (used for alignment) and key (used to pair up corresponding events)."""

    timestamp: float
    """When a real-world sync event occurred, according to a particular reader and its clock."""

    key: float
    """Key used to match up sync events that represent the same real-world event, as seen by different readers."""


class ReaderSyncRegistry():
    """Keep track of sync events as seen by different readers, and clock drift compared to a referencce reader.

        When comparing sync event times between readers the registry will use the latest sync information recorded so far.
        It will also try to line up times in pairs so that both times correspond to the same real-world sync event.

            reference: |   |   |   |   |   |   |   |
            other:     |   |   |   |   |  |   |   |
                                                  ^^ latest pair seen so far, seems like a reasonable drift estimate

        The registry will form the pairs based on difference in time, as opposed just lining up array indexes.
        This should make the drift estimates robust in case readers record different numbers of sync events.
        For example, one reader might suddenly stop recording sync altogether.

            reference: |   |   |   |   |   |   |   |
            other:     |   |   |
                                  ^ oops, sync from other dropped around here here!

        In this case, pairing up the latest events by array index would lead to "drift" estimates that grow
        in real time, and don't really reflect the underlying clock rates.

        So instead, the registry will consider the latest sync event time from each reader, and pair it with the closest
        event time from the other reader.  From these two "closest" pairs, it will choose the pair with the smallest
        time difference.
            reference: |   |   |   |   |   |   |   |
            other:     |   |   |                   ^ "closest" from reference is huge and growing in real time!
                               ^ "closest" from other is older, but still looks reasonable

        All this assumes that clock drift is small compared to the interval between real-world sync events.  If that's
        true then looking for small differences between readers is a good way to discover which times go together.
    """

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

    def get_drift(
        self,
        reader_name: str,
        reference_end_time: float = None,
        reader_end_time: float = None
    ) -> float:
        """Estimate clock drift between the named reader and the reference, based on events marked for each reader."""
        reference_events = self.find_events(self.reference_reader_name, reference_end_time)
        if not reference_events:
            return 0.0

        reader_events = self.find_events(reader_name, reader_end_time)
        if not reader_events:
            return 0.0

        reader_last = reader_events[-1]
        reader_offsets = [reader_last.key - reference_event.key for reference_event in reference_events]
        drift_from_reader = min(reader_offsets, key=abs)

        reference_last = reference_events[-1]
        reference_offsets = [reader_event.key - reference_last.key for reader_event in reader_events]
        drift_from_reference = min(reference_offsets, key=abs)

        return min(drift_from_reader, drift_from_reference, key=abs)
