classdef Hdf5TrialIterator < handle
    % Read a Pyramid HDF5 trial file, one group/trial at a time.

    properties (SetAccess = private)
        % The HDF5 file to read from incrementally.
        trialFile

        % HDF5 file info structure including the groups to iterate.
        info

        % Current group index, representing iteration state.
        index = 0
    end

    methods

        function obj = Hdf5TrialIterator(trialFile)
            % Set up to read HDF5 groups as trials.
            arguments
                trialFile {mustBeFile}
            end
            obj.trialFile = trialFile;
            obj.info = h5info(trialFile);
        end

        function trial = next(obj)
            % Read one trial from the next HDF5 group.
            obj.index = obj.index + 1;
            if obj.index > numel(obj.info.Groups)
                % Empty result signals end of groups.
                trial = [];
                return
            end

            group = obj.info.Groups(obj.index);
            trial = struct();

            % Get trial timing and enhancements from HDF5 attributes.
            for attribute = group.Attributes'
                switch attribute.Name
                    case 'enhancements'
                        % JSON encoding supports nested enhancements.
                        trial.enhancements = jsondecode(attribute.Value);
                    case 'enhancement_categories'
                        trial.enhancement_categories = jsondecode(attribute.Value);
                    otherwise
                        trial.(attribute.Name) = attribute.Value;
                end
            end

            % Get data arrays from HDF5 subgroups.
            for dataGroup = group.Groups'
                subgroupName = dataGroup.Name(numel(group.Name)+2:end);
                switch subgroupName
                    case 'numeric_events'
                        for dataset = dataGroup.Datasets'
                            % HDF5 read includes decompression as needed.
                            dataPath = [dataGroup.Name '/' dataset.Name];
                            data = h5read(obj.trialFile, dataPath);
                            if isempty(data)
                                trial.numeric_events.(dataset.Name) = [];
                            else
                                trial.numeric_events.(dataset.Name) = double(data');
                            end
                        end

                    case 'text_events'
                        for textSubgroup = dataGroup.Groups'
                            % HDF5 read includes decompression as needed.
                            timestampDataPath = [textSubgroup.Name '/' 'timestamp_data'];
                            timestampData = h5read(obj.trialFile, timestampDataPath);
                            textDataPath = [textSubgroup.Name '/' 'text_data'];
                            textData = h5read(obj.trialFile, textDataPath);
                            textSubgroupName = textSubgroup.Name(numel(dataGroup.Name)+2:end);
                            if isempty(timestampData) || isempty(textData)
                                trial.text_events.(textSubgroupName).timestamp_data = [];
                                trial.text_events.(textSubgroupName).text_data = [];
                            else
                                trial.text_events.(textSubgroupName).timestamp_data  = double(timestampData);

                                % Pack text into cell array of strings.
                                textDataCell = cell(numel(textData), 1);
                                for ii = 1:numel(textData)
                                    % Strip trailing null padding.
                                    unpadded = strip(textData{ii}, char(0));

                                    % treat bytes as UTF-8.
                                    textDataCell{ii} = native2unicode(double(unpadded), "UTF-8");
                                end
                                trial.text_events.(textSubgroupName).text_data = textDataCell;
                            end
                        end

                    case 'signals'
                        for dataset = dataGroup.Datasets'
                            % HDF5 read includes decompression as needed.
                            dataPath = [dataGroup.Name '/' dataset.Name];
                            data = h5read(obj.trialFile, dataPath);
                            if isempty(data)
                                trial.signals.(dataset.Name).signal_data = [];
                            else
                                trial.signals.(dataset.Name).signal_data = double(data');
                            end

                            for attribute = dataset.Attributes'
                                trial.signals.(dataset.Name).(attribute.Name) = attribute.Value;
                            end
                        end
                end
            end
        end
    end
end
