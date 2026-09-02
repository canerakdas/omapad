"""The mapping wizard: what it learns, what it refuses, and what it writes."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import config as config_module, mapping


class WizardTests(unittest.TestCase):
    def setUp(self):
        self.model = mapping.MappingModel()
        self.model.start("057E:2009", "BEITONG  BTP-KP20 NS")

    def press(self, *codes):
        return [self.model.learn("button", code) for code in codes][-1]

    def test_it_asks_for_the_face_buttons_first(self):
        # A wrong profile scrambles those before anything else, and they are
        # the ones someone reaches for to check whether it worked.
        self.assertEqual(self.model.step, "A")
        self.press(0x130)
        self.assertEqual(self.model.step, "B")

    def test_a_press_is_written_down_under_the_name_being_asked_for(self):
        self.press(0x130, 0x131)
        self.assertEqual(self.model.learned["A"], ("button", 0x130))
        self.assertEqual(self.model.learned["B"], ("button", 0x131))
        self.assertEqual(self.model.buttons(), {0x130: "A", 0x131: "B"})

    def test_a_button_that_already_has_a_name_skips_the_step(self):
        # The only gesture left when the pad has no such button - an Xbox pad
        # has no Capture - and the answer to pressing the same one twice.
        self.press(0x130)
        self.assertEqual(self.press(0x130), "skipped")
        self.assertEqual(self.model.step, "X")
        self.assertNotIn("B", self.model.learned)
        self.assertIn("B", self.model.skipped)

    def test_an_axis_is_learned_as_a_trigger_rather_than_a_button(self):
        # XInput pads report ZL/ZR as axes; a wizard that only knew buttons
        # would leave exactly the two the console scheme clicks with unmapped.
        for code in (0x130, 0x131, 0x133, 0x134, 0x136, 0x137):
            self.model.learn("button", code)
        self.assertEqual(self.model.step, "ZL")
        self.model.learn("axis", 0x02)
        self.assertEqual(self.model.triggers(), {0x02: "ZL"})
        self.assertNotIn(0x02, self.model.buttons())

    def test_a_button_and_an_axis_of_the_same_number_are_not_the_same_thing(self):
        self.model.learn("button", 0x02)
        self.assertEqual(self.model.taken("axis", 0x02), None)

    def test_back_un_asks_the_last_step(self):
        self.press(0x130, 0x131)
        self.assertTrue(self.model.back())
        self.assertEqual(self.model.step, "B")
        self.assertNotIn("B", self.model.learned)
        self.assertEqual(self.model.buttons(), {0x130: "A"})

    def test_back_off_the_first_step_does_nothing(self):
        self.assertFalse(self.model.back())
        self.assertEqual(self.model.step, "A")

    def test_the_last_step_is_a_confirmation(self):
        for index, code in enumerate(range(0x130, 0x130 + len(mapping.STEPS))):
            self.model.learn("button", code)
        self.assertTrue(self.model.done)
        self.assertIsNone(self.model.step)

    def test_saving_is_asked_for_in_the_names_just_learned(self):
        # The cheapest possible test of the mapping: a wizard that got A wrong
        # cannot be saved with A.
        self.press(0x131)          # A is where the pad's B usually sits
        self.press(0x130)          # B likewise
        for code in range(0x133, 0x133 + len(mapping.STEPS) - 2):
            self.model.learn("button", code)
        self.assertTrue(self.model.done)
        # A code that names nothing cannot answer the question.
        self.assertEqual(self.model.learn("button", 0x200), "ignored")
        # Where the pad prints A is where the profile expected B, and saving
        # follows what was learned rather than what the profile believed.
        self.assertEqual(self.model.learn("button", 0x130), "discard")
        self.assertEqual(self.model.learn("button", 0x131), "save")

    def test_b_discards_and_x_starts_over(self):
        self.press(0x130, 0x131, 0x133)
        for code in range(0x134, 0x134 + len(mapping.STEPS) - 3):
            self.model.learn("button", code)
        self.assertEqual(self.model.learn("button", 0x131), "discard")
        self.assertEqual(self.model.learn("button", 0x133), "restart")
        self.assertEqual(self.model.step, "A")
        self.assertEqual(self.model.learned, {})

    def test_the_view_says_where_every_button_stands(self):
        self.press(0x130)
        self.model.skip()
        state = self.model.view_state(True)
        rows = {row["n"]: row["s"] for row in state["rows"]}
        self.assertEqual(rows["A"], "done")
        self.assertEqual(rows["B"], "skipped")
        self.assertEqual(rows["X"], "asking")
        self.assertEqual(rows["Y"], "waiting")
        self.assertEqual(state["step"], "X")
        self.assertFalse(state["confirm"])


class RenderTests(unittest.TestCase):
    def test_a_block_per_identity_with_the_codes_under_it(self):
        text = mapping.render({
            "057E:2009": {
                "name": "BEITONG  BTP-KP20 NS",
                "buttons": {0x130: "A", 0x131: "B"},
                "triggers": {},
            },
            "20BC:5127": {
                "name": "Beitong KP20A",
                "buttons": {0x130: "A"},
                "triggers": {0x02: "ZL"},
            },
        })
        self.assertIn('[pad."057E:2009"]', text)
        self.assertIn('0x130 = "A"', text)
        self.assertIn('[pad."20BC:5127".triggers]', text)
        self.assertIn('0x002 = "ZL"', text)

    def test_what_it_writes_is_what_the_config_reads_back(self):
        text = mapping.render({
            "057E:2009": {
                "name": "BEITONG  BTP-KP20 NS",
                "buttons": {0x130: "A", 0x134: "X"},
                "triggers": {0x02: "ZL"},
            },
        })
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "mapping.toml")
            with open(path, "w") as handle:
                handle.write(text)
            missing = os.path.join(directory, "no-such-config.toml")
            config = config_module.load(path=missing, mapping=path,
                                        settings=missing)
        self.assertEqual(
            config.pad_mappings["057E:2009"]["buttons"],
            {0x130: "A", 0x134: "X"},
        )
        name, buttons, triggers = config.profile_for(
            "BEITONG  BTP-KP20 NS", "057E:2009"
        )
        self.assertEqual(name, "nintendo_pro")
        # Measured beats the profile, which calls 0x134 "Y".
        self.assertEqual(buttons[0x134], "X")
        self.assertEqual(buttons[0x130], "A")
        self.assertEqual(triggers, {0x02: "ZL"})

    def test_a_mapping_only_speaks_for_the_pad_it_was_measured_on(self):
        # The KP20 has one identity per hardware mode and different codes in
        # each, so a mapping that leaked across them would break the other.
        text = mapping.render({
            "057E:2009": {"name": "NS mode", "buttons": {0x130: "A"},
                          "triggers": {}},
        })
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "mapping.toml")
            with open(path, "w") as handle:
                handle.write(text)
            missing = os.path.join(directory, "no-such-config.toml")
            config = config_module.load(path=missing, mapping=path,
                                        settings=missing)
        _, buttons, _ = config.profile_for("Beitong KP20A", "20BC:5127")
        self.assertEqual(buttons[0x130], "A")  # the xbox profile's own answer
        _, ns_buttons, _ = config.profile_for("BEITONG NS", "057E:2009")
        self.assertEqual(ns_buttons[0x130], "A")  # measured, not the profile's B

    def test_a_hand_written_override_still_wins(self):
        data = {
            "device": {"buttons": {"0x130": "Y"}},
            "pad": {"057E:2009": {"buttons": {"0x130": "A"}}},
        }
        config = config_module.Config(data)
        _, buttons, _ = config.profile_for("pad", "057E:2009")
        self.assertEqual(buttons[0x130], "Y")


class LabelTests(unittest.TestCase):
    """What the screen asks for is what the pad in hand prints on it."""

    def model(self, layout):
        model = mapping.MappingModel(layout=layout)
        model.start("045E:0B12", "Xbox Wireless Controller")
        return model

    def state(self, layout, step):
        model = self.model(layout)
        model.index = mapping.STEPS.index(step)
        return model.view_state(True)

    def test_the_asked_for_button_is_badged_like_the_pad(self):
        # The name a mapping is written under is the Switch's whatever is
        # plugged in, and asking an Xbox pad for MINUS names nothing on it.
        state = self.state("xbox", "MINUS")
        self.assertEqual(state["step"], "MINUS")
        self.assertEqual(state["label"], "View")
        self.assertEqual(state["kind"], "system")
        self.assertEqual(self.state("nintendo", "MINUS")["label"], "−")
        self.assertEqual(self.state("xbox", "ZL")["label"], "LT")
        self.assertEqual(self.state("playstation", "L")["label"], "L1")

    def test_a_shape_is_said_in_words_underneath_it(self):
        # "Press ✕" reads as a crossed-out step; the prompt is what stops it.
        state = self.state("playstation", "A")
        self.assertEqual(state["label"], "✕")
        self.assertEqual(state["prompt"], "Cross")
        # Everywhere else the prompt still names both printings, which is the
        # case this whole screen exists for.
        self.assertEqual(self.state("xbox", "MINUS")["prompt"],
                         "Minus, or Back / View")

    def test_the_progress_strip_is_printed_the_same_way(self):
        rows = self.state("xbox", "A")["rows"]
        printed = {row["n"]: row["b"] for row in rows}
        self.assertEqual(printed["PLUS"], "Menu")
        self.assertEqual(printed["CAPTURE"], "Share")

    def test_the_confirmation_names_buttons_the_pad_has(self):
        keys = self.state("playstation", "A")["keys"]
        self.assertEqual(keys["save"], "✕")
        self.assertEqual(keys["discard"], "○")
        self.assertEqual(keys["restart"], "□")

    def test_the_switch_printing_is_what_nobody_saying_gets(self):
        self.assertEqual(mapping.MappingModel().layout, "nintendo")


if __name__ == "__main__":
    unittest.main()
