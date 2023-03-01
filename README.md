# ColourWheelEffort

ColourWheelEffort is a paradigm for studying the acute effects of attentional effort on pupil size.

![ColourWheelEffort](task.gif)

During the task, colour targets can appear at one of two locations on the screen, and are preceeded either by neutral cues (an X) or directional cues (left/right arrows) that can be either valid or invalid. The task of the participant is to respond quickly to targets when they appear by pressing the space bar.

On some trials of the task, the central stimuli are grey: this means that in addition to quickly detecting the target, the participant must also report the colour of the target on a colour wheel immediately after (i.e. difficult trials). On other trials, the central stimula are colourful, meaning that they just need to respond quickly to the target and do not need to pay attention to its colour (i.e. easy trials).

Given that difficult trials require more attentional effort than easy trials, and participants are made aware of whether the trial will be 'easy' or 'difficult' at its onset, this paradigm thus allows us to look at the relationship between changes in attentional effort and changes in pupil size during the pre-target window.

## Requirements

ColourWheelEffort is programmed in Python 3.9 using the [KLibs framework](https://github.com/a-hurst/klibs). It has been developed and tested on recent versions of macOS and Linux, but should also work without issue on Windows systems.

The task also requires an SR Research EyeLink eye tracker, but can be run and tested without one using a fallback mouse simulation mode.


## Getting Started

### Installation

First, you will need to install the KLibs framework by following the instructions [here](https://github.com/a-hurst/klibs).

Then, you can then download and install the experiment program with the following commands (replacing `~/Downloads` with the path to the folder where you would like to put the program folder):

```
cd ~/Downloads
git clone https://github.com/TheKleinLab/ColourWheelEffort.git
```

To run the task with a hardware eye tracker, you will also need to have the [EyeLink Developer's Kit](https://www.sr-research.com/support/thread-13.html) installed on your system (requires registering for a free account on the SR Support forums).

To install all Python dependencies for the task in a self-contained environment with Pipenv, run `pipenv install` while in the ColourWheelEffort folder (Pipenv must be already installed).

### Running the Experiment

ColourWheelEffort is a KLibs experiment, meaning that it is run using the `klibs` command at the terminal (running the 'experiment.py' file using Python directly will not work).

To run the experiment, navigate to the ColourWheelEffort folder in Terminal and run `klibs run [screensize]`, replacing `[screensize]` with the diagonal size of your display in inches (e.g. `klibs run 21.5` for a 21.5-inch monitor). Note that the stimulus sizes for the study assume that a) the screen size for the monitor has been specified accurately, and b) that participants are seated approximately 57 cm from the screen (the exact view distance can be modified in the project's `params.py` file).

If running the task in a self-contained Pipenv environment, simply prefix all `klibs` commands with `pipenv run` (e.g. `pipenv run klibs run 21.5`).

If you just want to test the program out for yourself and skip demographics collection, you can add the `-d` flag to the end of the command to launch the experiment in development mode.
 

### Exporting Data

To export data from the task, simply run

```
klibs export
```

while in the root of the ColourWheelEffort directory. This will export the trial data for each participant into individual tab-separated text files in the project's `ExpAssets/Data` subfolder.

The raw EyeLink data files (EDFs) recorded during the task are automatically copied over into the `ExpAssets/EDF` folder each time the experiment exits successfully.