# Pyramid Command Line Interface

This page is about Pyramid's command line interface (CLI) which is the main, indended way to invoke Pyramid.
Your command line and your [Pyramid YAML file](./yaml-config.md) tell Pyramid what to do with your data.

# Help Text

The `pyramid` executable is installed when you install Pyramid with `pip`.
Call this with the `--help` option to get the source of truth / reference / help text for how you can invoke Pyramid.

As of writing in June 2024 the help text looks like this:

```
$ pyramid --help

2024-06-20 14:06:41,384 [INFO] Pyramid 0.0.1
usage: pyramid [-h] [--experiment EXPERIMENT] [--subject SUBJECT] [--readers READERS [READERS ...]] [--trial-file TRIAL_FILE] [--graph-file GRAPH_FILE] [--plot-positions PLOT_POSITIONS] [--search-path SEARCH_PATH [SEARCH_PATH ...]] [--version]
               {gui,convert,graph}

Read raw data and extract trials for viewing and analysis.

positional arguments:
  {gui,convert,graph}   mode to run in: interactive gui, noninteractive convert, or configuration graph

options:
  -h, --help            show this help message and exit
  --experiment EXPERIMENT, -e EXPERIMENT
                        Name of the experiment YAML file
  --subject SUBJECT, -s SUBJECT
                        Name of the subject YAML file
  --readers READERS [READERS ...], -r READERS [READERS ...]
                        Reader args eg: --readers reader_name.arg_name=value reader_name.arg_name=value ...
  --trial-file TRIAL_FILE, -f TRIAL_FILE
                        Trial file to write: (.json or .jsonl) -> JSON lines, (.hdf, .h5, .hdf5, or .he5) -> HDF5
  --graph-file GRAPH_FILE, -g GRAPH_FILE
                        Graph file to write: several formats supported like .pfd and .png
  --plot-positions PLOT_POSITIONS, -p PLOT_POSITIONS
                        Name of a YAML where Pyramid can record and restore plot figure window positions
  --search-path SEARCH_PATH [SEARCH_PATH ...], -P SEARCH_PATH [SEARCH_PATH ...]
                        List of paths to search for files (YAML config, data, etc.)
  --version, -v         show program's version number and exit
```

Read on for some examples and discussion of how to use the Pyramid CLI.

# CLI Examples

Here are some example of how to call Pyramid from the CLI.

## convert

Here's the simplest command to tell Pyramid to `convert` some data to an HDF5 trial file.

```
pyramid convert --trial-file my-trials.hdf5 --experiment my_experiment.yaml
```

This would expect YAML configuration in `my_experiment.yaml`, including which data files or other sources to read.

This would create an HDF5 trial file named `my-trials.hdf5`.

## override reader args

This extends the simple example above with some argument overrides.

```
pyramid convert \
  --trial-file my-trials.hdf5 \
  --experiment my_experiment.yaml \
  --readers my_reader_1.file_name=override.csv my_reader_2.file_name=override.bin
```

This expects that `my_experiment.yaml` declares readers named `my_reader_1` and `my_reader_2`.
For each reader, it overrides the `file_name` name arg expected by that reader.

Overrides with the `--readers` option should allow you to reuse an experiment YAML configuration across sessions of a given experiment / paradigm.

## trial file format: JSON lines or HDF5

The file extension passed to `--trial-file` determines the format of the trial file written.
Pyramid supports [JSON Lines](https://jsonlines.org/) and [HDF5](https://en.wikipedia.org/wiki/Hierarchical_Data_Format).

```
# JSON Lines
pyramid convert --trial-file my-trials.json ...
pyramid convert --trial-file my-trials.jsonl ...

# HDF5
pyramid convert --trial-file my-trials.hdf ...
pyramid convert --trial-file my-trials.h5 ...
pyramid convert --trial-file my-trials.hdf5 ...
pyramid convert --trial-file my-trials.he5 ...
```

## session subject info

The `--subject` option allows for a subject description that's separate from the main experiment configuration.
This should allow you to reuse an experiment YAML configuration across sessions of a given experiment / paradigm.

```
pyramid convert \
  --trial-file my-trials.hdf5 \
  --experiment my_experiment.yaml \
  --subject subject_1.yaml
```

This example assumes `subject_1.yaml` contains a info about the subject for a particular session.
The content of `subject_1.yaml` should have a key-value mapping at the top level (ie be a dictionary, not a list, string, or scalar).
Other than that, the subject info can be free-form.

Here's a possible contents for `subject_1.yaml`:

```
subject:
  subject_id: SBJ0
  sex: F
  species: H Subjectus
  date_of_birth: 2000-05-08T14:00:07Z
  description: Wow!
  weight: 10.0 kg
  preferred_eye: L
recruiter:
  name: an online service
```

Pyramid will pass a dictionary of subject info to each enhancer and each plotter, along with each new trial.
This would allow you do subject-specific calculations or plotting based on, say, a subject's `weight`, `preferred_eye`, or other annotation.

## search path

The `--search-path` option lets you specify one or more local directories where Pyramid can search for YAML files, reader data files, and custom code `package_path`s.

```
pyramid convert \
  --trial-file my-trials.hdf5 \
  --experiment my_experiment.yaml \
  --search-path "/my/path/to/shared/data/"
```

In this example, the search path `/my/path/to/shared/data/` could be the local file path to a directory where a shared data repository is mounted.
This could allow collaborators to share the same `my_experiment.yaml`.
The search path could capture what's different between machines and user accounts.
The config in `my_experiment.yaml` could refer to relative paths that are consistent with the shared data repository.

## gui

Here's the simplest command to tell Pyramid to convert some data and update plots after each trial.
This works like the conversion examples above, with all the same options, but using `gui` mode instead of `convert` mode.

```
pyramid gui --trial-file my-trials.hdf5 --experiment my_experiment.yaml
```

This would expect YAML configuration in `my_experiment.yaml`, including a list of plotters under the `plotters` key.
For each plotter, Pyramid would create a figure at startup, and update the figure after each trial.

## gui figure positions

The `--plot-positions` allows Pyramid to record and restore plot figure window positions automatically.

```
pyramid gui \
  --trial-file my-trials.hdf5 \
  --experiment my_experiment.yaml \
  --plot-positions my_plot_positions.yaml
```

This assumes `my_plot_positions.yaml` is readable and writable.

If `my_plot_positions.yaml` exists at startup, Pyramid will use this to restore the position of each plot figure window.
On exit, Pyramid will write the current postion of each plot figure window into `my_plot_positions.yaml`.

Pyramid figure windows are managed by [matplotlib](https://matplotlib.org/stable/).
This provides cross-platform support in interactive and non-interactive environments -- which is great!
Unfortunately, not all of the [interactive backends](https://matplotlib.org/stable/users/explain/figure/backends.html#interactive-backends) support programmatic window positioning.
So far, we've had good luck on Linux systems that use the `TkAgg` backend, but not on macOS with the `macosx` backend.

## graph

Pyramid can render an image graph to depict your experiment YAML.
This is indended to help confirm that Pyramid interpreted your configuration the way you expected.

Here's the simplest command to tell Pyramid to read YAML configt and render a graph.

```
pyramid graph --graph-file my-config.png --experiment my_experiment.yaml
```

This will produce an image file like the one in the [core-demo](../core-demo/demo_experiment.png) in this repo.

# Python Script

You can also invoke Pyramid from Python.

This example shows how to invoke Pyramid from a Python script instead of from a command shell, using the same entry point as the CLI.
It imports the Pyramid `cli` module instead of using the `pyramid` excutable.

```
from pyramid import cli

# Choose data and config arguments.
# These could be hard-coded, searched for using other Pyton utils, iterated in a loop, etc.
trial_file = "my-trials.hdf5"
shared_data_path = "/my/path/to/shared/data/"
experiment_yaml = "my_experiment.yaml"
event_data = "events.csv"
signal_data = "signal.bin"

# Build up a command as a list of parts.
# From a shell, these same parts would be separated by spaces.
command = [
  "convert",
  "--trial-file", output_fname,
  "--search-path", shared_data_path,
  "--experiment", experiment_yaml,
  "--readers",
  f"my_reader_1.file_name={event_data}",
  f"my_reader_2.file_name={signal_data}"
]

# Invoke pyramid using the same entry point as the CLI.
cli.main(command)
 ```

The Python script above would be equivalent to this CLI command:

```
pyramid convert \
  --trial-file my-trials.hdf5 \
  --search-path "/my/path/to/shared/data/"
  --experiment my_experiment.yaml \
  --readers \
  my_reader_1.file_name=events.csv \
  my_reader_2.file_name=signal.bin
```
