% Return a Matlab struct representation of expected Pyramid trial files.
% This is used as a fixture to support testing Matlab TrialFiles.
%
% This file was created manually, to match the contents of
% sample_trials.json and sample_trials.hdf5.  See also
% generate_fixture_files.sh for where those originals came from.
function trials = sampleTrials()

% Numeric event data, reused in different trials.
emptyNumericEvents = [];
simpleNumericEvents = [0.1 0; 0.2 1; 0.3 0];
complexNumericEvents = [0.1 0 42.42; 0.2 1 42.42; 0.3 0 43.43];

% Text event data, reused in different trials.
emptyTextEvents = struct('timestamp_data', {[]}, 'text_data', {[]});
shortTextEvents = struct('timestamp_data', {[0.1; 0.2]}, 'text_data', {{'0'; '1'}});
emojiText = compose('smile for THREE :-) \xd83d\xde04');
longTextEvents = struct('timestamp_data', {[0.1; 0.2; 0.3]}, 'text_data', {{'the number zero'; '#1 is the best!'; emojiText{1}}});

% Signal data, reused in different trials.
emptySignal.signal_data = [];
emptySignal.sample_frequency = [];
emptySignal.first_sample_time = [];
emptySignal.channel_ids = {'q'; 'r'};

simpleSignal.signal_data = [0; 1; 2; 3; 0; 5];
simpleSignal.sample_frequency = 10;
simpleSignal.first_sample_time = 0.1;
simpleSignal.channel_ids = {'x'};

complexSignal.signal_data = [ ...
    0 10 100; ...
    1 11 100.1; ...
    2 12 100.2; ...
    3 13 100.3; ...
    0 10 100; ...
    5 15 100.5];
complexSignal.sample_frequency = 100;
complexSignal.first_sample_time = -0.5;
complexSignal.channel_ids = {'a'; 'b'; 'c'};

% Per-trial enhancements, reused in different trials
enhancements.string = 'I''m a string.';
enhancements.int = 42;
enhancements.float = 1.11;
enhancements.empty_dict = struct();
enhancements.empty_list = [];
enhancements.dict = struct('a', 1, 'b', 2);
enhancements.list = {'a'; 1; 'b'; 2};

enhancement_categories.value = fieldnames(enhancements);

% A simple trial with no data added.
trials(1).start_time = 0;
trials(1).end_time = 1;
trials(1).wrt_time = 0;
trials(1).numeric_events = [];
trials(1).text_events = [];
trials(1).signals = [];
trials(1).enhancements = [];
trials(1).enhancement_categories = [];

% A trial with only numeric events.
trials(2).start_time = 1;
trials(2).end_time = 1.5;
trials(2).wrt_time = 1.25;
trials(2).numeric_events.empty = emptyNumericEvents;
trials(2).numeric_events.simple = simpleNumericEvents;
trials(2).numeric_events.complex = complexNumericEvents;
trials(2).text_events = [];
trials(2).signals = [];
trials(2).enhancements = [];
trials(2).enhancement_categories = [];

% A trial with only text events
trials(3).start_time = 1.5;
trials(3).end_time = 2;
trials(3).wrt_time = 1.75;
trials(3).numeric_events = [];
trials(3).text_events.empty = emptyTextEvents;
trials(3).text_events.short = shortTextEvents;
trials(3).text_events.long = longTextEvents;
trials(3).signals = [];
trials(3).enhancements = [];
trials(3).enhancement_categories = [];

% A trial with only signals.
trials(4).start_time = 2;
trials(4).end_time = 3;
trials(4).wrt_time = 2.5;
trials(4).numeric_events = [];
trials(4).text_events = [];
trials(4).signals.empty = emptySignal;
trials(4).signals.simple = simpleSignal;
trials(4).signals.complex = complexSignal;
trials(4).enhancements = [];
trials(4).enhancement_categories = [];

% A trial with only per-trial enhancements.
trials(5).start_time = 3;
trials(5).end_time = 4;
trials(5).wrt_time = 3.5;
trials(5).numeric_events = [];
trials(5).text_events = [];
trials(5).signals = [];
trials(5).enhancements = enhancements;
trials(5).enhancement_categories = enhancement_categories;

% A trial with everyting!
trials(6).start_time = 4;
trials(6).end_time = [];
trials(6).wrt_time = 4.5;
trials(6).numeric_events.empty = emptyNumericEvents;
trials(6).numeric_events.simple = simpleNumericEvents;
trials(6).numeric_events.complex = complexNumericEvents;
trials(6).text_events.empty = emptyTextEvents;
trials(6).text_events.short = shortTextEvents;
trials(6).text_events.long = longTextEvents;
trials(6).signals.empty = emptySignal;
trials(6).signals.simple = simpleSignal;
trials(6).signals.complex = complexSignal;
trials(6).enhancements = enhancements;
trials(6).enhancement_categories = enhancement_categories;
