from pathlib import Path

import numpy as np
from pytest import fixture, raises

from pyramid.model.events import NumericEventList, TextEventList
from pyramid.model.signals import SignalChunk
from pyramid.neutral_zone.readers.csv import CsvNumericEventReader, CsvTextEventReader, CsvSignalReader, WideCsvEventReader


@fixture
def fixture_path(request):
    this_file = Path(request.module.__file__)
    return Path(this_file.parent, 'fixture_files')


def test_numeric_events_equality():
    foo_reader_1 = CsvNumericEventReader("foo.foo")
    foo_reader_2 = CsvNumericEventReader("foo.foo", result_name="different")
    foo_reader_3 = CsvNumericEventReader("foo.foo", dialect="different")
    foo_reader_4 = CsvNumericEventReader("foo.foo", other="different")
    bar_reader_1 = CsvNumericEventReader("bar.bar")

    assert foo_reader_1 == foo_reader_1
    assert foo_reader_2 == foo_reader_2
    assert foo_reader_3 == foo_reader_3
    assert foo_reader_4 == foo_reader_4
    assert bar_reader_1 == bar_reader_1

    assert foo_reader_1 != foo_reader_2
    assert foo_reader_1 != foo_reader_3
    assert foo_reader_1 != foo_reader_4
    assert foo_reader_1 != bar_reader_1

    assert foo_reader_1 != "wrong type!"


def test_numeric_events_safe_to_spam_exit(fixture_path):
    csv_file = Path(fixture_path, 'numeric_events', 'empty.csv').as_posix()
    reader = CsvNumericEventReader(csv_file)
    reader.__exit__(None, None, None)
    reader.__enter__()
    reader.__exit__(None, None, None)
    reader.__exit__(None, None, None)

    assert reader.reader.file_stream is None


def test_numeric_events_empty_file(fixture_path):
    csv_file = Path(fixture_path, 'numeric_events', 'empty.csv').as_posix()
    with CsvNumericEventReader(csv_file) as reader:
        initial = reader.get_initial()
        with raises(StopIteration) as exception_info:
            reader.read_next()

    expected_initial = {
        reader.result_name: NumericEventList.empty(1)
    }
    assert initial == expected_initial
    assert exception_info.errisinstance(StopIteration)
    assert reader.reader.file_stream is None


def test_numeric_events_with_header_line(fixture_path):
    csv_file = Path(fixture_path, 'numeric_events', 'header_line.csv').as_posix()

    # Treat the first line as a header, use this to swap the order of value columns.
    column_selector = ["time", "value 2", "value 1"]
    with CsvNumericEventReader(csv_file, first_row_is_header=True, column_selector=column_selector) as reader:
        # Should sort out column headers and selection by name when entering the context.
        assert reader.reader.first_row == ["time", "value 1", "value 2"]
        assert reader.reader.column_indices == [0, 2, 1]

        # Should also sort out columns during get_initial().
        # Try the same again, selecting numeric indices rather than string names.
        reader.reader.first_row = None
        reader.reader.column_indices = None
        reader.reader.column_selector = [0, 2, 1]
        initial = reader.get_initial()
        expected_initial = {
            reader.result_name: NumericEventList.empty(2)
        }
        assert initial == expected_initial

        assert reader.reader.first_row == ["time", "value 1", "value 2"]
        assert reader.reader.column_indices == [0, 2, 1]

        # Read 32 lines with value columns swapped...
        for t in range(32):
            result = reader.read_next()
            event_list = result[reader.result_name]
            expected_event_list = NumericEventList(np.array([[t, t + 1000, t + 100]]))
            assert event_list == expected_event_list

        # ...then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.reader.file_stream is None


def test_numeric_events_with_no_header_line(fixture_path):
    csv_file = Path(fixture_path, 'numeric_events', 'no_header_line.csv').as_posix()
    with CsvNumericEventReader(csv_file) as reader:
        initial = reader.get_initial()
        expected_initial = {
            reader.result_name: NumericEventList.empty(2)
        }
        assert initial == expected_initial

        # With no header row, get_initial() just peeks at the first data row.
        assert reader.reader.first_row == ["0", "100", "1000"]

        # By default, don't try to select specific columns.
        assert reader.reader.column_indices is None

        # Read 32 lines...
        for t in range(32):
            result = reader.read_next()
            event_list = result[reader.result_name]
            expected_event_list = NumericEventList(np.array([[t, t + 100, t + 1000]]))
            assert event_list == expected_event_list

        # ...then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.reader.file_stream is None


def test_numeric_events_skip_nonnumeric_lines(fixture_path):
    csv_file = Path(fixture_path, 'numeric_events', 'nonnumeric_lines.csv').as_posix()
    nonnumeric_lines = [1, 11, 15, 21, 28]
    with CsvNumericEventReader(csv_file) as reader:
        initial = reader.get_initial()
        expected_initial = {
            reader.result_name: NumericEventList.empty(2)
        }
        assert initial == expected_initial

        # Read 32 lines...
        for t in range(32):
            result = reader.read_next()
            if t in nonnumeric_lines:
                assert result is None
            else:
                event_list = result[reader.result_name]
                expected_event_list = NumericEventList(np.array([[t, t + 100, t + 1000]]))
                assert event_list == expected_event_list

        # ...then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.reader.file_stream is None


def test_numeric_events_with_list_data(fixture_path):
    csv_file = Path(fixture_path, 'numeric_events', 'list_data.csv').as_posix()
    with CsvNumericEventReader(csv_file, first_row_is_header=True, unpack_lists=True) as reader:
        initial = reader.get_initial()
        expected_initial = {
            reader.result_name: NumericEventList.empty(2)
        }
        assert initial == expected_initial

        # Read 9 CSV lines, where some cells are packed with lists of data...
        result_1 = reader.read_next()[reader.result_name]
        assert result_1 == NumericEventList(np.array([[0, 100, 1000], [1, 101, 1001], [2, 102, 1002]]))
        result_2 = reader.read_next()[reader.result_name]
        assert result_2 == NumericEventList(np.array([[3, 103, 1003]]))
        assert reader.read_next() is None
        result_4 = reader.read_next()[reader.result_name]
        assert result_4 == NumericEventList.empty(2)
        result_5 = reader.read_next()[reader.result_name]
        assert result_5 == NumericEventList(np.array([[4, 104, 1004], [5, 105, 1005], [6, 106, 1006], [7, 107, 1007]]))
        result_6 = reader.read_next()[reader.result_name]
        assert result_6 == NumericEventList(np.array([[8, 108, 1008], [9, 109, 1009]]))
        result_7 = reader.read_next()[reader.result_name]
        assert result_7 == NumericEventList(np.array([[10, 110, 1010]]))
        result_8 = reader.read_next()[reader.result_name]
        assert result_8 == NumericEventList(np.array([[11, 111, 1011]]))
        result_9 = reader.read_next()[reader.result_name]
        assert result_9 == NumericEventList(np.array([[12, 112, 1012], [13, 113, 1013]]))

        # ...then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.reader.file_stream is None


def test_numeric_events_timestamp_only(fixture_path):
    csv_file = Path(fixture_path, 'numeric_events', 'header_line.csv').as_posix()

    # Treat the first line as a header, use this to select just the timestamp column
    column_selector = ["time"]
    with CsvNumericEventReader(csv_file, first_row_is_header=True, column_selector=column_selector) as reader:
        # Should sort out column headers and selection by name when entering the context.
        assert reader.reader.first_row == ["time", "value 1", "value 2"]
        assert reader.reader.column_indices == [0]

        # Should also sort out columns during get_initial().
        # Try the same again, selecting numeric indices rather than string names.
        reader.reader.first_row = None
        reader.reader.column_indices = None
        reader.reader.column_selector = [0]
        initial = reader.get_initial()
        expected_initial = {
            reader.result_name: NumericEventList.empty(0)
        }
        assert initial == expected_initial

        assert reader.reader.first_row == ["time", "value 1", "value 2"]
        assert reader.reader.column_indices == [0]

        # Read 32 lines with value columns swapped...
        for t in range(32):
            result = reader.read_next()
            event_list = result[reader.result_name]
            expected_event_list = NumericEventList(np.array([[t]]))
            assert event_list == expected_event_list

        # ...then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.reader.file_stream is None


def test_text_events_equality():
    foo_reader_1 = CsvTextEventReader("foo.foo")
    foo_reader_2 = CsvTextEventReader("foo.foo", result_name="different")
    foo_reader_3 = CsvTextEventReader("foo.foo", dialect="different")
    foo_reader_4 = CsvTextEventReader("foo.foo", other="different")
    bar_reader_1 = CsvTextEventReader("bar.bar")

    assert foo_reader_1 == foo_reader_1
    assert foo_reader_2 == foo_reader_2
    assert foo_reader_3 == foo_reader_3
    assert foo_reader_4 == foo_reader_4
    assert bar_reader_1 == bar_reader_1

    assert foo_reader_1 != foo_reader_2
    assert foo_reader_1 != foo_reader_3
    assert foo_reader_1 != foo_reader_4
    assert foo_reader_1 != bar_reader_1

    assert foo_reader_1 != "wrong type!"


def test_text_events_safe_to_spam_exit(fixture_path):
    csv_file = Path(fixture_path, 'text_events', 'empty.csv').as_posix()
    reader = CsvTextEventReader(csv_file)
    reader.__exit__(None, None, None)
    reader.__enter__()
    reader.__exit__(None, None, None)
    reader.__exit__(None, None, None)

    assert reader.reader.file_stream is None


def test_text_events_empty_file(fixture_path):
    csv_file = Path(fixture_path, 'text_events', 'empty.csv').as_posix()
    with CsvTextEventReader(csv_file) as reader:
        initial = reader.get_initial()
        with raises(StopIteration) as exception_info:
            reader.read_next()

    expected_initial = {
        reader.result_name: TextEventList.empty()
    }
    assert initial == expected_initial
    assert exception_info.errisinstance(StopIteration)
    assert reader.reader.file_stream is None


def test_text_events_with_header_line(fixture_path):
    csv_file = Path(fixture_path, 'text_events', 'header_line.csv').as_posix()

    # Treat the first line as a header, use this to select the second column for text values.
    column_selector = ["time", "value 2"]
    with CsvTextEventReader(csv_file, first_row_is_header=True, column_selector=column_selector) as reader:
        # Should sort out column headers and selection by name when entering the context.
        assert reader.reader.first_row == ["time", "value 1", "value 2"]
        assert reader.reader.column_indices == [0, 2]

        # Should also sort out columns during get_initial().
        # Try the same again, selecting numeric indices rather than string names.
        reader.reader.first_row = None
        reader.reader.column_indices = None
        reader.reader.column_selector = [0, 2]
        initial = reader.get_initial()
        expected_initial = {
            reader.result_name: TextEventList.empty()
        }
        assert initial == expected_initial

        assert reader.reader.first_row == ["time", "value 1", "value 2"]
        assert reader.reader.column_indices == [0, 2]

        # Read first and third column from 32 lines...
        for t in range(32):
            result = reader.read_next()
            event_list = result[reader.result_name]
            expected_event_list = TextEventList(np.array([t]), np.array([str(t+1000)], dtype=np.str_))
            assert event_list == expected_event_list

        # ...then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.reader.file_stream is None


def test_text_events_with_no_header_line(fixture_path):
    csv_file = Path(fixture_path, 'text_events', 'no_header_line.csv').as_posix()
    with CsvTextEventReader(csv_file) as reader:
        initial = reader.get_initial()
        expected_initial = {
            reader.result_name: TextEventList.empty()
        }
        assert initial == expected_initial

        # With no header row, get_initial() just peeks at the first data row.
        assert reader.reader.first_row == ["0", "100", "1000"]

        # By default, don't try to select specific columns.
        assert reader.reader.column_indices is None

        # Read first and second column from 32 lines...
        for t in range(32):
            result = reader.read_next()
            event_list = result[reader.result_name]
            expected_event_list = TextEventList(np.array([t]), np.array([str(t+100)], dtype=np.str_))
            assert event_list == expected_event_list

        # ...then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.reader.file_stream is None


def test_text_events_skip_nonnumeric_timestamps(fixture_path):
    csv_file = Path(fixture_path, 'text_events', 'nonnumeric_lines.csv').as_posix()
    nonnumeric_timestamp_lines = [1, 15, 28]
    with CsvTextEventReader(csv_file) as reader:
        initial = reader.get_initial()
        expected_initial = {
            reader.result_name: TextEventList.empty()
        }
        assert initial == expected_initial

        # Read 32 lines...
        for t in range(32):
            result = reader.read_next()
            if t in nonnumeric_timestamp_lines:
                assert result is None
            else:
                event_list = result[reader.result_name]
                expected_event_list = TextEventList(np.array([t]), np.array([str(t+100)], dtype=np.str_))
                assert event_list == expected_event_list

        # ...then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.reader.file_stream is None


def test_text_events_with_list_data(fixture_path):
    csv_file = Path(fixture_path, 'text_events', 'list_data.csv').as_posix()
    with CsvTextEventReader(csv_file, first_row_is_header=True, unpack_lists=True) as reader:
        initial = reader.get_initial()
        expected_initial = {
            reader.result_name: TextEventList.empty()
        }
        assert initial == expected_initial

        # Read 7 CSV lines, where some cells are packed with lists of data...
        result_1 = reader.read_next()[reader.result_name]
        assert result_1 == TextEventList(np.array([0, 1, 2]), np.array(['zero', 'one', 'two'], dtype=np.str_))
        result_2 = reader.read_next()[reader.result_name]
        assert result_2 == TextEventList(np.array([4]), np.array(['four'], dtype=np.str_))
        assert reader.read_next() is None
        result_4 = reader.read_next()[reader.result_name]
        assert result_4 == TextEventList(np.array([5]), np.array(['five'], dtype=np.str_))
        result_5 = reader.read_next()[reader.result_name]
        assert result_5 == TextEventList(np.array([6, 6, 6]), np.array(['six_a', 'six_b', 'six_c'], dtype=np.str_))
        result_6 = reader.read_next()[reader.result_name]
        assert result_6 == TextEventList(np.array([7]), np.array(['seven'], dtype=np.str_))
        result_7 = reader.read_next()[reader.result_name]
        assert result_7 == TextEventList(np.array([8]), np.array(['eight'], dtype=np.str_))

        # ...then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.reader.file_stream is None


def test_signals_equality():
    foo_reader_1 = CsvSignalReader("foo.foo")
    foo_reader_2 = CsvSignalReader("foo.foo", result_name="different")
    foo_reader_3 = CsvSignalReader("foo.foo", dialect="different")
    foo_reader_4 = CsvSignalReader("foo.foo", other="different")
    foo_reader_5 = CsvSignalReader("foo.foo", sample_frequency="different")
    foo_reader_6 = CsvSignalReader("foo.foo", next_sample_time="different")
    foo_reader_7 = CsvSignalReader("foo.foo", lines_per_chunk="different")
    bar_reader_1 = CsvSignalReader("bar.bar")

    assert foo_reader_1 == foo_reader_1
    assert foo_reader_2 == foo_reader_2
    assert foo_reader_3 == foo_reader_3
    assert foo_reader_4 == foo_reader_4
    assert foo_reader_5 == foo_reader_5
    assert foo_reader_6 == foo_reader_6
    assert foo_reader_7 == foo_reader_7
    assert bar_reader_1 == bar_reader_1

    assert foo_reader_1 != foo_reader_2
    assert foo_reader_1 != foo_reader_3
    assert foo_reader_1 != foo_reader_4
    assert foo_reader_1 != foo_reader_5
    assert foo_reader_1 != foo_reader_6
    assert foo_reader_1 != foo_reader_7
    assert foo_reader_1 != bar_reader_1

    assert foo_reader_1 != "wrong type!"


def test_signals_safe_to_spam_exit(fixture_path):
    csv_file = Path(fixture_path, 'signals', 'empty.csv').as_posix()
    reader = CsvSignalReader(csv_file)
    reader.__exit__(None, None, None)
    reader.__enter__()
    reader.__exit__(None, None, None)
    reader.__exit__(None, None, None)

    assert reader.reader.file_stream is None


def test_signals_empty_file(fixture_path):
    csv_file = Path(fixture_path, 'signals', 'empty.csv').as_posix()
    with CsvSignalReader(csv_file) as reader:
        initial = reader.get_initial()
        with raises(StopIteration) as exception_info:
            reader.read_next()

    expected_initial = {reader.result_name: SignalChunk.empty(reader.sample_frequency, 0.0, None)}
    assert initial == expected_initial
    assert exception_info.errisinstance(StopIteration)
    assert reader.reader.file_stream is None


def test_signals_only_complete_chunks(fixture_path):
    csv_file = Path(fixture_path, 'signals', 'header_line.csv').as_posix()
    with CsvSignalReader(csv_file, lines_per_chunk=10) as reader:
        initial = reader.get_initial()
        expected_initial = {
            reader.result_name: SignalChunk.empty(
                reader.sample_frequency,
                first_sample_time=0.0,
                channel_ids=["a", "b", "c"]
            )
        }
        assert initial == expected_initial

        # Read 15 chunks of 10 lines each...
        for chunk_index in range(15):
            chunk_time = chunk_index * 10
            assert reader.next_sample_time == chunk_time

            result = reader.read_next()
            signal_chunk = result[reader.result_name]
            assert signal_chunk.sample_count() == 10

            sample_times = signal_chunk.times()
            assert np.array_equal(sample_times, np.array(range(chunk_time, chunk_time + 10)))
            assert np.array_equal(signal_chunk.values(0), sample_times)
            assert np.array_equal(signal_chunk.values(1), 100 - sample_times * 0.1)
            assert np.array_equal(signal_chunk.values(2), sample_times * 2 - 1000)

        # ...then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.reader.file_stream is None


def test_signals_last_partial_chunk(fixture_path):
    csv_file = Path(fixture_path, 'signals', 'header_line.csv').as_posix()
    with CsvSignalReader(csv_file, lines_per_chunk=11) as reader:
        initial = reader.get_initial()
        expected_initial = {
            reader.result_name: SignalChunk.empty(
                reader.sample_frequency,
                first_sample_time=0.0,
                channel_ids=["a", "b", "c"]
            )
        }
        assert initial == expected_initial

        # Read 13 chunks of 11 lines each...
        for chunk_index in range(13):
            chunk_time = chunk_index * 11
            assert reader.next_sample_time == chunk_time

            result = reader.read_next()
            signal_chunk = result[reader.result_name]
            assert signal_chunk.sample_count() == 11

            sample_times = signal_chunk.times()
            assert np.array_equal(sample_times, np.array(range(chunk_time, chunk_time + 11)))
            assert np.array_equal(signal_chunk.values(0), sample_times)
            assert np.array_equal(signal_chunk.values(1), 100 - sample_times * 0.1)
            assert np.array_equal(signal_chunk.values(2), sample_times * 2 - 1000)

        # Read a last, partial chunk of 7 lines.
        chunk_time = 143
        assert reader.next_sample_time == chunk_time

        result = reader.read_next()
        signal_chunk = result[reader.result_name]
        assert signal_chunk.sample_count() == 7

        sample_times = signal_chunk.times()
        assert np.array_equal(sample_times, np.array(range(chunk_time, chunk_time + 7)))
        assert np.array_equal(signal_chunk.values(0), sample_times)
        assert np.array_equal(signal_chunk.values(1), 100 - sample_times * 0.1)
        assert np.array_equal(signal_chunk.values(2), sample_times * 2 - 1000)

        # ...then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.reader.file_stream is None


def test_signals_skip_nonnumeric_lines(fixture_path):
    csv_file = Path(fixture_path, 'signals', 'nonnumeric_lines.csv').as_posix()
    with CsvSignalReader(csv_file, lines_per_chunk=10) as reader:
        initial = reader.get_initial()
        expected_initial = {
            reader.result_name: SignalChunk.empty(
                reader.sample_frequency,
                first_sample_time=0.0,
                channel_ids=["a", "b", "c"]
            )
        }
        assert initial == expected_initial

        # Read 15 chunks of 10 lines each...
        for chunk_index in range(15):
            chunk_time = chunk_index * 10
            assert reader.next_sample_time == chunk_time

            result = reader.read_next()
            signal_chunk = result[reader.result_name]
            assert signal_chunk.sample_count() == 10

            sample_times = signal_chunk.times()
            assert np.array_equal(sample_times, np.array(range(chunk_time, chunk_time + 10)))
            assert np.array_equal(signal_chunk.values(0), sample_times)
            assert np.array_equal(signal_chunk.values(1), 100 - sample_times * 0.1)
            assert np.array_equal(signal_chunk.values(2), sample_times * 2 - 1000)

        # ...then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.reader.file_stream is None


def test_signals_select_columns(fixture_path):
    csv_file = Path(fixture_path, 'signals', 'header_line.csv').as_posix()

    # Select a subset of columns, out of order, with name aliases.
    with CsvSignalReader(csv_file, column_selector=["c", "a"], channel_ids=["cee", "aye"]) as reader:
        # The reader should sort out columns from the CSV header, when entering context.
        assert reader.reader.first_row == ["a", "b", "c"]
        assert reader.reader.column_indices == [2, 0]
        assert reader.channel_ids == ["cee", "aye"]

        # The reader also should sort out columns during get_initial().
        # So try it again, this time selecting columns by index rather than name.
        reader.reader.first_row = None
        reader.reader.column_indices = None
        reader.reader.column_selector = [2, 0]
        initial = reader.get_initial()
        expected_initial = {
            reader.result_name: SignalChunk.empty(
                reader.sample_frequency,
                first_sample_time=0.0,
                channel_ids=["cee", "aye"]
            )
        }
        assert initial == expected_initial

        assert reader.reader.first_row == ["a", "b", "c"]
        assert reader.reader.column_indices == [2, 0]
        assert reader.channel_ids == ["cee", "aye"]

        # Read 15 chunks of 10 lines each...
        for chunk_index in range(15):
            chunk_time = chunk_index * 10
            assert reader.next_sample_time == chunk_time

            result = reader.read_next()
            signal_chunk = result[reader.result_name]
            assert signal_chunk.sample_count() == 10

            assert signal_chunk.channel_index("cee") == 0
            assert signal_chunk.channel_index("aye") == 1

            sample_times = signal_chunk.times()
            assert np.array_equal(sample_times, np.array(range(chunk_time, chunk_time + 10)))
            assert np.array_equal(signal_chunk.values(0), sample_times * 2 - 1000)
            assert np.array_equal(signal_chunk.values(1), sample_times)

        # ...then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.reader.file_stream is None


def test_signals_with_list_data(fixture_path):
    csv_file = Path(fixture_path, 'signals', 'list_data.csv').as_posix()
    with CsvSignalReader(csv_file, lines_per_chunk=1, unpack_lists=True) as reader:
        initial = reader.get_initial()
        expected_initial = {
            reader.result_name: SignalChunk.empty(
                reader.sample_frequency,
                first_sample_time=0.0,
                channel_ids=["a", "b", "c"]
            )
        }
        assert initial == expected_initial

        # Read 6 CSV lines, where some cells are packed with lists of data...
        result_1 = reader.read_next()[reader.result_name]
        sample_times = result_1.times()
        assert np.array_equal(sample_times, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        assert np.array_equal(result_1.values(0), sample_times)
        assert np.array_equal(result_1.values(1), 100 - sample_times * 0.1)
        assert np.array_equal(result_1.values(2), sample_times * 2 - 1000)

        result_2 = reader.read_next()[reader.result_name]
        sample_times = result_2.times()
        assert np.array_equal(sample_times, [10])
        assert np.array_equal(result_2.values(0), sample_times)
        assert np.array_equal(result_2.values(1), 100 - sample_times * 0.1)
        assert np.array_equal(result_2.values(2), sample_times * 2 - 1000)

        # result_3 would be here, but gets automatically skipped during next read.

        result_4 = reader.read_next()[reader.result_name]
        assert result_4.sample_count() == 0

        result_5 = reader.read_next()[reader.result_name]
        sample_times = result_5.times()
        assert np.array_equal(sample_times, [11, 12, 13, 14, 15, 16, 17, 18, 19])
        assert np.array_equal(result_5.values(0), sample_times)
        assert np.array_equal(result_5.values(1), 100 - sample_times * 0.1)
        assert np.array_equal(result_5.values(2), sample_times * 2 - 1000)

        result_6 = reader.read_next()[reader.result_name]
        sample_times = result_6.times()
        assert np.array_equal(sample_times, [20])
        assert np.array_equal(result_6.values(0), sample_times)
        assert np.array_equal(result_6.values(1), 100 - sample_times * 0.1)
        assert np.array_equal(result_6.values(2), sample_times * 2 - 1000)

        # ...then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.reader.file_stream is None


def test_wide_csv_event_reader(fixture_path):
    csv_file = Path(fixture_path, 'wide_events', 'wide.csv').as_posix()

    column_config = {
        "times_only": {
            "numeric": True,
            "column_selector": ["time"]
        },
        "numeric_scalars": {
            "numeric": True,
            "column_selector": ["time", "numeric_2", "numeric_1"]
        },
        "text_scalars_1": {
            "column_selector": ["time", "text_1"]
        },
        "text_scalars_2": {
            "column_selector": ["time", "text_2"]
        },
        "numeric_lists": {
            "numeric": True,
            "unpack_lists": True,
            "column_selector": ["list_times", "list_elements_1", "list_elements_2"]
        }
    }

    with WideCsvEventReader(csv_file=csv_file, column_config=column_config) as reader:
        initial = reader.get_initial()
        expected_initial = {
            "times_only": NumericEventList.empty(0),
            "numeric_scalars": NumericEventList.empty(2),
            "text_scalars_1": TextEventList.empty(),
            "text_scalars_2": TextEventList.empty(),
            "numeric_lists": NumericEventList.empty(2),
        }
        assert initial == expected_initial

        # Read 10 rows...
        result_0 = reader.read_next()
        assert np.array_equal(result_0["times_only"].times(), [0])
        assert np.array_equal(result_0["numeric_scalars"].times(), [0])
        assert np.array_equal(result_0["numeric_scalars"].values(0), [1000])
        assert np.array_equal(result_0["numeric_scalars"].values(1), [100])
        assert np.array_equal(result_0["text_scalars_1"].times(), [0])
        assert np.array_equal(result_0["text_scalars_1"].values(), ["zero"])
        assert np.array_equal(result_0["text_scalars_2"].times(), [0])
        assert np.array_equal(result_0["text_scalars_2"].values(), ["a"])
        assert np.array_equal(result_0["numeric_lists"].times(), [0.0, 0.1, 0.2])
        assert np.array_equal(result_0["numeric_lists"].values(0), [0, 1, 2])
        assert np.array_equal(result_0["numeric_lists"].values(1), [-0, -1, -2])

        result_1 = reader.read_next()
        assert np.array_equal(result_1["times_only"].times(), [1])
        assert np.array_equal(result_1["numeric_scalars"].times(), [1])
        assert np.array_equal(result_1["numeric_scalars"].values(0), [1001])
        assert np.array_equal(result_1["numeric_scalars"].values(1), [101])
        assert np.array_equal(result_1["text_scalars_1"].times(), [1])
        assert np.array_equal(result_1["text_scalars_1"].values(), ["one"])
        assert np.array_equal(result_1["text_scalars_2"].times(), [1])
        assert np.array_equal(result_1["text_scalars_2"].values(), ["b"])
        assert np.array_equal(result_1["numeric_lists"].times(), [1.0, 1.1, 1.2])
        assert np.array_equal(result_1["numeric_lists"].values(0), [3, 4, 5])
        assert np.array_equal(result_1["numeric_lists"].values(1), [-3, -4, -5])

        result_2 = reader.read_next()
        assert np.array_equal(result_2["times_only"].times(), [2])
        assert np.array_equal(result_2["numeric_scalars"].times(), [2])
        assert np.array_equal(result_2["numeric_scalars"].values(0), [1002])
        assert np.array_equal(result_2["numeric_scalars"].values(1), [102])
        assert np.array_equal(result_2["text_scalars_1"].times(), [2])
        assert np.array_equal(result_2["text_scalars_1"].values(), ["two"])
        assert np.array_equal(result_2["text_scalars_2"].times(), [2])
        assert np.array_equal(result_2["text_scalars_2"].values(), ["c"])
        assert np.array_equal(result_2["numeric_lists"].times(), [2.0, 2.1, 2.2])
        assert np.array_equal(result_2["numeric_lists"].values(0), [6, 7, 8])
        assert np.array_equal(result_2["numeric_lists"].values(1), [-6, -7, -8])

        result_3 = reader.read_next()
        assert np.array_equal(result_3["times_only"].times(), [3])
        assert np.array_equal(result_3["numeric_scalars"].times(), [3])
        assert np.array_equal(result_3["numeric_scalars"].values(0), [1003])
        assert np.array_equal(result_3["numeric_scalars"].values(1), [103])
        assert np.array_equal(result_3["text_scalars_1"].times(), [3])
        assert np.array_equal(result_3["text_scalars_1"].values(), ["three"])
        assert np.array_equal(result_3["text_scalars_2"].times(), [3])
        assert np.array_equal(result_3["text_scalars_2"].values(), ["d"])
        assert np.array_equal(result_3["numeric_lists"].times(), [3.0, 3.1, 3.2])
        assert np.array_equal(result_3["numeric_lists"].values(0), [9, 10, 11])
        assert np.array_equal(result_3["numeric_lists"].values(1), [-9, -10, -11])

        result_4 = reader.read_next()
        assert np.array_equal(result_4["times_only"].times(), [4])
        assert np.array_equal(result_4["numeric_scalars"].times(), [4])
        assert np.array_equal(result_4["numeric_scalars"].values(0), [1004])
        assert np.array_equal(result_4["numeric_scalars"].values(1), [104])
        assert np.array_equal(result_4["text_scalars_1"].times(), [4])
        assert np.array_equal(result_4["text_scalars_1"].values(), ["four"])
        assert np.array_equal(result_4["text_scalars_2"].times(), [4])
        assert np.array_equal(result_4["text_scalars_2"].values(), ["e"])
        assert np.array_equal(result_4["numeric_lists"].times(), [4.0, 4.1, 4.2])
        assert np.array_equal(result_4["numeric_lists"].values(0), [12, 13, 14])
        assert np.array_equal(result_4["numeric_lists"].values(1), [-12, -13, -14])

        result_5 = reader.read_next()
        assert np.array_equal(result_5["times_only"].times(), [5])
        assert np.array_equal(result_5["numeric_scalars"].times(), [5])
        assert np.array_equal(result_5["numeric_scalars"].values(0), [1005])
        assert np.array_equal(result_5["numeric_scalars"].values(1), [105])
        assert np.array_equal(result_5["text_scalars_1"].times(), [5])
        assert np.array_equal(result_5["text_scalars_1"].values(), ["five"])
        assert np.array_equal(result_5["text_scalars_2"].times(), [5])
        assert np.array_equal(result_5["text_scalars_2"].values(), ["f"])
        assert np.array_equal(result_5["numeric_lists"].times(), [5.0, 5.1, 5.2])
        assert np.array_equal(result_5["numeric_lists"].values(0), [15, 16, 17])
        assert np.array_equal(result_5["numeric_lists"].values(1), [-15, -16, -17])

        result_6 = reader.read_next()
        assert np.array_equal(result_6["times_only"].times(), [6])
        assert np.array_equal(result_6["numeric_scalars"].times(), [6])
        assert np.array_equal(result_6["numeric_scalars"].values(0), [1006])
        assert np.array_equal(result_6["numeric_scalars"].values(1), [106])
        assert np.array_equal(result_6["text_scalars_1"].times(), [6])
        assert np.array_equal(result_6["text_scalars_1"].values(), ["six"])
        assert np.array_equal(result_6["text_scalars_2"].times(), [6])
        assert np.array_equal(result_6["text_scalars_2"].values(), ["g"])
        assert np.array_equal(result_6["numeric_lists"].times(), [6.0, 6.1, 6.2])
        assert np.array_equal(result_6["numeric_lists"].values(0), [18, 19, 20])
        assert np.array_equal(result_6["numeric_lists"].values(1), [-18, -19, -20])

        result_7 = reader.read_next()
        assert np.array_equal(result_7["times_only"].times(), [7])
        assert np.array_equal(result_7["numeric_scalars"].times(), [7])
        assert np.array_equal(result_7["numeric_scalars"].values(0), [1007])
        assert np.array_equal(result_7["numeric_scalars"].values(1), [107])
        assert np.array_equal(result_7["text_scalars_1"].times(), [7])
        assert np.array_equal(result_7["text_scalars_1"].values(), ["seven"])
        assert np.array_equal(result_7["text_scalars_2"].times(), [7])
        assert np.array_equal(result_7["text_scalars_2"].values(), ["h"])
        assert np.array_equal(result_7["numeric_lists"].times(), [7.0, 7.1, 7.2])
        assert np.array_equal(result_7["numeric_lists"].values(0), [21, 22, 23])
        assert np.array_equal(result_7["numeric_lists"].values(1), [-21, -22, -23])

        result_8 = reader.read_next()
        assert np.array_equal(result_8["times_only"].times(), [8])
        assert np.array_equal(result_8["numeric_scalars"].times(), [8])
        assert np.array_equal(result_8["numeric_scalars"].values(0), [1008])
        assert np.array_equal(result_8["numeric_scalars"].values(1), [108])
        assert np.array_equal(result_8["text_scalars_1"].times(), [8])
        assert np.array_equal(result_8["text_scalars_1"].values(), ["eight"])
        assert np.array_equal(result_8["text_scalars_2"].times(), [8])
        assert np.array_equal(result_8["text_scalars_2"].values(), ["i"])
        assert np.array_equal(result_8["numeric_lists"].times(), [8.0, 8.1, 8.2])
        assert np.array_equal(result_8["numeric_lists"].values(0), [24, 25, 26])
        assert np.array_equal(result_8["numeric_lists"].values(1), [-24, -25, -26])

        result_9 = reader.read_next()
        assert np.array_equal(result_9["times_only"].times(), [9])
        assert np.array_equal(result_9["numeric_scalars"].times(), [9])
        assert np.array_equal(result_9["numeric_scalars"].values(0), [1009])
        assert np.array_equal(result_9["numeric_scalars"].values(1), [109])
        assert np.array_equal(result_9["text_scalars_1"].times(), [9])
        assert np.array_equal(result_9["text_scalars_1"].values(), ["nine"])
        assert np.array_equal(result_9["text_scalars_2"].times(), [9])
        assert np.array_equal(result_9["text_scalars_2"].values(), ["j"])
        assert np.array_equal(result_9["numeric_lists"].times(), [9.0, 9.1, 9.2])
        assert np.array_equal(result_9["numeric_lists"].values(0), [27, 28, 29])
        assert np.array_equal(result_9["numeric_lists"].values(1), [-27, -28, -29])

        # ...then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert all([reader.reader.file_stream is None for reader in reader.readers])
