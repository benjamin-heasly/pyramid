# End-To-End Tutorial with PsychPy?

This is a work in progress, towards an end-to-end tutorial for Pyramid:
 - a PsychoPy experiment you can run yourself (official PsychoPy demo?)
 - a Pyramid YAML that that captures the experiment and PsychoPy data files
 - touch on Pyramid features: Readers, Transformers, Buffers, Trials, Enhancements, Collecters
 - trial files
 - reading a trial file in an analysis script
 - plotting your own data as a pshychometric function, reaction times, or similar

The experiment
 - screen shots
 - description
 - you can run it if you install psychopy!
    - recommend GUI because it seems better supported
    - running as Python script works too, but setup is messy and janky
 - generate a data file
 - or use a canned one here

Pyramid
 - configure to look at "long wide" CSV output from Pyramid
 - identify events and signals to add to trials
 - create a trial file
 - load the trial file in Matlab
 - plot a summary of the data
   - separate miscue vs good cue
   - summarize number and percent correct
   - show mouse trails: green for correct, red for incorrect

# PsychoPy

https://psychopy.org/download.html

Linux

conda create -n psychopy python=3.10
conda activate psychopy

pip install psychopy

Very slow:
  Building wheel for wxPython (setup.py) ... \
Apparently slow is expected:
  https://discuss.wxpython.org/t/wxpython-4-2-1-ubuntu-22-04-installation-via-pip-fails/36551/5
Eventually completed some time over night
  Successfully built wxPython esprima html2text
  etc...

```
# a link error
psychopy

# seems OK
LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6 psychopy
```

macOS

brew install hdf5

conda create -n psychopy python=3.10
conda activate psychopy

pip install psychopy

psychopy

Gui etc Seemed OK

python hello_pyramid.py

NameError: name 'backend' is not defined
1.0672  ERROR   Failed to load any of the audioLibs: ['ptb']. Falling back to PsychToolbox ('ptb') backend for sound. Be sure to add 'ptb' to preferences to avoid seeing this message again.
1.0692  ERROR   No audioLib could be loaded. Tried: ['ptb']
 Check whether the necessary audioLibs are installed

Same when running task from GUI.
Screwed up stuff in there.

Latest version, not on pypi?
pip install git+https://github.com/psychopy/psychopy.git@2024.1.5
Nope, same error.

Standalone installer?
https://www.psychopy.org/download.html

Getting farther, saw fullscreen "measuring refresh rate"
Hung there, then

"RuntimeError: Error starting ioHub server: ioHub startup failed."

What the heck is that?
https://discourse.psychopy.org/t/runtimeerror-error-starting-iohub-server-iohub-startup-failed-exit-code-1/29807

Workround PsychToolbox or Pyglet input backend works better.
I can play through the task.
But cursor is not visible!

Change to windowed mode, not fullscreen.
Seems OK now.

## startup errors

Efter installing above, running "psychopy" from the terminal fails
There's no graphics and no error message, but the exit code is nonzero.

Trying in python shell

$ python
>>> from psychopy import visual

Crashes with error

libGL error: MESA-LOADER: failed to open iris: /usr/lib/dri/iris_dri.so: cannot open shared object file: No such file or directory (search paths /usr/lib/x86_64-linux-gnu/dri:\$${ORIGIN}/dri:/usr/lib/dri, suffix _dri)
...
pyglet.gl.ContextException: Could not create GL context

Maybe this?
https://stackoverflow.com/questions/71010343/cannot-load-swrast-and-iris-drivers-in-fedora-35/72200748#72200748

$ find / -name libstdc++.so.6 2>/dev/null
Gives many results, including 
/usr/lib/x86_64-linux-gnu/libstdc++.so.6

Then this works -- thanks, folks!
LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6 psychopy

There's a dialong that wants me to configure my system for performance.

"For optimal performance on Linux, Psychtoolbox requires additional configuration changes to be made to this system..."

What?  Why does it say Psychtoolbox?
I guess there are some "PsychToolbox bindings" they are using.
https://psychopy.org/download.html#linux-install

Who cares, I'm not running this.

## data files
https://psychopy.org/general/dataOutputs.html

Probably want "long wide" output for Pyramid: https://psychopy.org/general/dataOutputs.html#long-wide-data-file
Maybe we can consume these as excel/CSV and cherry-pick columns for text and numeric events.

Can we get mouse trails for signals?
I think yes, might create a disgusting csv?
https://psychopy.org/builder/components/mouse.html


## learning...
https://psychopy.org/gettingStarted.html

Able to run the Hello World OK now.
What does the code look like?
There's a large amount of cruft related to settings, "piloting", participant info, timing, etc.
Irrelevant for this demo.
It did save a csv, and looks like a row per "trial"?
Hard to tell since Hello World is just one thing.
OK, looks like we can get multiple formats.
  savePickle=True, saveWideText=True,

https://psychopy.org/builder/index.html
https://psychopy.org/builder/concepts.html
https://psychopy.org/builder/routines.html
https://psychopy.org/builder/flow.html
https://psychopy.org/builder/gotchas.html

## coding

I'll try from these docs.
https://workshops.psychopy.org/

"Coding an experiment in Python"
https://drive.google.com/drive/folders/17KfU3r8rVH-iiScOVl3dVZW3LGyLe8fs?usp=sharing

I strongly prefer this way of creating a task.
But it's probably not representative of what others would want to feed into Pyramd, so kind of pointless.

## builder

Instead, I put together a task in the builder.
Use the mouse to click, following instructions.
Don't get foolded by silly miscue arrows!
Save the mouse clicks and position trails.

These tutorials were helpful for putting to gether a "click on stuff" example.

Using Multiple Mouse Clicks in One Trial in PsychoPy 🖱️:
https://www.youtube.com/watch?v=E4LcWESNu10&ab_channel=PsychoPy

Accuracy Feedback From Key Presses & Mouse Clicks (Touchscreen Compatible):
https://www.youtube.com/watch?v=o6gG1LRngmU&ab_channel=PsychoPy

I changed the mouse component -> Data to:
 - Save mouse state every frame
 - Time relative to experiment

This should give data representative of PsychoPy to deal with in Pyramid.

I'm thinking we might need a custom reader for PsychoPy mouse data.

We get lots of mouse samples for x, y, and button states.
We also get lots of explicit timestamps.
With time "relative to experiment", the timestamps look comparable to other columns like trial.started.

So, pretty explicit.
To make these into a Pyramid signal, maybe:
 - read numeric events as [mouse.time, mouse.x, mouse.y, mouse button]
 - make a Transformer to go from NumericEventList -> SignalChunk
 - divide and round timestamps to sample numbers at a fixed sample rate (the psychopy frame rate)
 - let sample number zero be experiment time zero
 - look for gaps in each chunk read, to pad with zero? previous?
 - keep track of last sample number chunks read
 - pad gaps between reads with zero

For numeric and text events, maybe existing CSV readers will work.
Maybe want to allow selecting relevant columns, though.
 - which column has the time?
 - which column(s) have numberic event data?
 - which column has text data?
