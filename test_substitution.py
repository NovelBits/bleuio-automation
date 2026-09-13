#!/usr/bin/env python3
"""Tests for --set / {{KEY}} substitution in run-session.py.

Pure string work, so this runs with no dongles attached:
    python3 test_substitution.py
"""
import importlib.util
import pathlib
import unittest

# run-session.py has a hyphen, so it cannot be imported by name. Load it by path
# rather than splitting a deliberately single-file tool into a library.
_spec = importlib.util.spec_from_file_location(
    "run_session", pathlib.Path(__file__).parent / "run-session.py")
_rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rs)
parse_sets, substitute = _rs.parse_sets, _rs.substitute


class ParseSets(unittest.TestCase):
    def test_single(self):
        self.assertEqual(parse_sets(["CI=24"]), {"CI": "24"})

    def test_multiple(self):
        self.assertEqual(parse_sets(["CI=24", "MAC=AA:BB:CC:DD:EE:FF"]),
                         {"CI": "24", "MAC": "AA:BB:CC:DD:EE:FF"})

    def test_value_may_contain_equals(self):
        # AT syntax uses '=' inside values, so only the FIRST '=' separates.
        self.assertEqual(parse_sets(["P=intv_min=30"]), {"P": "intv_min=30"})

    def test_none(self):
        self.assertEqual(parse_sets(None), {})

    def test_missing_equals_is_an_error(self):
        with self.assertRaises(ValueError):
            parse_sets(["CI24"])

    def test_empty_key_is_an_error(self):
        with self.assertRaises(ValueError):
            parse_sets(["=24"])


class Substitute(unittest.TestCase):
    def test_single_placeholder(self):
        self.assertEqual(substitute("[A] AT+X={{CI}}", {"CI": "24"}), "[A] AT+X=24")

    def test_repeated_placeholder(self):
        self.assertEqual(substitute("{{CI}}:{{CI}}", {"CI": "24"}), "24:24")

    def test_multiple_keys(self):
        out = substitute("[0]{{MAC}}={{CI}}:{{CI}}:0:400", {"MAC": "AA:BB", "CI": "40"})
        self.assertEqual(out, "[0]AA:BB=40:40:0:400")

    def test_value_with_colons_is_literal(self):
        # A MAC is not a regex; colons and any other metacharacters must survive.
        out = substitute("{{MAC}}", {"MAC": "AA:BB:CC:DD:EE:FF"})
        self.assertEqual(out, "AA:BB:CC:DD:EE:FF")

    def test_value_with_backslash_is_literal(self):
        self.assertEqual(substitute("{{V}}", {"V": r"a\1b"}), r"a\1b")

    def test_no_placeholders_and_no_sets_is_unchanged(self):
        text = "[A] ATI @expect BleuIO\n[B] AT+ADVSTART\n"
        self.assertEqual(substitute(text, {}), text)

    def test_unsubstituted_placeholder_is_an_error(self):
        # Silently sending a literal {{CI}} to the dongle fails confusingly later.
        with self.assertRaises(ValueError) as cm:
            substitute("[A] AT+X={{CI}}", {})
        self.assertIn("CI", str(cm.exception))

    def test_unused_set_is_an_error(self):
        # A typo'd key would otherwise sweep the same value N times and look like it worked.
        with self.assertRaises(ValueError) as cm:
            substitute("[A] ATI", {"CI": "24"})
        self.assertIn("CI", str(cm.exception))

    def test_whitespace_inside_braces_is_not_a_placeholder(self):
        text = "{{ CI }}"
        self.assertEqual(substitute(text, {}), text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
