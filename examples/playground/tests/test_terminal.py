import contextlib
import io
import json
import os
import unittest
from unittest.mock import patch
from terminal import color, display

class TTY(io.StringIO):
    def isatty(self): return True

class TerminalTests(unittest.TestCase):
    def test_bold_colors_ignore_theme_and_respect_no_color(self):
        with contextlib.redirect_stdout(TTY()), patch.dict(os.environ, {}, clear=True):
            expected = '\x1b[1;38;2;95;179;196mx\x1b[0m'
            self.assertEqual(color('accent', 'x'), expected)
            for theme in ('light', 'dark'):
                os.environ['PROOFPRESS_THEME'] = theme
                os.environ['COLORFGBG'] = '0;15'
                self.assertEqual(color('accent', 'x'), expected)
            os.environ['NO_COLOR'] = '1'
            self.assertEqual(color('accent', 'x'), 'x')
    def test_pipes_stay_concise_unless_json_requested(self):
        result={'records':[], 'runs':[], 'events':['private verbose event']}
        with contextlib.redirect_stdout(io.StringIO()) as out:
            display('inspect',result)
        self.assertIn('0 judgment revisions',out.getvalue())
        self.assertNotIn('private verbose event',out.getvalue())
        self.assertNotIn('\x1b',out.getvalue())
        for stream in [io.StringIO(),TTY()]:
            with contextlib.redirect_stdout(stream):display('inspect',result,True)
            self.assertEqual(json.loads(stream.getvalue()),result)
            self.assertNotIn('\x1b',stream.getvalue())
    def test_review_never_truncates_conditions_or_statement(self):
        statement='Guidance '+('long ' * 100)
        record={'judgment':{'statement':statement,'kind':'conditional_guidance','rationale':'why'},
                'applicability':{'scope':'coding','when':[{'field':'internal','equals':False}], 'limits':['Do not publish']},
                'provenance':{'origin':'human_guidance','judged_by':'human:fixture','recorded_by':'agent:fixture',
                              'recorded_at':'2026-11-08T00:00:00Z','capture_method':'explicit','source_refs':['fixture://source']},
                'evidence':[],'links':[]}
        item={'state':'proposed','name':'example','version':1,'record':record}
        with contextlib.redirect_stdout(io.StringIO()) as out:display('review',item)
        self.assertIn(statement,out.getvalue())
        self.assertIn('internal = false',out.getvalue())
        self.assertIn('Do not publish',out.getvalue())
        self.assertIn('fixture://source',out.getvalue())

    def test_history_handles_native_null_payloads(self):
        session={'id':'legacy_id','metadata':{'description':'Coding task'},'events':[
            {'type':'decision','annotation':None,'decision':{'description':'Use hyphens'}},
            {'type':'annotation','decision':None,'annotation':{'category':'correction','content':'Use underscores'}}]}
        with contextlib.redirect_stdout(io.StringIO()) as out:display('history',[session])
        self.assertIn('Use underscores',out.getvalue())
        self.assertNotIn('Use hyphens',out.getvalue())
