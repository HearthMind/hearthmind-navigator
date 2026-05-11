"""
Tests for /api/clients endpoints + the underlying SQLite layer.

Run from repo root:
    python3 -m unittest tests.test_clients_api
"""

import os
import sys
import json
import tempfile
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, '..', 'src'))

from flask import Flask
import clients_db
import routes_v2


def _make_app(db_path):
    app = Flask(__name__)
    app.config['CLIENTS_DB_PATH'] = db_path
    app.register_blueprint(routes_v2.bp)
    return app


class ClientsApiTests(unittest.TestCase):

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(prefix='nav_test_', suffix='.db')
        os.close(fd)
        os.unlink(self.db_path)  # let init_db create it cleanly
        self.app = _make_app(self.db_path)
        self.client = self.app.test_client()

    def tearDown(self):
        try:
            if os.path.exists(self.db_path):
                os.unlink(self.db_path)
        except OSError:
            pass

    # ---- helpers ----

    def _post(self, path, payload):
        return self.client.post(path, data=json.dumps(payload),
                                content_type='application/json')

    def _put(self, path, payload):
        return self.client.put(path, data=json.dumps(payload),
                               content_type='application/json')

    # ---- tests ----

    def test_create_client_minimal(self):
        r = self._post('/api/clients', {
            'caseworker_id': 'cw-abc-123',
            'name': 'Sarah W.'
        })
        self.assertEqual(r.status_code, 201)
        data = r.get_json()
        self.assertTrue(data['id'].startswith('CL-'))
        self.assertEqual(len(data['id']), 9)  # "CL-" + 6 hex
        self.assertEqual(data['caseworker_id'], 'cw-abc-123')
        self.assertEqual(data['name'], 'Sarah W.')
        self.assertIsNone(data['state'])
        self.assertIsNone(data['intake'])
        self.assertIsNone(data['plan'])
        self.assertIsNone(data['archived_at'])
        self.assertTrue(data['created_at'])
        self.assertTrue(data['updated_at'])

    def test_create_client_full(self):
        intake = {'goal': 'benefits', 'barriers': ['phone'], 'urgency': 'today',
                  'style': 'gentle', 'state': 'Washington', 'name': 'Sarah'}
        plan = {'action_card': {'text': 'Call 211'}, 'next_steps': [],
                'programs_snapshot': [], 'generated_at': '2026-05-11T00:00:00Z'}
        r = self._post('/api/clients', {
            'caseworker_id': 'cw-1',
            'name': 'Sarah W.',
            'state': 'Washington',
            'intake': intake,
            'plan': plan
        })
        self.assertEqual(r.status_code, 201)
        created = r.get_json()
        # Round-trip via GET
        r2 = self.client.get('/api/clients/' + created['id'])
        self.assertEqual(r2.status_code, 200)
        fetched = r2.get_json()
        self.assertEqual(fetched['state'], 'Washington')
        self.assertEqual(fetched['intake'], intake)
        self.assertEqual(fetched['plan'], plan)

    def test_list_clients_filters_by_caseworker(self):
        self._post('/api/clients', {'caseworker_id': 'cw-A', 'name': 'Alice'})
        self._post('/api/clients', {'caseworker_id': 'cw-A', 'name': 'Adam'})
        self._post('/api/clients', {'caseworker_id': 'cw-B', 'name': 'Bea'})

        r_a = self.client.get('/api/clients?caseworker_id=cw-A')
        self.assertEqual(r_a.status_code, 200)
        names_a = sorted(c['name'] for c in r_a.get_json()['clients'])
        self.assertEqual(names_a, ['Adam', 'Alice'])

        r_b = self.client.get('/api/clients?caseworker_id=cw-B')
        names_b = [c['name'] for c in r_b.get_json()['clients']]
        self.assertEqual(names_b, ['Bea'])

    def test_list_clients_excludes_archived_by_default(self):
        a = self._post('/api/clients', {'caseworker_id': 'cw-X', 'name': 'Active 1'}).get_json()
        b = self._post('/api/clients', {'caseworker_id': 'cw-X', 'name': 'Archived 1'}).get_json()
        self.client.post('/api/clients/' + b['id'] + '/archive')

        r = self.client.get('/api/clients?caseworker_id=cw-X')
        names = [c['name'] for c in r.get_json()['clients']]
        self.assertEqual(names, ['Active 1'])

        r_all = self.client.get('/api/clients?caseworker_id=cw-X&include_archived=true')
        names_all = sorted(c['name'] for c in r_all.get_json()['clients'])
        self.assertEqual(names_all, ['Active 1', 'Archived 1'])

    def test_update_client_partial(self):
        intake = {'goal': 'benefits', 'barriers': [], 'urgency': 'week',
                  'style': 'direct', 'state': 'Oregon', 'name': 'Original'}
        created = self._post('/api/clients', {
            'caseworker_id': 'cw-U', 'name': 'Original', 'state': 'Oregon', 'intake': intake
        }).get_json()
        original_updated_at = created['updated_at']

        # Sleep a hair so updated_at can actually change (sqlite datetime is 1-sec).
        import time; time.sleep(1.05)

        new_plan = {'action_card': None, 'next_steps': [{'t': 'do thing', 's': ''}],
                    'programs_snapshot': [], 'generated_at': '2026-05-11T12:00:00Z'}
        r = self._put('/api/clients/' + created['id'], {'plan': new_plan})
        self.assertEqual(r.status_code, 200)
        updated = r.get_json()

        # Unchanged fields preserved
        self.assertEqual(updated['name'], 'Original')
        self.assertEqual(updated['state'], 'Oregon')
        self.assertEqual(updated['intake'], intake)
        # Plan changed
        self.assertEqual(updated['plan'], new_plan)
        # updated_at bumped
        self.assertNotEqual(updated['updated_at'], original_updated_at)

    def test_get_nonexistent_client_returns_404(self):
        r = self.client.get('/api/clients/CL-NOPE99')
        self.assertEqual(r.status_code, 404)
        self.assertIn('error', r.get_json())

    def test_archive_and_unarchive_roundtrip(self):
        c = self._post('/api/clients', {'caseworker_id': 'cw-Z', 'name': 'Z'}).get_json()
        self.assertIsNone(c['archived_at'])

        r_arc = self.client.post('/api/clients/' + c['id'] + '/archive')
        self.assertEqual(r_arc.status_code, 200)
        self.assertIsNotNone(r_arc.get_json()['archived_at'])

        r_un = self.client.post('/api/clients/' + c['id'] + '/unarchive')
        self.assertEqual(r_un.status_code, 200)
        self.assertIsNone(r_un.get_json()['archived_at'])

        r_arc_missing = self.client.post('/api/clients/CL-MISSING/archive')
        self.assertEqual(r_arc_missing.status_code, 404)
        r_un_missing = self.client.post('/api/clients/CL-MISSING/unarchive')
        self.assertEqual(r_un_missing.status_code, 404)

    def test_validation_rejects_missing_caseworker_id(self):
        r = self._post('/api/clients', {'name': 'No CW'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('caseworker_id', r.get_json()['error'])

        r_blank = self._post('/api/clients', {'caseworker_id': '   ', 'name': 'Sarah'})
        self.assertEqual(r_blank.status_code, 400)

        r_list = self.client.get('/api/clients')
        self.assertEqual(r_list.status_code, 400)

    def test_validation_rejects_missing_name(self):
        r = self._post('/api/clients', {'caseworker_id': 'cw-1'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('name', r.get_json()['error'])

        r_blank = self._post('/api/clients', {'caseworker_id': 'cw-1', 'name': '   '})
        self.assertEqual(r_blank.status_code, 400)

    def test_validation_rejects_non_object_intake(self):
        r = self._post('/api/clients', {
            'caseworker_id': 'cw-1', 'name': 'Sarah', 'intake': 'not-a-dict'
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn('intake', r.get_json()['error'])


if __name__ == '__main__':
    unittest.main()
