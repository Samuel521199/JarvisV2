"""Counterexamples for the mutable-session audit, not product test replacement."""
from pathlib import Path
import copy,hashlib,tempfile,time,unittest,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from unittest.mock import patch
import compare_daily as audit


class SessionAudit(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.backup=self.base/'backup';(self.backup/'private').mkdir(parents=True)
        (self.backup/'private/workbench-sessions.dpapi').write_bytes(b'synthetic placeholder')
        (self.backup/'inventory.json').write_text('{}',encoding='utf-8')
        self.now=time.time();self.key='synthetic-owner-key-1234567890123456';binding=hashlib.sha256(self.key.encode()).hexdigest()
        self.old={'key_hash':binding,'sessions':{'old-valid':self.now+100,'old-expired':self.now-100}}
        self.good={'key_hash':binding,'sessions':{'old-valid':self.now+101,'new-audit-session':self.now+200}}
    def check(self,value):
        with patch.object(audit,'load_envelope',side_effect=[self.old,value]),patch.object(audit,'read_key',return_value=self.key):
            return audit.browser_sessions(self.base/'current',self.backup,1)
    def test_exact_new_session_and_existing_valid_are_accepted(self):self.assertTrue(self.check(self.good)['passed'])
    def test_removed_or_shortened_valid_session_is_rejected(self):
        for value in (None,self.now+50):
            candidate=copy.deepcopy(self.good)
            if value is None:candidate['sessions'].pop('old-valid')
            else:candidate['sessions']['old-valid']=value
            self.assertFalse(self.check(candidate)['passed'])
    def test_revived_expired_session_is_rejected(self):
        candidate=copy.deepcopy(self.good);candidate['sessions']['old-expired']=self.now+200
        self.assertFalse(self.check(candidate)['passed'])
    def test_changed_key_binding_is_rejected(self):
        candidate=copy.deepcopy(self.good);candidate['key_hash']='other-binding'
        self.assertFalse(self.check(candidate)['passed'])
    def test_additional_or_missing_new_session_is_rejected(self):
        for remove in (False,True):
            candidate=copy.deepcopy(self.good)
            if remove:candidate['sessions'].pop('new-audit-session')
            else:candidate['sessions']['unexpected-session']=self.now+200
            self.assertFalse(self.check(candidate)['passed'])
    def test_unbounded_expiry_is_rejected(self):
        candidate=copy.deepcopy(self.good);candidate['sessions']['new-audit-session']=self.now+audit.SESSION_SECONDS+1000
        self.assertFalse(self.check(candidate)['passed'])


if __name__=='__main__':unittest.main()
