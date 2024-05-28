from pathlib import Path
import numpy as np

from pyramid.file_finder import FileFinder
from pyramid.model.events import NumericEventList, TextEventList
from pyramid.model.signals import SignalChunk
from pyramid.trials.trials import Trial
from pyramid.trials.standard_enhancers import (
    PairedCodesEnhancer,
    EventTimesEnhancer,
    ExpressionEnhancer,
    TextKeyValueEnhancer,
    SaccadesEnhancer
)


def test_paired_codes_enhancer(tmp_path):
    # Write out a .csv file with rules in it.
    rules_csv = Path(tmp_path, "rules.csv")
    with open(rules_csv, 'w') as f:
        f.write('type,value,name,base,min,max,scale,comment\n')
        f.write('id,42,foo,3000,2000,4000,0.25,this is just a comment\n')
        f.write('id,43,bar,3000,2000,4000,0.25,this is just a comment\n')
        f.write('value,44,baz,3000,2000,4000,0.25,this is just a comment\n')
        f.write('value,45,quux,3000,2000,4000,0.025,this is just a comment\n')
        f.write('ignore,777,ignore_me,3000,2000,4000,0.25,this is just a comment\n')

    enhancer = PairedCodesEnhancer(
        buffer_name="propcodes",
        rules_csv=rules_csv,
        file_finder=FileFinder()
    )

    # The "id" and "value" rows should be included.
    assert 42 in enhancer.rules.keys()
    assert 43 in enhancer.rules.keys()
    assert 44 in enhancer.rules.keys()
    assert 45 in enhancer.rules.keys()

    # Other rows should ne ignored.
    assert 777 not in enhancer.rules.keys()

    paired_code_data = [
        [0.0, 42.0],    # code for property "foo"
        [1, 3000],      # value 0
        [2, 43],        # code for property "bar"
        [3, 3005],      # value 1.25
        [4, 13],        # irrelevant
        [5, 44],        # code for property "baz"
        [6, 10000],     # irrelevant
        [7, 3600],      # value 150
        [8, 44],        # code for property "baz" (again)
        [9, 13],        # irrelevant
        [10, 3604],     # value 151
        [11, 45],       # code for property "quux"
        [12, 14],       # irrelevant
        [13, 20002],    # irrelevant
        [14, 15],       # irrelevant
        [15, 16],       # irrelevant
        [16, 3101],     # value 2.525 (quux has scale 10 time finer than the others)
    ]
    event_list = NumericEventList(event_data=np.array(paired_code_data))
    trial = Trial(
        start_time=0,
        end_time=20,
        wrt_time=0,
        numeric_events={
            "propcodes": event_list
        }
    )

    enhancer.enhance(trial, 0, {}, {})
    expected_enhancements = {
        "foo": 0.0,
        "bar": 1.25,
        "baz": 151.0,
        "quux": 2.5250000000000004,
    }
    assert trial.enhancements == expected_enhancements

    expected_categories = {
        "id": ["foo", "bar"],
        "value": ["baz", "quux"]
    }
    assert trial.enhancement_categories == expected_categories


def test_paired_codes_enhancer_multiple_csvs(tmp_path):
    # Write some .csv files with overlapping / overriding rules in them.
    rules_1_csv = Path(tmp_path, "rules_1.csv")
    with open(rules_1_csv, 'w') as f:
        f.write('type,value,name,base,min,max,scale,comment\n')
        f.write('id,42,foo,3000,2000,4000,0.25,this is just a comment\n')
        f.write('id,43,bar,3000,2000,4000,0.25,this is just a comment\n')
        f.write('value,44,baz,3000,2000,4000,0.25,this is just a comment\n')
    rules_2_csv = Path(tmp_path, "rules_2.csv")
    with open(rules_2_csv, 'w') as f:
        f.write('type,value,name,base,min,max,scale,comment\n')
        f.write('value,44,baz,3000,2000,4000,0.25,this is just a comment\n')
        f.write('value,45,quux,3000,2000,4000,0.025,this is just a comment\n')
    rules_3_csv = Path(tmp_path, "rules_3.csv")
    with open(rules_3_csv, 'w') as f:
        f.write('type,value,name,base,min,max,scale,comment\n')
        f.write('id,43,bar_2,3000,2000,4000,0.25,this is just a comment\n')
        f.write('value,45,quux_2,3000,2000,4000,0.025,this is just a comment\n')

    enhancer = PairedCodesEnhancer(
        buffer_name="propcodes",
        rules_csv=[rules_1_csv, rules_2_csv, rules_3_csv],
        file_finder=FileFinder()
    )

    # Only the "id" and "value" rows should be kept.
    # Expect the union of the first two csvs, with partial overrides from the last csv.
    expected_rules = {
        42: {'type': 'id', 'name': 'foo', 'base': 3000, 'min': 2000, 'max': 4000, 'scale': 0.25},
        43: {'type': 'id', 'name': 'bar_2', 'base': 3000, 'min': 2000, 'max': 4000, 'scale': 0.25},
        44: {'type': 'value', 'name': 'baz', 'base': 3000, 'min': 2000, 'max': 4000, 'scale': 0.25},
        45: {'type': 'value', 'name': 'quux_2', 'base': 3000, 'min': 2000, 'max': 4000, 'scale': 0.025}
    }
    assert enhancer.rules == expected_rules


def test_event_times_enhancer(tmp_path):
    # Write out a .csv file with rules in it.
    rules_csv = Path(tmp_path, "rules.csv")
    with open(rules_csv, 'w') as f:
        f.write('type,value,name,comment\n')
        f.write('time,42,foo,this is just a comment\n')
        f.write('time,43,bar,this is just a comment\n')
        f.write('time,44,baz,this is just a comment\n')
        f.write('ignore,777,this is just a comment\n')

    enhancer = EventTimesEnhancer(
        buffer_name="events",
        rules_csv=rules_csv,
        file_finder=FileFinder()
    )

    # The "time" rows should be included.
    assert 42 in enhancer.rules.keys()
    assert 43 in enhancer.rules.keys()
    assert 44 in enhancer.rules.keys()

    # Other rows should ne ignored.
    assert 777 not in enhancer.rules.keys()

    event_data = [
        [0.0, 42.0],    # code for event "foo"
        [1, 3000],      # irrelevant
        [2, 43],        # code for event "bar"
        [3, 3005],      # irrelevant
        [4, 13],        # irrelevant
        [5, 42.0],      # code for event "foo" (again)
        [6, 10000],     # irrelevant
    ]
    event_list = NumericEventList(event_data=np.array(event_data))
    trial = Trial(
        start_time=0,
        end_time=20,
        wrt_time=0,
        numeric_events={
            "events": event_list
        }
    )

    enhancer.enhance(trial, 0, {}, {})
    expected_enhancements = {
        "foo": [0.0, 5.0],
        "bar": [2.0],
        "baz": []
    }
    assert trial.enhancements == expected_enhancements

    expected_categories = {
        "time": ["foo", "bar", "baz"]
    }
    assert trial.enhancement_categories == expected_categories


def test_event_times_enhancer_multiple_csvs(tmp_path):
    # Write some .csv files with overlapping / overriding rules in them.
    rules_1_csv = Path(tmp_path, "rules_1.csv")
    with open(rules_1_csv, 'w') as f:
        f.write('type,value,name,comment\n')
        f.write('time,42,foo,this is just a comment\n')
        f.write('time,43,bar,this is just a comment\n')
    rules_2_csv = Path(tmp_path, "rules_2.csv")
    with open(rules_2_csv, 'w') as f:
        f.write('type,value,name,comment\n')
        f.write('time,43,bar,this is just a comment\n')
        f.write('time,44,baz,this is just a comment\n')
    rules_3_csv = Path(tmp_path, "rules_3.csv")
    with open(rules_3_csv, 'w') as f:
        f.write('type,value,name,comment\n')
        f.write('time,42,foo_2,this is just a comment\n')
        f.write('time,44,baz_2,this is just a comment\n')

    enhancer = EventTimesEnhancer(
        buffer_name="events",
        rules_csv=[rules_1_csv, rules_2_csv, rules_3_csv],
        file_finder=FileFinder()
    )

    # Only the "time" rows should be kept.
    # Expect the union of the first two csvs, with partial overrides from the last csv.
    expected_rules = {
        42: {'type': 'time', 'name': 'foo_2'},
        43: {'type': 'time', 'name': 'bar'},
        44: {'type': 'time', 'name': 'baz_2'}
    }
    assert enhancer.rules == expected_rules


def test_expression_enhancer_with_buffer_data():
    enhancer = ExpressionEnhancer(
        expression="numbers.event_count() == 0 and text.event_count() == 0 and signal.sample_count() == 0",
        value_name="all_empty",
        value_category="id",
        default_value="No way!"
    )

    not_all_empty_trial = Trial(
        start_time=0,
        end_time=1.0,
        wrt_time=0.5,
        numeric_events={
            'numbers': NumericEventList(np.array([[0, 100]]))
        },
        text_events={
            'text': TextEventList(np.array([0]), np.array(['zero'], dtype=np.str_))
        },
        signals={
            'signal': SignalChunk.empty()
        }
    )
    enhancer.enhance(not_all_empty_trial, 0, {}, {})
    assert not_all_empty_trial.enhancements == {
        "all_empty": False,
    }

    all_empty_trial = Trial(
        start_time=0,
        end_time=1.0,
        wrt_time=0.5,
        numeric_events={
            'numbers': NumericEventList.empty(1)
        },
        text_events={
            'text': TextEventList.empty()
        },
        signals={
            'signal': SignalChunk.empty()
        }
    )
    enhancer.enhance(all_empty_trial, 0, {}, {})
    assert all_empty_trial.enhancements == {
        "all_empty": True,
    }

    # The expected buffers are missing, fall back to default value.
    error_trial = Trial(
        start_time=0,
        end_time=1.0,
        wrt_time=0.5,
    )
    enhancer.enhance(error_trial, 0, {}, {})
    assert error_trial.enhancements == {
        "all_empty": "No way!"
    }


def test_expression_enhancer_with_enhancements():
    enhancer = ExpressionEnhancer(
        expression="foo + bar > 42",
        value_name="greater",
        value_category="id",
        default_value="No way!"
    )

    greater_trial = Trial(
        start_time=0,
        end_time=20,
        wrt_time=0,
        enhancements={
            "foo": 41,
            "bar": 41
        }
    )
    enhancer.enhance(greater_trial, 0, {}, {})
    assert greater_trial.enhancements == {
        "foo": 41,
        "bar": 41,
        "greater": True
    }

    lesser_trial = Trial(
        start_time=0,
        end_time=20,
        wrt_time=0,
        enhancements={
            "foo": 41,
            "bar": 0
        }
    )
    enhancer.enhance(lesser_trial, 0, {}, {})
    assert lesser_trial.enhancements == {
        "foo": 41,
        "bar": 0,
        "greater": False
    }

    # The expected enchancements "foo" and "bar" are missing, fall back to default value.
    error_trial = Trial(
        start_time=0,
        end_time=20,
        wrt_time=0
    )
    enhancer.enhance(error_trial, 0, {}, {})
    assert error_trial.enhancements == {
        "greater": "No way!"
    }


def test_expression_enhancer_bool_conversion():
    enhancer = ExpressionEnhancer(
        expression="foo > 0",
        value_name="nonzero"
    )

    trial = Trial(
        start_time=0,
        end_time=20,
        wrt_time=0,
        enhancements={
            "foo": np.array(42),
        }
    )

    # The expression "foo > 0" expands to "np.array(42) > 0".
    # This produces a numpy.bool_ rather than a standard Python bool.
    # Check that the enhancer converts the result to standard (ie json-serializable) types only.
    enhancer.enhance(trial, 0, {}, {})
    assert trial.enhancements == {
        "foo": np.array(42),
        "nonzero": True
    }

    nonzero = trial.get_enhancement("nonzero")
    assert type(nonzero) == bool


def test_text_key_value_enhancer_defaults():
    enhancer = TextKeyValueEnhancer(buffer_name="text")

    text = [
        "garbage",
        "unknown=ignored",
        "name=name_2",
        "  name  =  name_3  ",
        "name=name_4,value=value_4",
        "name=name_5,value=value_5,type=garbage",
        "name=name_6,value=not an int,type=int",
        "name=name_7,value=42,type=int",
        "name=name_8,value=not a float,type=float",
        "name=name_9,value=3.14,type=float",
        "name=name_10,value=multi_10",
        "name=name_10,value=multi_11",
        "name=name_10,value=multi_12",
        "name=name_11,value=13.13,type=float",
        "name=name_11,value=14.14,type=float",
        "name=name_11,value=15.15,type=float",
    ]
    event_list = TextEventList(np.array(range(len(text))), np.array(text, dtype=np.str_))
    trial = Trial(
        start_time=0,
        end_time=20,
        wrt_time=0,
        text_events={
            "text": event_list,
        }
    )

    enhancer.enhance(trial, 0, {}, {})

    # Some events are parsed as numeric values, otherse as text.
    assert trial.numeric_events.keys() == {"name_2", "name_3", "name_6", "name_7", "name_8", "name_9", "name_11"}
    assert trial.text_events.keys() == {"text", "name_4", "name_5", "name_10"}

    # Events that use timestamps for their values.
    assert trial.numeric_events["name_2"].times() == [2]
    assert trial.numeric_events["name_2"].values() == [2]
    assert trial.numeric_events["name_3"].times() == [3]
    assert trial.numeric_events["name_3"].values() == [3]

    # Events that use text values.
    assert trial.text_events["name_4"].times() == [4]
    assert trial.text_events["name_4"].values() == ["value_4"]
    assert trial.text_events["name_5"].times() == [5]
    assert trial.text_events["name_5"].values() == ["value_5"]

    # Events that use parsed or default numeric values.
    assert trial.numeric_events["name_6"].times() == [6]
    assert trial.numeric_events["name_6"].values() == [enhancer.int_default]
    assert trial.numeric_events["name_7"].times() == [7]
    assert trial.numeric_events["name_7"].values() == [42]
    assert trial.numeric_events["name_8"].times() == [8]
    assert trial.numeric_events["name_8"].values() == [enhancer.float_default]
    assert trial.numeric_events["name_9"].times() == [9]
    assert trial.numeric_events["name_9"].values() == [3.14]

    # Events with multiple occurrences, grouped by name.
    assert np.array_equal(trial.text_events["name_10"].times(), [10, 11, 12])
    assert np.array_equal(trial.text_events["name_10"].values(), ["multi_10", "multi_11", "multi_12"])

    assert np.array_equal(trial.numeric_events["name_11"].times(), [13, 14, 15])
    assert np.array_equal(trial.numeric_events["name_11"].values(), [13.13, 14.14, 15.15])


def test_text_key_value_enhancer_configure_literals():
    enhancer = TextKeyValueEnhancer(
        buffer_name="crazy_text",
        entry_delimiter="|",
        key_value_delimiter="->",
        name_key="N",
        value_key="V",
        type_key="T",
        float_types=["F", "D"],
        float_default=-1e6,
        int_types=["I", "L"],
        int_default=-1
    )

    text = [
        "garbage",
        "unknown->ignored",
        "N->name_2",
        "  N  ->  name_3  ",
        "N->name_4|V->value_4",
        "N->name_5|V->value_5|T->garbage",
        "N->name_6|V->not an int|T->I",
        "N->name_7|V->42|T->L",
        "N->name_8|V->not a float|T->F",
        "N->name_9|V->3.14|T->D",
        "N->name_10|V->multi_10",
        "N->name_10|V->multi_11",
        "N->name_10|V->multi_12",
        "N->name_11|V->13.13|T->F",
        "N->name_11|V->14.14|T->F",
        "N->name_11|V->15.15|T->F",
    ]

    event_list = TextEventList(np.array(range(len(text))), np.array(text, dtype=np.str_))
    trial = Trial(
        start_time=0,
        end_time=20,
        wrt_time=0,
        text_events={
            "crazy_text": event_list,
        }
    )

    enhancer.enhance(trial, 0, {}, {})

    # Some events are parsed as numeric values, otherse as text.
    assert trial.numeric_events.keys() == {"name_2", "name_3", "name_6", "name_7", "name_8", "name_9", "name_11"}
    assert trial.text_events.keys() == {"crazy_text", "name_4", "name_5", "name_10"}

    # Events that use timestamps for their values.
    assert trial.numeric_events["name_2"].times() == [2]
    assert trial.numeric_events["name_2"].values() == [2]
    assert trial.numeric_events["name_3"].times() == [3]
    assert trial.numeric_events["name_3"].values() == [3]

    # Events that use text values.
    assert trial.text_events["name_4"].times() == [4]
    assert trial.text_events["name_4"].values() == ["value_4"]
    assert trial.text_events["name_5"].times() == [5]
    assert trial.text_events["name_5"].values() == ["value_5"]

    # Events that use parsed or default numeric values.
    assert trial.numeric_events["name_6"].times() == [6]
    assert trial.numeric_events["name_6"].values() == [enhancer.int_default]
    assert trial.numeric_events["name_7"].times() == [7]
    assert trial.numeric_events["name_7"].values() == [42]
    assert trial.numeric_events["name_8"].times() == [8]
    assert trial.numeric_events["name_8"].values() == [enhancer.float_default]
    assert trial.numeric_events["name_9"].times() == [9]
    assert trial.numeric_events["name_9"].values() == [3.14]

    # Events with multiple occurrences, grouped by name.
    assert np.array_equal(trial.text_events["name_10"].times(), [10, 11, 12])
    assert np.array_equal(trial.text_events["name_10"].values(), ["multi_10", "multi_11", "multi_12"])

    assert np.array_equal(trial.numeric_events["name_11"].times(), [13, 14, 15])
    assert np.array_equal(trial.numeric_events["name_11"].values(), [13.13, 14.14, 15.15])


def test_saccades_enhancer_empty_trial():
    enhancer = SaccadesEnhancer()
    trial = Trial(
        start_time=0,
        end_time=1,
        wrt_time=0.5
    )
    # Don't error out if the trial is incomplete (like the 0th trial, often), just no-op.
    enhancer.enhance(trial, 0, {}, {})
    assert not trial.enhancements


def test_saccades_enhancer_short_data():
    enhancer = SaccadesEnhancer()
    trial = Trial(
        start_time=0,
        end_time=1,
        wrt_time=0.5
    )
    gaze = SignalChunk(
        sample_data=np.zeros([10, 2]),
        sample_frequency=1000,
        first_sample_time=0.0,
        channel_ids=["x", "y"]
    )
    trial.add_buffer_data("gaze", gaze)
    trial.add_enhancement("fp_off", 4.5)

    # Don't error out if the gaze signal is too short, just no-op.
    enhancer.enhance(trial, 0, {}, {})
    assert not trial.get_enhancement('saccades')


def test_saccades_enhancer_step_saccade():
    enhancer = SaccadesEnhancer(
        min_duration_ms=0.0,
        position_smoothing_kernel_size_ms=1.0,
        acceleration_smoothing_kernel_size_ms=1.0
    )
    trial = Trial(
        start_time=0,
        end_time=10,
        wrt_time=5
    )

    # Fake up gaze positions that start off at (0,0) for 5 seconds,
    # then abruptly step to (5,5) for 5 seconds.
    step_size = 5
    step_samples = np.concatenate([np.zeros([5000,]), np.ones([5000,])]) * step_size
    gaze_samples = np.stack([step_samples, step_samples], axis=1)
    gaze = SignalChunk(
        sample_data=gaze_samples,
        sample_frequency=1000,
        first_sample_time=0.0,
        channel_ids=["x", "y"]
    )
    trial.add_buffer_data("gaze", gaze)

    # Fake trial config roughly consistent with the fake gaze positions.
    trial.add_enhancement("fp_off", 4.5)
    trial.add_enhancement("all_off", 5.5)
    trial.add_enhancement("fp_x", 0.0)
    trial.add_enhancement("fp_y", 0.0)

    # Find the a saccade at the step in gaze position.
    # The code will end up detecting this by gaze acceleration.
    enhancer.enhance(trial, 0, {}, {})
    saccades = trial.get_enhancement('saccades')
    assert saccades == [
        {
            't_start': 4.981,
            't_end': 5.004,
            'v_max': 280.70917823751074,
            'v_avg': 307.437730950677,
            'x_start': 0.0,
            'y_start': 0.0,
            'x_end': 5.0,
            'y_end': 5.0,
            'raw_distance': 4.31435627109525,
            'vector_distance': 7.0710678118654755
        }
    ]

    # Find the same saccade again, but force the code to use saccade velocity.
    enhancer.acceleration_threshold_deg_per_s2 = 1000
    enhancer.velocity_threshold_deg_per_s = 200
    enhancer.enhance(trial, 0, {}, {})
    saccades = trial.get_enhancement('saccades')
    assert saccades == [
        {
            't_start': 4.992,
            't_end': 5.009,
            'v_max': 280.70917823751074,
            'v_avg': 415.94516540384296,
            'x_start': 0.0,
            'y_start': 0.0,
            'x_end': 5.0,
            'y_end': 5.0,
            'raw_distance': 4.260679185446772,
            'vector_distance': 7.0710678118654755
        }
    ]
