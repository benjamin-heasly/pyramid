# Pyramid YAML schema.

## YAML?
This page has an informal, detailed schema for what you can do with Pyramid YAML files.

[YAML](https://yaml.org/) is a language for writing things like data and configuration files as text.
It's somewhat like [JSON](https://www.json.org/json-en.html) or [XML](https://en.wikipedia.org/wiki/XML): flexible, structured text that both humans and machines can read and write.

YAML is less verbose that the others, includes text indentation as part of its structure, and supports comments.
In these ways it's somewhat akin to the Python programming language, and relatively-easier for humans to read and write.

## Pyramid YAML

Pyramd uses YAML as the main configuration file to describe the outline and the details of what you want Pyramid to do.
You might write a separate YAML file for each of your experiments / paradigms, then reuse that YAML file across sessions.

This page provides a detailed, informal schema for how Pyramid uses YAML.
From this you should be able to look up / remember:

 - the main sections of YAML to write
 - which sections drive which Pyramid features
 - specific syntax to use within each section
 - links to the Pyramid code where classes and their expected arguments are defined

This page won't be a motivated end-to-end example.
For that, please see the several demos in the [docs/](../../docs/) folder of this repo.

# Informal Schema

This informal schema uses acutal Pyramid YAML syntax, plus comments and links to code.
There are probably cool ways to auto-generate this kind of schema documentation.
For now, we're starting low-tech, right here.

## Main Sections

These are all the main sections to include in a Pyramid YAML file.

```
experiment:
  # Optional.
  # This is header info about the experiment, lab, institution, etc.
  # This is similar to what you might include in an NWB file.
  # See experiment: details below.
readers:
  # Required.
  # A mapping of reader names, like "reader_1", "reader_2", etc., to reader configs.
  # Each config will specify the type of data to read, like CSV, Open Ephys, etc.
  # It includes parameters like CSV dialect, expected channel names, etc.
  # It includes a list of Transformations to apply to the data in The Neutral Zone.
  reader_1:
    # see readers: details below
  reader_2:
    # see readers: details below
  more_etc:
    # see readers: details below
trials:
  # Required.
  # This tells pyramid how to look for trial-delimiting events.
  # It will refer to one or more buffer names declared in the readers: section.
  # It includes a list of Enhancers to apply to each trial.
  # See trials: details below.
plotters:
  # Optional.
  # This is a list of Plotters to set up and update after each trial.
  # See plotters: details below.
```

Below, please find details of what to include in each section.

## experiment:

The `experiment:` section has header info about the experiment, lab, institution, etc.
It doesn't have required fields or drive specific behavior.
It should be similar to what you'd include at the top level of an NWB file.

A dictionary containing the `experiment:` info will be passed to trial enhancers and plotters along with each new trial.

Here's an example of a full `experiment:` section:

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

Note: information about the experiment's subject can be supplied separately from the [comnand line](./command-line-interface.md) when invoking Pyramid.
This way, the same experiment / paradigm can have a different subject for each session.

## readers:

The `readers:` section sets up the data sources Pyramid will read from.
It's a mapping from reader names like `reader_1`, `reader_2`, etc. to reader configs.

The config for each reader has several sections in itself.
These tell Pyramid the `class:` of the reader to create and `args:` to pass to the reader's constructor.
Optionally, these also give Pyramid a list of Transformers to apply to data after reading into the Neutral Zone, and how to look out for sync events.

### simple reader

Here's a simple config for a reader that reads numeric events from a CSV file.

```
reader:
  simple_reader:
    class: pyramid.neutral_zone.readers.csv.CsvNumericEventReader
    args:
      csv_file: default.csv
      result_name: my_events
```

Here's where the [CsvNumericEventReader](../../src/pyramid/neutral_zone/readers/csv.py) is defined.

### reader with transformations

Here's config for a reader that reads signal data from a Plexon `.plx` file, applies a Transformer to the data in the Neutral Zone.

The `extra_buffers:` section tells Pyramid to copy raw data coming from the reader into a new buffer, with a new name.
In this example, Pyramid will copy the raw `gaze_x` data into a new buffer called `gaze_x_degrees`.
Along the way, it will transform the data by applying a gain.

```
readers:
  gaze_reader:
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

Here's where the [PlexonPlxReader](../../src/pyramid/neutral_zone/readers/plexon.py) is defined.
Here's where the [OffsetThenGain](../../src/pyramid/neutral_zone/transformers/standard_transformers.py) is defined.

Each `transformers:` section within `extra_buffers:` is a list of transformers to apply in order, starting from the top.

### reader with sync events

Note: any of the `args:` passed to a reader can be overridden from the [comnand line](./command-line-interface.md) when invoking Pyramid.
This allows you to do things like swap between data files from different sessions, without having to edit the YAML each time.

## built in readers

Pyramid has a number of readers classes built in.
Any of these can be used in the `readers:` section.
To figure out what `args:` are expected by a given reader class, please see class-level Python comments in the Pyramid code.

 - [csv](../../src/pyramid/neutral_zone/readers/csv.py)
 - [open ephys session](../../src/pyramid/neutral_zone/readers/open_ephys_session.py)
 - [open ephys zmq](../../src/pyramid/neutral_zone/readers/open_ephys_zmq.py)
 - [phy](../../src/pyramid/neutral_zone/readers/phy.py)
 - [plexon](../../src/pyramid/neutral_zone/readers/plexon.py)

### custom readers

You can also write and use custom reader classes.
Pyramid can load these dynamically based on the full `class:` you provide, as well as a `package_path:` that tells Pyramid where to search for your class.

For example, you could write a reader class named `CustomReader`, in a file named `custom_stuff/my_readers.py`.
You could use this in your YAML like this:

```
readers:
  custom_reader:
    class: my_readers.CustomReader
    package_path: custom_stuff
    args:
      custom_arg_1: 123
      custom_arg_2: abc
```

### sync:



## trials:

## plotters: