import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import playground as app


class PlaygroundTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.previous=app.PROJECT
        app.PROJECT=Path(self.tmp.name)/'sandbox'
    def tearDown(self):
        app.PROJECT=self.previous
        self.tmp.cleanup()
    def test_fresh_install_is_empty_and_idempotent(self):
        self.assertFalse(app.state()['installed'])
        app.install()
        self.assertEqual(app.state()['records'],[])
        self.assertEqual(app.install()['created'],[])
    def test_synthetic_review_reuse_revision_and_withdrawal(self):
        app.install()
        a=app.capture('Synthetic fixture: retain Unicode in internal URLs.')
        def context(surface):
            with app.store() as s:return s.context(app.SCOPE,{'surface':surface},'agent:synthetic','Test fixture')
        self.assertEqual(context('internal')['judgments'],[])
        # Explicit synthetic Owner fixture in a temporary store; never a real approval.
        app.review({**a,'action':'admit','reason':'Synthetic review fixture'})
        packet=context('internal')
        self.assertEqual(len(packet['judgments']),1)
        self.assertEqual(context('public')['judgments'],[])
        b=app.capture('Synthetic revised fixture: retain all Unicode letters and digits.',True)
        self.assertEqual(context('internal')['judgments'][0]['version'],1)
        app.review({**b,'action':'admit','reason':'Synthetic review fixture'})
        with app.store() as s:
            self.assertFalse(s.check(packet['receipt']['receipt_id'],{'surface':'internal'})['ok'])
        app.review({**b,'action':'withdraw','reason':'Synthetic withdrawal fixture'})
        self.assertEqual(context('internal')['judgments'],[])
    def test_stale_review_digest_is_rejected(self):
        app.install();item=app.capture('Synthetic fixture')
        with self.assertRaises(ValueError):app.review({**item,'action':'admit','digest':'wrong'})
        self.assertEqual(app.state()['records'][0]['state'],'proposed')
    def test_local_http_rejects_forged_mutations_and_exposes_initial_state(self):
        previous=app.PORT
        server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        app.PORT=server.server_address[1]
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{app.PORT}'
        try:
            with urlopen(base+'/state') as r:self.assertFalse(json.load(r)['installed'])
            request=Request(base+'/install',data=b'{}',headers={'Content-Type':'application/json'},method='POST')
            with self.assertRaises(HTTPError) as e:urlopen(request)
            self.assertEqual(e.exception.code,403)
            self.assertFalse(app.PROJECT.exists())
            with urlopen(base) as r:self.assertIn(b'Capture for review',r.read())
        finally:
            server.shutdown();server.server_close();thread.join();app.PORT=previous
