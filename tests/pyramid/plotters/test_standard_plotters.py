import numpy as np

from pyramid.model.events import NumericEventList, TextEventList
from pyramid.model.signals import SignalChunk
from pyramid.trials.trials import Trial
from pyramid.plotters.plotters import PlotFigureController
from pyramid.plotters.standard_plotters import (
    BasicInfoPlotter,
    NumericEventsPlotter,
    TextEventsPlotter,
    SignalChunksPlotter,
    EnhancementTimesPlotter,
    EnhancementXYPlotter,
    SpikeEventsPlotter
)


def test_basic_info_plotter():
    trial = Trial(0.0, 1.0, 0.5)
    experiment_info = {
        "experimenter": ["Person One", "Second Person"]
    }
    subject_info = {
        "subject_id": "The subject"
    }
    plotter = BasicInfoPlotter()
    with PlotFigureController([plotter], experiment_info, subject_info) as controller:
        controller.plot_next(trial, trial_number=0)
        controller.update()

        assert plotter.static_table[0, 0].get_text().get_text() == "experimenter"
        assert plotter.static_table[0, 1].get_text().get_text() == "['Person One', 'Second Person']"
        assert plotter.static_table[1, 0].get_text().get_text() == "subject_id"
        assert plotter.static_table[1, 1].get_text().get_text() == "The subject"

        assert plotter.trials_table[0, 0].get_text().get_text() == "pyramid elapsed:"
        assert plotter.trials_table[1, 0].get_text().get_text() == "trial number:"
        assert plotter.trials_table[1, 1].get_text().get_text() == "0"
        assert plotter.trials_table[2, 0].get_text().get_text() == "trial start:"
        assert plotter.trials_table[2, 1].get_text().get_text() == "0.000 sec"
        assert plotter.trials_table[3, 0].get_text().get_text() == "trial wrt:"
        assert plotter.trials_table[3, 1].get_text().get_text() == "0.500 sec"
        assert plotter.trials_table[4, 0].get_text().get_text() == "trial end:"
        assert plotter.trials_table[4, 1].get_text().get_text() == "1.000 sec"


def test_numeric_events_plotter():
    trial_0 = Trial(0.0, 1.0, 0.5)
    trial_0.add_buffer_data("foo", NumericEventList(np.array([[0, 100], [1, 101], [2, 102]])))
    trial_0.add_buffer_data("bar", NumericEventList(np.array([[0, 42], [1, 43], [2, 42]])))
    trial_0.add_buffer_data("baz", NumericEventList.empty(1))
    trial_1 = Trial(1.0, 2.0, 1.5)
    trial_1.add_buffer_data("foo", NumericEventList(np.array([[0, 200], [1, 201], [2, 202]])))
    trial_1.add_buffer_data("bar", NumericEventList(np.array([[0, 52], [1, 53], [2, 52]])))
    trial_1.add_buffer_data("baz", NumericEventList.empty(1))
    plotter = NumericEventsPlotter(match_pattern="foo|bar")
    with PlotFigureController([plotter]) as controller:
        controller.plot_next(trial_0, trial_number=0)
        controller.update()
        assert len(plotter.history) == 1
        assert plotter.history[0]["foo"] == trial_0.numeric_events["foo"]
        assert plotter.history[0]["bar"] == trial_0.numeric_events["bar"]
        assert "baz" not in plotter.history[0]

        controller.plot_next(trial_1, trial_number=1)
        controller.update()
        assert len(plotter.history) == 2
        assert plotter.history[0]["foo"] == trial_0.numeric_events["foo"]
        assert plotter.history[0]["bar"] == trial_0.numeric_events["bar"]
        assert "baz" not in plotter.history[0]
        assert plotter.history[1]["foo"] == trial_1.numeric_events["foo"]
        assert plotter.history[1]["bar"] == trial_1.numeric_events["bar"]
        assert "baz" not in plotter.history[1]


def test_text_events_plotter_no_filter():
    trial_0 = Trial(0.0, 1.0, 0.5)
    trial_0.add_buffer_data("foo", TextEventList(np.array(range(2)), np.array(range(2), dtype=np.str_)))
    trial_0.add_buffer_data("bar", TextEventList(np.array(range(8)), np.array(range(8), dtype=np.str_)))
    trial_0.add_buffer_data("baz", TextEventList(np.array(range(1)), np.array(range(1), dtype=np.str_)))
    plotter = TextEventsPlotter()
    with PlotFigureController([plotter]) as controller:

        controller.update()
        assert len(plotter.history) == 0

        controller.plot_next(trial_0, trial_number=0)
        controller.update()
        assert len(plotter.history) == 11
        trials = [row[0] for row in plotter.history]
        assert trials == [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        buffers = [row[1] for row in plotter.history]
        assert buffers == ["foo", "foo", "bar", "bar", "bar", "bar", "bar", "bar", "bar", "bar", "baz"]


def test_text_events_plotter_with_filter():
    trial_0 = Trial(0.0, 1.0, 0.5)
    trial_0.add_buffer_data("baz", TextEventList(np.array(range(1)), np.array(range(1), dtype=np.str_)))
    trial_1 = Trial(1.0, 2.0, 1.5)
    trial_1.add_buffer_data("foo", TextEventList(np.array(range(2)), np.array(range(2), dtype=np.str_)))
    trial_1.add_buffer_data("bar", TextEventList(np.array(range(8)), np.array(range(8), dtype=np.str_)))
    trial_1.add_buffer_data("baz", TextEventList(np.array(range(1)), np.array(range(1), dtype=np.str_)))
    trial_2 = Trial(2.0, 3.0, 2.5)
    trial_2.add_buffer_data("foo", TextEventList(np.array(range(2)), np.array(range(2), dtype=np.str_)))
    trial_2.add_buffer_data("bar", TextEventList(np.array(range(8)), np.array(range(8), dtype=np.str_)))
    trial_2.add_buffer_data("baz", TextEventList(np.array(range(1)), np.array(range(1), dtype=np.str_)))
    trial_3 = Trial(3.0, 4.0, 3.5)
    trial_3.add_buffer_data("foo", TextEventList(np.array(range(2)), np.array(range(2), dtype=np.str_)))
    trial_3.add_buffer_data("bar", TextEventList(np.array(range(3)), np.array(range(3), dtype=np.str_)))
    trial_3.add_buffer_data("baz", TextEventList(np.array(range(1)), np.array(range(1), dtype=np.str_)))
    plotter = TextEventsPlotter(match_pattern="foo|bar")
    with PlotFigureController([plotter]) as controller:

        controller.update()
        assert len(plotter.history) == 0

        controller.plot_next(trial_0, trial_number=0)
        controller.update()
        assert len(plotter.history) == 0

        controller.plot_next(trial_1, trial_number=1)
        controller.update()
        assert len(plotter.history) == 10
        trials = [row[0] for row in plotter.history]
        assert trials == [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
        buffers = [row[1] for row in plotter.history]
        assert buffers == ["foo", "foo", "bar", "bar", "bar", "bar", "bar", "bar", "bar", "bar"]

        controller.plot_next(trial_2, trial_number=2)
        controller.update()
        assert len(plotter.history) == 20
        trials = [row[0] for row in plotter.history]
        assert trials == [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2]
        buffers = [row[1] for row in plotter.history]
        assert buffers == ["foo", "foo", "bar", "bar", "bar", "bar", "bar", "bar", "bar", "bar",
                           "foo", "foo", "bar", "bar", "bar", "bar", "bar", "bar", "bar", "bar"]

        controller.plot_next(trial_3, trial_number=3)
        controller.update()
        assert len(plotter.history) == 20
        trials = [row[0] for row in plotter.history]
        assert trials == [1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3]
        buffers = [row[1] for row in plotter.history]
        assert buffers == ["bar", "bar", "bar", "bar", "bar",
                           "foo", "foo", "bar", "bar", "bar", "bar", "bar", "bar", "bar", "bar",
                           "foo", "foo", "bar", "bar", "bar"]


def test_signal_chunks_plotter():
    trial_0 = Trial(0.0, 1.0, 0.5)
    trial_0.add_buffer_data(
        "foo",
        SignalChunk(
            sample_data=np.array([[0, 100], [1, 101], [2, 102]]),
            sample_frequency=1,
            first_sample_time=0,
            channel_ids=[10, 11]
        )
    )
    trial_0.add_buffer_data(
        "bar",
        SignalChunk(
            sample_data=np.array([[0, 42], [1, 43], [2, 42]]),
            sample_frequency=1,
            first_sample_time=0,
            channel_ids=[12, 13]
        )
    )
    trial_0.add_buffer_data(
        "baz",
        SignalChunk.empty(
            sample_frequency=1,
            first_sample_time=0,
            channel_ids=[14, 15]
        )
    )
    trial_1 = Trial(1.0, 2.0, 1.5)
    trial_1.add_buffer_data(
        "foo",
        SignalChunk(
            sample_data=np.array([[0, 200], [1, 201], [2, 202]]),
            sample_frequency=1,
            first_sample_time=0,
            channel_ids=[10, 11]
        )
    )
    trial_1.add_buffer_data(
        "bar",
        SignalChunk(
            sample_data=np.array([[0, 52], [1, 53], [2, 52]]),
            sample_frequency=1,
            first_sample_time=0,
            channel_ids=[12, 13]
        )
    )
    trial_1.add_buffer_data(
        "baz",
        SignalChunk.empty(
            sample_frequency=1,
            first_sample_time=0,
            channel_ids=[14, 15]
        )
    )
    plotter = SignalChunksPlotter(match_pattern="foo|bar", channel_ids=[10, 11, 12])
    with PlotFigureController([plotter]) as controller:
        controller.plot_next(trial_0, trial_number=0)
        controller.update()
        assert len(plotter.history) == 1
        assert plotter.history[0]["foo"] == trial_0.signals["foo"]
        assert plotter.history[0]["bar"] == trial_0.signals["bar"]
        assert "baz" not in plotter.history[0]

        controller.plot_next(trial_1, trial_number=1)
        controller.update()
        assert len(plotter.history) == 2
        assert plotter.history[0]["foo"] == trial_0.signals["foo"]
        assert plotter.history[0]["bar"] == trial_0.signals["bar"]
        assert "baz" not in plotter.history[0]
        assert plotter.history[1]["foo"] == trial_1.signals["foo"]
        assert plotter.history[1]["bar"] == trial_1.signals["bar"]
        assert "baz" not in plotter.history[1]


def test_enhancement_times_plotter():
    trial_0 = Trial(0.0, 1.0, 0.5)
    trial_0.add_enhancement("foo", [0.1, 0.2, 0.3], "time")
    trial_0.add_enhancement("bar", [1.6], "time")
    trial_0.add_enhancement("baz", [42], "time")
    trial_0.add_enhancement("quux", 9.8, "value")
    trial_1 = Trial(1.0, 2.0, 1.5)
    trial_1.add_enhancement("foo", [0.11, 0.21, 0.31], "time")
    trial_1.add_enhancement("bar", [1.7], "time")
    trial_1.add_enhancement("baz", [43], "time")
    trial_1.add_enhancement("quux", 6.2, "value")
    plotter = EnhancementTimesPlotter(match_pattern="foo|bar")
    with PlotFigureController([plotter]) as controller:
        controller.plot_next(trial_0, trial_number=0)
        controller.update()
        assert len(plotter.history) == 1
        assert plotter.history[0]["foo"] == trial_0.get_enhancement("foo")
        assert plotter.history[0]["bar"] == trial_0.get_enhancement("bar")
        assert "baz" not in plotter.history[0]
        assert "quuz" not in plotter.history[0]

        controller.plot_next(trial_1, trial_number=1)
        controller.update()
        assert len(plotter.history) == 2
        assert plotter.history[0]["foo"] == trial_0.get_enhancement("foo")
        assert plotter.history[0]["bar"] == trial_0.get_enhancement("bar")
        assert "baz" not in plotter.history[0]
        assert "quuz" not in plotter.history[0]
        assert plotter.history[1]["foo"] == trial_1.get_enhancement("foo")
        assert plotter.history[1]["bar"] == trial_1.get_enhancement("bar")
        assert "baz" not in plotter.history[1]
        assert "quuz" not in plotter.history[1]


def test_enhancement_xy_plotter():
    trial_0 = Trial(0.0, 1.0, 0.5)
    trial_0.add_enhancement("foox", 0)
    trial_0.add_enhancement("fooy", 1)
    trial_0.add_enhancement("bar", {"x": 2, "y": 3})
    trial_0.add_enhancement("bazx", 4)
    trial_0.add_enhancement("bazy", 5)
    trial_1 = Trial(1.0, 2.0, 1.5)
    trial_1.add_enhancement("foox", 6)
    trial_1.add_enhancement("fooy", 7)
    trial_1.add_enhancement("bar", {"x": 8, "y": 9})
    trial_1.add_enhancement("bazx", 0)
    trial_1.add_enhancement("bazy", 1)
    plotter = EnhancementXYPlotter(
        xy_points={"foox": "fooy"},
        xy_groups={"bar": {"x": "y"}}
    )
    with PlotFigureController([plotter]) as controller:
        controller.plot_next(trial_0, trial_number=0)
        controller.update()
        assert len(plotter.history) == 1
        assert plotter.history[0]["foox"] == (trial_0.get_enhancement("foox"), trial_0.get_enhancement("fooy"))
        assert plotter.history[0]["bar"] == ([trial_0.get_enhancement("bar")['x']],
                                             [trial_0.get_enhancement("bar")['y']])
        assert "bazx" not in plotter.history[0]
        assert "bazy" not in plotter.history[0]

        controller.plot_next(trial_1, trial_number=1)
        controller.update()
        assert len(plotter.history) == 2
        assert plotter.history[0]["foox"] == (trial_0.get_enhancement("foox"), trial_0.get_enhancement("fooy"))
        assert plotter.history[0]["bar"] == ([trial_0.get_enhancement("bar")['x']],
                                             [trial_0.get_enhancement("bar")['y']])
        assert "bazx" not in plotter.history[0]
        assert "bazy" not in plotter.history[0]
        assert plotter.history[1]["foox"] == (trial_1.get_enhancement("foox"), trial_1.get_enhancement("fooy"))
        assert plotter.history[1]["bar"] == ([trial_1.get_enhancement("bar")['x']],
                                             [trial_1.get_enhancement("bar")['y']])
        assert "bazx" not in plotter.history[1]
        assert "bazy" not in plotter.history[1]


def test_spike_events_plotter():
    trial_0 = Trial(0.0, 1.0, 0.5)
    trial_0.add_buffer_data("foo", NumericEventList(np.array([[0, 1, 0], [1, 1, 1], [2, 1, 0]])))
    trial_0.add_buffer_data("bar", NumericEventList(np.array([[0, 2, 0], [1, 2, 1], [2, 2, 2]])))
    trial_0.add_buffer_data("baz", NumericEventList.empty(1))
    trial_1 = Trial(1.0, 2.0, 1.5)
    trial_1.add_buffer_data("foo", NumericEventList(np.array([[0, 1, 1], [1, 1, 1], [2, 3, 0]])))
    trial_1.add_buffer_data("bar", NumericEventList(np.array([[0, 2, 2], [1, 4, 1], [2, 2, 0]])))
    trial_1.add_buffer_data("baz", NumericEventList.empty(1))
    plotter = SpikeEventsPlotter(
        match_pattern="foo|bar",
        value_index=1,
        value_selection=0
    )
    with PlotFigureController([plotter]) as controller:
        controller.plot_next(trial_0, trial_number=0)
        controller.update()

        controller.plot_next(trial_1, trial_number=1)
        controller.update()
