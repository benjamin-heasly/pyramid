"""
This script defines a PsychoPy experiment that we can use with Pyramid.

It's based on PsychoPy workshop material from here:

    https://workshops.psychopy.org/

Specifically, the material on "Coding an experiment in Python":

    https://drive.google.com/drive/folders/17KfU3r8rVH-iiScOVl3dVZW3LGyLe8fs?usp=sharing

(accessed 2 May 2024)

Before you can run this you need to install PsychoPy.
If you're using the terminal and Conda/Anaconda, the following might work for you:

    conda create -n psychopy python=3.10
    conda activate psychopy
    pip install psychopy

With that or similar, you can then run the experiment with

    cd pyramid/docs/tutorial
    python hello.py

This will bring up a window and let you play through several trials.
It will write data from your experiment session in the "data/" subfolder.

    pyramid/docs/tutorial/data/

This is where we'll look for data with Pyramid in the rest of the tutorial.
"""

from pathlib import Path

from psychopy import visual, data, core, gui
from psychopy.hardware import keyboard

# Create a window.
win = visual.Window([1024, 768], fullscr=False, units='pix')

# Create a fixation dot.
fixation = visual.Circle(win, size=5, lineColor='white', fillColor='lightGrey')

# Create a cue.
cue = visual.ShapeStim(win, vertices=[[-30, -20], [-30, 20], [30, 0]], lineColor='red', fillColor='salmon')

# Create a target.
target = visual.GratingStim(win, size=80, pos=[300, 0], tex=None, mask='gauss', color='green')

# Create a keyboard object.
# Using backend 'iohub' since this seems straightforward and portable.
# This avoids unnecessary errors and system config related to the 'ptb' backend.
# We don't need all that for this demo, so give us a break.
kb = keyboard.Keyboard(backend='iohub')

# Load the trial conditions from CSV/spreadsheet.
conditions = data.importConditions('conditions.csv')

# Give conditions to a trial handler object.
trials = data.TrialHandler(trialList=conditions, nReps=5, method='random')

# Set up an experiment handler object.
info = {
    'participant': 'parsnip',
    'session': '0',
    'fixTime': 0.5,
    'cueTime': 0.5
}
dlg = gui.DlgFromDict(info)
if not dlg.OK:
    core.quit()

info['dateStr'] = data.getDateStr()

current_dir = Path().resolve()
data_file_base = Path(current_dir, 'data', f'hello_{info["participant"]}_{info["session"]}_{info["dateStr"]}')
thisExp = data.ExperimentHandler(
    name='Posner',
    version='1.0',
    extraInfo=info,
    dataFileName=str(data_file_base)
)
thisExp.addLoop(trials)

for trial in trials:
    # Update stimuli using the trial dict.
    cue.setOri(trial['cue_orientation'])
    target.setPos([trial['target_x'], 0])

    # Draw the fixation dot.
    fixation.draw()
    win.flip()
    core.wait(info['fixTime'])

    # Draw the cue arrow.
    cue.draw()
    win.flip()
    core.wait(info['cueTime'])

    # Draw the target.
    target.draw()

    # Reset the keyboard clock to 0 when the target is visible.
    # We won't need to do this with Pyramid.
    win.callOnFlip(kb.clock.reset)
    win.flip()

    # Wait for an expected key press.
    keys = kb.waitKeys(keyList=['left', 'right', 'escape'])
    print(keys[-1].name)
    print(keys[-1].rt)

    if ('escape' in keys):
        core.quit()

    # Was the response correct?
    if (trial['correct_keypress'] in keys):
        correct = True
    else:
        correct = False

    # Append to the data file.
    thisExp.addData('key_response', keys[-1].name)
    thisExp.addData('response_time', keys[-1].rt)
    thisExp.addData('correct', correct)

    # Move on to the next row in the data file.
    thisExp.nextEntry()
