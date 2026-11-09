"""Synthetic human fixtures exercise interactive approval transaction boundaries."""
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import hook_demo
from judgment_layer.store import Store

class ReviewFlowTests(unittest.TestCase):
    def test_approve_and_bind_roll_back_together_on_binding_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'fixture';item=hook_demo.setup(root)
            with patch.object(sys,'argv',['hook-demo','review','--root',str(root)]), patch('builtins.input',return_value='a'), patch('hook_demo.bind',side_effect=ValueError('Synthetic binding failure')), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(ValueError):hook_demo.main()
            s=Store(root/'.judgment')
            try:
                self.assertEqual(s.state(s.record(item['id'])),'proposed')
                self.assertEqual([e['kind'] for e in s.events()],['captured'])
            finally:s.close()

    def test_edit_creates_candidate_and_returns_to_combined_review(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'fixture'
            hook_demo.setup(root)
            answers=iter(['e','','Clarified synthetic reason','','a'])
            with patch.object(sys,'argv',['hook-demo','review','--root',str(root)]),patch('builtins.input',side_effect=lambda _:next(answers)),contextlib.redirect_stdout(io.StringIO()) as out:
                hook_demo.main()
            self.assertIn('Proposed',out.getvalue().title())
            s=Store(root/'.judgment')
            try:
                rows=list(s.db.execute('select id,version from revisions order by version'))
                self.assertEqual([s.state(s.record(x[0],x[1])) for x in rows],['superseded','admitted'])
                bindings=[e for e in s.events() if e['kind']=='runtime_bound']
                self.assertEqual(bindings[-1]['version'],2)
            finally:s.close()
