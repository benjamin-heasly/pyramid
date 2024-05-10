import numpy as np

from pyramid.model.events import NumericEventList, TextEventList


def test_numeric_list_getters():
    event_count = 100
    raw_data = [[t, 10*t] for t in range(event_count)]
    event_data = np.array(raw_data)
    event_list = NumericEventList(event_data)

    assert event_list.event_count() == event_count
    assert event_list.values_per_event() == 1
    assert np.array_equal(event_list.times(), np.array(range(event_count)))
    assert np.array_equal(event_list.values(), 10*np.array(range(event_count)))

    assert event_list.first() == 0
    assert event_list.first(0) == 0
    assert event_list.first(1) == 0
    assert event_list.last() == 99
    assert event_list.last(0) == 99
    assert event_list.last(1) == 990
    assert np.array_equal(event_list.values(), 10*np.array(range(100)))
    assert np.array_equal(event_list.values(start_time=40), 10*np.array(range(40, 100)))
    assert np.array_equal(event_list.values(end_time=60), 10*np.array(range(60)))
    assert np.array_equal(event_list.values(start_time=40, end_time=60), 10*np.array(range(40, 60)))
    assert np.array_equal(event_list.values(start_time=60, end_time=40), [])

    assert event_list.start() == 0
    assert event_list.end() == 99
    assert np.array_equal(event_list.times(), event_list.times())
    assert np.array_equal(event_list.times(0.0), np.array([0.0]))
    assert np.array_equal(event_list.times(10.0), np.array([1.0]))
    assert np.array_equal(event_list.times(990.0), np.array([99.0]))
    assert event_list.times(-1.0).size == 0
    assert event_list.times(10.42).size == 0
    assert event_list.times(1000).size == 0

    assert np.array_equal(event_list.times(50.0, start_time=4.0), np.array([5.0]))
    assert np.array_equal(event_list.times(50.0, start_time=5.0), np.array([5.0]))
    assert event_list.times(50.0, start_time=6.0).size == 0
    assert event_list.times(50.0, end_time=4.0).size == 0
    assert event_list.times(50.0, end_time=5.0).size == 0
    assert np.array_equal(event_list.times(50.0, end_time=6.0), np.array([5.0]))
    assert np.array_equal(event_list.times(50.0, start_time=4.0, end_time=6.0), np.array([5.0]))


def test_numeric_list_append():
    event_count = 100
    half_count = int(event_count / 2)
    event_list_a = NumericEventList(np.array([[t, 10*t] for t in range(half_count)]))
    event_list_b = NumericEventList(np.array([[t, 10*t] for t in range(half_count, event_count)]))
    event_list_a.append(event_list_b)

    assert event_list_a.event_count() == event_count
    assert event_list_a.values_per_event() == 1
    assert np.array_equal(event_list_a.times(), np.array(range(event_count)))
    assert np.array_equal(event_list_a.values(), 10*np.array(range(event_count)))


def test_numeric_list_discard_before():
    event_count = 100
    half_count = int(event_count / 2)
    raw_data = [[t, 10*t] for t in range(event_count)]
    event_data = np.array(raw_data)
    event_list = NumericEventList(event_data)

    event_list.discard_before(half_count)
    assert np.array_equal(event_list.times(), np.array(range(half_count, event_count)))
    assert np.array_equal(event_list.values(), 10*np.array(range(half_count, event_count)))


def test_numeric_list_shift_times():
    event_count = 100
    raw_data = [[t, 10*t] for t in range(event_count)]
    event_data = np.array(raw_data)
    event_list = NumericEventList(event_data)

    event_list.shift_times(5)
    assert np.array_equal(event_list.times(), 5 + np.array(range(100)))


def test_numeric_list_shift_times_empty():
    event_list = NumericEventList.empty(1)
    event_list.shift_times(5)
    assert event_list.times().size == 0
    assert event_list.start() == None
    assert event_list.end() == None
    assert event_list.first() == None
    assert event_list.last() == None


def test_numeric_list_transform_values():
    event_count = 100
    raw_data = [[t, 10*t] for t in range(event_count)]
    event_data = np.array(raw_data)
    event_list = NumericEventList(event_data)

    event_list.apply_offset_then_gain(offset=-500, gain=2)
    assert np.array_equal(event_list.times(), np.array(range(100)))
    assert np.array_equal(event_list.values(), 2*10*np.array(range(-50, 50)))


def test_numeric_list_copy_value_range():
    event_count = 100
    raw_data = [[t, 10*t] for t in range(event_count)]
    event_data = np.array(raw_data)
    event_list = NumericEventList(event_data)

    range_event_list = event_list.copy_value_range(min=400, max=600)
    assert np.array_equal(range_event_list.times(), np.array(range(40, 60)))
    assert np.array_equal(range_event_list.values(), 10*np.array(range(40, 60)))

    # original list should be unchanged
    assert np.array_equal(event_list.times(), np.array(range(100)))
    assert np.array_equal(event_list.values(), 10*np.array(range(100)))


def test_numeric_list_copy_value_range_no_min():
    event_count = 100
    raw_data = [[t, 10*t] for t in range(event_count)]
    event_data = np.array(raw_data)
    event_list = NumericEventList(event_data)

    range_event_list = event_list.copy_value_range(max=600)
    assert np.array_equal(range_event_list.times(), np.array(range(60)))
    assert np.array_equal(range_event_list.values(), 10*np.array(range(60)))


def test_numeric_list_copy_value_range_no_max():
    event_count = 100
    raw_data = [[t, 10*t] for t in range(event_count)]
    event_data = np.array(raw_data)
    event_list = NumericEventList(event_data)

    range_event_list = event_list.copy_value_range(min=400)
    assert np.array_equal(range_event_list.times(), np.array(range(40, 100)))
    assert np.array_equal(range_event_list.values(), 10*np.array(range(40, 100)))


def test_numeric_list_copy_time_range():
    event_count = 100
    raw_data = [[t, 10*t] for t in range(event_count)]
    event_data = np.array(raw_data)
    event_list = NumericEventList(event_data)

    range_event_list = event_list.copy_time_range(40, 60)
    assert np.array_equal(range_event_list.times(), np.array(range(40, 60)))
    assert np.array_equal(range_event_list.values(), 10*np.array(range(40, 60)))

    tail_event_list = event_list.copy_time_range(start_time=40)
    assert np.array_equal(tail_event_list.times(), np.array(range(40, event_count)))
    assert np.array_equal(tail_event_list.values(), 10*np.array(range(40, event_count)))

    head_event_list = event_list.copy_time_range(end_time=60)
    assert np.array_equal(head_event_list.times(), np.array(range(0, 60)))
    assert np.array_equal(head_event_list.values(), 10*np.array(range(0, 60)))

    # original list should be unchanged
    assert np.array_equal(event_list.times(), np.array(range(100)))
    assert np.array_equal(event_list.values(), 10*np.array(range(100)))


def test_numeric_list_equality():
    foo_events = NumericEventList(np.array([[t, 10*t] for t in range(100)]))
    bar_events = NumericEventList(np.array([[t/10, 2*t] for t in range(1000)]))
    baz_events = NumericEventList(np.array([[t/10, 2*t] for t in range(1000)]))

    assert foo_events == foo_events
    assert bar_events == bar_events
    assert baz_events == baz_events
    assert bar_events == baz_events
    assert baz_events == bar_events

    assert foo_events != bar_events
    assert bar_events != foo_events
    assert foo_events != baz_events
    assert baz_events != foo_events

    assert foo_events != "wrong type"
    assert bar_events != "wrong type"
    assert baz_events != "wrong type"


def test_text_list_getters():
    event_count = 100
    raw_data = list(range(event_count))
    timestamp_data = np.array(raw_data, dtype=np.float32)
    text_data = np.array(raw_data, dtype=np.str_)
    event_list = TextEventList(timestamp_data, text_data)

    assert event_list.first() == '0'
    assert event_list.last() == '99'
    assert np.array_equal(event_list.values(), [str(t) for t in range(event_count)])
    assert np.array_equal(event_list.values(start_time=40), [str(t) for t in range(40, 100)])
    assert np.array_equal(event_list.values(end_time=60), [str(t) for t in range(60)])
    assert np.array_equal(event_list.values(start_time=40, end_time=60), [str(t) for t in range(40, 60)])
    assert np.array_equal(event_list.values(start_time=60, end_time=40), [])

    assert event_list.start() == 0
    assert event_list.end() == 99
    assert np.array_equal(event_list.times(), range(event_count))
    assert np.array_equal(event_list.times('0'), np.array([0.0]))
    assert np.array_equal(event_list.times('1'), np.array([1.0]))
    assert np.array_equal(event_list.times('99'), np.array([99.0]))
    assert event_list.times('-1').size == 0
    assert event_list.times('no way').size == 0
    assert event_list.times('1000').size == 0

    assert np.array_equal(event_list.times('5', start_time=4.0), np.array([5.0]))
    assert np.array_equal(event_list.times('5', start_time=5.0), np.array([5.0]))
    assert event_list.times('5', start_time=6.0).size == 0
    assert event_list.times('5', end_time=4.0).size == 0
    assert event_list.times('5', end_time=5.0).size == 0
    assert np.array_equal(event_list.times('5', end_time=6.0), np.array([5.0]))
    assert np.array_equal(event_list.times('5', start_time=4.0, end_time=6.0), np.array([5.0]))


def test_text_list_append():
    event_count = 100
    half_count = int(event_count / 2)
    event_list_a = TextEventList(np.array(range(half_count)), np.array(range(half_count), dtype="U"))
    event_list_b = TextEventList(np.array(range(half_count, event_count)),
                                 np.array(range(half_count, event_count), dtype="U"))
    event_list_a.append(event_list_b)

    assert event_list_a.event_count() == event_count
    assert np.array_equal(event_list_a.timestamp_data, np.array(range(event_count)))
    assert np.array_equal(event_list_a.text_data, np.array(range(event_count), dtype="U"))


def test_text_list_discard_before():
    event_count = 100
    half_count = int(event_count / 2)
    event_list = TextEventList(np.array(range(event_count)), np.array(range(event_count), dtype="U"))

    event_list.discard_before(half_count)
    assert np.array_equal(event_list.timestamp_data, np.array(range(half_count, event_count)))
    assert np.array_equal(event_list.text_data, np.array(range(half_count, event_count), dtype="U"))


def test_text_list_shift_times():
    event_count = 100
    event_list = TextEventList(np.array(range(event_count)), np.array(range(event_count), dtype="U"))

    event_list.shift_times(5)
    assert np.array_equal(event_list.timestamp_data, 5 + np.array(range(100)))


def test_text_list_shift_times_empty():
    event_list = TextEventList.empty()
    event_list.shift_times(5)
    assert event_list.timestamp_data.size == 0
    assert event_list.start() == None
    assert event_list.end() == None
    assert event_list.first() == None
    assert event_list.last() == None


def test_text_list_copy_time_range():
    event_count = 100
    event_list = TextEventList(np.array(range(event_count)), np.array(range(event_count), dtype="U"))

    range_event_list = event_list.copy_time_range(40, 60)
    assert np.array_equal(range_event_list.timestamp_data, np.array(range(40, 60)))
    assert np.array_equal(range_event_list.text_data, np.array(range(40, 60), dtype="U"))

    tail_event_list = event_list.copy_time_range(start_time=40)
    assert np.array_equal(tail_event_list.timestamp_data, np.array(range(40, event_count)))
    assert np.array_equal(tail_event_list.text_data, np.array(range(40, event_count), dtype="U"))

    head_event_list = event_list.copy_time_range(end_time=60)
    assert np.array_equal(head_event_list.timestamp_data, np.array(range(0, 60)))
    assert np.array_equal(head_event_list.text_data, np.array(range(0, 60), dtype="U"))

    # original list should be unchanged
    assert np.array_equal(event_list.timestamp_data, np.array(range(100)))
    assert np.array_equal(event_list.text_data, np.array(range(100), dtype="U"))


def test_text_list_equality():
    foo_events = TextEventList(np.array(range(100)), np.array(range(100), dtype="U"))
    bar_events = TextEventList(np.array(range(1000)), np.array(range(1000), dtype="U"))
    baz_events = TextEventList(np.array(range(1000)), np.array(range(1000), dtype="U"))
    empty_events = TextEventList.empty()

    assert foo_events == foo_events.copy()

    assert foo_events == foo_events
    assert bar_events == bar_events
    assert baz_events == baz_events
    assert bar_events == baz_events
    assert baz_events == bar_events
    assert empty_events == empty_events

    assert foo_events != bar_events
    assert bar_events != foo_events
    assert foo_events != baz_events
    assert baz_events != foo_events
    assert foo_events != empty_events
    assert empty_events != foo_events

    assert foo_events != "wrong type"
    assert bar_events != "wrong type"
    assert baz_events != "wrong type"
    assert empty_events != "wrong type"
