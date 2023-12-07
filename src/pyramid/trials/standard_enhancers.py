from typing import Any
from numpy import bool_
import numpy as np
import csv
import matplotlib.pyplot as plt
import time
from scipy.ndimage import gaussian_filter1d
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
            property_times = event_list.get_times_of(value, self.value_index)
            if property_times is not None and property_times.size > 0:
                # Get potential events that hold values for the indicated rule/property.
                value_list = event_list.copy_value_range(min=rule['min'], max=rule['max'], value_index=self.value_index)
                value_list.apply_offset_then_gain(-rule['base'], rule['scale'])
                for property_time in property_times:
                    # For each property event, pick the soonest value event that follows.
                    values = value_list.get_values(start_time=property_time, value_index=self.value_index)
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
            event_times = event_list.get_times_of(value, self.value_index)
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

        # Many numpy types are json-serializable like standard Python float, int, etc. -- But not numpy.bool_ !
        if isinstance(value, bool_):
            value = bool(value)

        trial.add_enhancement(self.value_name, value, self.value_category)

class SaccadesEnhancer(TrialEnhancer):
    """
        Parse saccades from the x,y eye position traces in a trial
        Uses velocity and acceleration thresholds
    """

    def __init__(
        self,
        max_saccades: int = 1,
        center_at_fp: bool = True,
        x_buffer_name: str = "gaze_x",
        y_buffer_name: str = "gaze_y",
        fp_off_name: str = "fp_off",
        all_off_name: str = "all_off",
        fp_x_name: str = "fp_x",
        fp_y_name: str = "fp_y",
        max_time_ms: int = 2000,
        sample_rate_hz: float = 1000,
        position_smoothing_kernel_size_ms: int = 0, # >1 for smoothing
        velocity_smoothing_kernel_size_ms: int = 10, # >1 for smoothing
        acceleration_smoothing_kernel_size_ms: int = 0, # >1 for smoothing
        velocity_threshold_deg_per_s: float = 300, # deg/s
        acceleration_threshold_deg_per_s2: float = 8, # deg/s^2
        min_length_deg: float = 3.0,
        min_latency_ms: float = 10,
        min_duration_ms: float = 5.0, 
        max_duration_ms: float = 90.0,
        saccades_name: str = "saccades",
        saccades_category: str = "saccades",
        debug_plot: bool = True,
        debug_plot_pause_s: int = 2
    ) -> None:
        self.max_saccades = max_saccades
        self.center_at_fp = center_at_fp
        self.x_buffer_name = x_buffer_name
        self.y_buffer_name = y_buffer_name
        self.fp_off_name = fp_off_name
        self.all_off_name = all_off_name
        self.fp_x_name = fp_x_name
        self.fp_y_name = fp_y_name
        self.max_time_ms = max_time_ms
        self.sample_rate_hz = sample_rate_hz
        self.position_smoothing_kernel_size_ms = position_smoothing_kernel_size_ms
        self.velocity_smoothing_kernel_size_ms = velocity_smoothing_kernel_size_ms
        self.acceleration_smoothing_kernel_size_ms = acceleration_smoothing_kernel_size_ms
        self.velocity_threshold_deg_per_s = velocity_threshold_deg_per_s
        self.acceleration_threshold_deg_per_s2 = acceleration_threshold_deg_per_s2
        self.min_length_deg = min_length_deg
        self.min_latency_ms = min_latency_ms
        self.min_duration_ms = min_duration_ms
        self.max_duration_ms = max_duration_ms
        self.saccades_name = saccades_name
        self.saccades_category = saccades_category
        self.debug_plot_pause_s = debug_plot_pause_s
        
        if debug_plot:
            # turn on interactive mode and set up axes
            self.fig, self.axs = plt.subplots(4)
            plt.ion()
        else:
            self.fig = None

    def enhance(self, trial: Trial, trial_number: int, experiment_info: dict, subject_info: dict) -> None:

        # Use trial.get_one() to get the time of the first occurence of the named "time" event.
        fp_off_time = trial.get_one(self.fp_off_name)
        all_off_time = trial.get_one(self.all_off_name)

        # Use trial.signals for gaze signal chunks.
        x_signal = trial.signals[self.x_buffer_name]
        y_signal = trial.signals[self.y_buffer_name]
        if x_signal.get_end_time() < fp_off_time or y_signal.get_end_time() < fp_off_time:
            return

        # Possibly center at fp
        if self.center_at_fp is True:
            x_signal.apply_offset_then_gain(-x_signal.copy_time_range(fp_off_time, fp_off_time).get_channel_values(), 1)
            y_signal.apply_offset_then_gain(-y_signal.copy_time_range(fp_off_time, fp_off_time).get_channel_values(), 1)

        # Get x,y data from fp_off to all_off
        x_position = x_signal.copy_time_range(fp_off_time, all_off_time).get_channel_values()
        y_position = y_signal.copy_time_range(fp_off_time, all_off_time).get_channel_values()

        # Possibly smooth position
        if self.position_smoothing_kernel_size_ms > 0:
            kernel_width = self.position_smoothing_kernel_size_ms*self.sample_rate_hz/1000.0 # convert to samples
            x_position = gaussian_filter1d(x_position, kernel_width)
            y_position = gaussian_filter1d(y_position, kernel_width)

        # Compute instantaneous velocity
        dx = np.diff(x_position)
        dy = np.diff(y_position)
        distance = np.sqrt(dx**2 + dy**2)
        velocity = distance*self.sample_rate_hz

        # Possibly smooth velocity
        if self.velocity_smoothing_kernel_size_ms > 0:
            kernel_width = self.velocity_smoothing_kernel_size_ms*self.sample_rate_hz/1000.0 # convert to samples
            velocity = gaussian_filter1d(velocity, kernel_width)

        # Compute instantaneous acceleration
        acceleration = np.concatenate([[0], np.diff(velocity)])

        # Possibly smooth acceleration
        if self.acceleration_smoothing_kernel_size_ms > 0:
            kernel_width = self.acceleration_smoothing_kernel_size_ms*self.sample_rate_hz/1000.0 # convert to samples
            acceleration = gaussian_filter1d(acceleration, kernel_width)
        
        # Look for saccades
        num_samples = len(distance)
        sample_index = 0
        saccades = []
        while (sample_index < num_samples) and (len(saccades) < self.max_saccades):

            # Reset indices
            start_index = -1
            end_index = -1

            # Check for saccade, first try acceleration, then velocity treshold
            if acceleration[sample_index] >= self.acceleration_threshold_deg_per_s2:
                
                # Crossed acceleration threshold
                start_index = sample_index

                # Look for deceleration
                while (sample_index < num_samples) and (acceleration[sample_index] > -self.acceleration_threshold_deg_per_s2):
                    sample_index += 1

                # Look for end of deceleration    
                if (sample_index < num_samples) and ((acceleration[sample_index] <= -self.acceleration_threshold_deg_per_s2) or
                                                     (velocity[sample_index] <= -self.velocity_threshold_deg_per_s)):
                    end_index = sample_index

            elif velocity[sample_index] >= self.velocity_threshold_deg_per_s:

                # Crossed velocity threshold
                start_index = sample_index

                # Look for slowing
                while (sample_index < num_samples) and (velocity[sample_index] >= self.velocity_threshold_deg_per_s):
                    sample_index += 1
                
                # Look for end of super-threshold velocity     
                if (sample_index < num_samples) and (velocity[sample_index] <= -self.velocity_threshold_deg_per_s):
                    end_index = sample_index

            # Check if we found something
            if (start_index != -1) and (end_index != 1):

                # Get start/end times wrt fixation onset
                sac_start_time = fp_off_time + (start_index+1)/self.sample_rate_hz*1000
                sac_end_time = fp_off_time + (end_index+1)/self.sample_rate_hz*1000
                sac_duration = sac_end_time - sac_start_time

                # Saccade distance
                sac_length = np.sqrt(
                    (x_position[end_index+1] - x_position[start_index+1])**2 + 
                    (y_position[end_index+1] - y_position[start_index+1])**2)
                
                if ((sac_length >= self.min_length_deg) and
                    (sac_duration >= self.min_duration_ms) and
                    (sac_duration >= self.min_duration_ms) and
                    (sac_start_time >= self.min_latency_ms)):

                    # Save the saccade as a dictionary in the list of saccades
                    saccades.append({
                        "t_start": sac_start_time,
                        "t_end": sac_end_time,
                        "v_max": np.max(velocity[start_index:end_index]),
                        "v_avg": sac_length / sac_duration,
                        "x_start": x_position[start_index+1],
                        "y_start": y_position[start_index+1],
                        "x_end": x_position[end_index+1],
                        "y_end": y_position[end_index+1],
                        "raw_distance": np.sum(velocity[start_index:end_index])/self.sample_rate_hz*1000,
                        "vector_distance": sac_length,
                    })

            # Update index
            sample_index += 1

        # Add the list of saccade dictionaries to trial enhancements.
        trial.add_enhancement(self.saccades_name, saccades, self.saccades_category)

        if self.fig is not None:
            times = x_signal.copy_time_range(fp_off_time, all_off_time).get_times()
            times = times - times[0]
            self.axs[0].cla()
            self.axs[0].plot(times, x_position, 'r-')
            self.axs[0].plot(times, y_position, 'b-')
            self.axs[0].set_xlim([0, 2])
            self.axs[0].set_ylim([-30, 30])
            self.axs[1].cla()
            self.axs[1].plot(times, np.sqrt(x_position**2+y_position**2))
            self.axs[1].plot(times, np.zeros_like(times)+10, 'k--')
            self.axs[1].set_xlim([0, 2])
            self.axs[1].set_ylim([0, 20])

            for sac in saccades:
                #print(sac)
                self.axs[1].plot([sac["t_start"]/1000, sac["t_start"]/1000], [0, 20], 'g-')
                self.axs[1].plot([sac["t_end"]/1000, sac["t_end"]/1000], [0, 20], 'r-')

            self.axs[2].cla()
            self.axs[2].plot(times[:-1], velocity)
            self.axs[2].plot(times[:-1], np.zeros_like(times[:-1])+self.velocity_threshold_deg_per_s, 'k--')
            self.axs[2].set_xlim([0, 2])
            self.axs[2].set_ylim([0, 800])
            self.axs[3].cla()
            self.axs[3].plot(times[:-1], acceleration)
            self.axs[3].plot(times[:-1], np.zeros_like(times[:-1])+self.acceleration_threshold_deg_per_s2, 'k--')
            self.axs[3].plot(times[:-1], np.zeros_like(times[:-1])-self.acceleration_threshold_deg_per_s2, 'k--')
            self.axs[3].set_xlim([0, 2])
            self.axs[3].set_ylim([-25, 25])

            plt.pause(self.debug_plot_pause_s)
            self.fig.canvas.draw_idle()
            self.fig.canvas.flush_events()
