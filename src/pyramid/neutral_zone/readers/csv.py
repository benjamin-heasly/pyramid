from types import TracebackType
from ast import literal_eval
from typing import Self
import logging
import csv
import numpy as np

from pyramid.file_finder import FileFinder
from pyramid.model.model import BufferData
from pyramid.model.events import NumericEventList, TextEventList
from pyramid.model.signals import SignalChunk
from pyramid.neutral_zone.readers.readers import Reader


class CsvReader():
    """A shared util to iterate through rows of a CSV, manage context state, etc."""

    def __init__(
        self,
        csv_file: str = None,
        first_row_is_header: bool = False,
        column_selector: list[str | int] = None,
        dialect: str = 'excel',
        **fmtparams
    ) -> None:
        self.csv_file = csv_file
        self.first_row_is_header = first_row_is_header
        self.column_selector = column_selector
        self.dialect = dialect
        self.fmtparams = fmtparams

        self.file_stream = None
        self.csv_reader = None
        self.first_row = None
        self.column_indices = None

    def __eq__(self, other: object) -> bool:
        """Compare CsvReaders field-wise, to support use of this class in tests."""
        if isinstance(other, self.__class__):
            return (
                self.csv_file == other.csv_file
                and self.first_row_is_header == other.first_row_is_header
                and self.column_selector == other.column_selector
                and self.dialect == other.dialect
                and self.fmtparams == other.fmtparams
            )
        else:  # pragma: no cover
            return False

    def __enter__(self) -> Self:
        # See https://docs.python.org/3/library/csv.html#id3 for why this has newline=''
        # The encoding "utf-8-sig" means treat as utf-8, and ignore any (discouraged!) BOM prefix bytes.
        # https://docs.python.org/3/library/codecs.html
        self.file_stream = open(self.csv_file, mode='r', newline='', encoding='utf-8-sig')
        self.csv_reader = csv.reader(self.file_stream, self.dialect, **self.fmtparams)
        if (self.first_row_is_header):
            try:
                # Consume the first row as column headers.
                self.first_row = self.csv_reader.__next__()
                self.find_columns()
            except StopIteration:
                logging.warning(f"No first row to read in CSV file {self.csv_file}", exc_info=True)

        return self

    def __exit__(
        self,
        __exc_type: type[BaseException] | None,
        __exc_value: BaseException | None,
        __traceback: TracebackType | None
    ) -> bool | None:
        if self.file_stream:
            self.file_stream.close()
            self.file_stream = None
        self.csv_reader = None

    def find_column(self, column):
        if self.first_row and isinstance(column, str):
            return self.first_row.index(column)
        else:
            return column

    def find_columns(self):
        if self.column_selector is None:
            self.column_indices = None
            return

        self.column_indices = [self.find_column(column) for column in self.column_selector]

    def select_columns(self, row):
        if self.column_indices is None:
            return row
        else:
            return [row[index] for index in self.column_indices]

    def peek_first(self) -> list[str]:
        """Open the CSV, peek at the first line, then close it.

        This is useful to discover header data before opening the context for reading.
        """
        try:
            with open(self.csv_file, mode='r', newline='', encoding='utf-8-sig') as f:
                reader = csv.reader(f, self.dialect, **self.fmtparams)
                self.first_row = reader.__next__()
                self.find_columns()
                return self.select_columns(self.first_row)
        except Exception:
            logging.warning(f"Unable to peek at CSV file {self.csv_file}", exc_info=True)
            return []

    def next(self) -> list[str]:
        """Read the next line of the CSV, or throw StopIteration."""
        next_row = self.csv_reader.__next__()
        return self.select_columns(next_row)


class CsvNumericEventReader(Reader):
    """Read numeric events from a CSV of numbers.

    Skips lines that contain non-numeric values.
    """

    def __init__(
        self,
        csv_file: str = None,
        file_finder: FileFinder = FileFinder(),
        first_row_is_header: bool = False,
        column_selector: list[str | int] = None,
        result_name: str = "events",
        unpack_lists: bool = False,
        dialect: str = 'excel',
        **fmtparams
    ) -> None:
        self.reader = CsvReader(file_finder.find(csv_file), first_row_is_header, column_selector, dialect, **fmtparams)
        self.result_name = result_name
        self.unpack_lists = unpack_lists

    def __eq__(self, other: object) -> bool:
        """Compare CSV readers field-wise, to support use of this class in tests."""
        if isinstance(other, self.__class__):
            return (
                self.reader == other.reader
                and self.result_name == other.result_name
                and self.unpack_lists == other.unpack_lists
            )
        else:
            return False

    def __enter__(self) -> Self:
        self.reader.__enter__()
        return self

    def __exit__(
        self,
        __exc_type: type[BaseException] | None,
        __exc_value: BaseException | None,
        __traceback: TracebackType | None
    ) -> bool | None:
        return self.reader.__exit__(__exc_type, __exc_value, __traceback)

    def parse_row(self, row) -> np.ndarray:
        # The row is a list of strings, one per column.
        if self.unpack_lists:
            # Get multiple events from this row.
            # Parse each string as a *list* of floats.
            unpacked_row = [literal_eval(element) for element in row]
            if isinstance(unpacked_row[0], list):
                # Assume all columns in this row are lists of the same size.
                # They come from the CSV like [[time, time, time], [value, value, value]]
                # Transpose these to event list format like [[time, value], [time, value], [time, value]]
                return np.array(unpacked_row).T
            else:
                # Get one event from this row, after all.
                # Assume all columns in this row are scalars.
                return np.array([unpacked_row])
        else:
            # Get one event from this row.
            # Parse each string as a scalar float.
            numeric_row = [float(element) for element in row]
            return np.array([numeric_row])

    def read_next(self) -> dict[str, NumericEventList]:
        line_num = self.reader.csv_reader.line_num
        next_row = self.reader.next()
        try:
            parsed_row = self.parse_row(next_row)
            return {
                self.result_name: NumericEventList(parsed_row)
            }
        except ValueError as error:
            logging.info(f"Skipping CSV '{self.reader.csv_file}' line {line_num} {next_row} because {error.args}")
            return None

    def get_initial(self) -> dict[str, NumericEventList]:
        first_row = self.reader.peek_first()
        if first_row:
            column_count = len(first_row)
        else:
            column_count = 2
            logging.warning("Using default column count for CSV events: {column_count}")

        return {
            self.result_name: NumericEventList.empty(column_count - 1)
        }


class CsvTextEventReader(Reader):
    """Read text events from a CSV."""

    def __init__(
        self,
        csv_file: str = None,
        file_finder: FileFinder = FileFinder(),
        first_row_is_header: bool = False,
        column_selector: list[str | int] = None,
        result_name: str = "events",
        unpack_lists: bool = False,
        dialect: str = 'excel',
        **fmtparams
    ) -> None:
        self.reader = CsvReader(file_finder.find(csv_file), first_row_is_header, column_selector, dialect, **fmtparams)
        self.result_name = result_name
        self.unpack_lists = unpack_lists

    def __eq__(self, other: object) -> bool:
        """Compare CSV readers field-wise, to support use of this class in tests."""
        if isinstance(other, self.__class__):
            return (
                self.reader == other.reader
                and self.result_name == other.result_name
                and self.unpack_lists == other.unpack_lists
            )
        else:
            return False

    def __enter__(self) -> Self:
        self.reader.__enter__()
        return self

    def __exit__(
        self,
        __exc_type: type[BaseException] | None,
        __exc_value: BaseException | None,
        __traceback: TracebackType | None
    ) -> bool | None:
        return self.reader.__exit__(__exc_type, __exc_value, __traceback)

    def parse_row(self, row) -> tuple[np.ndarray, np.ndarray]:
        # The row is a pair of strings, one from the timestamp column, one from the text column.
        if self.unpack_lists:
            # Get multiple events from this row.
            # Parse the string from each column as a *list* of floats or text values.
            unpacked_row = [literal_eval(element) for element in row]
            if isinstance(unpacked_row[1], list):
                # The text column has a list of values.
                text_data = np.array(unpacked_row[1], dtype=np.str_)
                if isinstance(unpacked_row[0], list):
                    # The timestamp column has a list of (corresponding!!) timestamps.
                    timestamp_data = np.array(unpacked_row[0])
                    return (timestamp_data, text_data)
                else:
                    # The timestamp column has a scalar to reuse across all text values.
                    timestamp = unpacked_row[0]
                    timestamp_data = np.full_like(text_data, timestamp, dtype=np.float64)
                    return (timestamp_data, text_data)
            else:
                # The text column was not a list, get one event from this row after all.
                return (np.array([unpacked_row[0]]), np.array([unpacked_row[1]], dtype=np.str_))
        else:
            # Get one event from this row.
            # Parse the first string as a scalar float, take the second string as a text value.
            timestamp = float(row[0])
            text = row[1]
            return (np.array([timestamp]), np.array([text], dtype=np.str_))

    def read_next(self) -> dict[str, TextEventList]:
        line_num = self.reader.csv_reader.line_num
        next_row = self.reader.next()
        try:
            (timestamp_data, text_data) = self.parse_row(next_row)
            return {
                self.result_name: TextEventList(timestamp_data, text_data)
            }
        except ValueError as error:
            logging.info(f"Skipping CSV '{self.reader.csv_file}' line {line_num} {next_row} because {error.args}")
            return None

    def get_initial(self) -> dict[str, TextEventList]:
        self.reader.peek_first()
        return {
            self.result_name: TextEventList.empty()
        }


class CsvSignalReader(Reader):
    """Read numeric signals from a CSV of numbers.

    By default the first line should be a header with channel ids.
    Skips any other lines that contain non-numeric values.
    Channel ids can also be provided explicitly to the constructor.
    """

    def __init__(
        self,
        csv_file: str = None,
        file_finder: FileFinder = FileFinder(),
        first_row_is_header: bool = True,
        column_selector: list[str | int] = None,
        sample_frequency: float = 1.0,
        next_sample_time: float = 0.0,
        lines_per_chunk: int = 10,
        result_name: str = "samples",
        channel_ids: list[str | int] = None,
        unpack_lists: bool = False,
        dialect: str = 'excel',
        **fmtparams
    ) -> None:
        self.reader = CsvReader(file_finder.find(csv_file), first_row_is_header, column_selector, dialect, **fmtparams)
        self.sample_frequency = sample_frequency
        self.next_sample_time = next_sample_time
        self.lines_per_chunk = lines_per_chunk
        self.result_name = result_name
        self.channel_ids = channel_ids
        self.unpack_lists = unpack_lists

    def __enter__(self) -> Self:
        self.reader.__enter__()
        if self.channel_ids is None:
            self.channel_ids = self.reader.select_columns(self.reader.first_row)
        return self

    def __exit__(
        self,
        __exc_type: type[BaseException] | None,
        __exc_value: BaseException | None,
        __traceback: TracebackType | None
    ) -> bool | None:
        return self.reader.__exit__(__exc_type, __exc_value, __traceback)

    def parse_row(self, row) -> np.ndarray:
        # The row is a list of strings, one per column.
        if self.unpack_lists:
            # Get multiple signal samples from this row.
            # Parse each string as a *list* of floats.
            unpacked_row = [literal_eval(element) for element in row]
            if isinstance(unpacked_row[0], list):
                # Assume all columns in this row are lists of the same size.
                # They come from the CSV like [[chan_a, chan_a, chan_a], [chan_b, chan_b, chan_b]]
                # Transpose these to signal chunk format like [[chan_a, chan_b], [chan_a, chan_b], [chan_a, chan_b]]
                return np.array(unpacked_row).T
            else:
                # Get one sample from this row, after all.
                # Assume all columns in this row are scalars.
                return np.array([unpacked_row])
        else:
            # Get one sample from this row.
            # Parse each string as a scalar float.
            numeric_row = [float(element) for element in row]
            return np.array([numeric_row])

    def read_next(self) -> dict[str, SignalChunk]:
        parsed_lines = []
        while len(parsed_lines) < self.lines_per_chunk:
            line_num = self.reader.csv_reader.line_num
            try:
                next_row = self.reader.next()
            except StopIteration:
                # We reached the end.  We still want to return the last, partial chunk below.
                break

            try:
                parsed_lines.append(self.parse_row(next_row))
            except ValueError as error:
                logging.info(f"Skipping CSV '{self.reader.csv_file}' line {line_num} {next_row} because {error.args}")
                continue

        if parsed_lines:
            # We got a complete chunk, or the last, partial chunk.
            signal_chunk = SignalChunk(
                np.concatenate(parsed_lines),
                self.sample_frequency,
                self.next_sample_time,
                self.channel_ids
            )
            self.next_sample_time += signal_chunk.sample_count() / self.sample_frequency
            return {self.result_name: signal_chunk}
        else:
            # We're really at the end, past the last chunk, signal stop to the caller.
            raise StopIteration

    def get_initial(self) -> dict[str, SignalChunk]:
        self.reader.peek_first()
        if self.channel_ids is None:
            self.channel_ids = self.reader.select_columns(self.reader.first_row)
        initial = SignalChunk.empty(self.sample_frequency, self.next_sample_time, self.channel_ids)
        return {self.result_name: initial}


class WideCsvEventReader(Reader):
    """Read various numeric and text events from columns of a "wide" CSV.

    This reader creates multiple CsvNumericEventReaders and CsvTextEventReaders from a common CSV file.
    This is intended as a convenience for working with "wide" CSVs that have many columns of data of
    various interpretations and non-homogenious data types.

    From such a CSV you might want to identify and extract several distinct buffers of data, for example:
     - timestamps from one numeric column
     - timestamp-number tuples from other numeric columns
     - timestamp-text tuples from another numeric column and a string column
     - *lists* of timestamps and values packed into the cells of two other columns

    The PsychoPy "long-wide" output format is one example of a "wide" CSV with columns like these, which
    WideCsvEventReader supports.
    """

    def __init__(
        self,
        csv_file: str = None,
        file_finder: FileFinder = FileFinder(),
        first_row_is_header: bool = True,
        column_config: dict[str, dict[str, str]] = {},
        dialect: str = 'excel',
        **fmtparams
    ) -> None:
        self.readers = []
        for result_name, config in column_config.items():
            numeric = config.get("numeric", False)
            unpack_lists = config.get("unpack_lists", False)
            column_selector = config.get("column_selector", [])
            if numeric:
                reader = CsvNumericEventReader(
                    csv_file,
                    file_finder,
                    first_row_is_header,
                    column_selector,
                    result_name,
                    unpack_lists,
                    dialect,
                    **fmtparams
                )
                self.readers.append(reader)
            else:
                reader = CsvTextEventReader(
                    csv_file,
                    file_finder,
                    first_row_is_header,
                    column_selector,
                    result_name,
                    unpack_lists,
                    dialect,
                    **fmtparams
                )
                self.readers.append(reader)

    def __enter__(self) -> Self:
        for reader in self.readers:
            reader.__enter__()
        return self

    def __exit__(
        self,
        __exc_type: type[BaseException] | None,
        __exc_value: BaseException | None,
        __traceback: TracebackType | None
    ) -> bool | None:
        results = [reader.__exit__(__exc_type, __exc_value, __traceback) for reader in self.readers]
        return all(results)

    def get_initial(self) -> dict[str, BufferData]:
        initial = {}
        for reader in self.readers:
            for result_name, data in reader.get_initial().items():
                initial[result_name] = data
        return initial

    def read_next(self) -> dict[str, BufferData]:
        # Read until any of the nested readers throws an exception.
        # For StopIteration this works out naturally since all readers are reading the same CSV in step.
        # For errors this means all nested readers will appear to error as one, and get ignored as one.
        next = {}
        for reader in self.readers:
            for result_name, data in reader.read_next().items():
                next[result_name] = data
        return next
