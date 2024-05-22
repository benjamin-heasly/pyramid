import numpy as np

from pyramid.model.signals import SignalChunk


def test_signal_chunk_getters():
    sample_count = 100
    raw_data = [[v, 10 + v, 10 * v] for v in range(sample_count)]
    signal_chunk = SignalChunk(
        np.array(raw_data),
        10,
        0,
        ["a", "b", "c"]
    )

    assert signal_chunk.sample_count() == sample_count
    assert signal_chunk.channel_count() == 3

    assert signal_chunk.channel_index("a") == 0
    assert signal_chunk.channel_index("b") == 1
    assert signal_chunk.channel_index("c") == 2

    assert signal_chunk.first() == 0
    assert signal_chunk.first(0) == 0
    assert signal_chunk.first(1) == 10
    assert signal_chunk.first(2) == 0
    assert signal_chunk.last() == 99
    assert signal_chunk.last(0) == 99
    assert signal_chunk.last(1) == 109
    assert signal_chunk.last(2) == 990
    assert np.array_equal(signal_chunk.values(), np.array(range(sample_count)))
    assert np.array_equal(signal_chunk.values(0), np.array(range(sample_count)))
    assert np.array_equal(signal_chunk.values(1), np.array(range(sample_count)) + 10)
    assert np.array_equal(signal_chunk.values(2), np.array(range(sample_count)) * 10)
    assert np.array_equal(signal_chunk.values(start_time=4), np.array(range(40, 100)))
    assert np.array_equal(signal_chunk.values(end_time=6), np.array(range(0, 60)))
    assert np.array_equal(signal_chunk.values(start_time=4, end_time=6), np.array(range(40, 60)))
    assert np.array_equal(signal_chunk.values(start_time=6, end_time=4), np.empty([0,]))

    assert signal_chunk.at(-1) == 0
    assert signal_chunk.at(0) == 0
    assert signal_chunk.at(0, 0) == 0
    assert signal_chunk.at(0, 1) == 10
    assert signal_chunk.at(0, 2) == 0
    assert signal_chunk.at(5) == 50
    assert signal_chunk.at(5, 0) == 50
    assert signal_chunk.at(5, 1) == 60
    assert signal_chunk.at(5, 2) == 500
    assert signal_chunk.at(5.001) == 50
    assert signal_chunk.at(5.1) == 51
    assert signal_chunk.at(9.9) == 99
    assert signal_chunk.at(10) == None

    assert np.array_equal(signal_chunk.times(), np.array(range(sample_count)) / 10)
    assert signal_chunk.start() == 0
    assert signal_chunk.end() == 0 + (sample_count - 1) / 10
    assert np.array_equal(signal_chunk.times(), signal_chunk.times())
    assert np.array_equal(signal_chunk.times(0.0), np.array([0.0]))
    assert np.array_equal(signal_chunk.times(1.0), np.array([0.1]))
    assert np.array_equal(signal_chunk.times(99.0), np.array([9.9]))
    assert np.array_equal(signal_chunk.times(10.0, value_index=1), np.array([0.0]))
    assert np.array_equal(signal_chunk.times(11.0, value_index=1), np.array([0.1]))
    assert np.array_equal(signal_chunk.times(109.0, value_index=1), np.array([9.9]))
    assert np.array_equal(signal_chunk.times(0.0, value_index=2), np.array([0.0]))
    assert np.array_equal(signal_chunk.times(10.0, value_index=2), np.array([0.1]))
    assert np.array_equal(signal_chunk.times(990.0, value_index=2), np.array([9.9]))
    assert signal_chunk.times(-1.0).size == 0
    assert signal_chunk.times(10.42).size == 0
    assert signal_chunk.times(1000).size == 0

    assert np.array_equal(signal_chunk.times(5.0, start_time=0.4), np.array([0.5]))
    assert np.array_equal(signal_chunk.times(5.0, start_time=0.5), np.array([0.5]))
    assert signal_chunk.times(5.0, start_time=0.6).size == 0
    assert signal_chunk.times(5.0, end_time=0.4).size == 0
    assert signal_chunk.times(5.0, end_time=0.5).size == 0
    assert np.array_equal(signal_chunk.times(5.0, end_time=0.6), np.array([0.5]))
    assert np.array_equal(signal_chunk.times(5.0, start_time=0.4, end_time=6.0), np.array([0.5]))


def test_signal_chunk_append():
    sample_count = 100
    half_count = int(sample_count / 2)
    raw_data = [[v, 10 + v, 10 * v] for v in range(sample_count)]
    signal_chunk_a = SignalChunk(
        np.array(raw_data[0:half_count]),
        10,
        0,
        ["a", "b", "c"]
    )
    assert np.array_equal(signal_chunk_a.times(), np.array(range(half_count)) / 10)
    assert signal_chunk_a.end() == 4.9

    signal_chunk_b = SignalChunk(
        np.array(raw_data[half_count:]),
        10,
        half_count / 10,
        ["a", "b", "c"]
    )
    assert np.array_equal(signal_chunk_b.times(), np.array(range(half_count, sample_count)) / 10)
    assert signal_chunk_b.end() == 9.9

    signal_chunk_a.append(signal_chunk_b)
    assert np.array_equal(signal_chunk_a.times(), np.array(range(sample_count)) / 10)
    assert signal_chunk_a.end() == 9.9
    assert np.array_equal(signal_chunk_a.values(0), np.array(range(sample_count)))
    assert np.array_equal(signal_chunk_a.values(1), np.array(range(sample_count)) + 10)
    assert np.array_equal(signal_chunk_a.values(2), np.array(range(sample_count)) * 10)


def test_signal_chunk_append_fill_in_missing_fields():
    # An empty placeholder signal chunk, as if we haven't read any data yet.
    signal_chunk_a = SignalChunk.empty(channel_ids=["0"])

    # A full signal chunk, perhaps the first data we read in.
    signal_chunk_b = SignalChunk(
        sample_data=np.arange(100).reshape([-1, 1]),
        sample_frequency=10,
        first_sample_time=7.7,
        channel_ids=["0"]
    )

    assert signal_chunk_a.sample_frequency is None
    assert signal_chunk_a.first_sample_time is None

    # The append operation should fill in sample_frequency if missing.
    signal_chunk_a.append(signal_chunk_b)
    assert signal_chunk_a.sample_frequency == signal_chunk_b.sample_frequency
    assert signal_chunk_a.first_sample_time == signal_chunk_b.first_sample_time


def test_signal_chunk_discard_before():
    sample_count = 100
    raw_data = [[v, 10 + v, 10 * v] for v in range(sample_count)]
    signal_chunk = SignalChunk(
        np.array(raw_data),
        10,
        0,
        ["a", "b", "c"]
    )
    assert np.array_equal(signal_chunk.times(), np.array(range(sample_count)) / 10)
    assert signal_chunk.end() == 9.9

    signal_chunk.discard_before(None)
    assert np.array_equal(signal_chunk.times(), np.array(range(sample_count)) / 10)
    assert signal_chunk.end() == 9.9

    half_count = int(sample_count / 2)
    signal_chunk.discard_before(half_count / 10)
    assert np.array_equal(signal_chunk.times(), np.array(range(half_count, sample_count)) / 10)
    assert signal_chunk.end() == 9.9
    assert np.array_equal(signal_chunk.values(0), np.array(range(half_count, sample_count)))
    assert np.array_equal(signal_chunk.values(1), np.array(range(half_count, sample_count)) + 10)
    assert np.array_equal(signal_chunk.values(2), np.array(range(half_count, sample_count)) * 10)

    signal_chunk.discard_before(1000)
    assert signal_chunk.times().size == 0
    assert signal_chunk.end() == None


def test_signal_chunk_shift_times():
    sample_count = 100
    raw_data = [[v, 10 + v, 10 * v] for v in range(sample_count)]
    signal_chunk = SignalChunk(
        np.array(raw_data),
        10,
        0,
        ["a", "b", "c"]
    )

    signal_chunk.shift_times(5)
    assert np.array_equal(signal_chunk.times(), np.array(range(sample_count)) / 10 + 5)
    assert signal_chunk.end() == 5 + 9.9


def test_signal_chunk_shift_times_empty():
    signal_chunk = SignalChunk.empty(
        sample_frequency=10,
        first_sample_time=0,
        channel_ids=["a", "b", "c"]
    )
    signal_chunk.shift_times(5)
    assert signal_chunk.times().size == 0
    assert signal_chunk.start() == None
    assert signal_chunk.end() == None
    assert signal_chunk.first() == None
    assert signal_chunk.last() == None


def test_signal_chunk_transform_all_values():
    sample_count = 100
    raw_data = [[v, 10 + v, 10 * v] for v in range(sample_count)]
    signal_chunk = SignalChunk(
        np.array(raw_data),
        10,
        0,
        ["a", "b", "c"]
    )

    signal_chunk.apply_offset_then_gain(offset=-500, gain=2)

    assert np.array_equal(signal_chunk.times(), np.array(range(sample_count)) / 10)
    assert signal_chunk.end() == 9.9
    assert np.array_equal(signal_chunk.values(0), (np.array(range(sample_count)) - 500) * 2)
    assert np.array_equal(signal_chunk.values(1), ((np.array(range(sample_count)) + 10) - 500) * 2)
    assert np.array_equal(signal_chunk.values(2), ((np.array(range(sample_count)) * 10) - 500) * 2)


def test_signal_chunk_transform_channel_values():
    sample_count = 100
    raw_data = [[v, 10 + v, 10 * v] for v in range(sample_count)]
    signal_chunk = SignalChunk(
        np.array(raw_data),
        10,
        0,
        ["a", "b", "c"]
    )

    signal_chunk.apply_offset_then_gain(offset=-500, gain=2, channel_id="b")

    assert np.array_equal(signal_chunk.times(), np.array(range(sample_count)) / 10)
    assert signal_chunk.end() == 9.9
    assert np.array_equal(signal_chunk.values(0), np.array(range(sample_count)))
    assert np.array_equal(signal_chunk.values(1), ((np.array(range(sample_count)) + 10) - 500) * 2)
    assert np.array_equal(signal_chunk.values(2), np.array(range(sample_count)) * 10)


def test_signal_chunk_copy_time_range():
    sample_count = 100
    raw_data = [[v, 10 + v, 10 * v] for v in range(sample_count)]
    signal_chunk = SignalChunk(
        np.array(raw_data),
        10,
        0,
        ["a", "b", "c"]
    )

    range_chunk = signal_chunk.copy_time_range(4, 6)
    assert np.array_equal(range_chunk.times(), np.array(range(40, 60)) / 10)
    assert range_chunk.end() == 5.9
    assert np.array_equal(range_chunk.values(0), np.array(range(40, 60)))

    tail_chunk = signal_chunk.copy_time_range(start_time=4)
    assert np.array_equal(tail_chunk.times(), np.array(range(40, sample_count)) / 10)
    assert tail_chunk.end() == 9.9
    assert np.array_equal(tail_chunk.values(0), np.array(range(40, sample_count)))

    head_chunk = signal_chunk.copy_time_range(end_time=6)
    assert np.array_equal(head_chunk.times(), np.array(range(0, 60)) / 10)
    assert head_chunk.end() == 5.9
    assert np.array_equal(head_chunk.values(0), np.array(range(0, 60)))

    empty_chunk = signal_chunk.copy_time_range(start_time=1000)
    assert empty_chunk.times().size == 0
    assert empty_chunk.end() == None
    assert empty_chunk.values(0).size == 0

    # original list should be unchanged
    assert np.array_equal(signal_chunk.times(), np.array(range(100)) / 10)
    assert signal_chunk.end() == 9.9
    assert np.array_equal(signal_chunk.values(0), np.array(range(100)))


def test_signal_chunk_equality():
    foo_chunk = SignalChunk(
        np.array([[v, 10 + v, 10 * v] for v in range(100)]),
        10,
        0,
        ["a", "b", "c"]
    )
    bar_chunk = SignalChunk(
        np.array([[v, 10 + v, 10 * v] for v in range(100)]),
        1000,
        0,
        ["a", "b", "c"]
    )
    baz_chunk = bar_chunk.copy()

    # copies should be equal, but not the same object in memory.
    assert baz_chunk is not bar_chunk

    assert foo_chunk == foo_chunk
    assert bar_chunk == bar_chunk
    assert baz_chunk == baz_chunk
    assert bar_chunk == baz_chunk
    assert baz_chunk == bar_chunk

    assert foo_chunk != bar_chunk
    assert bar_chunk != foo_chunk
    assert foo_chunk != baz_chunk
    assert baz_chunk != foo_chunk

    assert foo_chunk != "wrong type"
    assert bar_chunk != "wrong type"
    assert baz_chunk != "wrong type"
