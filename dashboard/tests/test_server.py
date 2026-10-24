import importlib
import io
import json
import os
import tempfile
import unittest

class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        os.environ.update(DASHBOARD_DB=self.tmp.name+'/test.db',DASHBOARD_PASSWORD='test-password',INGEST_TOKEN='test-token',PAIRING_CODE='one-time',COOKIE_SECURE='0')
        import dashboard.server
        self.server=importlib.reload(dashboard.server)
    def tearDown(self):self.tmp.cleanup()
    def call(self,path,method='GET',data=None,token='',cookie='',origin=None):
        raw=json.dumps(data).encode() if data is not None else b''
        env={'PATH_INFO':path,'REQUEST_METHOD':method,'wsgi.input':io.BytesIO(raw),'CONTENT_LENGTH':str(len(raw)),'HTTP_AUTHORIZATION':'Bearer '+token,'HTTP_COOKIE':cookie,'HTTP_HOST':'127.0.0.1:8080','REMOTE_ADDR':'127.0.0.1'}
        if origin:env['HTTP_ORIGIN']=origin
        out={}
        def start(status,headers):out.update(status=status,headers=dict(headers))
        out['body']=b''.join(self.server.application(env,start));return out
    def run_record(self):return dict(id='unit-1',strategy='breakout',symbol='NQ',source='unit-test',worker='test',dataset='test-only',status='running',progress=30)
    def test_private_state_and_writer_auth(self):
        self.assertTrue(self.call('/api/state')['status'].startswith('401'))
        self.assertTrue(self.call('/api/runs','POST',self.run_record())['status'].startswith('401'))
        self.assertTrue(self.call('/api/runs','POST',self.run_record(),token='test-token')['status'].startswith('200'))
    def test_pair_once_and_use_worker_token(self):
        response=self.call('/api/pair','POST',{'code':'one-time'})
        token=json.loads(response['body'])['token']
        self.assertTrue(self.call('/api/pair','POST',{'code':'one-time'})['status'].startswith('409'))
        self.assertTrue(self.call('/api/heartbeat','POST',{'id':'test'},token=token)['status'].startswith('200'))
    def test_validation_and_terminal_run(self):
        r=self.run_record();r['metrics']={'net':float('nan')}
        self.assertTrue(self.call('/api/runs','POST',r,token='test-token')['status'].startswith('400'))
        r=self.run_record();r.update(status='completed',completed_at=10)
        self.call('/api/runs','POST',r,token='test-token')
        self.assertTrue(self.call('/api/runs','POST',self.run_record(),token='test-token')['status'].startswith('409'))
    def test_csrf_and_forged_session(self):
        self.assertTrue(self.call('/api/runs','POST',self.run_record(),token='test-token',origin='https://evil.example')['status'].startswith('403'))
        self.assertTrue(self.call('/api/state',cookie='qvsd_session=9999999999.fake')['status'].startswith('401'))
    def test_idempotent_upload_and_stale_worker(self):
        r=self.run_record()
        for _ in range(2):self.call('/api/runs','POST',r,token='test-token')
        self.call('/api/heartbeat','POST',{'id':'test'},token='test-token')
        with self.server.connect() as c:c.execute('UPDATE workers SET updated=0')
        result=self.call('/api/state',cookie='qvsd_session='+self.server.session_value())
        state=json.loads(result['body'])
        self.assertEqual(sum(x['id']=='unit-1' for x in state['runs']),1)
        self.assertFalse(state['workers'][0]['online'])
        self.assertEqual(len(state['events']),1)
    def test_persist_across_reload(self):
        self.call('/api/runs','POST',self.run_record(),token='test-token')
        self.server=importlib.reload(self.server)
        with self.server.connect() as c:self.assertIsNotNone(c.execute('SELECT 1 FROM runs WHERE id=?',('unit-1',)).fetchone())
if __name__=='__main__':unittest.main()
