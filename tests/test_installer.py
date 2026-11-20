import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'install.sh'


class InstallerTests(unittest.TestCase):
    def test_piped_install_defaults_and_setup_failure_paths(self):
        for failure in ('none', 'existing', 'git', 'uv'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                if failure == 'existing':
                    (root / '.judgment').mkdir()
                tools = root / 'tools'
                tools.mkdir()
                log = root / 'log'
                program = '''import json,os,sys
from pathlib import Path
name=Path(sys.argv[0]).name
with open(os.environ['INSTALL_LOG'],'a') as out: out.write(json.dumps([name,*sys.argv[1:]])+'\\n')
if name==os.environ['FAIL_STAGE']: sys.exit(1)
if name=='uv' and sys.argv[1:]==['tool','dir','--bin']: print(os.environ['TEST_BIN'])
'''
                for name in ('git', 'uv', 'proofpress'):
                    path = tools / name
                    path.write_text('#!' + sys.executable + '\n' + program)
                    path.chmod(0o755)
                env = {**os.environ, 'PATH': str(tools)+os.pathsep+os.environ['PATH'],
                       'INSTALL_LOG': str(log), 'FAIL_STAGE': failure, 'TEST_BIN': str(tools)}
                result = subprocess.run(['/bin/bash'], input=SCRIPT.read_text(), cwd=root,
                                        env=env, text=True, capture_output=True)
                calls = [json.loads(x) for x in log.read_text().splitlines()]
                if failure in ('none', 'existing'):
                    self.assertEqual(result.returncode, 0, result.stderr)
                    setup = next(x for x in calls if x[0] == 'proofpress')
                    if failure == 'existing':
                        self.assertEqual(setup[1:], ['onboard', '--startup', '--confirm', '--upgrade'])
                    else:
                        self.assertEqual(setup[1:], ['onboard', '--startup', '--confirm'])
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(any(x[0] == 'proofpress' for x in calls))
                    if failure == 'git':
                        self.assertFalse(any(x[0] == 'uv' for x in calls))
