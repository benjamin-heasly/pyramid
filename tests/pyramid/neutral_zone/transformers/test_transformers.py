import numpy as np

from pyramid.file_finder import FileFinder
from pyramid.model.events import NumericEventList, TextEventList
from pyramid.model.signals import SignalChunk
from pyramid.neutral_zone.transformers.transformers import Transformer
from pyramid.neutral_zone.transformers.standard_transformers import OffsetThenGain, FilterRange, SmashCase, SparseSignal


def test_installed_transformer_dynamic_import():
    # Import a transformer that was installed in the usual way (eg by pip) along with pyramid itself.
    import_spec = "pyramid.neutral_zone.transformers.standard_transformers.OffsetThenGain"
    transformer = Transformer.from_dynamic_import(import_spec, FileFinder())
    assert isinstance(transformer, Transformer)
    assert isinstance(transformer, OffsetThenGain)


def test_offset_then_gain_dynamic_imports_with_kwargs():
    offset_then_gain_spec = "pyramid.neutral_zone.transformers.standard_transformers.OffsetThenGain"
    offset_then_gain = Transformer.from_dynamic_import(
        offset_then_gain_spec,
        FileFinder(),
        offset=10,
        gain=-2,
        ignore="ignore me"
    )
    assert offset_then_gain.offset == 10
    assert offset_then_gain.gain == -2


def test_filter_range_dynamic_imports_with_kwargs():
    filter_range_spec = "pyramid.neutral_zone.transformers.standard_transformers.FilterRange"
    filter_range = Transformer.from_dynamic_import(
        filter_range_spec,
        FileFinder(),
        min=-100,
        max=55,
        ignore="ignore me"
    )
    assert filter_range.min == -100
    assert filter_range.max == 55


def test_smash_case_dynamic_imports_with_kwargs():
    filter_range_spec = "pyramid.neutral_zone.transformers.standard_transformers.SmashCase"
    filter_range = Transformer.from_dynamic_import(
        filter_range_spec,
        FileFinder(),
        upper_case=False,
        ignore="ignore me"
    )
    assert filter_range.upper_case == False


def test_offset_then_gain_event_list():
    event_count = 100
    raw_data = [[t, 10*t] for t in range(event_count)]
    event_list = NumericEventList(np.array(raw_data))

    transformer = OffsetThenGain(offset=10, gain=-2)
    transformed = transformer.transform(event_list)

    expected_data = [[t, -2 * (10 + (10*t))] for t in range(event_count)]
    expected = NumericEventList(np.array(expected_data))
    assert transformed == expected


def test_offset_then_gain_signal_chunk():
    sample_count = 100
    raw_data = [[s, 10 * s] for s in range(sample_count)]
    signal_chunk = SignalChunk(np.array(raw_data), sample_frequency=1.0, first_sample_time=0.0, channel_ids=[0, 1])

    transformer = OffsetThenGain(offset=10, gain=-2)
    transformed = transformer.transform(signal_chunk)

    expected_data = [[-2 * (10 + s), -2 * (10 + (10 * s))] for s in range(sample_count)]
    expected = SignalChunk(np.array(expected_data), sample_frequency=1.0, first_sample_time=0.0, channel_ids=[0, 1])
    assert transformed == expected


def test_filter_range():
    raw_data = [[t, 10*t] for t in range(100)]
    event_list = NumericEventList(np.array(raw_data))

    transformer = FilterRange(min=250, max=750)
    transformed = transformer.transform(event_list)

    expected_data = [[t, 10*t] for t in range(25, 75)]
    expected = NumericEventList(np.array(expected_data))
    assert transformed == expected


def test_smash_case():
    event_list = TextEventList(
        np.array([0, 1, 2, 3]),
        np.array(["aBc", "AbC", "qWeRtY123456!@#$%^", ""], dtype=np.str_)
    )

    to_upper = SmashCase(upper_case=True)
    all_caps = to_upper.transform(event_list)
    assert np.array_equal(all_caps.timestamp_data, event_list.timestamp_data)
    assert all_caps.text_data.tolist() == ["ABC", "ABC", "QWERTY123456!@#$%^", ""]

    to_lower = SmashCase(upper_case=False)
    no_caps = to_lower.transform(event_list)
    assert np.array_equal(no_caps.timestamp_data, event_list.timestamp_data)
    assert no_caps.text_data.tolist() == ["abc", "abc", "qwerty123456!@#$%^", ""]


def test_sparse_signal_fill_gaps_with_constant():
    # Events with timestamps roughly but not quite 1 second apart.
    event_data_a = [
        [0.0, 0, 100],
        [1.0, 10, 100],
        [2.0, 20, 100],
        [2.9, 30, 100],
        [4.1, 40, 0],
        [5.0, 50, 0]
    ]
    event_list_a = NumericEventList(np.array(event_data_a))

    # A gap until more events arrive.

    # Later events with timestamps roughly but not quite 1 second apart.
    event_data_b = [
        [10.0, 100, 100],
        [11.0, 110, 100],
        [12.0, 120, 100],
        [12.9, 130, 100],
        [14.1, 140, 0],
        [15.0, 150, 0]
    ]
    event_list_b = NumericEventList(np.array(event_data_b))

    # Wrangle these events into a continuous signal.
    # Deal in event data to whatever samples they happen to fall on.
    fill_with_transformer = SparseSignal(
        fill_with=-1,
        sample_frequency=1.0,
        channel_ids=["proportional", "square"]
    )

    # Transform event list a to a signal chunk.
    signal_chunk_a = fill_with_transformer.transform(event_list_a)

    # Expect gaps from misaligned event timestamps.
    signal_data_a = [
        [0, 100],
        [10, 100],
        [30, 100],
        [-1, -1],
        [40, 0],
        [50, 0],
    ]
    assert signal_chunk_a == SignalChunk(
        sample_data=np.array(signal_data_a),
        sample_frequency=1.0,
        first_sample_time=0.0,
        channel_ids=["proportional", "square"]
    )

    # The transformer has state.  It should keep track of where it left off.
    assert fill_with_transformer.last_sample_time == 5
    assert np.array_equal(fill_with_transformer.last_sample_value, [50, 0])

    # Transform event list b to a signal chunk.
    signal_chunk_b = fill_with_transformer.transform(event_list_b)

    # Expect a big gap betwen event lists and gaps from misaligned event timestamps.
    signal_data_b = [
        [-1, -1],
        [-1, -1],
        [-1, -1],
        [-1, -1],
        [100, 100],
        [110, 100],
        [130, 100],
        [-1, -1],
        [140, 0],
        [150, 0],
    ]
    assert signal_chunk_b == SignalChunk(
        sample_data=np.array(signal_data_b),
        sample_frequency=1.0,
        first_sample_time=6.0,
        channel_ids=["proportional", "square"]
    )

    # The transformer has state.  It should keep track of where it left off.
    assert fill_with_transformer.last_sample_time == 15
    assert np.array_equal(fill_with_transformer.last_sample_value, [150, 0])


def test_sparse_signal_interpolate_gaps():
    # Events with timestamps roughly but not quite 1 second apart.
    event_data_a = [
        [0.0, 0, 100],
        [1.0, 10, 100],
        [2.0, 20, 100],
        [2.9, 30, 100],
        [4.1, 40, 0],
        [5.0, 50, 0]
    ]
    event_list_a = NumericEventList(np.array(event_data_a))

    # A gap until more events arrive.

    # Later events with timestamps roughly but not quite 1 second apart.
    event_data_b = [
        [10.0, 100, 100],
        [11.0, 110, 100],
        [12.0, 120, 100],
        [12.9, 130, 100],
        [14.1, 140, 0],
        [15.0, 150, 0]
    ]
    event_list_b = NumericEventList(np.array(event_data_b))

    # Wrangle these events into a continuous signal.
    # Interpolate between gaps.
    interpolate_transformer = SparseSignal(
        fill_with=None,
        sample_frequency=1.0,
        channel_ids=["proportional", "square"]
    )

    # Transform event list a to a signal chunk.
    signal_chunk_a = interpolate_transformer.transform(event_list_a)

    # Expect gaps filled in with interpolated values.
    signal_data_a = [
        [0, 100],
        [10, 100],
        [20, 100],
        [30.833333333333336, 91.66666666666666],
        [39.16666666666667, 8.3333333333333],
        [50, 0],
    ]
    assert signal_chunk_a == SignalChunk(
        sample_data=np.array(signal_data_a),
        sample_frequency=1.0,
        first_sample_time=0.0,
        channel_ids=["proportional", "square"]
    )

    # The transformer has state.  It should keep track of where it left off.
    assert interpolate_transformer.last_sample_time == 5
    assert np.array_equal(interpolate_transformer.last_sample_value, [50, 0])

    # Transform event list b to a signal chunk.
    signal_chunk_b = interpolate_transformer.transform(event_list_b)

    # Expect both big and little gaps filled in with interpolated values.
    signal_data_b = [
        [60, 20],
        [70, 40],
        [80, 60],
        [90, 80],
        [100, 100],
        [110, 100],
        [120, 100],
        [130.83333333333334, 91.66666666666669],
        [139.16666666666666, 8.3333333333333],
        [150, 0],
    ]
    assert signal_chunk_b == SignalChunk(
        sample_data=np.array(signal_data_b),
        sample_frequency=1.0,
        first_sample_time=6.0,
        channel_ids=["proportional", "square"]
    )

    # The transformer has state.  It should keep track of where it left off.
    assert interpolate_transformer.last_sample_time == 15
    assert np.array_equal(interpolate_transformer.last_sample_value, [150, 0])


def test_sparse_signal_no_ops():
    # Don't crash on unexpected data type, just return it.
    wrong_event_list = TextEventList(
        np.array([0, 1, 2, 3]),
        np.array(["aBc", "AbC", "qWeRtY123456!@#$%^", ""], dtype=np.str_)
    )
    transformer = SparseSignal(
        fill_with=None,
        sample_frequency=1.0,
        channel_ids=["a", "b"]
    )
    same_event_list = transformer.transform(wrong_event_list)
    assert same_event_list == wrong_event_list

    # Don't crash on empty data, just return empty signal chunk.
    empty_signal_chunk = transformer.transform(NumericEventList.empty(2))
    assert empty_signal_chunk == SignalChunk.empty(
        sample_frequency=transformer.sample_frequency,
        channel_ids=transformer.channel_ids
    )
