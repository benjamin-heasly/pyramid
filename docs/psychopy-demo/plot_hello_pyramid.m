% This script will load a Pyramid trial file and plot some results.
% It expects you've already run Pyramid for a Hello Pyramid session.
%
% It also expects the pyramid/matlab/ subdir to be on the Matlab path.
%
% Run this from the demo folder, pyramid/docs/psychopy-demo/

%% Load the trial file for a session.

clear
clc

%session_file = 'my_data.json';
session_file = 'some_errors.json';
%session_file = 'all_correct.json';

trial_file = TrialFile(session_file);
trials = trial_file.read();

%% Set up to plot cue and miscue trials separately.

figure('Name', session_file);

% Get normalized axes limits for the 800x600 task window.
w = (800 / 2) / 600;
h = (600 / 2) / 600;

cue_mouse_axes = subplot(2, 2, 1);
title('cue');
xlim([-w w]);
xlabel('mouse x (normalized)');
ylim([-h h]);
ylabel('mouse y (normalized)');
grid('on')

miscue_mouse_axes = subplot(2, 2, 2);
title('miscue');
xlim([-w w]);
xlabel('mouse x (normalized)');
ylim([-h h]);
grid('on')

cue_rt_axes = subplot(2, 2, 3);
xlim([0, numel(trials) + 1]);
xlabel('trial');
ylabel('reaction time (s)');
grid('on')

miscue_rt_axes = subplot(2, 2, 4);
xlim([0, numel(trials) + 1]);
xlabel('trial');
grid('on')

%% Plot completed trials.

cue_count = 0;
cue_correct = 0;
miscue_count = 0;
miscue_correct = 0;
for tt = 1:numel(trials)

    % Get the next trial that Pyramid made for us.
    trial = trials(tt);

    % Is this a complete trial where the participant clicked something?
    % Look at the 'complete_trial' enhancement.
    if ~trial.enhancements.complete_trial
        continue;
    end

    % Was this a cue or miscue trial?
    % Look at the 'miscue' enhancement.
    miscue = trial.enhancements.miscue;
    if miscue
        mouse_axes = miscue_mouse_axes;
        rt_axes = miscue_rt_axes;

        miscue_count = miscue_count + 1;
    else
        mouse_axes = cue_mouse_axes;
        rt_axes = cue_rt_axes;

        cue_count = cue_count + 1;
    end

    % Was this a correct or incorrect response?
    % Look at the 'correct' enhancement.
    correct = trial.enhancements.correct;
    if correct
        response_color = 'green';
        if miscue
            miscue_correct = miscue_correct + 1;
        else
            cue_correct = cue_correct + 1;
        end
    else
        response_color = 'red';
    end

    % Get mouse trails between cue (trial time 0) and click.
    % Look at the 'mouse_position' signal and 'clicked_name' text event.
    frequency = trial.signals.mouse_position.sample_frequency;
    first_sample_time = trial.signals.mouse_position.first_sample_time;
    click_time = trial.text_events.clicked_name.timestamp_data(1);
    click_samples = floor((click_time - first_sample_time) * frequency);
    mouse_x = trial.signals.mouse_position.signal_data(1:click_samples, 1);
    mouse_y = trial.signals.mouse_position.signal_data(1:click_samples, 2);

    % Plot the mouse trail, plus a marker at the click.
    line(mouse_x, mouse_y, 'Color', response_color, 'Parent', mouse_axes);
    line(mouse_x(end), mouse_y(end), 'Color', response_color, 'Marker', '*', 'Parent', mouse_axes);

    % Plot the reaction time on this trial.
    % Look at the 'reaction_time' enhancement.
    line(tt, trial.enhancements.reaction_time, 'Color', response_color, 'Marker', '+', 'Parent', rt_axes);
end

% Summarize percent correct.
cue_subtitle = sprintf('%d / %d (%.0f%%) correct', cue_correct, cue_count, 100 * cue_correct / cue_count);
subtitle(cue_mouse_axes, cue_subtitle);

miscue_subtitle = sprintf('%d / %d (%.0f%%) correct', miscue_correct, miscue_count, 100 * miscue_correct / miscue_count);
subtitle(miscue_mouse_axes, miscue_subtitle);

% Make reaction time axes start at 0 and have the same max.
max_rt = max(cue_rt_axes.YLim(2), miscue_rt_axes.YLim(2));
ylim(cue_rt_axes, [0, max_rt]);
ylim(miscue_rt_axes, [0, max_rt]);
