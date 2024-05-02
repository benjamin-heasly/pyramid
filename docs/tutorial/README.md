# End-To-End Tutorial with PsychPy?

This is a work in progress, towards an end-to-end tutorial for Pyramid:
 - a PsychoPy experiment you can run yourself (official PsychoPy demo?)
 - a Pyramid YAML that that captures the experiment and PsychoPy data files
 - touch on Pyramid features: Readers, Transformers, Buffers, Trials, Enhancements, Collecters
 - trial files
 - reading a trial file in an analysis script
 - plotting your own data as a pshychometric function, reaction times, or similar

# PsychoPy

https://psychopy.org/download.html

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
I guess there are some "PsychTollbox bindings" they are using.
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

## builder

The Builder is painful to me, and learning from videos is so damn slow.
This is the wrong direction for the field.
Solve these sub-problems reasonable in code.
Learn to code against reasonably implemented libraries.
Not, throw tons of shit code against the wall and hide it behind a GUI.
And teach people that coding sucks so don't bother learning.
I hate this shit.

## coding

I'll try from these docs instead.
https://workshops.psychopy.org/

"Coding an experiment in Python"
https://drive.google.com/drive/folders/17KfU3r8rVH-iiScOVl3dVZW3LGyLe8fs?usp=sharing

