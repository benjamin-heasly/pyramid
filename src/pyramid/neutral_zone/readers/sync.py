from dataclasses import dataclass

@dataclass
class ReaderSyncConfig():
    """Specify configuration for how a reader should find sync events and correct for clock drift."""

    is_reference: str = False
    """Whether the reader represents the canonical, reference clock to which others readers will be aligned."""

    buffer_name: str = None
    """The name of the reader result or extra buffer that will contain clock sync events."""

    event_value: int | float = None
    """The value of sync events to look for, within the named event buffer."""

    event_value_index: int = 0
    """The numeric event value index to use within the named event buffer."""

    reader_name: str = None
    """The name of the reader to act as when aligning data within trials.

    Usually reader_name would be the name of the same reader that this config applies to.
    Or it may be the name of a different reader so that one reader may reuse sync info from another.
    For example, a Phy spike reader might want to use sync info from an upstream data source like Plexon or OpenEphys.
    """

    init_event_count: int = 1
    """How many initial sync events Pyramid to try to read for this reader, before deliminting trials."""

    init_max_reads: int = 10
    """How many times Pyramid should keep trying to read when waiting for initial sync events."""


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
        self.event_times = {}

    def __eq__(self, other: object) -> bool:
        """Compare registry field-wise, to support use of this class in tests."""
        if isinstance(other, self.__class__):
            return (
                self.reference_reader_name == other.reference_reader_name
                and self.event_times == other.event_times
            )
        else:  # pragma: no cover
            return False

    def event_count(self, reader_name: str) -> int:
        times = self.event_times.get(reader_name, [])
        return len(times)

    def record_event(self, reader_name: str, event_time: float) -> None:
        """Record a sync event as seen by the named reader."""
        reader_event_times = self.event_times.get(reader_name, [])
        reader_event_times.append(event_time)
        self.event_times[reader_name] = reader_event_times

    def events(self, reader_name: str, end_time: float) -> list[float]:
        """Find sync events for the given reader, at or before the given end time.

        In case end_time is before the first sync event, return the first sync event.
        """
        event_times = self.event_times.get(reader_name, [])
        if not event_times:
            return []

        if end_time is None:
            return event_times

        filtered_event_times = [time for time in event_times if time <= end_time]
        if not filtered_event_times and event_times:
            # We have sync data but it's after the requested end time.
            # Return the first event we have, as the best match for end_time.
            return [event_times[0]]

        # Return times at or before the requested end_time.
        return filtered_event_times

    def get_drift(
        self,
        reader_name: str,
        reference_end_time: float = None,
        reader_end_time: float = None
    ) -> float:
        """Estimate clock drift between the named reader and the reference, based on events marked for each reader."""
        reference_event_times = self.events(self.reference_reader_name, reference_end_time)
        if not reference_event_times:
            return 0.0

        reader_event_times = self.events(reader_name, reader_end_time)
        if not reader_event_times:
            return 0.0

        reader_last = reader_event_times[-1]
        reader_offsets = [reader_last - ref_time for ref_time in reference_event_times]
        drift_from_reader = min(reader_offsets, key=abs)

        reference_last = reference_event_times[-1]
        reference_offsets = [reader_time - reference_last for reader_time in reader_event_times]
        drift_from_reference = min(reference_offsets, key=abs)

        return min(drift_from_reader, drift_from_reference, key=abs)
