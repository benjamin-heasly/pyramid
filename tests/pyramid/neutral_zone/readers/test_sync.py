from pyramid.neutral_zone.readers.sync import ReaderSyncRegistry


def test_sync_registry_find_events():
    sync_registry = ReaderSyncRegistry("ref")

    # It's okay to ask for sync events before any have been reported.
    assert sync_registry.find_events("ref") == []

    sync_registry.record_event("ref", 1.0)
    sync_registry.record_event("ref", 2.0)
    sync_registry.record_event("ref", 3.0)
    sync_registry.record_event("ref", 4.0)

    # With no end time, return all events for the given reader.
    assert sync_registry.find_events("ref", end_time=None) == [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (4.0, 4.0)]

    # Return events at or before the given end time.
    assert sync_registry.find_events("ref", end_time=3.0) == [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]

    # Return at least the first event, if we have it, event if this has timestamp after the given end time.
    assert sync_registry.find_events("ref", end_time=-100) == [(1.0, 1.0)]


def test_sync_registry_offset_for_closest_wall_time():
    # This test steps through a use case where readers pair up sync events based on closest values.
    # For example, the readers might both start at the same time zero, but drift slowly over time.
    # Or, the readers might both add a sync event key that's the "wall time" when events occurred in real time.
    # This relies on event keys being complarable between readers,
    # but should be robust in case either reader is missing events or has extra events.

    sync_registry = ReaderSyncRegistry("ref")

    # With no data yet, offset should default to 0.
    assert sync_registry.compute_offset("ref", "closest") == 0
    assert sync_registry.compute_offset("foo", "closest") == 0

    # With only a reference event, offset should still evaluate to 0.
    #  - ref vs ref offset is zero by definition.
    #  - ref vs foo offset is still undefined and defaults to 0.
    sync_registry.record_event("ref", 1.0)
    assert sync_registry.compute_offset("ref", "closest") == 0
    assert sync_registry.compute_offset("foo", "closest") == 0

    # With both reference and other events, offset is now meaningful.
    #   ref:    |
    #   foo:     |
    #   bar:   |
    #          ^ ^ relevant events for offset estimation
    sync_registry.record_event("foo", 1.11)
    sync_registry.record_event("bar", 0.91)
    assert sync_registry.compute_offset("ref", "closest") == 0
    assert sync_registry.compute_offset("foo", "closest") == 1.11 - 1.0
    assert sync_registry.compute_offset("bar", "closest") == 0.91 - 1.0

    # If bar misses a sync event use an older, more reasonable offset estimate.
    #   ref:    |    |
    #   foo:     |    |
    #   bar:   |    x
    #          ^bar   ^foo
    sync_registry.record_event("ref", 2.0)
    sync_registry.record_event("foo", 2.12)
    assert sync_registry.compute_offset("ref", "closest") == 0
    assert sync_registry.compute_offset("foo", "closest") == 2.12 - 2.0
    assert sync_registry.compute_offset("bar", "closest") == 0.91 - 1.0

    # Let bar recover after recording the next sync event.
    #   ref:    |    |    |
    #   foo:     |    |    |
    #   bar:   |    x    |
    #                    ^ ^
    sync_registry.record_event("ref", 3.0)
    sync_registry.record_event("foo", 3.13)
    sync_registry.record_event("bar", 2.93)
    assert sync_registry.compute_offset("ref", "closest") == 0
    assert sync_registry.compute_offset("foo", "closest") == 3.13 - 3.0
    assert sync_registry.compute_offset("bar", "closest") == 2.93 - 3.0

    # If ref misses a sync event use older, more reasonable offset estimates for both foo and bar.
    #   ref:    |    |    |    x
    #   foo:     |    |    |    |
    #   bar:   |    x    |    |
    #                    ^ ^
    sync_registry.record_event("foo", 4.14)
    sync_registry.record_event("bar", 3.94)
    assert sync_registry.compute_offset("ref", "closest") == 0
    assert sync_registry.compute_offset("foo", "closest") == 3.13 - 3.0
    assert sync_registry.compute_offset("bar", "closest") == 2.93 - 3.0

    # Let ref recover after recording the next sync event.
    #   ref:    |    |    |    x    |
    #   foo:     |    |    |    |    |
    #   bar:   |    x    |    |    |
    #                              ^ ^
    sync_registry.record_event("ref", 5.0)
    sync_registry.record_event("foo", 5.15)
    sync_registry.record_event("bar", 4.95)
    assert sync_registry.compute_offset("ref", "closest") == 0
    assert sync_registry.compute_offset("foo", "closest") == 5.15 - 5.0
    assert sync_registry.compute_offset("bar", "closest") == 4.95 - 5.0

    # Accept end times to keep the offset estimate contemporary to a time range of interest (eg a trial).
    # This is like going back in time to a prevous example, above.
    assert sync_registry.compute_offset("ref", "closest", reference_end_time=3.5, reader_end_time=3.5) == 0
    assert sync_registry.compute_offset("foo", "closest", reference_end_time=3.5, reader_end_time=3.5) == 3.13 - 3.0
    assert sync_registry.compute_offset("bar", "closest", reference_end_time=3.5, reader_end_time=3.5) == 2.93 - 3.0

    # On eg. trial zero, the trial end time might be before the first sync event arrives,
    # perhaps if trial one is the first trial with complete data.
    # In this case, use the earliest sync data available.
    # This is like going back in time to the very first example, above.
    assert sync_registry.compute_offset("ref", "closest", reference_end_time=-1.0, reader_end_time=-1.0) == 0
    assert sync_registry.compute_offset("foo", "closest", reference_end_time=-1.0, reader_end_time=-1.0) == 1.11 - 1.0
    assert sync_registry.compute_offset("bar", "closest", reference_end_time=-1.0, reader_end_time=-1.0) == 0.91 - 1.0
