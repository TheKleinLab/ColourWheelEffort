# -*- coding: utf-8 -*-

__author__ = "Austin Hurst"

# Import required KLibs classes and functions

import klibs
from klibs.KLConstants import TK_S, TK_MS, STROKE_INNER, TIMEOUT, EL_GAZE_POS
from klibs import P
from klibs.KLUtilities import deg_to_px
from klibs.KLBoundary import CircleBoundary
from klibs.KLTime import Stopwatch
from klibs.KLEventQueue import pump, flush
from klibs.KLUserInterface import any_key, ui_request, key_pressed, smart_sleep, hide_cursor
from klibs.KLGraphics import KLDraw as kld
from klibs.KLGraphics import fill, flip, blit
from klibs.KLGraphics import NumpySurface as NpS
from klibs.KLResponseCollectors import (
    ResponseCollector, KeyPressResponse, ColorWheelResponse,
)
from klibs.KLEventInterface import TrialEventTicket as ET
from klibs.KLCommunication import message

# Import additional required libraries

import time
import math
import random
from copy import copy

from colormath.color_objects import LCHuvColor, sRGBColor
from colormath.color_conversions import convert_color


# Define colours for the experiment

WHITE = [255, 255, 255, 255]
BLACK = [0, 0, 0, 255]
DARK_GREY = [64, 64, 64, 255]
MED_GREY = [128, 128, 128, 255]
LIGHT_GREY = [192, 192, 192, 255]


mixed_instructions = (
    "During this block, you will need to remember the colours of targets on some "
    "trials,\nbut not on others. If the dots in the middle of the screen are grey, "
    "you will be\nasked to identify the colour of the target at the end of that "
    "trial. If the dots are\ncolourful, you only need to detect the target quickly "
    "when it appears."
)


class ColourWheelEffort(klibs.Experiment):

    def setup(self):
        
        # Colour spectrum
        cieluv = []
        for i in range(0, 360):
            rgb = convert_color(LCHuvColor(75, 59, i, illuminant='d65'), sRGBColor)
            cieluv.append(rgb.get_upscaled_value_tuple())

        # Other colors
        self.bg_fill = P.default_fill_color
        stim_grey = convert_color(LCHuvColor(75, 0, 0, illuminant='d65'), sRGBColor)
        self.stim_grey = stim_grey.get_upscaled_value_tuple()

        # Stimulus Sizes
        probe_area = 0.4 # degrees^2
        fixation_size = deg_to_px(1.0)
        box_size = deg_to_px(2.0)
        wheel_size = deg_to_px(12.0)
        wheel_thickness = deg_to_px(2.0)
        fixation_stroke = deg_to_px(0.1)
        self.box_stroke = deg_to_px(0.15, even=True)
        self.dot_size = deg_to_px(0.1)
        self.dot_spacing = deg_to_px(0.15, even=True)
        self.probe_diameter = deg_to_px(2 * math.sqrt(probe_area / math.pi))

        # Generate dots for fixation/cue stimuli
        line_h_pts = [(offset, 0) for offset in (-2, -1, 0, 1, 2)]
        self.cue_pts = {
            "fixation": line_h_pts + [(0, 2), (0, 1), (0, -1), (0, -2)],
            "left": line_h_pts + [(0, 2), (0, -2), (-1, 1), (-1, -1)],
            "right": line_h_pts + [(0, 2), (0, -2), (1, 1), (1, -1)],
        }
        self.cue_pts["neutral"] = [(0, 0)]
        for offset in (-2, -1, 1, 2):
            self.cue_pts["neutral"].append((offset, offset))
            self.cue_pts["neutral"].append((-offset, offset))

        # Generate dots for drift correct stimulus (diamond w/ dot in centre)
        dc_pts = [(0, 0)]
        for offsets in [(2, 0), (1, 1)]:
            x, y = offsets
            dc_pts += [(-x, y), (x, -y), (y, x), (-y, -x)]
        
        # Stimulus Drawbjects (the rest are generated dynamically in trial_prep)
        self.dc_fixation = dot_grid(
            dc_pts, self.dot_size, self.dot_spacing, self.stim_grey
        )
        self.fixation = dot_grid(
            self.cue_pts["fixation"], self.dot_size, self.dot_spacing, self.stim_grey
        )
        self.box = kld.Rectangle(box_size)
        self.box.stroke = [self.box_stroke, self.stim_grey, STROKE_INNER]
        self.wheel  = kld.ColorWheel(wheel_size, thickness=wheel_thickness, colors=cieluv)
        self.placeholder = kld.Ellipse(self.probe_diameter, fill=self.stim_grey)
        
        # Layout
        box_offset = deg_to_px(6.0)
        self.box_l_pos = (P.screen_c[0]-box_offset, P.screen_c[1])
        self.box_r_pos = (P.screen_c[0]+box_offset, P.screen_c[1])

        # Timing
        self.probe_duration = 150 # ms
        self.detection_timeout = (1000 + self.probe_duration) / 1000 # seconds
        
        # Initialize colour wheel ResponseCollector
        self.wheel_rc = ResponseCollector(uses=[ColorWheelResponse])
        self.wheel_rc.terminate_after = [60, TK_S]
        self.wheel_rc.display_callback = self.wheel_callback
        self.wheel_rc.color_listener.interrupts = True
        self.wheel_rc.color_listener.color_response = True
        self.wheel_rc.color_listener.set_wheel(self.wheel)

        # Add fixation boundary to eye tracker
        fix_bounds = CircleBoundary('fixation', P.screen_c, fixation_size * 3.0)
        self.el.add_boundary(fix_bounds)

        # Add separate practice blocks for easy/difficult trials
        self.num_practice_blocks = 0
        if P.run_practice_blocks:
            self.insert_practice_block(1, 16, factor_mask={'easy_trial': True})
            self.insert_practice_block(2, 16, factor_mask={'easy_trial': False})
            self.num_practice_blocks = 2

        # Before we start, measure the size range of the participant's pupil
        self.get_pupil_range()

        # Show the task instructions to the participant
        self.task_demo()
    

    def block(self):
        # At the start of each block, display a start message.
        if P.practicing:
            block = P.block_number
            n_blocks = self.num_practice_blocks
            txt = "Practice Block {0} of {1}".format(block, n_blocks)
        else:
            block = P.block_number - self.num_practice_blocks
            n_blocks = P.blocks_per_experiment - self.num_practice_blocks
            txt = "Block {0} of {1}".format(block, n_blocks)

        if P.run_practice_blocks and P.block_number == 1:
            txt += "\n\n" + (
                "During this block, you do not need to pay attention to the colour "
                "of the\ntargets. Just try to respond quickly when targets appear."
            )
        elif P.run_practice_blocks and P.block_number == 2:
            txt += "\n\n" + (
                "During this block, please pay attention to the colour of each target "
                "as you\nwill be asked to accurately identify its colour at the end of "
                "each trial."
            )
        else:
            txt += "\n\n" + mixed_instructions
        msg = message(txt, align="center", blit_txt=False)

        # Show block message and wait 1500 ms before allowing block start
        fill()
        blit(msg, 8, (P.screen_c[0], P.screen_y * 0.35))
        flip()
        smart_sleep(1500)
        
        start_msg = message("Press any key to start.", blit_txt=False)
        fill()
        blit(msg, 8, (P.screen_c[0], P.screen_y * 0.35))
        blit(start_msg, 5, (P.screen_c[0], P.screen_y * 0.7))
        flip()
        any_key()


    def trial_prep(self):

        # Reset the colour probe at the start of each trial
        self.probe = kld.Ellipse(self.probe_diameter, fill=None)
        self.wheel_rc.color_listener.set_target(self.probe)
        
        # Set up colour probe and colour wheel
        self.wheel.rotation = random.randrange(0, 360, 1)
        self.wheel.render()
        self.probe.fill = self.wheel.color_from_angle(random.randrange(0, 360, 1))
        self.probe.render()

        # Determine probe location and cue type for the trial
        self.probe_loc = self.box_l_pos if self.probe_location == "L" else self.box_r_pos
        if self.cue_validity == "valid":
            cue_type = "left" if self.probe_location == "L" else "right"
        elif self.cue_validity == "invalid":
            cue_type = "left" if self.probe_location == "R" else "right"
        else:
            cue_type = "neutral"
        
        # Dynamically alter the fixation/cue stimuli between trials
        fix_col = self.probe.fill_color if self.easy_trial else self.stim_grey
        self.fixation = self.render_fixation(fix_col)
        self.cue = self.render_cue(cue_type, fix_col)
        
        # Add timecourse of events to EventManager
        self.probe_onset = random.randrange(1000, 3050, 50)
        events = []
        events.append([1000, 'cue_on'])
        events.append([1000 + self.probe_onset, 'probe_on'])
        events.append([events[-1][0] + self.probe_duration, 'probe_off'])
        for e in events:
            self.evm.register_ticket(ET(e[1], e[0]))

        # If it's been 40 trials since the last block or break, present break message
        if P.trial_number > 1 and P.trial_number % 40 == 1:
            self.break_msg()

        # Perform drift correct before each trial
        self.el.drift_correct(target=self.dc_fixation)
        

    def trial(self):
        # Initialize trial default data
        trialdat = {
            "block_num": P.block_number,
            "trial_num": P.trial_number,
            "practice": P.practicing,
            "difficulty": "easy" if self.easy_trial else "difficult",
            "catch_trial": self.catch_trial,
            "probe_loc": "NA" if self.catch_trial else self.probe_location,
            "probe_onset": 0 if self.catch_trial else self.probe_onset,
            "probe_rt": TIMEOUT,
            "wheel_rt": "NA",
            "angle_err": "NA",
            "probe_col": str(tuple(self.probe.fill_color[:3])),
            "response_col": "NA",
            "probe_angle": self.wheel.angle_from_color(self.probe.fill_color),
            "response_angle": "NA",
            "trial_err": "NA",
        }

        # Draw fixation + cue placeholders to the screen
        self.draw_screen_layout()
        blit(self.fixation, 5, P.screen_c)
        flip()

        # Wait for cue onset and ensure gaze stays within fixation
        self.el.write("trial_start b{0} t{1}".format(P.block_number, P.trial_number))
        while self.evm.before('cue_on'):
            if key_pressed(' '):
                trialdat["trial_err"] = "too_soon"
                self.err_msg("Responded too soon!")
                return trialdat
            if self.el.saccade_from_boundary('fixation'):
                #if not self.el.within_boundary('fixation', EL_GAZE_POS):
                trialdat["trial_err"] = "gaze_err"
                self.err_msg("Looked away!")
                return trialdat

        # Replace fixation with isoluminant cue stimulus
        self.draw_screen_layout()
        blit(self.cue, 5, P.screen_c)
        flip()
        
        # Wait for probe onset and ensure gaze stays within fixation
        self.el.write("cue_on b{0} t{1}".format(P.block_number, P.trial_number))
        while self.evm.before('probe_on'):
            if key_pressed(' '):
                trialdat["trial_err"] = "too_soon"
                self.err_msg("Responded too soon!")
                return trialdat
            if self.el.saccade_from_boundary('fixation'):
                #if not self.el.within_boundary('fixation', EL_GAZE_POS):
                trialdat["trial_err"] = "gaze_err"
                self.err_msg("Looked away!")
                return trialdat
        
        # Present probe (unless catch trial)
        self.draw_screen_layout()
        blit(self.cue, 5, P.screen_c)
        if not self.catch_trial:
            blit(self.probe, 5, self.probe_loc)
        flip()

        # Enter collection loop for detection response
        probe_on = True
        timer = Stopwatch()
        self.el.write("probe_on b{0} t{1}".format(P.block_number, P.trial_number))
        flush()
        while timer.elapsed() < self.detection_timeout:
            q = pump(True)
            # Log RT immediately on space bar press
            if key_pressed(' ', queue=q):
                trialdat["probe_rt"] = timer.elapsed() * 1000
                break
            # Stop trial and show error if gaze leaves fixation before response
            if not self.el.within_boundary('fixation', EL_GAZE_POS):#self.el.saccade_from_boundary('fixation'):
                trialdat["trial_err"] = "gaze_err"
                self.err_msg("Looked away!")
                return trialdat
            # Remove probe after probe duration elapsed
            if probe_on and (timer.elapsed() * 1000) > self.probe_duration:
                self.draw_screen_layout()
                blit(self.cue, 5, P.screen_c)
                flip()
                probe_on = False

        # Show error if participant responds on a catch trial or times out on a
        # non-catch trial
        if trialdat["probe_rt"] == TIMEOUT:
            if not self.catch_trial:
                trialdat["trial_err"] = "no_resp"
                self.err_msg("Too slow!")
                return trialdat
        else:
            if self.catch_trial:
                trialdat["trial_err"] = "catch_resp"
                self.err_msg("Responded too soon!") # NOTE: Do we want a different message?
                return trialdat
        
        # If difficult trial, present the colour wheel and wait for a response
        if not self.catch_trial and not self.easy_trial:

            self.el.write("wheel_on b{0} t{1}".format(P.block_number, P.trial_number))
            self.wheel_rc.collect()

            if self.wheel_rc.color_listener.timed_out:
                trialdat["wheel_rt"] = "timeout"
            else:
                wheel_resp = self.wheel_rc.color_listener.response(rt=False)
                trialdat["wheel_rt"] = self.wheel_rc.color_listener.response(value=False)
                trialdat["angle_err"] = wheel_resp[0]
                trialdat["response_col"] = str(tuple(wheel_resp[1][:3]))
                trialdat["response_angle"] = self.wheel.angle_from_color(wheel_resp[1])

        return trialdat


    def trial_clean_up(self):
        self.wheel_rc.reset()


    def clean_up(self):

        txt = "You're all done!\n\nPress any key to exit the experiment."
        fill()
        message(txt, location=P.screen_c)
        flip()
        smart_sleep(200)
        any_key()

        if not "TryLink" in self.el.version:
            fill()
            message("Transferring EyeLink data, please wait...", location=P.screen_c)
            flip()


    def draw_screen_layout(self):
        fill(self.bg_fill)
        blit(self.box, 5, self.box_l_pos)
        blit(self.box, 5, self.box_r_pos)
        blit(self.placeholder, 5, self.box_l_pos)
        blit(self.placeholder, 5, self.box_r_pos)


    def break_msg(self):
        msg1 = message("Take a break if you need one!")
        msg2 = message("When ready, press any key to start the next trial.")
        fill()
        blit(msg1, 2, P.screen_c)
        flip()
        smart_sleep(1000)
        fill()
        blit(msg1, 2, P.screen_c)
        blit(msg2, 8, (P.screen_c[0], int(P.screen_c[1] + 0.5 * msg1.height)))
        flip()
        any_key()


    def err_msg(self, msg):
        err = message(msg, "alert", blit_txt=False)
        fill()
        blit(err, 5, P.screen_c)
        flip()
        smart_sleep(1000)

    
    def wheel_callback(self):
        fill(self.bg_fill)
        blit(self.wheel, location=P.screen_c, registration=5)
        flip()


    def render_fixation(self, color):
        fix_pts = self.cue_pts["fixation"]
        return dot_grid(fix_pts, self.dot_size, self.dot_spacing, color)


    def render_cue(self, cue_type, color):
        cue_pts = self.cue_pts[cue_type]
        return dot_grid(cue_pts, self.dot_size, self.dot_spacing, color)


    def show_demo_text(self, msgs, stim_set, duration=1.0, wait=True, msg_y=None):
        msg_x = int(P.screen_x / 2)
        msg_y = int(P.screen_y * 0.25) if msg_y is None else msg_y
        half_space = deg_to_px(0.5)

        fill()
        if not isinstance(msgs, list):
            msgs = [msgs]
        for msg in msgs:
            txt = message(msg, blit_txt=False, align="center")
            blit(txt, 8, (msg_x, msg_y))
            msg_y += txt.height + half_space
    
        for stim, locs in stim_set:
            if not isinstance(locs, list):
                locs = [locs]
            for loc in locs:
                blit(stim, 5, loc)
        flip()
        smart_sleep(duration * 1000)
        if wait:
            any_key()


    def demo_cue_target(self, text, base_layout, cue_type, target_loc, pretarget=None):
        # Render stimuli
        target_col = self.wheel.color_from_angle(random.randrange(0, 360, 1))
        cue = self.render_cue(cue_type, self.stim_grey)
        target = kld.Ellipse(self.probe_diameter, fill=target_col)
        # Show example event sequence
        if pretarget:
            self.show_demo_text(
                text, base_layout + [(cue, P.screen_c)], duration=pretarget, wait=False
            )
        else:
            self.show_demo_text(
                text, base_layout + [(cue, P.screen_c)],
            )
        self.show_demo_text(
            " ", base_layout + [(cue, P.screen_c), (target, target_loc)],
            duration=0.15, wait=False
        )
        self.show_demo_text(
            " ", base_layout + [(cue, P.screen_c)],
            duration=0.6, wait=False
        )


    def task_demo(self):
        # Initialize task stimuli for the demo
        self.probe = kld.Ellipse(self.probe_diameter, fill=None)
        self.probe.fill = self.wheel.color_from_angle(90)
        fixation_grey = self.render_fixation(self.stim_grey)
        base_layout = [
            (self.box, self.box_l_pos),
            (self.box, self.box_r_pos),
            (self.placeholder, self.box_l_pos),
            (self.placeholder, self.box_r_pos),
        ]
        
        # Actually run through demo
        self.show_demo_text(
            "Welcome to the experiment! This tutorial will help explain the task.",
            base_layout + [(fixation_grey, P.screen_c)]
        )
        self.show_demo_text(
            ("On most trials of the task, a colour target will appear briefly in one\n"
             "of two locations on the screen after a random delay."),
            base_layout + [(fixation_grey, P.screen_c), (self.probe, self.box_l_pos)],
        )
        self.show_demo_text(
            ("Your job will be to respond quickly to these targets when they appear\n"
             "by pressing the space bar on the keyboard."),
            base_layout + [(fixation_grey, P.screen_c)]
        )
        self.show_demo_text(
            ("At some point before each target appears, a spatial cue will appear in\n"
              "the middle of the screen to direct your attention to one of the two\n"
              "possible target locations."),
            base_layout + [(self.render_cue("left", self.stim_grey), P.screen_c)]
        )
        self.demo_cue_target(
            ("If the cue is a left arrow, the target will most likely (but not always)\n"
             "appear in the left location."),
            base_layout, cue_type="left", target_loc=self.box_l_pos
        )
        self.demo_cue_target(
            ("Likewise, if the cue is a right arrow, the target will most likely\n"
             "appear in the right location."),
            base_layout, cue_type="right", target_loc=self.box_r_pos
        )
        self.demo_cue_target(
            ("If the cue is an 'X', this means that the target is equally likely to\n"
             "appear at either location."),
            base_layout, cue_type="neutral", target_loc=self.box_r_pos
        )
        self.show_demo_text(
            ("If a trial starts with a *grey* fixation cross, this means that in "
             "addition\nto detecting the target, you will also need to report its "
             "colour."),
            base_layout + [(fixation_grey, P.screen_c)]
        )
        self.demo_cue_target(
            " ", base_layout, cue_type="left", target_loc=self.box_l_pos, pretarget=1.2
        )
        self.show_demo_text(
            ("On these trials, a colour wheel will appear on screen after you respond\n"
             "to the target. When this happens, please click the colour on the wheel\n"
             "that best matches the colour of the target you just saw."),
            [(self.wheel, P.screen_c)], msg_y=int(P.screen_y * 0.1)
        )
        demo_col = self.wheel.color_from_angle(180)
        self.probe.fill = demo_col
        fixation_col = self.render_fixation(demo_col)
        self.show_demo_text(
            ("On the other hand, if the trial starts with a *colorful* fixation cross, "
             "you only\nneed to detect the target and will not be asked to report its "
             "color."),
            base_layout + [(fixation_col, P.screen_c)]
        )
        self.show_demo_text(
            ["Before each trial, a diamond will appear in the middle of the screen.",
             ("To start the trial, please look directly at the center of the diamond\n"
              "and press the space bar."),
            ],
            [(self.dc_fixation, P.screen_c)], msg_y=int(P.screen_y * 0.2)
        )
        self.show_demo_text(
            ("During each trial, do your best to keep your eyes fixed on the middle of "
             "the\nscreen and use your peripheral vision to detect the targets."),
            base_layout + [(fixation_grey, P.screen_c)]
        )
        self.show_demo_text(
            ("Now that we've explained the basics, we'll do a few practice trials to\n"
             "help you get comfortable with the task!"),
            base_layout + [(fixation_grey, P.screen_c)]
        )


    def get_pupil_range(self):
        # Show instructions and wait for response
        txt = (
            "Before you start the task, the experiment will measure your baseline "
            "pupil size\nand how it changes based on the screen's brightness.\n\n"
            "Over the next 20 seconds, the screen will slowly increase in brightness "
            "and then\nslowly return to minimum brightness. Please keep your eyes as "
            "still as possible\nduring pupil size calibration."
        )
        msg1 = message(txt, align="center")
        msg2 = message("Press any key to begin.")
        fill()
        blit(msg1, 2, P.screen_c)
        flip()
        # Wait 1500 ms before allowing participant to start
        smart_sleep(1500)
        fill()
        blit(msg1, 2, P.screen_c)
        blit(msg2, 8, (P.screen_c[0], int(P.screen_y * 0.6)))
        flip()
        any_key()

        # Start the baseline with a fully black screen
        l = 0  # luminence (0 = black, 255 = white)
        fill((l, l, l))
        flip()

        # Start recording and hold on black screen for 4 sec
        self.el.start(trial_number=0)
        self.el.write("PUPIL_BASELINE START")
        smart_sleep(4000)

        # Slowly ramp up to maximum brigthness (~4 sec)
        self.el.write("PUPIL_BASELINE INCREASE")
        while l < 255:
            ui_request()
            fill((l, l, l))
            flip()
            l += 1

        # Hold at maximum brightness for 4 sec
        self.el.write("PULIL_BASELINE MAXIMUM")
        smart_sleep(4000)

        # Slowly ramp down to minimum brightness (~4 sec)
        self.el.write("PUPIL_BASELINE DECREASE")
        while l > 0:
            ui_request()
            fill((l, l, l))
            flip()
            l -= 1

        # Hold at minimum brightness for 4 sec, then stop recording
        self.el.write("PULIL_BASELINE MINIMUM")
        smart_sleep(4000)
        self.el.write("PUPIL_BASELINE END")
        self.el.stop()



def dot_grid(points, diameter, spacing, color):
    # Determine canvas size
    x_max, y_max = (0, 0)
    for x, y in points:
        x_max = abs(x) if abs(x) > x_max else x_max
        y_max = abs(y) if abs(y) > y_max else y_max
    surf_w = (x_max * 2) * spacing + diameter
    surf_h = (y_max * 2) * spacing + diameter

    # Render point and surface
    pt = kld.Ellipse(diameter, fill=color)
    surf = NpS(width=surf_w, height=surf_h)

    # Draw points on surface
    sc_x, sc_y = surf.surface_c
    for x, y in points:
        loc = (sc_x + x * spacing, sc_y + y * spacing)
        surf.blit(pt, 5, loc, blend=False)
    
    return surf.render()

