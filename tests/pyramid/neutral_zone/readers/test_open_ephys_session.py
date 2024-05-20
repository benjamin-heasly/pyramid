from pathlib import Path

import numpy as np
from pytest import fixture, raises

from pyramid.model.events import NumericEventList, TextEventList
from pyramid.model.signals import SignalChunk
from pyramid.neutral_zone.readers.open_ephys_session import OpenEphysSessionSignalReader, OpenEphysSessionNumericEventReader

# TODO: test calling get_initial() before entering context!


@fixture
def binary_session_path(request):
    this_file = Path(request.module.__file__)
    return Path(this_file.parent, 'fixture_files', 'open_ephys_sessions', '2024-05-17_10-53-50')


@fixture
def nwb_session_path(request):
    this_file = Path(request.module.__file__)
    return Path(this_file.parent, 'fixture_files', 'open_ephys_sessions', '2024-05-17_10-59-28')


expected_signal_sample_frequency = 40000.0

expected_signal_first_sample = np.array([
    -17.350000258535147,
    -17.900000266730785,
    -62.65000093355775,
    -49.55000073835254,
    -31.050000462681055,
    -38.250000569969416,
    0.3500000052154064,
    -9.300000138580799,
    -25.7500003837049,
    -34.1000005081296,
    -51.10000076144934,
    -88.55000131949782,
    -37.15000055357814,
    -36.15000053867698,
    -50.150000747293234,
    -43.30000064522028,
])

expected_signal_channel_ids = [
    'CH1',
    'CH2',
    'CH3',
    'CH4',
    'CH5',
    'CH6',
    'CH7',
    'CH8',
    'CH9',
    'CH10',
    'CH11',
    'CH12',
    'CH13',
    'CH14',
    'CH15',
    'CH16'
]


def test_signal_locate_binary_format(binary_session_path):
    # Load the whole session folder with potentially multiple record nodes.
    with OpenEphysSessionSignalReader(binary_session_path) as reader:
        assert reader.recording.format == 'binary'
        assert reader.result_name == "example_data"
        assert reader.total_samples == 296032
        assert reader.get_initial() == {
            reader.result_name: SignalChunk.empty(
                sample_frequency=expected_signal_sample_frequency,
                channel_ids=expected_signal_channel_ids
            )
        }

    assert reader.recording is None

    # Load the folder for one specific record node.
    record_node_path = Path(binary_session_path, 'Record Node 105')
    with OpenEphysSessionSignalReader(record_node_path, record_node_index=None) as reader:
        assert reader.result_name == "example_data"
        assert reader.total_samples == 296032
        assert reader.get_initial() == {
            reader.result_name: SignalChunk.empty(
                sample_frequency=expected_signal_sample_frequency,
                channel_ids=expected_signal_channel_ids
            )
        }

    assert reader.recording is None


def test_signal_default_read_binary_format(binary_session_path):
    with OpenEphysSessionSignalReader(binary_session_path) as reader:
        assert reader.recording.format == 'binary'
        assert reader.result_name == "example_data"
        assert reader.total_samples == 296032
        assert reader.get_initial() == {
            reader.result_name: SignalChunk.empty(
                sample_frequency=expected_signal_sample_frequency,
                channel_ids=expected_signal_channel_ids
            )
        }

        assert reader.next_sample == 0

        # Spot check the first read.
        first = reader.read_next()
        assert first.keys() == {"example_data"}
        first_chunk = first["example_data"]
        assert first_chunk.sample_data.shape == (10000, 16)
        first_sample = first_chunk.sample_data[0, :]
        assert np.array_equal(first_sample, expected_signal_first_sample)
        assert first_chunk.sample_frequency == expected_signal_sample_frequency
        assert first_chunk.first_sample_time == 0.0
        assert first_chunk.channel_ids == expected_signal_channel_ids

        assert reader.next_sample == 10000

        # Get many complete reads in the middle.
        for read_index in range(28):
            next = reader.read_next()
            assert next.keys() == {"example_data"}
            next_chunk = next["example_data"]
            assert next_chunk.sample_data.shape == (10000, 16)
            assert next_chunk.sample_frequency == expected_signal_sample_frequency
            assert next_chunk.channel_ids == expected_signal_channel_ids

            assert reader.next_sample == (read_index + 2) * 10000

        # Spot check the last, smaller read.
        last = reader.read_next()
        assert last.keys() == {"example_data"}
        last_chunk = last["example_data"]
        assert last_chunk.sample_data.shape == (6032, 16)
        assert last_chunk.sample_frequency == expected_signal_sample_frequency
        assert last_chunk.channel_ids == expected_signal_channel_ids

        assert reader.next_sample == reader.total_samples

        # Then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.recording is None


def test_signal_custom_read_binary_format(binary_session_path):
    # Specify the stream name explicitly.
    stream_name = "example_data"

    # Read selected channels, out of order.
    selected_channel_names = ['CH16', 'CH2', 'CH3']
    selected_first_sample = np.array([
        -43.30000064522028,
        -17.900000266730785,
        -62.65000093355775,
    ])

    # Use a non-default result buffer name.
    result_name = "my_signal"

    # Do 32 reads of 9251 samples each -- with no remainder on the last read.
    samples_per_chunk = 9251
    with OpenEphysSessionSignalReader(
        binary_session_path,
        stream_name=stream_name,
        channel_names=selected_channel_names,
        result_name=result_name,
        samples_per_chunk=samples_per_chunk
    ) as reader:
        assert reader.recording.format == 'binary'
        assert reader.result_name == result_name
        assert reader.total_samples == 296032
        assert reader.get_initial() == {
            reader.result_name: SignalChunk.empty(
                sample_frequency=expected_signal_sample_frequency,
                channel_ids=selected_channel_names
            )
        }

        assert reader.next_sample == 0

        # Spot check the first read.
        first = reader.read_next()
        assert first.keys() == {result_name}
        first_chunk = first[result_name]
        assert first_chunk.sample_data.shape == (samples_per_chunk, 3)
        first_sample = first_chunk.sample_data[0, :]
        assert np.array_equal(first_sample, selected_first_sample)
        assert first_chunk.sample_frequency == expected_signal_sample_frequency
        assert first_chunk.first_sample_time == 0.0
        assert first_chunk.channel_ids == selected_channel_names

        assert reader.next_sample == samples_per_chunk

        # Get 31 more complete reads
        for read_index in range(31):
            next = reader.read_next()
            assert next.keys() == {result_name}
            next_chunk = next[result_name]
            assert next_chunk.sample_data.shape == (samples_per_chunk, 3)
            assert next_chunk.sample_frequency == expected_signal_sample_frequency
            assert next_chunk.channel_ids == selected_channel_names

            assert reader.next_sample == (read_index + 2) * samples_per_chunk

        assert reader.next_sample == reader.total_samples

        # Then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.recording is None


def test_signal_locate_nwb_format(nwb_session_path):
    # Load the whole session folder with potentially multiple record nodes.
    with OpenEphysSessionSignalReader(nwb_session_path) as reader:
        assert reader.recording.format == 'nwb'
        assert reader.result_name == "example_data"
        assert reader.total_samples == 296960
        assert reader.get_initial() == {
            reader.result_name: SignalChunk.empty(
                sample_frequency=expected_signal_sample_frequency,
                channel_ids=expected_signal_channel_ids
            )
        }

    assert reader.recording is None

    # Load the folder for one specific record node.
    record_node_path = Path(nwb_session_path, 'Record Node 106')
    with OpenEphysSessionSignalReader(record_node_path, record_node_index=None) as reader:
        assert reader.recording.format == 'nwb'
        assert reader.result_name == "example_data"
        assert reader.total_samples == 296960
        assert reader.get_initial() == {
            reader.result_name: SignalChunk.empty(
                sample_frequency=expected_signal_sample_frequency,
                channel_ids=expected_signal_channel_ids
            )
        }

    assert reader.recording is None


def test_signal_default_read_nwb_format(nwb_session_path):
    with OpenEphysSessionSignalReader(nwb_session_path) as reader:
        assert reader.recording.format == 'nwb'
        assert reader.result_name == "example_data"
        assert reader.total_samples == 296960
        assert reader.get_initial() == {
            reader.result_name: SignalChunk.empty(
                sample_frequency=expected_signal_sample_frequency,
                channel_ids=expected_signal_channel_ids
            )
        }

        assert reader.next_sample == 0

        # Spot check the first read.
        first = reader.read_next()
        assert first.keys() == {"example_data"}
        first_chunk = first["example_data"]
        assert first_chunk.sample_data.shape == (10000, 16)
        first_sample = first_chunk.sample_data[0, :]
        assert np.array_equal(first_sample, expected_signal_first_sample)
        assert first_chunk.sample_frequency == expected_signal_sample_frequency
        assert first_chunk.first_sample_time == 0.0
        assert first_chunk.channel_ids == expected_signal_channel_ids

        assert reader.next_sample == 10000

        # Get many complete reads in the middle.
        for read_index in range(28):
            next = reader.read_next()
            assert next.keys() == {"example_data"}
            next_chunk = next["example_data"]
            assert next_chunk.sample_data.shape == (10000, 16)
            assert next_chunk.sample_frequency == expected_signal_sample_frequency
            assert next_chunk.channel_ids == expected_signal_channel_ids

            assert reader.next_sample == (read_index + 2) * 10000

        # Spot check the last, smaller read.
        last = reader.read_next()
        assert last.keys() == {"example_data"}
        last_chunk = last["example_data"]
        assert last_chunk.sample_data.shape == (6960, 16)
        assert last_chunk.sample_frequency == expected_signal_sample_frequency
        assert last_chunk.channel_ids == expected_signal_channel_ids

        assert reader.next_sample == reader.total_samples

        # Then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.recording is None


def test_signal_custom_read_nwb_format(nwb_session_path):
    # Specify the stream name explicitly.
    stream_name = "example_data"

    # Read selected channels, out of order.
    selected_channel_names = ['CH16', 'CH2', 'CH3']
    selected_first_sample = np.array([
        -43.30000064522028,
        -17.900000266730785,
        -62.65000093355775,
    ])

    # Use a non-default result buffer name.
    result_name = "my_signal"

    # Do 29 reads of 10240 samples each -- with no remainder on the last read.
    samples_per_chunk = 10240
    with OpenEphysSessionSignalReader(
        nwb_session_path,
        stream_name=stream_name,
        channel_names=selected_channel_names,
        result_name=result_name,
        samples_per_chunk=samples_per_chunk
    ) as reader:
        assert reader.recording.format == 'nwb'
        assert reader.result_name == result_name
        assert reader.total_samples == 296960
        assert reader.get_initial() == {
            reader.result_name: SignalChunk.empty(
                sample_frequency=expected_signal_sample_frequency,
                channel_ids=selected_channel_names
            )
        }

        assert reader.next_sample == 0

        # Spot check the first read.
        first = reader.read_next()
        assert first.keys() == {result_name}
        first_chunk = first[result_name]
        assert first_chunk.sample_data.shape == (samples_per_chunk, 3)
        first_sample = first_chunk.sample_data[0, :]
        assert np.array_equal(first_sample, selected_first_sample)
        assert first_chunk.sample_frequency == expected_signal_sample_frequency
        assert first_chunk.first_sample_time == 0.0
        assert first_chunk.channel_ids == selected_channel_names

        assert reader.next_sample == samples_per_chunk

        # Get 28 more complete reads
        for read_index in range(28):
            next = reader.read_next()
            assert next.keys() == {result_name}
            next_chunk = next[result_name]
            assert next_chunk.sample_data.shape == (samples_per_chunk, 3)
            assert next_chunk.sample_frequency == expected_signal_sample_frequency
            assert next_chunk.channel_ids == selected_channel_names

            assert reader.next_sample == (read_index + 2) * samples_per_chunk

        assert reader.next_sample == reader.total_samples

        # Then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.recording is None


def test_numeric_events_locate_binary_format(binary_session_path):
    # Load the whole session folder with potentially multiple record nodes.
    with OpenEphysSessionNumericEventReader(binary_session_path) as reader:
        assert reader.recording.format == 'binary'
        assert reader.result_name == "ttl"
        assert reader.get_initial() == {
            reader.result_name: NumericEventList.empty(3)
        }

    assert reader.recording is None

    # Load the folder for one specific record node.
    record_node_path = Path(binary_session_path, 'Record Node 105')
    with OpenEphysSessionNumericEventReader(record_node_path, record_node_index=None) as reader:
        assert reader.recording.format == 'binary'
        assert reader.result_name == "ttl"
        assert reader.get_initial() == {
            reader.result_name: NumericEventList.empty(3)
        }

    assert reader.recording is None


def test_numeric_events_default_read_binary_format(binary_session_path):
    with OpenEphysSessionNumericEventReader(binary_session_path) as reader:
        assert reader.recording.format == 'binary'
        assert reader.result_name == "ttl"
        assert reader.get_initial() == {
            reader.result_name: NumericEventList.empty(3)
        }

        # Spot check the first event.
        first = reader.read_next()
        assert first.keys() == {reader.result_name}
        first_event = first[reader.result_name]
        assert first_event.times() == [1.9952]
        assert first_event.values(0) == [4]
        assert first_event.values(1) == [0]
        assert first_event.values(2) == [101]

        # Read 28 more events in the middle.
        for _ in range(28):
            next = reader.read_next()
            assert next.keys() == {reader.result_name}
            next_event = next[reader.result_name]
            assert next_event.event_count() == 1

        # Spot check the last event.
        last = reader.read_next()
        assert last.keys() == {reader.result_name}
        last_event = last[reader.result_name]
        assert last_event.times() == [6.7931]
        assert last_event.values(0) == [1]
        assert last_event.values(1) == [0]
        assert last_event.values(2) == [100]

        # Then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.recording is None


def test_numeric_events_custom_read_binary_format(binary_session_path):
    # Only read from the "example_data" stream.
    stream_name = "example_data"

    # Use a custom Pyramid result buffer name.
    result_name = "my_events"
    with OpenEphysSessionNumericEventReader(
        binary_session_path,
        stream_name=stream_name,
        result_name=result_name
    ) as reader:
        assert reader.recording.format == 'binary'
        assert reader.result_name == result_name
        assert reader.get_initial() == {
            reader.result_name: NumericEventList.empty(3)
        }

        # Spot check the first event.
        first = reader.read_next()
        assert first.keys() == {reader.result_name}
        first_event = first[reader.result_name]
        assert first_event.times() == [1.9952]
        assert first_event.values(0) == [4]
        assert first_event.values(1) == [0]
        assert first_event.values(2) == [101]

        # Read 28 more events in the middle.
        for _ in range(28):
            next = reader.read_next()
            assert next.keys() == {reader.result_name}
            next_event = next[reader.result_name]
            assert next_event.event_count() == 1

        # Spot check the last event.
        last = reader.read_next()
        assert last.keys() == {reader.result_name}
        last_event = last[reader.result_name]
        assert last_event.times() == [6.7931]
        assert last_event.values(0) == [1]
        assert last_event.values(1) == [0]
        assert last_event.values(2) == [100]

        # Then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.recording is None


def test_numeric_events_locate_nwb_format(nwb_session_path):
    # Load the whole session folder with potentially multiple record nodes.
    with OpenEphysSessionNumericEventReader(nwb_session_path) as reader:
        assert reader.recording.format == 'nwb'
        assert reader.result_name == "ttl"
        assert reader.get_initial() == {
            reader.result_name: NumericEventList.empty(3)
        }

    assert reader.recording is None

    # Load the folder for one specific record node.
    record_node_path = Path(nwb_session_path, 'Record Node 106')
    with OpenEphysSessionNumericEventReader(record_node_path, record_node_index=None) as reader:
        assert reader.recording.format == 'nwb'
        assert reader.result_name == "ttl"
        assert reader.get_initial() == {
            reader.result_name: NumericEventList.empty(3)
        }

    assert reader.recording is None


def test_numeric_events_default_read_nwb_format(nwb_session_path):
    with OpenEphysSessionNumericEventReader(nwb_session_path) as reader:
        assert reader.recording.format == 'nwb'
        assert reader.result_name == "ttl"
        assert reader.get_initial() == {
            reader.result_name: NumericEventList.empty(3)
        }

        # Spot check the first event.
        first = reader.read_next()
        assert first.keys() == {reader.result_name}
        first_event = first[reader.result_name]
        assert first_event.times() == [1.693600]
        assert first_event.values(0) == [4]
        assert first_event.values(1) == [0]
        assert first_event.values(2) == [101]

        # Read 28 more events in the middle.
        for index in range(28):
            next = reader.read_next()
            assert next.keys() == {reader.result_name}
            next_event = next[reader.result_name]
            assert next_event.event_count() == 1

        # Spot check the last event.
        last = reader.read_next()
        assert last.keys() == {reader.result_name}
        last_event = last[reader.result_name]
        assert last_event.times() == [6.468150]
        assert last_event.values(0) == [1]
        assert last_event.values(1) == [0]
        assert last_event.values(2) == [100]

        # Then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.recording is None


def test_numeric_events_custom_read_nwb_format(nwb_session_path):
    # Only read from the "example_data" stream.
    stream_name = "example_data"

    # Use stream_name as the default result_name.
    result_name = None
    with OpenEphysSessionNumericEventReader(
        nwb_session_path,
        stream_name=stream_name,
        result_name=result_name
    ) as reader:
        assert reader.recording.format == 'nwb'
        assert reader.result_name == stream_name
        assert reader.get_initial() == {
            reader.result_name: NumericEventList.empty(3)
        }

        # Spot check the first event.
        first = reader.read_next()
        assert first.keys() == {reader.result_name}
        first_event = first[reader.result_name]
        assert first_event.times() == [1.693600]
        assert first_event.values(0) == [4]
        assert first_event.values(1) == [0]
        assert first_event.values(2) == [101]

        # Read 28 more events in the middle.
        for _ in range(28):
            next = reader.read_next()
            assert next.keys() == {reader.result_name}
            next_event = next[reader.result_name]
            assert next_event.event_count() == 1

        # Spot check the last event.
        last = reader.read_next()
        assert last.keys() == {reader.result_name}
        last_event = last[reader.result_name]
        assert last_event.times() == [6.468150]
        assert last_event.values(0) == [1]
        assert last_event.values(1) == [0]
        assert last_event.values(2) == [100]

        # Then be done.
        with raises(StopIteration) as exception_info:
            reader.read_next()
        assert exception_info.errisinstance(StopIteration)

    assert reader.recording is None
