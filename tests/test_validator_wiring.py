"""
Tests for reply-side validator wiring inside /api/chat.

Verifies the integration contract laid out in
docs/handoffs/CC_HANDOFF_VALIDATOR_WIRING_2026-05-16.md:

  - When the first model call returns text that violates the user's stated
    barriers, the model is called a SECOND time with a repair-augmented
    system prompt (validator.repair_suggestion appended after the
    "--- ENFORCEMENT NOTE ---" marker).
  - When the second call still violates, the response ships with a
    fallback disclaimer naming the violated barriers — no third call.
  - When the first call is clean, the model is called exactly once.

The model client is mocked at the helper boundary
(routes_v2._call_model_with_system_prompt) so no real HTTP fires.

Run from repo root:
    python3 -m unittest tests.test_validator_wiring
"""

import json
import os
import sys
import unittest
from unittest.mock import patch

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, '..', 'src'))

from flask import Flask
import routes_v2


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(routes_v2.bp)
    return app


class ValidatorWiringTests(unittest.TestCase):

    def setUp(self):
        self.app = _make_app()
        self.client = self.app.test_client()
        # Azure credentials must look present so api_chat doesn't 503 out.
        self._env_patch = patch.dict(os.environ, {
            'AZURE_OPENAI_KEY': 'test-key',
            'AZURE_OPENAI_ENDPOINT': 'https://test.openai.azure.com',
            'AZURE_OPENAI_DEPLOYMENT': 'gpt-4o',
        })
        self._env_patch.start()
        # data_loader.get_context_for_chat is imported lazily inside api_chat;
        # patch it at the module level so we don't need real program data.
        self._data_patch = patch('data_loader.get_context_for_chat',
                                 return_value=[])
        self._data_patch.start()

    def tearDown(self):
        self._data_patch.stop()
        self._env_patch.stop()

    def _post_chat(self, payload):
        return self.client.post('/api/chat',
                                data=json.dumps(payload),
                                content_type='application/json')

    def test_phone_violation_triggers_repair_call_with_augmented_prompt(self):
        """First reply violates → second call gets repair-augmented system prompt."""
        violating = "Call 211 today for food assistance."
        clean = "You can apply online at fns.usda.gov/snap or visit any SNAP office."
        responses = [violating, clean]

        with patch.object(routes_v2, '_call_model_with_system_prompt',
                          side_effect=responses) as mock_call:
            resp = self._post_chat({
                'message': 'I need food help',
                'session': {'barriers': ['phone'], 'goal': 'benefits'},
                'history': [],
            })

        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body['reply'], clean)

        # Exactly two model calls: original + repair.
        self.assertEqual(mock_call.call_count, 2)

        first_system_prompt = mock_call.call_args_list[0][0][0]
        second_system_prompt = mock_call.call_args_list[1][0][0]

        # First call: vanilla system prompt, no enforcement marker.
        self.assertNotIn('ENFORCEMENT NOTE', first_system_prompt)

        # Second call: vanilla prompt PLUS repair guidance.
        self.assertTrue(second_system_prompt.startswith(first_system_prompt))
        self.assertIn('--- ENFORCEMENT NOTE ---', second_system_prompt)
        self.assertIn('Phone is named as a barrier', second_system_prompt)
        self.assertIn('Rewrite your previous response', second_system_prompt)

    def test_clean_first_reply_skips_repair_call(self):
        """No violation → exactly one model call, no repair pass."""
        clean = "You can apply online at fns.usda.gov/snap."
        with patch.object(routes_v2, '_call_model_with_system_prompt',
                          side_effect=[clean]) as mock_call:
            resp = self._post_chat({
                'message': 'I need food help',
                'session': {'barriers': ['phone']},
                'history': [],
            })

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['reply'], clean)
        self.assertEqual(mock_call.call_count, 1)

    def test_second_violation_appends_fallback_disclaimer(self):
        """Both passes violate → ship reply + disclaimer naming the barriers."""
        still_violating = "Call 211 right now."
        responses = ["Call 211 today.", still_violating]

        with patch.object(routes_v2, '_call_model_with_system_prompt',
                          side_effect=responses) as mock_call:
            resp = self._post_chat({
                'message': 'I need food help',
                'session': {'barriers': ['phone']},
                'history': [],
            })

        self.assertEqual(resp.status_code, 200)
        # Capped at two calls — no infinite loop.
        self.assertEqual(mock_call.call_count, 2)
        reply = resp.get_json()['reply']
        self.assertTrue(reply.startswith(still_violating))
        self.assertIn('based on your stated barriers (phone)', reply)
        self.assertIn("help me find another way", reply)

    def test_no_barriers_session_skips_validation(self):
        """Session without barriers → validator no-ops, single model call."""
        # Text that WOULD violate if 'phone' were active.
        reply_text = "Call 1-800-772-1213 for SSA."
        with patch.object(routes_v2, '_call_model_with_system_prompt',
                          side_effect=[reply_text]) as mock_call:
            resp = self._post_chat({
                'message': 'I need SSA help',
                'session': {},
                'history': [],
            })

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['reply'], reply_text)
        self.assertEqual(mock_call.call_count, 1)


if __name__ == '__main__':
    unittest.main()
