import os, sqlite3, tempfile, unittest, time
from apaa_security import validate_task_input, PolicyRegistry, ConsentRegistry, SignedBackup

class ValidationTests(unittest.TestCase):
    def test_valid_payload_is_detached(self):
        p={"a":[1,{"b":"ok"}]};q=validate_task_input("docs.create",p);q["a"].append(2)
        self.assertEqual(len(p["a"]),2)
    def test_rejects_action_injection_characters(self):
        for a in ("Docs.create","docs create","docs;delete","../admin"):
            with self.assertRaises(ValueError):validate_task_input(a,{})
    def test_rejects_non_json_and_nan(self):
        for p in ({"x":object()},{"x":float("nan")},{"x":float("inf")}):
            with self.assertRaises(ValueError):validate_task_input("safe.action",p)
    def test_rejects_oversized_payload(self):
        with self.assertRaises(ValueError):validate_task_input("safe.action",{"x":"a"*70000})
    def test_rejects_excessive_nesting(self):
        value={}
        for _ in range(14):value={"x":value}
        with self.assertRaises(ValueError):validate_task_input("safe.action",value)

class PolicyConsentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.policy=PolicyRegistry(os.path.join(self.tmp.name,"policy.db"))
        self.consent=ConsentRegistry(os.path.join(self.tmp.name,"consent.db"))
    def tearDown(self):self.policy.close();self.consent.close();self.tmp.cleanup()
    def test_missing_policy_denies(self):self.assertFalse(self.policy.allows("docs.read","v1"))
    def test_versioned_policy_allows_exact_version_only(self):
        self.policy.set_policy("docs.read","v2",True)
        self.assertTrue(self.policy.allows("docs.read","v2"))
        self.assertFalse(self.policy.allows("docs.read","v1"))
    def test_policy_can_be_revoked(self):
        self.policy.set_policy("docs.read","v1",True);self.policy.set_policy("docs.read","v1",False)
        self.assertFalse(self.policy.allows("docs.read","v1"))
    def test_consent_grant_and_scope(self):
        self.consent.grant("t1","docs.read")
        self.assertTrue(self.consent.is_valid("t1","docs.read"))
        self.assertFalse(self.consent.is_valid("t1","docs.delete"))
    def test_consent_expiry(self):
        self.consent.grant("t1","docs.read",expires_at=110,now=100)
        self.assertTrue(self.consent.is_valid("t1","docs.read",now=109))
        self.assertFalse(self.consent.is_valid("t1","docs.read",now=110))
    def test_consent_revocation_is_immediate(self):
        self.consent.grant("t1","docs.read")
        self.assertTrue(self.consent.revoke("t1"))
        self.assertFalse(self.consent.is_valid("t1","docs.read"))
        self.assertFalse(self.consent.revoke("t1"))
    def test_expired_grant_rejected(self):
        with self.assertRaises(ValueError):self.consent.grant("t1","x",expires_at=1,now=2)

class BackupRestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=self.tmp.name
        self.source=os.path.join(self.root,"source.db");self.backup=os.path.join(self.root,"backup.db")
        self.target=os.path.join(self.root,"restored.db");self.key=b"K"*32
        with sqlite3.connect(self.source) as db:
            db.execute("CREATE TABLE records(value TEXT)")
            db.execute("INSERT INTO records VALUES('checkpoint-A')")
    def tearDown(self):self.tmp.cleanup()
    def test_signed_backup_and_restore(self):
        sig=SignedBackup.create(self.source,self.backup,self.key)
        self.assertEqual(len(sig),64);SignedBackup.restore(self.backup,self.target,self.key)
        with sqlite3.connect(self.target) as db:
            self.assertEqual(db.execute("SELECT value FROM records").fetchone()[0],"checkpoint-A")
    def test_wrong_key_rejected(self):
        SignedBackup.create(self.source,self.backup,self.key)
        with self.assertRaises(ValueError):SignedBackup.restore(self.backup,self.target,b"Z"*32)
    def test_tampered_backup_rejected(self):
        SignedBackup.create(self.source,self.backup,self.key)
        with open(self.backup,"ab") as f:f.write(b"tamper")
        with self.assertRaises(ValueError):SignedBackup.restore(self.backup,self.target,self.key)
    def test_missing_signature_rejected(self):
        SignedBackup.create(self.source,self.backup,self.key)
        os.unlink(self.backup+".sig")
        with self.assertRaises(FileNotFoundError):SignedBackup.restore(self.backup,self.target,self.key)
    def test_short_signing_key_rejected(self):
        with self.assertRaises(ValueError):SignedBackup.create(self.source,self.backup,b"short")
    def test_source_not_modified_by_backup(self):
        before=open(self.source,"rb").read()
        SignedBackup.create(self.source,self.backup,self.key)
        self.assertEqual(open(self.source,"rb").read(),before)

if __name__=="__main__":unittest.main()
