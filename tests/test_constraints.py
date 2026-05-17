import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from constraints import has_barrier, normalize_barriers, validate_recommendation_text


class NormalizeBarriersTests(unittest.TestCase):

    def test_normalize_none_returns_empty_list(self):
        self.assertEqual(normalize_barriers(None), [])

    def test_normalize_empty_string_returns_empty_list(self):
        self.assertEqual(normalize_barriers(""), [])

    def test_normalize_phone_canonical(self):
        self.assertEqual(normalize_barriers("phone"), ["phone"])

    def test_normalize_phone_synonyms(self):
        for barrier in ["calls", "telephone", "cant call", "can't call", "phone calls"]:
            self.assertEqual(normalize_barriers(barrier), ["phone"])

    def test_normalize_mixed_case(self):
        self.assertEqual(normalize_barriers(["Phone", "PHONE", "phone"]), ["phone"])

    def test_normalize_list_input(self):
        self.assertEqual(normalize_barriers(["Phone", "TRANSPORT"]), ["phone", "transport"])

    def test_normalize_comma_separated_string(self):
        self.assertEqual(normalize_barriers("phone, transport"), ["phone", "transport"])

    def test_normalize_dedupe(self):
        self.assertEqual(normalize_barriers("phone, calls, telephone"), ["phone"])

    def test_normalize_unknown_token_dropped(self):
        self.assertEqual(normalize_barriers("flying, ???"), [])

    def test_normalize_extracted_from_sentence(self):
        self.assertEqual(normalize_barriers("I can't make phone calls"), ["phone"])


class HasBarrierTests(unittest.TestCase):

    def test_has_barrier_true(self):
        self.assertTrue(has_barrier(["phone"], "phone"))

    def test_has_barrier_false_unknown(self):
        self.assertFalse(has_barrier(["flying"], "phone"))

    def test_has_barrier_false_empty(self):
        self.assertFalse(has_barrier(None, "phone"))

    def test_has_barrier_normalizes_input(self):
        self.assertTrue(has_barrier("PHONE CALLS", "phone"))


class ValidateRecommendationTextTests(unittest.TestCase):

    def test_validate_no_barriers_always_valid(self):
        result = validate_recommendation_text("Call 211 today.", None)
        self.assertTrue(result["valid"])
        self.assertEqual(result["violations"], [])
        self.assertIsNone(result["repair_suggestion"])
        self.assertEqual(result["barriers_checked"], [])

    def test_validate_call_211_blocking(self):
        result = validate_recommendation_text("Call 211 today.", ["phone"])
        self.assertFalse(result["valid"])
        self.assertEqual(result["violations"][0]["barrier"], "phone")
        self.assertEqual(result["violations"][0]["severity"], "blocking")
        self.assertEqual(result["violations"][0]["matched_text"], "Call 211")

    def test_validate_call_988_blocking(self):
        result = validate_recommendation_text("Call 988 now.", ["phone"])
        self.assertFalse(result["valid"])
        self.assertEqual(result["violations"][0]["matched_text"], "Call 988")

    def test_validate_explicit_1800_blocking(self):
        result = validate_recommendation_text("Call 1-800-772-1213.", ["phone"])
        self.assertFalse(result["valid"])
        self.assertEqual(result["violations"][0]["matched_text"], "Call 1-800-772-1213")

    def test_validate_dial_imperative_blocking(self):
        result = validate_recommendation_text("Dial 5551212 for help.", ["phone"])
        self.assertFalse(result["valid"])
        self.assertEqual(result["violations"][0]["matched_text"], "Dial 5")

    def test_validate_phone_violation_returns_repair_suggestion(self):
        result = validate_recommendation_text("Call 211 today.", ["phone"])
        self.assertIn("Phone is named as a barrier", result["repair_suggestion"])

    def test_validate_no_violation_returns_empty_violations(self):
        result = validate_recommendation_text("Apply online at ssa.gov/apply.", ["phone"])
        self.assertTrue(result["valid"])
        self.assertEqual(result["violations"], [])
        self.assertIsNone(result["repair_suggestion"])

    def test_validate_transport_in_person_no_alternative_blocking(self):
        result = validate_recommendation_text(
            "Schedule an in-person appointment at the benefits office.",
            ["transport"],
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["violations"][0]["barrier"], "transport")
        self.assertEqual(result["violations"][0]["severity"], "blocking")

    def test_validate_transport_in_person_with_online_ok(self):
        result = validate_recommendation_text(
            "Schedule an in-person appointment, or use the online form.",
            ["transport"],
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["violations"], [])

    def test_validate_focus_stub_no_violation_yet(self):
        # TODO marker: focus checks are implemented Weekend 1 Sunday.
        result = validate_recommendation_text("- One\n- Two\n- Three", ["focus"])
        self.assertTrue(result["valid"])
        self.assertEqual(result["violations"], [])

    def test_validate_overwhelm_stub_no_violation_yet(self):
        # TODO marker: overwhelm checks are implemented Weekend 1 Sunday.
        result = validate_recommendation_text(
            "One. Two. Three. Four. Five.",
            ["overwhelm"],
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["violations"], [])

    def test_validate_multiple_barriers_concatenates_repair(self):
        result = validate_recommendation_text(
            "Call 211 today.\n\nSchedule an in-person appointment at the office.",
            ["phone", "transport"],
        )
        self.assertFalse(result["valid"])
        self.assertIn("\n\n", result["repair_suggestion"])
        self.assertIn("Phone is named as a barrier", result["repair_suggestion"])
        self.assertIn("Transportation is named as a barrier", result["repair_suggestion"])


if __name__ == '__main__':
    unittest.main()
