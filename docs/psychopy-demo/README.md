# Pyramid with PsychoPy CSV data.

Pyramid can process data from PsychoPy CSV files.
These are the [Long Wide](https://www.psychopy.org/general/dataOutputs.html#long-wide-data-file) data files that PsychoPy outputs by default.
Each of these CSVs contains many columns, from which Pyramid can read numeric events, text events, and/or signal data.

For this demo you can run a PsychoPy "Hello Pyramid" task included in this folder as [hello_pyramid.psyexp](./hello_pyramid.psyexp).
You'd have to install the PsychoPy Builder GUI first, following [instructions](https://www.psychopy.org/download.html) for your platform.
Data from running the task would go to the [data/](./data/) subfolder that's part of this demo.

Alternatively, you can skip PsychoPy and run Pyramid with sample already data included here in this repo.
 - [539585_hello_pyramid_2024-06-24_14h24.35.502.csv](./data/539585_hello_pyramid_2024-06-24_14h24.35.502.csv)

# The Hello Pyramid Task

description

screen shots
 - reduce task to 800x600 windowed
 - screen shots

I made this in the builder.
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

# Processing PsychoPy Data with Pyramid

configure to look at "long wide" CSV output from Pyramid

identify events and signals to add to trials
delimit and align trials
compute per-trial info with enhancers

create a trial file
pyramid convert --trial-file hello_pyramid.json --experiment hello_pyramid.yaml --readers wide_reader.csv_file=data/539585_hello_pyramid_2024-06-24_14h24.35.502.csv


# Analyzing Trials File in Matlab

load the trial file in Matlab

plot a summary of the data
   - separate miscue vs good cue
   - summarize number and percent correct
   - select mouse data between cue and selection
   - show mouse trails: green for correct, red for incorrect

screen shots