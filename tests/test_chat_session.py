"""
Backward-compat tests for /api/chat session injection.

Run from repo root:
    python3 -m unittest tests.test_chat_session

Verifies:
  - Empty/missing session falls back to the original hardcoded prompt
    (preserves backward compatibility with navigator_v2.html).
  - Populated session produces a prompt that includes the new context block.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from routes_v2 import _BASE_SYSTEM_PROMPT, _build_system_prompt


class BuildSystemPromptTests(unittest.TestCase):

    def test_empty_session_returns_base_prompt(self):
        self.assertEqual(_build_system_prompt({}), _BASE_SYSTEM_PROMPT)

    def test_none_session_returns_base_prompt(self):
        self.assertEqual(_build_system_prompt(None), _BASE_SYSTEM_PROMPT)

    def test_populated_session_extends_base(self):
        session = {
            'name': 'Sam',
            'goal': 'benefits',
            'barriers': ['phone', 'focus'],
            'urgency': 'today',
            'style': 'gentle',
            'state': 'Washington',
        }
        prompt = _build_system_prompt(session)
        self.assertTrue(prompt.startswith(_BASE_SYSTEM_PROMPT))
        self.assertIn('Sam', prompt)
        self.assertIn('benefits or assistance', prompt)
        self.assertIn('phone calls are a barrier', prompt)
        self.assertIn('act today', prompt)
        self.assertIn('gentle', prompt)
        self.assertIn('Washington', prompt)

    def test_session_without_state_does_not_leak_other_label(self):
        prompt = _build_system_prompt({'state': 'Other'})
        self.assertNotIn('They are in Other', prompt)
        prompt = _build_system_prompt({'state': 'Prefer not to say'})
        self.assertNotIn('Prefer not to say', prompt)

    def test_unknown_values_are_ignored(self):
        session = {
            'goal': 'totally-unknown-goal',
            'style': 'mystery',
            'barriers': ['flying', 'phone'],
            'urgency': 'someday',
        }
        prompt = _build_system_prompt(session)
        self.assertNotIn('totally-unknown-goal', prompt)
        self.assertNotIn('mystery', prompt)
        self.assertNotIn('flying', prompt)
        # known barrier still picked up
        self.assertIn('phone calls are a barrier', prompt)


if __name__ == '__main__':
    unittest.main()
