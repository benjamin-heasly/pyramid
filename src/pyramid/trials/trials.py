from typing import Any
from dataclasses import dataclass, field
import logging

from pyramid.model.model import DynamicImport, Buffer, BufferData
from pyramid.model.events import NumericEventList, TextEventList
from pyramid.model.signals import SignalChunk


@dataclass
class Trial():
    """A delimited part of the timeline with named event, signal, and computed data from the same time range."""

    start_time: float
    """The begining of the trial in time, often the time of a delimiting event."""

    end_time: float
    """The end of the trial in time, often the time of the next delimiting event after start_time."""

    wrt_time: float = 0.0
    """The "zero" time subtracted from events and signals assigned to this trial, often between start_time and end_time."""

    numeric_events: dict[str, NumericEventList] = field(default_factory=dict)
    """Named lists of numeric events assigned to this trial."""

    text_events: dict[str, TextEventList] = field(default_factory=dict)
    """Named lists of text events assigned to this trial."""

    signals: dict[str, SignalChunk] = field(default_factory=dict)
    """Named signal chunks assigned to this trial."""

    enhancements: dict[str, Any] = field(default_factory=dict)
    """Name-data pairs, to add to the trial."""

    categories: dict[str, list[str]] = field(default_factory=dict)
    """Categories to use for enhancements or buffered data, like "id", "value", or "time"."""

    def add_buffer_data(self, name: str, data: BufferData) -> bool:
        """Add named data to this trial, of a specific buffer data type that requires conversion before writing."""
        if isinstance(data, NumericEventList):
            self.numeric_events[name] = data
            return True
        elif isinstance(data, TextEventList):
            self.text_events[name] = data
            return True
        elif isinstance(data, SignalChunk):
            self.signals[name] = data
            return True
        else:
            logging.warning(
                f"Data for name {name} not added to trial because class {data.__class__.__name__} is not supported.")
            return False

    def add_enhancement(self, name: str, data: Any, category: str = "value") -> bool:
        """Add a name-data pair to the trial.

        Enhancements are added to the trial as name-data pairs.  The names must be unique per trial.

        The names are grouped in categories that inform downstream utilities how to interpret the data, for example:
         - "value": (default) discrete or continuous score or metric like a distance, a duration, etc.
         - "id": nominal or ordinal label for the trial -- a key you might use to group or sort trials
         - "time": list of timestamps for when a named event occurred during the trial -- zero or more occurrences

        The given data should be of a simple type that doesn't require special conversion to/from file, for example:
         - str
         - int
         - float
         - list (can be nested)
         - dict (can be nested)

        If the given data is one of the BufferData types, like NumericEventList or SignalChunk,
        it will be passed to add_buffer_data() instead of being saved as an enchancement.
        """
        if isinstance(data, BufferData):
            return self.add_buffer_data(name, data)
        else:
            if category not in self.categories:
                self.categories[category] = []
            if name not in self.categories[category]:
                self.categories[category].append(name)
            self.enhancements[name] = data
            return True

    def get_enhancement(self, name: str, default: Any = None) -> Any:
        """Get the value of a previously added enhancement, or return the given default."""
        return self.enhancements.get(name, default)

    def get_one(self, name: str, default: Any = None, index: int = 0, value_index: int = 0) -> Any:
        """Get one element from the named buffer or enhancement, indexing into lists if needed."""
        if name in self.signals:
            signal_chunk = self.signals[name]
            if signal_chunk.sample_count() <= index or signal_chunk.channel_count() <= value_index:
                return default
            else:
                return signal_chunk.sample_data[index, value_index]

        if name in self.numeric_events:
            event_list = self.numeric_events[name]
            if event_list.event_count() <= index or event_list.values_per_event() <= value_index:
                return default
            else:
                return event_list.event_data[index, value_index + 1]

        if name in self.text_events:
            event_list = self.text_events[name]
            if event_list.event_count() <= index:
                return default
            else:
                return event_list.text_data[index]

        if name in self.enhancements:
            data = self.enhancements[name]
            if isinstance(data, list):
                if len(data) <= index:
                    return default
                else:
                    return data[index]
            else:
                return data

        return default

    def get_time(self, name: str, default: Any = None, index: int = 0) -> Any:
        """Get one timestamp from the named buffer or enhancement, indexing into lists if needed."""
        if name in self.signals:
            times = self.signals[name].times()
            if len(times) <= index:
                return default
            else:
                return times[index]

        if name in self.numeric_events:
            times = self.numeric_events[name].times()
            if len(times) <= index:
                return default
            else:
                return times[index]

        if name in self.text_events:
            times = self.text_events[name].times()
            if len(times) <= index:
                return default
            else:
                return times[index]

        if name in self.enhancements:
            data = self.enhancements[name]
            if isinstance(data, list):
                if len(data) <= index:
                    return default
                else:
                    return data[index]
            else:
                return data

        return default


class TrialDelimiter():
    """Monitor a "start" event buffer, making new trials as delimiting events arrive."""

    def __init__(
        self,
        start_buffer: Buffer,
        start_value: Any,
        start_value_index: int = 0,
        start_time: float = 0.0,
        trial_count: int = 0,
        trial_log_mod: int = 50
    ) -> None:
        self.start_buffer = start_buffer
        self.start_value = start_value
        self.start_value_index = start_value_index
        self.start_time = start_time
        self.trial_count = trial_count
        self.trial_log_mod = trial_log_mod

    def __eq__(self, other: object) -> bool:
        """Compare delimiters field-wise, to support use of this class in tests."""
        if isinstance(other, self.__class__):
            return (
                self.start_buffer == other.start_buffer
                and self.start_value == other.start_value
                and self.start_value_index == other.start_value_index
                and self.start_time == other.start_time
                and self.trial_count == other.trial_count
            )
        else:  # pragma: no cover
            return False

    def next(self) -> dict[int, Trial]:
        """Check the start buffer for start events, produce new trials as new start events arrive.

        This has the side-effects of incrementing trial_start_time and trial_count.
        """
        trials = {}
        next_start_times = self.start_buffer.data.times(self.start_value, self.start_value_index)
        for next_start_time in next_start_times:
            if next_start_time > self.start_time:
                trial = Trial(
                    start_time=self.start_buffer.raw_time_to_reference(self.start_time),
                    end_time=self.start_buffer.raw_time_to_reference(next_start_time)
                )
                trials[self.trial_count] = trial

                self.start_time = next_start_time
                self.trial_count += 1
                if self.trial_count % self.trial_log_mod == 0:
                    logging.info(f"Delimited {self.trial_count} trials.")

        return trials

    def last(self) -> tuple[int, Trial]:
        """Make a best effort to make a trial with whatever's left on the start buffer.

        This has the side effect of incrementing trial_count.
        """
        trial = Trial(
            start_time=self.start_buffer.raw_time_to_reference(self.start_time),
            end_time=None
        )
        last_trial = (self.trial_count, trial)
        self.trial_count += 1
        logging.info(f"Delimited {self.trial_count} trials (last one).")
        return last_trial

    def discard_before(self, reference_time: float):
        """Let event buffer discard data no longer needed."""
        self.start_buffer.data.discard_before(self.start_buffer.reference_time_to_raw(reference_time))


class TrialEnhancer(DynamicImport):
    """Compute new name-value pairs to save with each trial.

    An informal naming convention:
     -  An "Enhancer" like adds new name-value pairs to each trial but leaves existing data untouched,
        for example standard_enhancers.ExpressionEnhancer.
     -  An "Adjuster" modifies or replaces existing trial data,
        for example standard_adjusters.SignalSmoother.
    """

    def enhance(
        self,
        trial: Trial,
        trial_number: int,
        experiment_info: dict[str: Any],
        subject_info: dict[str: Any]
    ) -> None:
        """Add simple data types to a trial's enchancements.

        Implementations should add to the given trial using either or:
         - trial.add_enhancement(name, data)
         - trial.add_enhancement(name, data, category)

        The data values must be standard, portable data types like int, float, or string, or lists and dicts of these types.
        Other data types might not survive being written to or read from the trial file.
        """
        raise NotImplementedError  # pragma: no cover


class TrialCollecter(TrialEnhancer):
    """Collect data or stats from across all trials in a session, then use the data or stats to adjust each trial."""

    def collect(
        self,
        trial: Trial,
        trial_number: int,
        experiment_info: dict[str: Any],
        subject_info: dict[str: Any]
    ) -> None:
        """Collect data and stats from across the whole session and sace in.

        Implementations should define their own fields for holding on to collected data, stats, etc.
        The data and stats from the whole session must be able to fit in memory!

        The overall data and stats can be used later, during enhance().
        Implementations can expect to have collect() called once per trial, in order, across the whole session.
        After that, implementations can expect to have enhance() called once per trial, in order, as well.
        """
        raise NotImplementedError  # pragma: no cover


class TrialExpression():
    """Evaluate a string expression using Python eval(), with trial enhancements for local variable values.

    Python eval() is generally unsafe!  This makes a best effort to remove global system variables from
    the evaluation context, but malicious things are still possible.  Please take care to use simple expressions,
    like arithmetic and logic, based on the values of trial enhancements.  Existing trial enchancements
    can be used by name as variables in these expressions.

    Args:
        expression:     A string Python expression with trial buffers and enhancements as local variables, like:
                            - "my_buffer.times(42)"
                            - "my_enhancement > 41"
                            - "my_enhancement + other_enhancement"
        default_value:  Default value to return in case of error evaluating the expression (default is None)
    """

    def __init__(
        self,
        expression: str,
        default_value: Any = None
    ) -> None:
        self.expression = expression
        self.compiled_expression = compile(expression, '<string>', 'eval')
        self.default_value = default_value

    def __eq__(self, other: object) -> bool:
        """Compare field-wise, to support use of this class in tests."""
        if isinstance(other, self.__class__):
            return (
                self.compiled_expression == other.compiled_expression
                and self.default_value == other.default_value
            )
        else:  # pragma: no cover
            return False

    def evaluate(self, trial: Trial) -> Any:
        try:
            locals = {
                **trial.numeric_events,
                **trial.text_events,
                **trial.signals,
                **trial.enhancements
            }
            return eval(self.compiled_expression, {}, locals)
        except:
            logging.warning(f"Error evaluating TrialExpression: {self.compiled_expression}", exc_info=True)
            logging.warning(f"Returning TrialExpression default value: {self.default_value}")
            return self.default_value


class TrialExtractor():
    """Populate trials with WRT-aligned data from named buffers."""

    def __init__(
        self,
        wrt_buffer: Buffer,
        wrt_value: Any,
        wrt_value_index: int = 0,
        named_buffers: dict[str, Buffer] = {},
        enhancers: dict[TrialEnhancer, TrialExpression] = {},
        collecters: dict[TrialCollecter, TrialExpression] = {}
    ) -> None:
        self.wrt_buffer = wrt_buffer
        self.wrt_value = wrt_value
        self.wrt_value_index = wrt_value_index
        self.named_buffers = named_buffers
        self.enhancers = enhancers
        self.collecters = collecters

    def __eq__(self, other: object) -> bool:
        """Compare extractors field-wise, to support use of this class in tests."""
        if isinstance(other, self.__class__):
            return (
                self.wrt_buffer == other.wrt_buffer
                and self.wrt_value == other.wrt_value
                and self.wrt_value_index == other.wrt_value_index
                and self.named_buffers == other.named_buffers
                and self.enhancers == other.enhancers
                and self.collecters == other.collecters
            )
        else:  # pragma: no cover
            return False

    def populate_trial(
        self,
        trial: Trial,
        trial_number: int,
        experiment_info: dict[str: Any],
        subject_info: dict[str: Any]
    ):
        """Fill in the given trial with data from configured buffers, in the trial's time range."""
        trial_wrt_times = self.wrt_buffer.data.times(
            self.wrt_value,
            self.wrt_value_index,
            self.wrt_buffer.reference_time_to_raw(trial.start_time),
            self.wrt_buffer.reference_time_to_raw(trial.end_time)
        )
        if trial_wrt_times.size > 0:
            raw_wrt_time = trial_wrt_times.min()
            trial.wrt_time = self.wrt_buffer.raw_time_to_reference(raw_wrt_time)
        else:
            trial.wrt_time = 0.0

        for name, buffer in self.named_buffers.items():
            data = buffer.data.copy_time_range(
                buffer.reference_time_to_raw(trial.start_time),
                buffer.reference_time_to_raw(trial.end_time)
            )
            raw_wrt_time = buffer.reference_time_to_raw(trial.wrt_time)
            data.shift_times(-raw_wrt_time)
            trial.add_buffer_data(name, data)

        self.apply_enhancers(self.enhancers, "enhance", trial, trial_number, experiment_info, subject_info)
        self.apply_enhancers(self.collecters, "collect", trial, trial_number, experiment_info, subject_info)

    def discard_before(self, reference_time: float):
        """Let event wrt and named buffers discard data no longer needed."""
        self.wrt_buffer.data.discard_before(self.wrt_buffer.reference_time_to_raw(reference_time))
        for buffer in self.named_buffers.values():
            buffer.data.discard_before(buffer.reference_time_to_raw(reference_time))

    def apply_enhancers(
        self,
        enhancers: dict[TrialEnhancer, TrialExpression],
        method_name: str,
        trial: Trial,
        trial_number: int,
        experiment_info: dict[str: Any],
        subject_info: dict[str: Any]
    ):
        """Conditionally apply the given method of each given enhancer to the given trial.

        This method is used internally to represet a repeated pattern of:
            - checking when to call each enhancer/collecter
            - calling one or another method on each enhancer/collecter, with the given trial

        It probably reads as too dynamic and too-clever-by-half!
        But the alternative of cutting-and-pasting the same code several times also felt wrong.
        """
        for enhancer, when_expression in enhancers.items():
            if when_expression is not None:
                when_result = when_expression.evaluate(trial)
                if not when_result:
                    continue
            try:
                method = getattr(enhancer, method_name)
                method(trial, trial_number, experiment_info, subject_info)
            except:
                class_name = enhancer.__class__.__name__
                logging.error(f"Error applying {class_name}.{method_name} to trial {trial_number}.", exc_info=True)

    def revise_trial(
        self,
        trial: Trial,
        trial_number: int,
        experiment_info: dict[str: Any],
        subject_info: dict[str: Any]
    ):
        """Let each configured collecter collect data or stats about the given trial."""
        self.apply_enhancers(self.collecters, "enhance", trial, trial_number, experiment_info, subject_info)
