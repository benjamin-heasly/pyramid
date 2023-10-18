from typing import Any, Self
from pathlib import Path
import time
import logging
from contextlib import ExitStack
from dataclasses import dataclass
import yaml
import graphviz

from pyramid.file_finder import FileFinder
from pyramid.model.model import Buffer
from pyramid.neutral_zone.readers.readers import Reader, ReaderRoute, ReaderRouter, Transformer, ReaderSyncConfig, ReaderSyncRegistry
from pyramid.neutral_zone.readers.delay_simulator import DelaySimulatorReader
from pyramid.trials.trials import TrialDelimiter, TrialExtractor, TrialEnhancer, TrialExpression
from pyramid.trials.trial_file import TrialFile
from pyramid.plotters.plotters import Plotter, PlotFigureController


@dataclass
class PyramidContext():
    """Pyramid context holds everything needed to run Pyramid including experiment YAML, CLI args, etc."""
    subject: dict[str, Any]
    experiment: dict[str, Any]
    readers: dict[str, Reader]
    named_buffers: dict[str, Buffer]
    start_router: ReaderRouter
    routers: dict[str, ReaderRouter]
    trial_delimiter: TrialDelimiter
    trial_extractor: TrialExtractor
    sync_registry: ReaderSyncRegistry
    plot_figure_controller: PlotFigureController
    file_finder: FileFinder

    @classmethod
    def from_yaml_and_reader_overrides(
        cls,
        experiment_yaml: str,
        subject_yaml: str = None,
        reader_overrides: list[str] = [],
        allow_simulate_delay: bool = False,
        plot_positions_yaml: str = None,
        search_path: list[str] = []
    ) -> Self:
        """Load a context the way it comes from the CLI, with a YAML files etc."""
        file_finder = FileFinder(search_path)

        with open(file_finder.find(experiment_yaml)) as f:
            experiment_config = yaml.safe_load(f)

        # For example, command line might have "--readers start_reader.csv_file=real.csv",
        # which should be equivalent to start_reader kwargs "csv_file=real.csv".
        if reader_overrides:
            for override in reader_overrides:
                (reader_name, assignment) = override.split(".", maxsplit=1)
                (property, value) = assignment.split("=", maxsplit=1)
                reader_config = experiment_config["readers"][reader_name]
                reader_args = reader_config.get("args", {})
                reader_args[property] = value
                reader_config["args"] = reader_args

        if subject_yaml:
            with open(file_finder.find(subject_yaml)) as f:
                subject_config = yaml.safe_load(f)
        else:
            subject_config = {}

        pyramid_context = cls.from_dict(
            experiment_config,
            subject_config,
            allow_simulate_delay,
            plot_positions_yaml,
            file_finder
        )
        return pyramid_context

    @classmethod
    def from_dict(
        cls,
        experiment_config: dict[str, Any],
        subject_config: dict[str, Any],
        allow_simulate_delay: bool = False,
        plot_positions_yaml: str = None,
        file_finder: FileFinder = FileFinder()
    ) -> Self:
        """Load a context after things like YAML files are already read into memory."""
        (readers, named_buffers, reader_routers, reader_sync_registry) = configure_readers(
            experiment_config["readers"],
            allow_simulate_delay,
            file_finder
        )
        (trial_delimiter, trial_extractor, start_buffer_name) = configure_trials(
            experiment_config["trials"],
            named_buffers,
            file_finder
        )

        # Rummage around in the configured reader routers for the one associated with the trial "start" delimiter.
        start_router = None
        for router in reader_routers.values():
            for buffer_name in router.named_buffers.keys():
                if buffer_name == start_buffer_name:
                    start_router = router

        plotters = configure_plotters(
            experiment_config.get("plotters", []),
            file_finder
        )
        subject = subject_config.get("subject", {})
        experiment = experiment_config.get("experiment", {})
        plot_figure_controller = PlotFigureController(
            plotters=plotters,
            experiment_info=experiment,
            subject_info=subject,
            plot_positions_yaml=file_finder.find(plot_positions_yaml)
        )
        return PyramidContext(
            subject=subject,
            experiment=experiment,
            readers=readers,
            named_buffers=named_buffers,
            start_router=start_router,
            routers=reader_routers,
            trial_delimiter=trial_delimiter,
            trial_extractor=trial_extractor,
            sync_registry=reader_sync_registry,
            plot_figure_controller=plot_figure_controller,
            file_finder=file_finder
        )

    def run_without_plots(self, trial_file: str) -> None:
        """Run without plots as fast as the data allow.

        Similar to run_with_plots(), below.
        It seemed nicer to have separate code paths, as opposed to lots of conditionals in one uber-function.
        run_without_plots() should run without touching any GUI code, avoiding potential host graphics config issues.
        """
        with ExitStack() as stack:
            # All these "context managers" will clean up automatically when the "with" exits.
            writer = stack.enter_context(TrialFile.for_file_suffix(self.file_finder.find(trial_file)))
            for reader in self.readers.values():
                stack.enter_context(reader)

            # Extract trials indefinitely, as they come.
            while self.start_router.still_going():
                got_start_data = self.start_router.route_next()
                if got_start_data:
                    new_trials = self.trial_delimiter.next()
                    for trial_number, new_trial in new_trials.items():
                        # Let all readers catch up to the trial end time.
                        for router in self.routers.values():
                            router.route_until(new_trial.end_time)

                        # Re-estimate clock drift for all readers using latest events from reference and other readers.
                        for router in self.routers.values():
                            router.update_drift_estimate(new_trial.end_time)

                        self.trial_extractor.populate_trial(new_trial, trial_number, self.experiment, self.subject)
                        writer.append_trial(new_trial)
                        self.trial_delimiter.discard_before(new_trial.start_time)
                        self.trial_extractor.discard_before(new_trial.start_time)

            # Make a best effort to catch the last trial -- which would have no "next trial" to delimit it.
            for router in self.routers.values():
                router.route_next()
            # Re-estimate clock drift for all readers using last events from reference and other readers.
            for router in self.routers.values():
                router.update_drift_estimate()
            (last_trial_number, last_trial) = self.trial_delimiter.last()
            if last_trial:
                self.trial_extractor.populate_trial(last_trial, last_trial_number, self.experiment, self.subject)
                writer.append_trial(last_trial)

    def run_with_plots(self, trial_file: str, plot_update_period: float = 0.025) -> None:
        """Run with plots and interactive GUI updates.

        Similar to run_without_plots(), above.
        It seemed nicer to have separate code paths, as opposed to lots of conditionals in one uber-function.
        run_without_plots() should run without touching any GUI code, avoiding potential host graphics config issues.
        """
        with ExitStack() as stack:
            # All these "context managers" will clean up automatically when the "with" exits.
            writer = stack.enter_context(TrialFile.for_file_suffix(self.file_finder.find(trial_file)))
            for reader in self.readers.values():
                stack.enter_context(reader)
            stack.enter_context(self.plot_figure_controller)

            # Extract trials indefinitely, as they come.
            next_gui_update = time.time()
            while self.start_router.still_going() and self.plot_figure_controller.stil_going():
                if time.time() > next_gui_update:
                    self.plot_figure_controller.update()
                    next_gui_update += plot_update_period

                got_start_data = self.start_router.route_next()

                if got_start_data:
                    new_trials = self.trial_delimiter.next()
                    for trial_number, new_trial in new_trials.items():
                        # Let all readers catch up to the trial end time.
                        for router in self.routers.values():
                            router.route_until(new_trial.end_time)

                        # Re-estimate clock drift for all readers using latest events from reference and other readers.
                        for router in self.routers.values():
                            router.update_drift_estimate(new_trial.end_time)

                        self.trial_extractor.populate_trial(new_trial, trial_number, self.experiment, self.subject)
                        writer.append_trial(new_trial)
                        self.plot_figure_controller.plot_next(new_trial, trial_number)
                        self.trial_delimiter.discard_before(new_trial.start_time)
                        self.trial_extractor.discard_before(new_trial.start_time)

            # Make a best effort to catch the last trial -- which would have no "next trial" to delimit it.
            for router in self.routers.values():
                router.route_next()
            # Re-estimate clock drift for all readers using last events from reference and other readers.
            for router in self.routers.values():
                router.update_drift_estimate()
            (last_trial_number, last_trial) = self.trial_delimiter.last()
            if last_trial:
                self.trial_extractor.populate_trial(last_trial, last_trial_number, self.experiment, self.subject)
                writer.append_trial(last_trial)
                self.plot_figure_controller.plot_next(last_trial, last_trial_number)

    def to_graphviz(self, graph_name: str, out_file: str):
        """Do introspection of loaded config and write out a graphviz "dot" file and overview image for viewing."""

        # TODO: visualize sync config, where present
        # TODO: visualize conditional enhancements, when present
        # TODO: visualize reader args

        dot = graphviz.Digraph(
            name=graph_name,
            graph_attr={
                "rankdir": "LR",
                "label": graph_name,
                "splines": "false",
                "overlap": "scale",
                "ranksep": "3.0"
            },
            node_attr={
                "penwidth": "2.0"
            },
            edge_attr={
                "penwidth": "2.0"
            }
        )

        results_styles = {}

        for reader_index, (name, reader) in enumerate(self.readers.items()):
            label = f"{name}|{reader.__class__.__name__}"
            for result_index, result_name in enumerate(reader.get_initial().keys()):
                label += f"|<{result_name}>{result_name}"
                style_index = (reader_index + result_index) % 3
                if style_index == 2:
                    results_styles[result_name] = {"color": '#648FFF'}
                elif style_index == 1:
                    results_styles[result_name] = {"color": '#DC267F'}
                else:
                    results_styles[result_name] = {"color": '#FFB000'}

            dot.node(name=name, label=label, shape="record")

        start_buffer_name = None
        wrt_buffer_name = None
        for name, buffer in self.named_buffers.items():
            label = f"{name}|{buffer.__class__.__name__}|{buffer.data.__class__.__name__}"
            buffer_style = results_styles.get(name, {})
            dot.node(name=name, label=label, shape="record", **buffer_style)
            if buffer is self.trial_delimiter.start_buffer:
                start_buffer_name = name
            if buffer is self.trial_extractor.wrt_buffer:
                wrt_buffer_name = name

        for reader_name, router in self.routers.items():
            for result_index, route in enumerate(router.routes):
                route_name = f"{reader_name}_route_{result_index}"
                if route.transformers:
                    labels = [transformer.__class__.__name__ for transformer in route.transformers]
                    route_label = "|".join(labels)
                else:
                    route_label = "as is"
                dot.node(name=route_name, label=route_label, shape="record", **results_styles[route.reader_result_name])

                dot.edge(f"{reader_name}:{route.reader_result_name}:e",
                         f"{route_name}:w", **results_styles[route.reader_result_name])
                dot.edge(f"{route_name}:e", f"{route.buffer_name}:w", **results_styles[route.reader_result_name])

        dot.node(
            name="trial_delimiter",
            label=f"{self.trial_delimiter.__class__.__name__}|start = {self.trial_delimiter.start_value}",
            shape="record"
        )
        dot.edge(
            start_buffer_name,
            "trial_delimiter",
            label="start",
            arrowhead="none",
            arrowtail="none")

        extractor_label = f"{self.trial_extractor.__class__.__name__}|wrt = {self.trial_extractor.wrt_value}"
        if self.trial_extractor.enhancers:
            enhancer_names = [enhancer.__class__.__name__ for enhancer in self.trial_extractor.enhancers]
            enhancers_label = "|".join(enhancer_names)
            extractor_label = f"{extractor_label}|{enhancers_label}"
        dot.node(
            name="trial_extractor",
            label=extractor_label,
            shape="record"
        )
        dot.edge(
            wrt_buffer_name,
            "trial_extractor",
            label=f"wrt",
            arrowhead="none",
            arrowtail="none"
        )

        out_path = Path(out_file)
        file_name = f"{out_path.stem}.dot"
        dot.render(directory=out_path.parent, filename=file_name, outfile=out_path)


def configure_readers(
    readers_config: dict[str, dict],
    allow_simulate_delay: bool = False,
    file_finder: FileFinder = FileFinder()
) -> tuple[dict[str, Reader], dict[str, Buffer], dict[str, ReaderRouter]]:
    """Load the "readers:" section of an experiment YAML file."""

    readers = {}
    named_buffers = {}
    routers = {}

    # We'll update the reference_reader_name below based on individual reader sync config.
    reader_sync_registry = ReaderSyncRegistry(reference_reader_name=None)

    logging.info(f"Using {len(readers_config)} readers.")
    for (reader_name, reader_config) in readers_config.items():
        # Instantiate the reader by dynamic import.
        reader_class = reader_config["class"]
        logging.info(f"  {reader_class}")
        package_path = reader_config.get("package_path", None)
        reader_args = reader_config.get("args", {})
        simulate_delay = allow_simulate_delay and reader_config.get("simulate_delay", False)
        reader = Reader.from_dynamic_import(
            reader_class,
            file_finder,
            external_package_path=package_path,
            **reader_args
        )
        if simulate_delay:
            reader = DelaySimulatorReader(reader)
        readers[reader_name] = reader

        # Configure default, pass-through routes for the reader.
        initial_results = reader.get_initial()
        named_routes = {buffer_name: ReaderRoute(buffer_name, buffer_name) for buffer_name in initial_results.keys()}

        # Update default routes with explicitly configured aliases and transformations.
        buffers_config = reader_config.get("extra_buffers", {})
        for buffer_name, buffer_config in buffers_config.items():

            # Instantiate transformers by dynamic import.
            transformers = []
            transformers_config = buffer_config.get("transformers", [])
            logging.info(f"Buffer {buffer_name} using {len(transformers_config)} transformers.")
            for transformer_config in transformers_config:
                transformer_class = transformer_config["class"]
                logging.info(f"  {transformer_class}")
                package_path = transformer_config.get("package_path", None)
                transformer_args = transformer_config.get("args", {})
                transformer = Transformer.from_dynamic_import(
                    transformer_class,
                    file_finder,
                    external_package_path=package_path,
                    **transformer_args
                )
                transformers.append(transformer)

            reader_result_name = buffer_config.get("reader_result_name", buffer_name)
            route = ReaderRoute(reader_result_name, buffer_name, transformers)
            named_routes[buffer_name] = route

        # Create a buffer to receive data from each route.
        reader_buffers = {}
        for route in named_routes.values():
            initial_data = initial_results[route.reader_result_name]
            if initial_data is not None:
                data_copy = initial_data.copy()
                for transformer in route.transformers:
                    data_copy = transformer.transform(data_copy)
                reader_buffers[route.buffer_name] = Buffer(data_copy)

        # Configure sync events for correcting clock drift for this reader.
        sync_config = reader_config.get("sync", {})
        if sync_config:
            sync_config_plus_default = {"reader_name": reader_name, **sync_config}
            reader_sync_config = ReaderSyncConfig(**sync_config_plus_default)

            # Fill in the reference reader name which had a None placeholder, above.
            if reader_sync_config.is_reference:
                reader_sync_registry.reference_reader_name = reader_name
        else:
            reader_sync_config = None

        # Create a router to route data from the reader along each configured route to its buffer.
        empty_reads_allowed = reader_config.get("empty_reads_allowed", 3)
        router = ReaderRouter(
            reader=reader,
            routes=list(named_routes.values()),
            named_buffers=reader_buffers,
            empty_reads_allowed=empty_reads_allowed,
            sync_config=reader_sync_config,
            sync_registry=reader_sync_registry
        )
        routers[reader_name] = router
        named_buffers.update(router.named_buffers)

    logging.info(f"Using {len(named_buffers)} named buffers.")
    for name in named_buffers.keys():
        logging.info(f"  {name}")

    return (readers, named_buffers, routers, reader_sync_registry)


def configure_trials(
    trials_config: dict[str, Any],
    named_buffers: dict[str, Buffer],
    file_finder: FileFinder = FileFinder()
) -> tuple[TrialDelimiter, TrialExtractor, str]:
    """Load the "trials:" section of an experiment YAML file."""

    start_buffer_name = trials_config.get("start_buffer", "start")
    start_value = trials_config.get("start_value", 0.0)
    start_value_index = trials_config.get("start_value_index", 0)
    trial_start_time = trials_config.get("trial_start_time", 0.0)
    trial_count = trials_config.get("trial_count", 0)
    trial_delimiter = TrialDelimiter(
        start_buffer=named_buffers[start_buffer_name],
        start_value=start_value,
        start_value_index=start_value_index,
        start_time=trial_start_time,
        trial_count=trial_count
    )

    wrt_buffer_name = trials_config.get("wrt_buffer", "wrt")
    wrt_value = trials_config.get("wrt_value", 0.0)
    wrt_value_index = trials_config.get("wrt_value_index", 0)

    other_buffers = {name: buffer for name, buffer in named_buffers.items()
                     if name != start_buffer_name and name != wrt_buffer_name}

    enhancers = {}
    enhancers_config = trials_config.get("enhancers", [])
    logging.info(f"Using {len(enhancers_config)} per-trial enhancers.")
    for enhancer_config in enhancers_config:
        enhancer_class = enhancer_config["class"]
        package_path = enhancer_config.get("package_path", None)
        enhancer_args = enhancer_config.get("args", {})
        enhancer = TrialEnhancer.from_dynamic_import(
            enhancer_class,
            file_finder,
            external_package_path=package_path,
            **enhancer_args
        )

        when_string = enhancer_config.get("when", None)
        if when_string is not None:
            logging.info(f"  {enhancer_class} when {when_string}")
            when_expression = TrialExpression(expression=when_string, default_value=False)
        else:
            logging.info(f"  {enhancer_class}")
            when_expression = None

        enhancers[enhancer] = when_expression

    trial_extractor = TrialExtractor(
        wrt_buffer=named_buffers[wrt_buffer_name],
        wrt_value=wrt_value,
        wrt_value_index=wrt_value_index,
        named_buffers=other_buffers,
        enhancers=enhancers
    )

    return (trial_delimiter, trial_extractor, start_buffer_name)


def configure_plotters(
    plotters_config: list[dict[str, str]],
    file_finder: FileFinder = FileFinder()
) -> list[Plotter]:
    """Load the "plotters:" section of an experiment YAML file."""

    if not plotters_config:
        logging.info(f"No plotters.")
        return []

    logging.info(f"Using {len(plotters_config)} plotters.")
    plotters = []
    for plotter_config in plotters_config:
        plotter_class = plotter_config["class"]
        logging.info(f"  {plotter_class}")
        package_path = plotter_config.get("package_path", None)
        plotter_args = plotter_config.get("args", {})
        plotter = Plotter.from_dynamic_import(
            plotter_class,
            file_finder,
            external_package_path=package_path,
            **plotter_args
        )
        plotters.append(plotter)

    return plotters
