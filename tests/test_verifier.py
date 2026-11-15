"""Offline regressions for the historical PoC's bounded local hash checks."""

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verifier = load_module('cloudflare_verifier', 'tools/vcp_verifier.py')
demo = load_module('cloudflare_demo', 'demo/run_demo.py')


class LocalChainTests(unittest.TestCase):
    def setUp(self):
        self.sample_bytes = (ROOT / 'demo/sample_events.jsonl').read_bytes()
        self.events = [json.loads(line) for line in self.sample_bytes.splitlines()
                       if line.strip()]

    def run_cli(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            path.write_bytes(data)
            result = subprocess.run([sys.executable, '-I', '-B',
                                     str(ROOT / 'tools/vcp_verifier.py'), str(path)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(path.read_bytes(), data)
            self.assertNotIn('Traceback', result.stderr)
            return result

    def check_api(self, events):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = verifier.verify_chain(events)
        return result, output.getvalue()

    def test_original_fixture_and_hash_bytes_are_preserved(self):
        self.assertEqual(hashlib.sha256(self.sample_bytes).hexdigest(),
                         '00ff0eedadf5109ba144e22c57c62f1ccce2325e1026dc4706e0b836ea937136')
        for event in self.events:
            self.assertEqual(verifier.compute_hash(event), event['security']['event_hash'])
        before = copy.deepcopy(self.events)
        self.assertTrue(self.check_api(self.events)[0])
        self.assertTrue(demo.verify_chain(self.events, show_details=False))
        self.assertEqual(self.events, before)

    def test_cli_match_is_explicitly_local(self):
        result = self.run_cli(self.sample_bytes)
        self.assertEqual(result.returncode, 0)
        self.assertIn('MATCH (local hash checks only)', result.stdout)
        self.assertIn('Not assessed: signatures, policy fields, anchors or history completeness.',
                      result.stdout)

    def test_empty_and_blank_files_are_unresolved(self):
        for data in (b'', b' \n\t\r\n'):
            with self.subTest(data=data):
                result = self.run_cli(data)
                self.assertEqual(result.returncode, 2)
                self.assertIn('INDETERMINATE', result.stdout)
                self.assertNotIn('VERIFIED', result.stdout)

    def test_empty_python_entrypoints_do_not_succeed(self):
        self.assertFalse(self.check_api([])[0])
        for details in (False, True):
            with self.subTest(details=details), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertFalse(demo.verify_chain([], show_details=details))
                self.assertNotIn('VERIFIED', out.getvalue())

    def test_duplicate_members_at_both_depths_are_rejected(self):
        first = json.dumps(self.events[0], separators=(',', ':'))
        duplicate_root = first.replace('"payload":', '"payload":{"discarded":true},"payload":', 1)
        duplicate_nested = first.replace('"event_type":', '"event_type":"DISCARDED","event_type":', 1)
        for text in (duplicate_root, duplicate_nested):
            with self.subTest(text=text):
                result = self.run_cli((text + '\n').encode())
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stderr, 'Invalid JSONL event input.\n')
                self.assertNotIn('MATCH', result.stdout)

    def test_nonfinite_and_overflow_numbers_are_rejected_even_outside_hash(self):
        first = json.dumps(self.events[0], separators=(',', ':'))
        for value in ('NaN', 'Infinity', '-Infinity', '1e999', '-1e999'):
            with self.subTest(value=value):
                text = first[:-1] + ',"unhashed_extra":' + value + '}\n'
                self.assertEqual(self.run_cli(text.encode()).returncode, 1)

    def test_python_nonfinite_input_is_rejected(self):
        for value in (float('nan'), float('inf'), float('-inf')):
            with self.subTest(value=value):
                events = copy.deepcopy(self.events)
                events[0]['unhashed_extra'] = value
                self.assertFalse(self.check_api(events)[0])

    def test_invalid_json_utf8_and_deep_nesting_fail_without_traceback(self):
        for data in (b'{', b'\xff\n'):
            with self.subTest(data=data[:8]):
                result = self.run_cli(data)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stderr, 'Invalid JSONL event input.\n')
        result = self.run_cli(b'[' * 10000 + b'0' + b']' * 10000)
        self.assertEqual(result.returncode, 1)
        # Python versions have different JSON nesting limits. If decoding
        # succeeds, this array still fails the event-object check. Both paths
        # must retain failure without a traceback or a successful local match.
        if result.stderr:
            self.assertEqual(result.stderr, 'Invalid JSONL event input.\n')
        else:
            self.assertIn('INVALID EVENT INPUT', result.stdout)
            self.assertIn('Chain Integrity: FAILED', result.stdout)
        self.assertNotIn('MATCH', result.stdout)

    def test_wrong_record_shapes_fail_without_traceback(self):
        malformed = [None, [], {}, {'header': []}]
        for field in ('header', 'payload', 'security'):
            event = copy.deepcopy(self.events[0])
            del event[field]
            malformed.append(event)
        for field, value in (('event_id', None), ('event_type', 5)):
            event = copy.deepcopy(self.events[0])
            event['header'][field] = value
            malformed.append(event)
        for event in malformed:
            with self.subTest(event=event):
                result = self.run_cli((json.dumps(event) + '\n').encode())
                self.assertEqual(result.returncode, 1)
                self.assertIn('INVALID EVENT INPUT', result.stdout)

    def test_invalid_stored_hashes_fail_without_traceback(self):
        for field in ('event_hash', 'prev_hash'):
            for value in (None, 0, [], '', '0' * 63, 'g' * 64):
                with self.subTest(field=field, value=value):
                    event = copy.deepcopy(self.events[0])
                    event['security'][field] = value
                    self.assertFalse(self.check_api([event])[0])

    def test_payload_tampering_and_link_mismatch_fail(self):
        for mutate in ('payload', 'link'):
            events = copy.deepcopy(self.events)
            if mutate == 'payload':
                events[0]['payload']['changed'] = True
            else:
                events[1]['security']['prev_hash'] = 'f' * 64
            result = self.run_cli(('\n'.join(json.dumps(e) for e in events) + '\n').encode())
            self.assertEqual(result.returncode, 1)
            self.assertIn('Chain Integrity: FAILED', result.stdout)

    def test_missing_file_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'missing.jsonl'
            result = subprocess.run([sys.executable, '-I', '-B',
                                     str(ROOT / 'tools/vcp_verifier.py'), str(path)],
                                    capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, 'Event input unavailable.\n')

    def test_valid_python_serialization_is_unchanged(self):
        event = copy.deepcopy(self.events[0])
        event['payload'] = {'z': 'é', '\U0001f600': -0.0, '\ue000': 1e20, 'finite': 1.25}
        original_bytes = json.dumps({'header': event['header'], 'payload': event['payload']},
                                    sort_keys=True, separators=(',', ':')).encode()
        self.assertEqual(verifier.compute_hash(event), hashlib.sha256(original_bytes).hexdigest())

    def test_coherent_rewrite_remains_only_a_local_match(self):
        # No trusted anchor exists in this format: rewriting all hashes can match.
        # This is an explicit limitation, not an authentication success.
        events = copy.deepcopy(self.events)
        previous = '0' * 64
        for event in events:
            event['payload']['rewritten'] = True
            event['security']['prev_hash'] = previous
            previous = verifier.compute_hash(event)
            event['security']['event_hash'] = previous
        result, output = self.check_api(events)
        self.assertTrue(result)
        self.assertIn('local hash checks only', output)
        self.assertIn('Not assessed:', output)


if __name__ == '__main__':
    unittest.main()
