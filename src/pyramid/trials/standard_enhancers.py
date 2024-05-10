from typing import Any
from numpy import bool_
import logging
import csv

from pyramid.file_finder import FileFinder
from pyramid.trials.trials import Trial, TrialEnhancer, TrialExpression


class TrialDurationEnhancer(TrialEnhancer):
    """A simple enhancer that computes trial duration, for demo and testing."""

    def __init__(self, default_duration: float = None) -> None:
        self.default_duration = default_duration

    def __eq__(self, other: object) -> bool:
        """Compare by attribute, to support use of this class in tests."""
        if isinstance(other, self.__class__):
            return self.default_duration == other.default_duration
        else:  # pragma: no cover
            return False

    def __hash__(self) -> int:
        """Hash by attribute, to support use of this class in tests."""
        return self.default_duration.__hash__()

    def enhance(
        self,
        trial: Trial,
        trial_number: int,
        experiment_info: dict[str: Any],
        subject_info: dict[str: Any]
    ) -> None:
        if trial.end_time is None:
            duration = None
        else:
            duration = trial.end_time - trial.start_time
        trial.add_enhancement("duration", duration, "value")


class PairedCodesEnhancer(TrialEnhancer):
    """Look for pairs of numeric events that represent property-value pairs.

    buffer_name is the name of a buffer of NumericEventList.

    rules_csv is one or more .csv files where each row contains a rule for how to extract a property from the
    named buffer.  Each .csv must have the following columns:

        - "type": Used to select relevant rows of the .csv, and also the trial enhancement category to
                  use for each property.  By defalt only types "id" and "value" will be used.
                  Pass in rule_types to change this default.
        - "value": a numeric value that represents a property, for example 1010
        - "name": the string name to use for the property, for example "fp_on"
        - "min": the smallest event value to consier when looking for the property's value events
        - "max": the largest event value to consier when looking for the property's value events
        - "base": the base value to subtract from the property's value events, for example 7000
        - "scale": how to scale each event value after subtracting its base, for example 0.1

    Each .csv may contain additional columns, which will be ignored (eg a "comment" column).

    file_finder is a utility to find() files in the conigured Pyramid configured search path.
    Pyramid will automatically create and pass in the file_finder for you.

    value_index is which event value to look for, in the NumericEventList
    (default is 0, the first value for each event).

    rule_types is a list of strings to match against the .csv "type" column.
    The default is ["id", "value"].

    dialect and any additional fmtparams are passed on to the .csv reader.
    """

    def __init__(
        self,
        buffer_name: str,
        rules_csv: str | list[str],
        file_finder: FileFinder,
        value_index: int = 0,
        rule_types: list[str] = ["id", "value"],
        dialect: str = 'excel',
        **fmtparams
    ) -> None:
        self.buffer_name = buffer_name
        if isinstance(rules_csv, list):
            self.rules_csv = [file_finder.find(file) for file in rules_csv]
        else:
            self.rules_csv = [file_finder.find(rules_csv)]
        self.value_index = value_index
        self.rule_types = rule_types
        self.dialect = dialect
        self.fmtparams = fmtparams

        rules = {}
        for rules_csv in self.rules_csv:
            with open(rules_csv, mode='r', newline='') as f:
                csv_reader = csv.DictReader(f, dialect=self.dialect, **self.fmtparams)
                for row in csv_reader:
                    if row['type'] in self.rule_types:
                        value = float(row['value'])
                        rules[value] = {
                            'type': row['type'],
                            'name': row['name'],
                            'base': float(row['base']),
                            'min': float(row['min']),
                            'max': float(row['max']),
                            'scale': float(row['scale']),
                        }
        self.rules = rules

    def enhance(
        self,
        trial: Trial,
        trial_number: int,
        experiment_info: dict[str: Any],
        subject_info: dict[str: Any]
    ) -> None:
        event_list = trial.numeric_events[self.buffer_name]
        for value, rule in self.rules.items():
            # Did / when did this trial contain events indicating this rule/property?
            property_times = event_list.times(value, self.value_index)
            if property_times is not None and property_times.size > 0:
                # Get potential events that hold values for the indicated rule/property.
                value_list = event_list.copy_value_range(min=rule['min'], max=rule['max'], value_index=self.value_index)
                value_list.apply_offset_then_gain(-rule['base'], rule['scale'])
                for property_time in property_times:
                    # For each property event, pick the soonest value event that follows.
                    values = value_list.values(start_time=property_time, value_index=self.value_index)
                    if values.size > 0:
                        trial.add_enhancement(rule['name'], values[0], rule['type'])


class EventTimesEnhancer(TrialEnhancer):
    """Look for times when named events occurred.

    buffer_name is the name of a buffer of NumericEventList.

    rules_csv is one or more .csv files where each row contains a rule for how to extract events from the
    named buffer.  Each .csv must have the following columns:

        - "type": Used to select relevant rows of the .csv, and also the trial enhancement category to
                  use for each property.  By defalt only the type "time" will be used.
                  Pass in rule_types to change this default.
        - "value": a numeric value that represents a property, for example 1010
        - "name": the string name to use for the property, for example "fp_on"

    Each .csv may contain additional columns, which will be ignored (eg a "comment" column).

    file_finder is a utility to find() files in the conigured Pyramid configured search path.
    Pyramid will automatically create and pass in the file_finder for you.

    value_index is which event value to look for, in the NumericEventList
    (default is 0, the first value for each event).

    rule_types is a list of strings to match against the .csv "type" column.
    The default is ["time"].

    dialect and any additional fmtparams are passed on to the .csv reader.
    """

    def __init__(
        self,
        buffer_name: str,
        rules_csv: str | list[str],
        file_finder: FileFinder,
        value_index: int = 0,
        rule_types: list[str] = ["time"],
        dialect: str = 'excel',
        **fmtparams
    ) -> None:
        self.buffer_name = buffer_name
        if isinstance(rules_csv, list):
            self.rules_csv = [file_finder.find(file) for file in rules_csv]
        else:
            self.rules_csv = [file_finder.find(rules_csv)]
        self.value_index = value_index
        self.rule_types = rule_types
        self.dialect = dialect
        self.fmtparams = fmtparams

        rules = {}
        for rules_csv in self.rules_csv:
            with open(rules_csv, mode='r', newline='') as f:
                csv_reader = csv.DictReader(f, dialect=self.dialect, **self.fmtparams)
                for row in csv_reader:
                    if row['type'] in self.rule_types:
                        value = float(row['value'])
                        rules[value] = {
                            'type': row['type'],
                            'name': row['name'],
                        }
        self.rules = rules

    def enhance(
        self,
        trial: Trial,
        trial_number: int,
        experiment_info: dict[str: Any],
        subject_info: dict[str: Any]
    ) -> None:
        event_list = trial.numeric_events[self.buffer_name]
        for value, rule in self.rules.items():
            # Did / when did this trial contain events of interest with the requested value?
            event_times = event_list.times(value, self.value_index)
            trial.add_enhancement(rule['name'], event_times.tolist(), rule['type'])


class ExpressionEnhancer(TrialEnhancer):
    """Evaluate a TrialExpression for each trial and add the result as a named enhancement.

    Args:
        expression:     string Python expression to evaluate for each trial as a TrialExpression
        value_name:     name of the enhancement to add to each trial, with the expression value
        value_category: optional category to go with value_name (default is "value")
        default_value:  default value to return in case of expression evaluation error (default is None)
    """

    def __init__(
        self,
        expression: str,
        value_name: str,
        value_category: str = "value",
        default_value: Any = None,
    ) -> None:
        self.trial_expression = TrialExpression(expression=expression, default_value=default_value)
        self.value_name = value_name
        self.value_category = value_category

    def enhance(
        self,
        trial: Trial,
        trial_number: int,
        experiment_info: dict[str: Any],
        subject_info: dict[str: Any]
    ) -> None:
        value = self.trial_expression.evaluate(trial)

        # Many numpy types are json-serializable like standard Python float, int, etc. -- but not numpy.bool_!
        if isinstance(value, bool_):
            value = bool(value)

        trial.add_enhancement(self.value_name, value, self.value_category)


class TextKeyValueEnhancer(TrialEnhancer):
    """Parse text events for key-value pairs, form them into enhancements, and add them to the trial.

    Each event should have text_data formated like these:

        - "name=<name>, value=<value>, type=<type>"
        - "name=fpon"
        - "name=fp_x, value=0, type=double"

    In general, the expected format is:

        - Event text_data is one list of **entries** that are separated by commas (",").
        - Each **entry** is a key-value pair with **key** and **value** separted by an equals sign ("=").
        - Both **key** and **value** can have surrounding whitespace, which will be trimmed.

    For each text event in a named buffer, this enhancer will parse out the keys and values,
    form them into an enhancement, and add this to the current trial. The formation works like this:

        - Look for an entry with **key** "name".  Use its **value** as the name of the trial enhancement.
            - If there is no "name" entry, skip the text event.
        - Look for an entry with **key** "value".  Parse its **value** to get the value for the enhancement.
            - If there is no "value" entry, the enhancement will take the value of the event's timestamp (and category "time").
        - Look for an entry with **key** "type".  If present, this can be a hint for how to parse the "value" entry:
            - type=float or type=double -> Try to parse "value" as a Python float (with category "value").
            - type=int or type=long -> Try to parse "value" as a Python int (with category "id").
            - type=str -> Take "value" as-is as a Python str (with category "value").
            - no "type" entry or unknown type -> Take "value" as-is as a Python str (with category "value").
        - Look for a key called "category".  If present, this can specify the enhancement's category explicitly
          and override the default categories (as guessed above).

    The literal delimiters and keys used for parsing can be cusomized as args to this enhancer.

    Args:
        buffer_name:            Name of a trial TextEventList buffer to read from.
        entry_delimiter:        How parse data into entries (default is ",")
        key_value_delimiter:    How to parse each entry into a **key** and **value** (default is "=")
        name_key:               Key to use for the name of each enhancement (default is "name")
        value_key:              Key to use for the value of each enhancement (default is "value")
        type_key:               Key to use for the type of each value (default is "type")
        category_key:           Key to use for the category of each enhancement (default is "category")
        float_types:            List of types to parse as Python floats (default is ["float", "double"])
        float_default:          Default value to use when float parsing fails (default is 0.0)
        int_types:              List of types to parse as Python ints (default is ["int", "long"])
        int_default:            Default value to use when int parsing fails (default is 0)
        timestamp_category:     Enhancement category to use with event timestamps (default is "time")
        str_category:           Default enhancement category to use with str values (default is "value")
        int_category:           Default enhancement category to use with int values (default is "id")
        float_category:         Default enhancement category to use with float values (default is "value")
    """

    def __init__(
        self,
        buffer_name: str,
        entry_delimiter: str = ",",
        key_value_delimiter: str = "=",
        name_key: str = "name",
        value_key: str = "value",
        type_key: str = "type",
        category_key: str = "category",
        float_types: list[str] = ["float", "double"],
        float_default: float = 0.0,
        int_types: list[str] = ["int", "long"],
        int_default: int = 0,
        timestamp_category: str = "time",
        str_category: str = "value",
        int_category: str = "id",
        float_category: str = "value",
    ) -> None:
        self.buffer_name = buffer_name
        self.entry_delimiter = entry_delimiter
        self.key_value_delimiter = key_value_delimiter
        self.name_key = name_key
        self.value_key = value_key
        self.type_key = type_key
        self.category_key = category_key
        self.float_types = float_types
        self.float_default = float_default
        self.int_types = int_types
        self.int_default = int_default
        self.timestamp_category = timestamp_category
        self.str_category = str_category
        self.int_category = int_category
        self.float_category = float_category

    def enhance(
        self,
        trial: Trial,
        trial_number: int,
        experiment_info: dict[str: Any],
        subject_info: dict[str: Any]
    ) -> None:
        event_list = trial.text_events[self.buffer_name]
        for index in range(event_list.event_count()):
            timestamp = event_list.timestamp_data[index]
            text = str(event_list.text_data[index])
            info = self.parse_entries(text)
            if not self.name_key in info:
                logging.warning(f"Skipping text that has no name key '{self.name_key}': {text}")
                continue
            name = info[self.name_key]
            (value, category) = self.parse_value(info, timestamp)
            trial.add_enhancement(name, value, category)

    def parse_entries(self, text: str) -> dict[str, str]:
        entries = text.split(self.entry_delimiter)
        info = {}
        for entry in entries:
            parts = entry.split(self.key_value_delimiter, maxsplit=1)
            if len(parts) != 2:
                logging.warning(f"Unable to parse key-value text: {entry}")
                continue
            key = parts[0].strip()
            value = parts[1].strip()
            info[key] = value
        return info

    def parse_value(self, info: dict[str, str], timestamp: float) -> tuple[Any, str]:
        raw_value = info.get(self.value_key, None)
        if raw_value is None:
            # Use the event's timesetamp as the enhancement value, with category "time".
            return (timestamp, self.timestamp_category)

        # Parse out a value based on the type, if provided.
        # Also guess a default enhancement category for the type.
        type = info.get(self.type_key, None)
        if type in self.int_types:
            category = self.int_category
            try:
                value = int(raw_value)
            except Exception:
                logging.warning(f"Could not parse value as int, using default ({self.int_default}): {raw_value}")
                value = self.int_default
        elif type in self.float_types:
            category = self.float_category
            try:
                value = float(raw_value)
            except Exception:
                logging.warning(f"Could not parse value as float, using default ({self.float_default}): {raw_value}")
                value = self.float_default
        else:
            category = self.str_category
            value = raw_value

        # Look for an explicit category to override the default guessed above.
        category = info.get(self.category_key, category)

        return (value, category)
