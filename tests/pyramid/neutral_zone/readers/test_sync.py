from pyramid.neutral_zone.readers.sync import ReaderSyncRegistry


def test_reader_sync_registry():
    sync_registry = ReaderSyncRegistry("ref")

    # With no data yet, drift should default to 0.
    assert sync_registry.get_drift("ref") == 0
    assert sync_registry.get_drift("foo") == 0

    # With only a reference event, drift should still evaluate to 0.
    #  - ref vs ref drift is zero by definition.
    #  - ref vs foo drift is still undefined and defaults to 0.
    sync_registry.record_event("ref", 1.0)
    assert sync_registry.get_drift("ref") == 0
    assert sync_registry.get_drift("foo") == 0

    # With both reference and other events, drift is now meaningful.
    #   ref:    |
    #   foo:     |
    #   bar:   |
    #          ^ ^ relevant events for drift estimation
    sync_registry.record_event("foo", 1.11)
    sync_registry.record_event("bar", 0.91)
    assert sync_registry.get_drift("ref") == 0
    assert sync_registry.get_drift("foo") == 1.11 - 1.0
    assert sync_registry.get_drift("bar") == 0.91 - 1.0

    # If bar misses a sync event use an older, more reasonable drift estimate.
    #   ref:    |    |
    #   foo:     |    |
    #   bar:   |    x
    #          ^bar   ^foo
    sync_registry.record_event("ref", 2.0)
    sync_registry.record_event("foo", 2.12)
    assert sync_registry.get_drift("ref") == 0
    assert sync_registry.get_drift("foo") == 2.12 - 2.0
    assert sync_registry.get_drift("bar") == 0.91 - 1.0

    # Let bar recover after recording the next sync event.
    #   ref:    |    |    |
    #   foo:     |    |    |
    #   bar:   |    x    |
    #                    ^ ^
    sync_registry.record_event("ref", 3.0)
    sync_registry.record_event("foo", 3.13)
    sync_registry.record_event("bar", 2.93)
    assert sync_registry.get_drift("ref") == 0
    assert sync_registry.get_drift("foo") == 3.13 - 3.0
    assert sync_registry.get_drift("bar") == 2.93 - 3.0

    # If ref misses a sync event use older, more reasonable drift estimates for both foo and bar.
    #   ref:    |    |    |    x
    #   foo:     |    |    |    |
    #   bar:   |    x    |    |
    #                    ^ ^
    sync_registry.record_event("foo", 4.14)
    sync_registry.record_event("bar", 3.94)
    assert sync_registry.get_drift("ref") == 0
    assert sync_registry.get_drift("foo") == 3.13 - 3.0
    assert sync_registry.get_drift("bar") == 2.93 - 3.0

    # Let ref recover after recording the next sync event.
    #   ref:    |    |    |    x    |
    #   foo:     |    |    |    |    |
    #   bar:   |    x    |    |    |
    #                              ^ ^
    sync_registry.record_event("ref", 5.0)
    sync_registry.record_event("foo", 5.15)
    sync_registry.record_event("bar", 4.95)
    assert sync_registry.get_drift("ref") == 0
    assert sync_registry.get_drift("foo") == 5.15 - 5.0
    assert sync_registry.get_drift("bar") == 4.95 - 5.0

    # Accept end times to keep the drift estimate contemporary to a time range of interest (eg a trial).
    # This is like going back in time to a prevous example, above.
    end_time = 3.5
    assert sync_registry.get_drift("ref", reference_end_time=end_time, reader_end_time=end_time) == 0
    assert sync_registry.get_drift("foo", reference_end_time=end_time, reader_end_time=end_time) == 3.13 - 3.0
    assert sync_registry.get_drift("bar", reference_end_time=end_time, reader_end_time=end_time) == 2.93 - 3.0

    # On eg. trial zero, the trial end time might be before the first sync event arrives,
    # perhaps if trial one is the first trial with complete data.
    # In this case, use the earliest sync data available.
    # This is like going back in time to the very first example, above.
    end_time = -1.0
    assert sync_registry.get_drift("ref", reference_end_time=end_time, reader_end_time=end_time) == 0
    assert sync_registry.get_drift("foo", reference_end_time=end_time, reader_end_time=end_time) == 1.11 - 1.0
    assert sync_registry.get_drift("bar", reference_end_time=end_time, reader_end_time=end_time) == 0.91 - 1.0
