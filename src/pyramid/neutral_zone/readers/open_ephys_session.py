from types import TracebackType
from ast import literal_eval
from typing import Self
import logging

import numpy as np
from open_ephys.analysis import Session

from pyramid.file_finder import FileFinder
from pyramid.model.model import BufferData
from pyramid.model.events import NumericEventList, TextEventList
from pyramid.model.signals import SignalChunk
from pyramid.neutral_zone.readers.readers import Reader


class OpenEphysSessionSignalReader(Reader):
    """Read continuous data from an Open Ephys session.

    This is based on the Open Ephys Python Tools Analysis module:
    https://github.com/open-ephys/open-ephys-python-tools/blob/main/src/open_ephys/analysis/README.md

    Args:
        session_dir:        Directory for Open Ephys Python Tools to seach for saved data (Open Ephys Binary or NWB2 format)
        file_finder:        Utility to find() files in the conigured Pyramid configured search path.
                            Pyramid will automatically create and pass in the file_finder for you.
        stream_name:        Which Open Ephys data stream to select for reading.
        channel_names:      List of channel names to keep within the selected data stream (default None, take all channels).
        record_node_index:  When session_dir contains record node subdirs, which node/dir to pick (default -1, the last one).
        recording_index:    When which recording to pick within a record node (default -1, the last one).
        result_name:        Name to use for the Pyramid SignalChunk results (default None, use the stream_name).
        samples_per_chunk:  How many signal samples (time steps across all channels) to take per read_next() (default 10000).
    """

    def __init__(
        self,
        session_dir: str,
        file_finder: FileFinder = FileFinder(),
        stream_name: str = None,
        channel_names: list[str] = None,
        record_node_index: int = -1,
        recording_index: int = -1,
        result_name: str = None,
        samples_per_chunk: int = 10000
    ) -> None:
        self.session_dir = file_finder.find(session_dir)
        self.stream_name = stream_name
        self.channel_names = channel_names
        self.record_node_index = record_node_index
        self.recording_index = recording_index
        self.result_name = result_name
        self.samples_per_chunk = samples_per_chunk

        self.session = None
        self.record_node = None
        self.recording = None
        self.continuous = None
        self.channel_ids = None
        self.channel_indexes = None
        self.next_sample = 0
        self.total_samples = None

    def __enter__(self) -> Self:
        self.session = Session(self.session_dir)
        if self.record_node_index is None:
            self.recording = self.session.recordings[self.recording_index]
        else:
            self.record_node = self.session.recordnodes[self.record_node_index]
            self.recording = self.record_node.recordings[self.recording_index]
        self.pick_stream()
        return self

    def __exit__(
        self,
        __exc_type: type[BaseException] | None,
        __exc_value: BaseException | None,
        __traceback: TracebackType | None
    ) -> bool | None:
        self.session = None
        self.record_node = None
        self.recording = None
        self.continuous = None
        return None

    def pick_stream(self) -> None:
        # Pick a continuous data object by name.
        if self.stream_name is None:
            self.continuous = self.recording.continuous[0]
        else:
            for continuous in self.recording.continuous:
                if continuous.metadata["stream_name"] == self.stream_name:
                    self.continuous = continuous

        # Pick a set of channels to keep, by name.
        if "channel_names" in self.continuous.metadata:
            all_names = self.continuous.metadata["channel_names"]
        else:
            # It seems the NWB format doesn't fill in explicit channel names.
            all_names = [f"CH{index+1}" for index in range(self.continuous.metadata['num_channels'])]
        if self.channel_names is None:
            # Default to all channels.
            self.channel_ids = all_names
            self.channel_indexes = list(range(self.continuous.metadata['num_channels']))
        else:
            self.channel_ids = self.channel_names
            self.channel_indexes = [all_names.index(name) for name in self.channel_names]

        # Default result buffer name is the name of the stream.
        if self.result_name is None:
            self.result_name = self.continuous.metadata["stream_name"]

        # Look ahead to know when to stop reading.
        self.total_samples = self.continuous.sample_numbers.size

    def get_initial(self) -> dict[str, BufferData]:
        self.pick_stream()
        return {
            self.result_name: SignalChunk.empty(
                sample_frequency=self.continuous.metadata['sample_rate'],
                channel_ids=self.channel_ids
            )
        }

    def read_next(self) -> dict[str, BufferData]:
        if self.next_sample >= self.total_samples:
            # The previous read exhausted the signal data -- all done.
            raise StopIteration

        # Read a full chunk, or up to the end of the signal.
        first_sample_time = self.continuous.timestamps[self.next_sample]
        samples = self.continuous.get_samples(
            self.next_sample,
            self.next_sample + self.samples_per_chunk,
            self.channel_indexes
        )
        self.next_sample += samples.shape[0]
        return {
            self.result_name: SignalChunk(
                sample_data=samples,
                sample_frequency=self.continuous.metadata['sample_rate'],
                first_sample_time=first_sample_time,
                channel_ids=self.channel_ids
            )
        }
