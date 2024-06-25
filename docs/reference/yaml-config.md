# Pyramid YAML Schema Commentary.

This page describes how you can configure Pyramid with YAML files.
This is the main way of telling Pyramid to do for your experiment / paradigm.

You can find a detailed, complete schema reference at [pyramid-schema.yaml](./pyramid-schema.yaml).
This referenceoutlines everything you can put into a Pyramid YAML file.

Read on below for more commentary about YAML and Pyramid. 

# Intro to YAML

Here's short intro to YAML.

[YAML](https://yaml.org/) is a language for writing things like data and configuration files as structured text.
It's somewhat like [JSON](https://www.json.org/json-en.html) or [XML](https://en.wikipedia.org/wiki/XML) -- flexible, structured text that humans and machines can read and write.

YAML is less verbose that those others, includes indentation as part of its structure, and supports comments.
In these ways it's somewhat like the Python language and relatively easy for humans to read and write.

YAML files are made up of a few data types that can be nested and combined with each other.
These YAML types map nicely onto Python data types.

## scalars

YAML supports scalars that map to Python types like None, bool, int and float:

```
null  # None

true  # True
True  # True

false # False
False # False

42    # int(42)

3.14  # float(3.14)
```

YAML strings can use double `"` or single `'` quotes:

```
"string 1"
'string 2'
```

YAML also supports unquoted strings, as long as these are not ambiguous (ie not numbers and no special characters like brackets `[]`, braces, `{}`, hyphens `-`, [etc.](https://stackoverflow.com/questions/19109912/yaml-do-i-need-quotes-for-strings-in-yaml)).

```
string 3
```

## key-value mappings (dictionaries)

YAML supports key-value mappings, which are like Python dictionaries.
These allow nesting with themselves and with other types.

You can write these across lines that have the same indentation level.

```
my_dict:
  my_int: 42
  my_float: 3.14
  my_string: hello world
```

Or you can write these on one line within curly braces:

```
my_dict: {my_int: 1, my_float: 3.14, my_string: hello world}
```

Either way, these become Python dicts:

```
my_dict = {
  'my_int': 42,
  'my_float': 3.14,
  'my_string': 'hello world'
}
```

## lists

YAML supports ordered lists.
These allow nesting with themselves and with other types.

You can write these across lines that have the same indentation level, using hyphens `-` to mark list elements.

```
my_list:
  - 42
  - 3.14
  - hello world
```

Or you can write these on one line within square brackets:

```
my_list: [42, 3.14, hello world]
```

Either way, these become Python lists:

```
my_list = [42, 3.14, 'hello world']
```

# Pyramid YAML

YAML is the main way of telling Pyramid what to do.
The YAML for your experiment / paradigm declares the outline and the details of what you want.
Pyramid reads your YAML, configures itself accordingly, then starts reading data and making trials.
You might write a separate YAML file for each of your experiments / paradigms and then reuse the same YAML across sessions.

The sections below describe each of the top-level YAML keys that Pyramid expects: `experiment`, `readers`, `trials`, and `plotters`.

## experiment

The `experiment` key maps to header info about your experiment, lab, institution, etc.
It should contain keys and values.
Other than that, it doesn't have specific requirements or drive specific behavior.
This might be similar to what you'd include at the top level of an NWB file.

A dictionary containing all the `experiment` info will be passed to trial enhancers and plotters along with each new trial.

Here's an example of a full `experiment` section:

```
experiment:
  experimenter:
    - Last, First
    - Family, Personal
  experiment_description: A test experiment
  institution: University of Fiction
  lab: The Fiction Lab
  keywords:
    - fictional
    - test
```

Note: information about the experiment's subject can be supplied separately, from the [command line](./command-line-interface.md) when invoking Pyramid.
This allows the same experiment to run with various subjects.

## readers

The `readers` key sets up the data sources that Pyramid will read from.
This creates various named buffers of signals and events collectively known as *The Neutral Zone*.

This section should contain key-value mappings.
The keys are user-chosen reader names.
The values are detailed reader configuration.

Here's an example reader from the [core-demo](../core-demo/README.md) in this repo.

```
readers:
  delimiter_reader:
    class: pyramid.neutral_zone.readers.csv.CsvNumericEventReader
    args:
      csv_file: default.csv
      result_name: delimiter
```

The user-chosen name of the reader is `delimiter_reader`.
Within that, Pyramid expects several reader configuration keys.

The `class` key is the most important.
It tells Pyramid what kind of reader to create, in this example a [CSV numeric event reader](../../src/pyramid/neutral_zone/readers/csv.py).

The `args` key is also important.
This contains keys and values to pass to the chosen class construtor as keyword args.

### class-specific reader constructor args

Currently, the best way to know what args to pass to a reader is by looking at the Python code.
Here's where all the built-in readers live:

 - [csv](../../src/pyramid/neutral_zone/readers/csv.py)
 - [open ephys session](../../src/pyramid/neutral_zone/readers/open_ephys_session.py)
 - [open ephys zmq](../../src/pyramid/neutral_zone/readers/open_ephys_zmq.py)
 - [phy](../../src/pyramid/neutral_zone/readers/phy.py)
 - [plexon](../../src/pyramid/neutral_zone/readers/plexon.py)

### command line overrides

In the reader example above the name of the file to read was hard-coded as `csv_file: default.csv`.
You might want to use different files, from session to session.
Instead of having to edit the YAML each for each session, you can pass in overrides using the `--readers` command line option.

For example, to override the `csv_file` arg for the reader named `delimiter_reader`, you could pass on the command line:

```
pyramid convert ...etc... --readers delimiter_reader.csv_file=different_file.csv
```

### extra buffers and transformers

Each reader will read from its configured source, into named buffers.
These are called "reader result" buffers.

You can add additional "extra buffers" that copy and transform data from the result buffers.

Here's an example of an extra buffer from the [plexon-demo](../plexon-demo/README.md) in this repo.

```
readers:
  plexon_reader:
    class: pyramid.neutral_zone.readers.plexon.PlexonPlxReader
    args:
      plx_file: my_file.plx
      signals:
        X50: gaze_x
    extra_buffers:
      gaze_x_degrees:
        reader_result_name: gaze_x
        transformers:
          - class: pyramid.neutral_zone.transformers.standard_transformers.OffsetThenGain
            args:
              gain: 10
```

The user-chosen name of the reader is `plexon_reader`.
This reader will read signal data into a results buffer named `gaze_x`.

An extra buffer named `gaze_x_degrees` will receive a copy of the `gaze_x` reader result.
The copy will be scaled by a `gain` of `10`.

### class-specific transformer constructor args

Each extra buffer can declare a list of transformers to apply to incoming reader result data.
Transformers are constructed using the same configuration keys as readers.
The `class` key tells Pyramid which kind of transformer to make, and the `args` key holds class-specific constructor keyword arguments.

Currently, the best way to know what args to pass to a transformer is by looking at the Python code.
Here's where all the built-in transformers live, including `OffsetThenGain`:

 - [standard_transformers](../../src/pyramid/neutral_zone/transformers/standard_transformers.py)

### sync

Optionally, Pyramid can look for "sync events" and use thes to estimate clock offsets between readers.
A sync event would be a real-world event recoded independently by more than one reader.

Here's an example of sync configuration for a reader in the [signal-demo](../signal-demo/README.md) in this repo.

```
readers:
  delimiter_reader:
    class: pyramid.neutral_zone.readers.csv.CsvNumericEventReader
    args:
      csv_file: delimiter.csv
      result_name: delimiter
    sync:
      is_reference: True
      buffer_name: delimiter
      filter: value[0] == 1
```

The user-chosen reader name is `delimiter_reader`.
This will read numeric events into a results buffer named `delimiter`.

The sync config will look at the same `buffer_name`, `delimiter` to find sync events.
From there, it will take sync events that have value `1`, and ignore other events.

The `is_reference` key tells Pyramid that this reader represents the canonical clock.
Other readers would have their data aligned to this reader's clock, based on sync events.

Please see the [signal-demo](../signal-demo/README.md) and [sync](../../src/pyramid/neutral_zone/readers/sync.py) module for more on sync.

## trials

All of the `readers` configuration above is aimed at getting data into *The Neutral Zone* using Pyramid's data model.
From there Pyramid will delimit trials in time and populate them with selected, aligned data.
It will also call back on enhancers that can process trial data and modify or add to it.

### delimit, align, and populate trials

Here's an example `trials` config from the [core-demo](../core-demo/README.md) in this repo.

```
trials:
  start_buffer: delimiter
  start_value: 1010
  wrt_buffer: delimiter
  wrt_value: 42
```

The `start_buffer` key tells Pyramid to delimit trials in time based on events in a buffer named `delimiter`.
This buffer would have been configured in the `readers` section above.
The `start_value` key tells Pyramid that only events with value `1010` are trial-delimiting events.
As these events come in, Pyramid will create new trials.

For each trial, Pyramid will query all the buffers in *The Neutral Zone* for data between delimiting events.
It will populate each trial with copies of all the query results, using the same buffer names.

The optional `wrt_buffer` key tells Pyramid to align trial data with respect to (wrt) an event in the trial.
This buffer would have been configured in the `readers` section above.
The `wrt_value` key tells Pyramid that only events with value `42` are trial-aligning events.
All this gives each trial its own, independent time origin (ie each trial contains its own time 0).

If reader sync events are configured, reader clock offset corrections are applied at the same time as "wrt" alignment -- once per trial.

### enhancers and collecters

In addition to creating and populating trials, Pyramid can let enhancers and collecters analyze trial data and update or add to the trial.

Here's an example of enhancer and collecter configuration from the [smooth-demo](../smooth-demo/README.md) in this repo.

```
trials:
  start_buffer: delimiter
  start_value: 1010
  wrt_buffer: delimiter
  wrt_value: 42
  enhancers:
    - class: pyramid.trials.standard_adjusters.SignalSmoother
      args:
        buffer_name: smoothed
        kernel_size: 20
  collecters:
    - class: pyramid.trials.standard_collecters.SignalNormalizer
      args:
        buffer_name: smoothed
```

The optional `enhancers` key contains a list of enhancers for Pyramid to create and apply to each trial as it's created.
Enhancers are constructed using the same configuration keys as readers.
The `class` key tells Pyramid which kind of enhancer to make, and the `args` key holds class-specific constructor keyword arguments.

In this example, `SignalSmoother` enhancer will smooth out data in `buffer_name` `smoothed`.
This buffer would have been configured in the `readers` section above.

Enhancers apply one trial at a time, right away, as each trial is created.
Collecters are similar, but they are able to look over all trials before deciding what to do to each trial.

The optional `collecters` key contains a list of collecters for Pyramid to create and apply after at the end, once all trials have been created.
Collecters are constructed using the same configuration keys as readers.
The `class` key tells Pyramid which kind of collecter to make, and the `args` key holds class-specific constructor keyword arguments.

In this example, the `SignalNormalizer` will examine the same `smoothed` buffer from all trials to determin the global extremes.
Then it will rescale the signal in each trial, using a single common scale factor.

### class-specific enhancer and collecter constructor args

Currently, the best way to know what args to pass to an enhancer or collecter is by looking at the Python code.
Here's where all the built-in enhancers and collecters live, including `SignalSmoother` and `SignalNormalizer`:

 - [standard_enhancers](../../src/pyramid/trials/standard_enhancers.py)
 - [standard_adjusters](../../src/pyramid/trials/standard_adjusters.py)
 - [standard_collecters](../../src/pyramid/trials/standard_collecters.py)

Note: `standard_enhancers` and `standard_adjusters` are functionally the same.
By convention, "enhancers" should add data to a trial, whereas "adjusters" should modify trial data in place.

## plotters

Once trials are created, populated, and enhanced, Pyramid can plot them.
This may be helpful for following live data, replaying data from disk, and/or debugging!

Here's an example of plotter configuration from the [plexon-demo](../plexon-demo/README.md) in this repo.

```
plotters:
  - class: pyramid.plotters.standard_plotters.BasicInfoPlotter
  - class: pyramid.plotters.standard_plotters.SignalChunksPlotter
    args:
      xmin: -1.0
      xmax: 5.0
      ylabel: 10x raw signal
  - class: pyramid.plotters.standard_plotters.SpikeEventsPlotter
    args:
      xmin: -1.0
      xmax: 5.0
      match_pattern: spike_.*
      value_index: 1
      value_selection: 1
      marker: "|"
```

The optional `plotters` key gives Pyramid a list of plotters to create at startup and update for each trial.
Plotters are constructed using the same configuration keys as readers.
The `class` key tells Pyramid which kind of plotter to make, and the `args` key holds class-specific constructor keyword arguments.

In this example the `BasicInfoPlotter` needs no `args`.
It shows basic info about how Pyramid is progressing through trials, like the elapsed time and trial count.

The `SignalChunksPlotter` plotter looks for any signals data present in each trial, and plots the signals over time.
The `xmin` and `xmax` args put the focus on signals near time zero, the independent time origin of each trial.

The `SpikeEventsPlotter` looks for numeric events in the same `xmin` and `xmax` range.
It looks for numeric event data in each trial, but only from buffers named like the `match_pattern` `spike_.*`.
It plots the times of matched events as a raster with point `marker` `|`.

### class-specific plotter constructor args, see reader code

Currently, the best way to know what args to pass to a plotter is by looking at the Python code.
Here's where all the built-in plotters live, including `BasicInfoPlotter`, `SignalChunksPlotter`, and `SpikeEventsPlotter`:

 - [standard_plotters](../../src/pyramid/plotters/standard_plotters.py)

## Custom Classes

Above, all the `readers`, `transformers`, `adjusters`, `collecters`, and `plotters` are configured following a similar pattern.
A `class` key tells Pyramid which class to instantiate, and an `args` key contains class-specific constructor keyword args.

This pattern makes Pyramid extensible to custom classes, in addition to standard classes that are part of Pyramid itself.
To help Pyramid find your custom classes, you can add a `package_path` key along with `class` and `args`.

For example, you could write a custom reader class named `MyCustomReader` in a file named `custom_stuff/readers/my_readers.py`.
You could then add this to your Pyramid YAML:

```
readers:
  my_custom_reader:
    class: readers.my_readers.MyCustomReader
    package_path: custom_stuff
    args:
      my_arg_1: 123
      my_arg_2: abc
```

The `package_path` should be a directory that contains your Python source files, like `my_readers.py`.
The source files are allowed to be in subdirectories of that directory, too.
Then the `class` key walks Pyramid from this known package directory, through any subdirectories, to the source file name, and finally to the class name.

This is actually the same way Pyramid loads build-in classes.
The only difference is that, once Pyramid is installed via `pip`, it already knows the "package path" for Pyramid itself.

In this example, the `class` key walks Pyramid from the base `src` folder in this repo (the "package path"), through subdirectories `pyramid`, `neutral_zone`, and `readers`, to the source file [csv.py](../../src/pyramid/neutral_zone/readers/csv.py), and to the class `CsvNumericEventReader`.

```
readers:
  delimiter_reader:
    class: pyramid.neutral_zone.readers.csv.CsvNumericEventReader
    args:
      csv_file: default.csv
      result_name: delimiter
```
