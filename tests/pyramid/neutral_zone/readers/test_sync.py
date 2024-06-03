from pyramid.neutral_zone.readers.sync import ReaderSyncConfig, ReaderSyncRegistry


def test_reader_sync_config_event_callbacks():
    # Default to no event filter -- take all events
    default_config = ReaderSyncConfig()
    assert default_config.filter_event(1.0, [1, 2, 3]) == True
    assert default_config.filter_event(2.0, [3, 4, 5]) == True

    # Default to given default as sync event timestamp.
    assert default_config.sync_timestamp(1.0, [1, 2, 3], 10.0) == 10.0
    assert default_config.sync_timestamp(2.0, [3, 4, 5], 20.0) == 20.0

    # Default to given default as sync event key.
    assert default_config.sync_key(1.0, [1, 2, 3], 111) == 111
    assert default_config.sync_key(2.0, [3, 4, 5], 222) == 222

    # Event filter has access to timestamp and value.
    filter_config = ReaderSyncConfig(filter="timestamp > 0 and value > 0")
    assert filter_config.filter_event(-1, -1) == False
    assert filter_config.filter_event(-1, 1) == False
    assert filter_config.filter_event(1, -1) == False
    assert filter_config.filter_event(1, 1) == True

    # Timestamps callback has access to timestamp and value.
    timestamps_config = ReaderSyncConfig(timestamps="int(timestamp) + value[0] / 1000")
    assert timestamps_config.sync_timestamp(1.1, [234, 567], 1.0) == 1 + 234 / 1000
    assert timestamps_config.sync_timestamp(2.2, [345, 678], 2.0) == 2 + 345 / 1000

    # Keys callback has access to timestamp and value.
    keys_config = ReaderSyncConfig(keys="value[0] if timestamp < 0 else value[1]")
    assert keys_config.sync_key(-5.5, [234, 567], 1.0) == 234
    assert keys_config.sync_key(+5.5, [345, 678], 2.0) == 678


def test_sync_registry_find_events():
    registry = ReaderSyncRegistry("ref")

    # It's okay to ask for sync events before any have been reported.
    assert registry.find_events("ref") == []

    registry.record_event("ref", 1.0)
    registry.record_event("ref", 2.0)
    registry.record_event("ref", 3.0)
    registry.record_event("ref", 4.0)

    # With no end time, return all events for the given reader.
    assert registry.find_events("ref", end_time=None) == [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (4.0, 4.0)]

    # Return events at or before the given end time.
    assert registry.find_events("ref", end_time=3.0) == [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]

    # Return at least the first event, if we have it, event if this has timestamp after the given end time.
    assert registry.find_events("ref", end_time=-100) == [(1.0, 1.0)]


def test_sync_registry_offset_for_closest_time():
    # This test steps through a use case where we pair up sync events based on closest timestamp values.
    # For example, the readers might both start at the same time zero, but drift slowly over time.
    # Or, the readers might both add a sync event key that's the "wall time" when events occurred in real time.
    # This relies on event keys being complarable between readers.
    # It should be robust in case either reader is missing events or has extra events.

    # In these examples, the correct clock offset should be close to zero, but is sometimes greater than one.

    registry = ReaderSyncRegistry("ref")

    # With no data yet, offset should default to 0.
    assert registry.compute_offset("ref", "closest") == 0
    assert registry.compute_offset("foo", "closest") == 0

    # With only a reference event, offset should still evaluate to 0.
    #  - ref vs ref offset is zero by definition.
    #  - ref vs foo offset is still undefined and defaults to 0.
    registry.record_event("ref", 1.0)
    assert registry.compute_offset("ref", "closest") == 0
    assert registry.compute_offset("foo", "closest") == 0

    # With both reference and other events, offset is now meaningful.
    #   ref:    |
    #   foo:     |
    #   bar:   |
    #          ^ ^ relevant events for offset estimation
    registry.record_event("foo", 1.11)
    registry.record_event("bar", 0.91)
    assert registry.compute_offset("ref", "closest") == 0
    assert registry.compute_offset("foo", "closest") == 1.11 - 1.0
    assert registry.compute_offset("bar", "closest") == 0.91 - 1.0

    # If bar misses a sync event use an older, more reasonable offset estimate.
    #   ref:    |    |
    #   foo:     |    |
    #   bar:   |    x
    #          ^bar   ^foo
    registry.record_event("ref", 2.0)
    registry.record_event("foo", 2.12)
    assert registry.compute_offset("ref", "closest") == 0
    assert registry.compute_offset("foo", "closest") == 2.12 - 2.0
    assert registry.compute_offset("bar", "closest") == 0.91 - 1.0

    # Let bar recover after recording the next sync event.
    #   ref:    |    |    |
    #   foo:     |    |    |
    #   bar:   |    x    |
    #                    ^ ^
    registry.record_event("ref", 3.0)
    registry.record_event("foo", 3.13)
    registry.record_event("bar", 2.93)
    assert registry.compute_offset("ref", "closest") == 0
    assert registry.compute_offset("foo", "closest") == 3.13 - 3.0
    assert registry.compute_offset("bar", "closest") == 2.93 - 3.0

    # If ref misses a sync event use older, more reasonable offset estimates for both foo and bar.
    #   ref:    |    |    |    x
    #   foo:     |    |    |    |
    #   bar:   |    x    |    |
    #                    ^ ^
    registry.record_event("foo", 4.14)
    registry.record_event("bar", 3.94)
    assert registry.compute_offset("ref", "closest") == 0
    assert registry.compute_offset("foo", "closest") == 3.13 - 3.0
    assert registry.compute_offset("bar", "closest") == 2.93 - 3.0

    # Let ref recover after recording the next sync event.
    #   ref:    |    |    |    x    |
    #   foo:     |    |    |    |    |
    #   bar:   |    x    |    |    |
    #                              ^ ^
    registry.record_event("ref", 5.0)
    registry.record_event("foo", 5.15)
    registry.record_event("bar", 4.95)
    assert registry.compute_offset("ref", "closest") == 0
    assert registry.compute_offset("foo", "closest") == 5.15 - 5.0
    assert registry.compute_offset("bar", "closest") == 4.95 - 5.0

    # Accept end times to keep the offset estimate contemporary to a time range of interest (eg a trial).
    # This is like going back in time to a prevous example, above.
    assert registry.compute_offset("ref", "closest", reference_end_time=3.5, reader_end_time=3.5) == 0
    assert registry.compute_offset("foo", "closest", reference_end_time=3.5, reader_end_time=3.5) == 3.13 - 3.0
    assert registry.compute_offset("bar", "closest", reference_end_time=3.5, reader_end_time=3.5) == 2.93 - 3.0

    # On eg. trial zero, the trial end time might be before the first sync event arrives,
    # perhaps if trial one is the first trial with complete data.
    # In this case, use the earliest sync data available.
    # This is like going back in time to the very first example, above.
    assert registry.compute_offset("ref", "closest", reference_end_time=-1.0, reader_end_time=-1.0) == 0
    assert registry.compute_offset("foo", "closest", reference_end_time=-1.0, reader_end_time=-1.0) == 1.11 - 1.0
    assert registry.compute_offset("bar", "closest", reference_end_time=-1.0, reader_end_time=-1.0) == 0.91 - 1.0


def test_sync_registry_offset_for_max_key():
    # This test steps through a use case where we always pair up the max/last sync event between readers.
    # For example, event keys might just be their array indexes, and we take the max index available.
    # This doesn't assume timestamps between readers are comparable -- they can have arbitrary initial offsets.
    # This does assume that sync events reliably occur in pairs, and reliably fall within the same trial.

    # In these examples, the correct clock offset is 100.0, but is sometimes off by one.

    registry = ReaderSyncRegistry("ref")

    # With no data yet, offset should default to 0.
    assert registry.compute_offset("ref", "max") == 0
    assert registry.compute_offset("foo", "max") == 0

    # With only a ref event, offset should still evaluate to 0.
    #  - ref vs ref offset is zero by definition.
    #  - ref vs foo offset is still undefined and defaults to 0.
    registry.record_event("ref", 0.0, 0)
    assert registry.compute_offset("ref", "max") == 0
    assert registry.compute_offset("foo", "max") == 0

    # With both ref and foo events, offset is now meaningful.
    #   ref:   0.0
    #   foo: 100.0
    #            ^ latest at index 0
    registry.record_event("foo", 100.0, 0)
    assert registry.compute_offset("ref", "max") == 0
    assert registry.compute_offset("foo", "max") == 100.0 - 0.0

    # As more sync events arrive, keep taking the max key.
    #   ref:   0.0    1.0     2.0
    #   foo: 100.0  101.0   102.0
    #                           ^ latest at index 2
    registry.record_event("ref", 1.0, 1)
    registry.record_event("ref", 2.0, 2)
    registry.record_event("foo", 101.0, 1)
    registry.record_event("foo", 102.0, 2)
    assert registry.compute_offset("ref", "max") == 0
    assert registry.compute_offset("foo", "max") == 102.0 - 2.0

    # If the ref goes ahead by one, the pairings will be off by one.
    # This isn't great, but it's expected behavior for this configuration.
    #   ref:   0.0    1.0     2.0     3.0
    #   foo: 100.0  101.0   102.0
    #                           ^       ^ latest at indices 2 and 3
    registry.record_event("ref", 3.0, 3)
    assert registry.compute_offset("ref", "max") == 0
    assert registry.compute_offset("foo", "max") == 102.0 - 3.0

    # Likewise, the reader might go ahead by one, and the pairings will be off by one.
    # This is still non-great, expected behavior for this configuration.
    #   ref:   0.0    1.0     2.0     3.0
    #   foo: 100.0  101.0   102.0   103.0   104.0
    #                                   ^       ^ latest at indices 3 and 4
    registry.record_event("foo", 103.0, 3)
    registry.record_event("foo", 104.0, 4)
    assert registry.compute_offset("ref", "max") == 0
    assert registry.compute_offset("foo", "max") == 104.0 - 3.0

    # Once the events get back in tandem, the offsets will recover.
    #   ref:   0.0    1.0     2.0     3.0     4.0
    #   foo: 100.0  101.0   102.0   103.0   104.0
    #                                           ^ latest index 4
    registry.record_event("ref", 4.0, 4)
    assert registry.compute_offset("ref", "max") == 0
    assert registry.compute_offset("foo", "max") == 104.0 - 4.0

    # After the fact, we could go back and look at the offset for index 3, now recovered.
    assert registry.compute_offset("ref", "max", reference_end_time=3.5, reader_end_time=3.5) == 0
    assert registry.compute_offset("foo", "max", reference_end_time=3.5, reader_end_time=103.5) == 103.0 - 3.0

    # If we ask for a time range before the first events, we'll use the first events.
    assert registry.compute_offset("ref", "max", reference_end_time=-1.0, reader_end_time=-1.0) == 0
    assert registry.compute_offset("foo", "max", reference_end_time=-1.0, reader_end_time=-1.0) == 100.0 - 0.0


def test_sync_registry_offset_for_tandem_indices():
    # This test steps through a use case where we pair up sync events in tandem based on equal array indices.
    # So here the event keys here are equal to the event array indices, and we zip up event pairs in tandem.
    # This doesn't assume timestamps between readers are comparable -- they can have arbitrary initial offsets.
    # This does assume that sync events reliably occur in pairs, and neither reader has extra events at the beginning.
    # It should be robust in case one reader or the other has extra events at the end.

    # In these examples, the correct clock offset is 100.0, but is sometimes off by one.

    registry = ReaderSyncRegistry("ref")

    # With no data yet, offset should default to 0.
    assert registry.compute_offset("ref", "last_equal") == 0
    assert registry.compute_offset("foo", "last_equal") == 0

    # With only a ref event, offset should still evaluate to 0.
    #  - ref vs ref offset is zero by definition.
    #  - ref vs foo offset is still undefined and defaults to 0.
    registry.record_event("ref", 0.0, 0)
    assert registry.compute_offset("ref", "last_equal") == 0
    assert registry.compute_offset("foo", "last_equal") == 0

    # If one reader starts with extra events that the other never saw, paring will go wrong.
    # This isn't great, but it is expected behavior for this configuration.
    #   ref:   0.0    1.0
    #   foo:        101.0
    #            ^      ^ last equal index is 0
    registry.record_event("ref", 1.0, 1)
    registry.record_event("foo", 101.0, 0)
    assert registry.compute_offset("ref", "last_equal") == 0
    assert registry.compute_offset("foo", "last_equal") == 101.0 - 0.0

    # As more sync events arrive in tandem, pairing will remain wrong.
    #   ref:   0.0    1.0     2.0
    #   foo:        101.0   102.0
    #                   ^       ^ last equal index is 1
    registry.record_event("ref", 2.0, 2)
    registry.record_event("foo", 102.0, 1)
    assert registry.compute_offset("ref", "last_equal") == 0
    assert registry.compute_offset("foo", "last_equal") == 102.0 - 1.0

    # To recover, both readers need to have the same number of sync events.
    # In this example that might mean repeating removing a ref event or repeating a foo event.
    #   ref:   0.0    1.0     2.0
    #   foo:        101.0   102.0   102.0
    #                           ^       ^ last equal index is 2
    registry.record_event("foo", 102.0, 2)
    assert registry.compute_offset("ref", "last_equal") == 0
    assert registry.compute_offset("foo", "last_equal") == 102.0 - 2.0

    # As events continue to come in we'll match equal keys and prefer the latest match.
    #   ref:   0.0    1.0     2.0     3.0
    #   foo:        101.0   102.0   102.0   103.0
    #                                   ^       ^ last equal index is 3
    registry.record_event("ref", 3.0, 3)
    registry.record_event("foo", 103.0, 3)
    assert registry.compute_offset("ref", "last_equal") == 0
    assert registry.compute_offset("foo", "last_equal") == 103.0 - 3.0

    # In case one reader gets ahead by one event, we'll stick with the latest index in common.
    #   ref:   0.0    1.0     2.0     3.0
    #   foo:        101.0   102.0   102.0   103.0   104.0
    #                                   ^       ^ last equal index is still 3
    registry.record_event("foo", 104.0, 4)
    assert registry.compute_offset("ref", "last_equal") == 0
    assert registry.compute_offset("foo", "last_equal") == 103.0 - 3.0

    # We can use end time to revisit a previous example.
    # For this strategy, looking back lets us recover the correct offset at index 2, since time and index are independent.
    assert registry.compute_offset("ref", "last_equal", reference_end_time=2.5, reader_end_time=2.5) == 0
    assert registry.compute_offset("foo", "last_equal", reference_end_time=2.5, reader_end_time=102.5) == 102.0 - 2.0

    # But the situation around index 1 is still messed up.
    assert registry.compute_offset("ref", "last_equal", reference_end_time=1.5, reader_end_time=1.5) == 0
    assert registry.compute_offset("foo", "last_equal", reference_end_time=1.5, reader_end_time=101.5) == 101.0 - 0.0

    # If we ask for a time range before the first events, we'll use the first events.
    assert registry.compute_offset("ref", "last_equal", reference_end_time=-1.0, reader_end_time=-1.0) == 0
    assert registry.compute_offset("foo", "last_equal", reference_end_time=-1.0, reader_end_time=-1.0) == 101.0 - 0.0


def test_sync_registry_offset_for_custom_keys():
    # This test steps through a use case where we pair up sync events based on arbitrary, equal keys.
    # So here the event keys here are contrived to be unique.
    # This is in a sense the strictest and most powerful way to match up keys.
    # It doesn't assume timestamps between readers are comparable -- they can have arbitrary initial offsets.
    # It should be robust to readers having extra or missing events and the beginning or at the end.
    # But it relies data sets having this extra, unique piece of data to include with each sync event.

    # In these examples, the correct clock offset is 100.0, but is sometimes off by one.

    registry = ReaderSyncRegistry("ref")

    # With no data yet, offset should default to 0.
    assert registry.compute_offset("ref", "last_equal") == 0
    assert registry.compute_offset("foo", "last_equal") == 0

    # With only a ref event, offset should still evaluate to 0.
    #  - ref vs ref offset is zero by definition.
    #  - ref vs foo offset is still undefined and defaults to 0.
    registry.record_event("ref", 0.0, 2000)
    assert registry.compute_offset("ref", "last_equal") == 0
    assert registry.compute_offset("foo", "last_equal") == 0

    # It's okay for either reader to start with a bunch of extra events that the other reader never sees.
    # Non-matching garbage will just be ignored.
    registry.record_event("ref", 0.0, 2001)
    registry.record_event("ref", 0.1, 2002)
    registry.record_event("ref", 0.2, 2003)
    registry.record_event("ref", 0.3, 2004)
    registry.record_event("foo", 100.0, 3004)
    registry.record_event("foo", 100.1, 3005)
    assert registry.compute_offset("ref", "last_equal") == 0
    assert registry.compute_offset("foo", "last_equal") == 0

    # Once a match arrives, it will be used to compute an offset.
    registry.record_event("ref", 0.0, 3004)
    assert registry.compute_offset("ref", "last_equal") == 0
    assert registry.compute_offset("foo", "last_equal") == 100.0 - 0.0

    # As later matches arrive, they will be preferred over earlier matches.
    registry.record_event("ref", 1.0, 3005)
    registry.record_event("foo", 101.0, 3005)
    assert registry.compute_offset("ref", "last_equal") == 0
    assert registry.compute_offset("foo", "last_equal") == 101.0 - 1.0

    # If either reader goes ahead, this will be ignored and a previous match will still be used.
    registry.record_event("foo", 102.0, 3006)
    assert registry.compute_offset("ref", "last_equal") == 0
    assert registry.compute_offset("foo", "last_equal") == 101.0 - 1.0

    # When the other reader catches up, the new match will be used.
    registry.record_event("ref", 2.0, 3006)
    assert registry.compute_offset("ref", "last_equal") == 0
    assert registry.compute_offset("foo", "last_equal") == 102.0 - 2.0

    # We can give a limit to go back in time to a previous example.
    assert registry.compute_offset("ref", "last_equal", reference_end_time=1.5, reader_end_time=1.5) == 0
    assert registry.compute_offset("foo", "last_equal", reference_end_time=1.5, reader_end_time=101.5) == 101.0 - 1.0

    # If we try to go back in time before the first sync events, we'll use the first sync events.
    # In this case, the first events are non-matching garbage that we ignore.
    assert registry.compute_offset("ref", "last_equal", reference_end_time=-1.0, reader_end_time=-1.0) == 0
    assert registry.compute_offset("foo", "last_equal", reference_end_time=-1.0, reader_end_time=-1.0) == 0
