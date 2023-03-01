from klibs.KLIndependentVariable import IndependentVariableSet

ColourWheelEffort_ind_vars = IndependentVariableSet()

## Factors ##
# 'probe_location': the location that the probe will appear (left or right)
# 'catch_trial': whether a target is presented on the trial (True or False)
# 'cue_validity': whether the central cue is valid, invalid, or neutral
# 'easy_trial': whether the trial is a simple detection trial (True) or also
#     requires a colour response (False).

ColourWheelEffort_ind_vars.add_variable("probe_location", str, ["L", "R"])
ColourWheelEffort_ind_vars.add_variable("catch_trial", bool, [True, (False, 4)])
ColourWheelEffort_ind_vars.add_variable(
    "cue_validity", str, [("valid", 4), "invalid", "neutral"]
)
ColourWheelEffort_ind_vars.add_variable("easy_trial", bool, [True, False])
