import os, sqlite3, tempfile, unittest, time
from apaa_execution import ExecutionEngine, StateStore, Task, TaskStatus

class DurableQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=os.path.join(self.tmp.name,"queue.sqlite")
        self.store=StateStore(self.db);self.engine=ExecutionEngine(self.store,worker_id="worker-A",lease_seconds=10)
        self.engine.register("echo",lambda p:{"echo":p["value"]})
        self.engine.set_policy("echo","v1",True)
    def tearDown(self):self.store.close();self.tmp.cleanup()
    def task(self,**kw):return Task.create("echo",{"value":"ok"},permission_granted=True,user_consented=True,**kw)
    def test_success_and_persisted_audit(self):
        t=self.task();self.engine.submit(t);self.engine.run_next()
        self.assertEqual(self.store.get(t.task_id)["status"],"succeeded")
        self.assertTrue(self.store.verify_audit_chain())
    def test_duplicate_idempotency_key_returns_original(self):
        a=self.task(idempotency_key="same-request");b=self.task(idempotency_key="same-request")
        self.assertEqual(self.engine.submit(a),self.engine.submit(b))
    def test_restart_recovers_expired_running_task(self):
        t=self.task();self.engine.submit(t);row=self.store.claim_next("dead-worker",1)
        self.assertEqual(self.store.recover_expired(now=row["lease_expires_at"]+1),1)
        self.assertEqual(self.store.get(t.task_id)["status"],"queued")
        self.engine.run_next();self.assertEqual(self.store.get(t.task_id)["status"],"succeeded")
    def test_retry_exhaustion_moves_to_dead_letter(self):
        self.engine.register("flaky",lambda p:(_ for _ in ()).throw(ValueError("no")))
        self.engine.set_policy("flaky","v1",True)
        t=Task.create("flaky",{},permission_granted=True,user_consented=True,max_attempts=2)
        self.engine.submit(t);self.engine.run_next();self.assertEqual(self.store.get(t.task_id)["status"],"queued")
        self.engine.run_next();self.assertEqual(self.store.get(t.task_id)["status"],"dead_letter")
        self.assertEqual(len(self.store.dead_letters()),1)
    def test_expired_lease_at_limit_moves_to_dead_letter(self):
        t=self.task(max_attempts=1);self.engine.submit(t);row=self.store.claim_next("lost",1)
        self.store.recover_expired(now=row["lease_expires_at"]+1)
        self.assertEqual(self.store.get(t.task_id)["status"],"dead_letter")
        self.assertEqual(len(self.store.dead_letters()),1)
    def test_worker_cannot_finish_another_workers_lease(self):
        t=self.task();self.engine.submit(t);self.store.claim_next("owner",30)
        with self.assertRaises(RuntimeError):self.store.finish(t.task_id,"intruder",TaskStatus.SUCCEEDED)
    def test_concurrent_claims_only_one_gets_task(self):
        t=self.task();self.engine.submit(t)
        self.assertEqual(self.store.claim_next("one",30)["task_id"],t.task_id)
        self.assertIsNone(self.store.claim_next("two",30))
    def test_missing_consent_blocks(self):
        t=Task.create("echo",{"value":"x"},permission_granted=True);self.engine.submit(t);self.engine.run_next()
        self.assertEqual(self.store.get(t.task_id)["status"],"blocked")
    def test_fifo_order(self):
        seen=[];self.engine.register("record",lambda p:seen.append(p["n"]))
        self.engine.set_policy("record","v1",True)
        ts=[Task.create("record",{"n":n},permission_granted=True,user_consented=True) for n in range(3)]
        for t in ts:self.engine.submit(t)
        self.engine.run_all();self.assertEqual(seen,[0,1,2])
    def test_cancel_queued_task(self):
        t=self.task();self.engine.submit(t);self.assertTrue(self.engine.cancel(t.task_id,"user requested"))
        self.assertEqual(self.store.get(t.task_id)["status"],"cancelled")
        self.assertIsNone(self.store.claim_next("worker-B",5))
    def test_running_task_cannot_be_force_cancelled(self):
        t=self.task();self.engine.submit(t);self.store.claim_next("worker-A",20)
        self.assertFalse(self.engine.cancel(t.task_id))
    def test_audit_tampering_is_detected(self):
        t=self.task();self.engine.submit(t)
        with self.store._db:self.store._db.execute("UPDATE audit_events SET detail='forged' WHERE task_id=?",(t.task_id,))
        self.assertFalse(self.store.verify_audit_chain())
    def test_audit_deletion_is_detected_by_chain_link(self):
        t=self.task();self.engine.submit(t);self.engine.run_next()
        with self.store._db:self.store._db.execute("DELETE FROM audit_events WHERE event_id=(SELECT MIN(event_id) FROM audit_events)")
        self.assertFalse(self.store.verify_audit_chain())
    def test_invalid_attempt_limit_rejected(self):
        with self.assertRaises(ValueError):Task.create("x",{},max_attempts=0)

    def test_missing_policy_blocks_handler(self):
        called=[]
        self.engine.register("unapproved",lambda p:called.append(True))
        t=Task.create("unapproved",{},permission_granted=True,user_consented=True)
        self.engine.submit(t);self.engine.run_next()
        self.assertEqual(self.store.get(t.task_id)["status"],"blocked")
        self.assertEqual(called,[])
    def test_policy_revoked_before_execution_blocks(self):
        called=[]
        self.engine.register("echo2",lambda p:called.append(True))
        self.engine.set_policy("echo2","v1",True)
        t=Task.create("echo2",{},permission_granted=True,user_consented=True)
        self.engine.submit(t);self.engine.set_policy("echo2","v1",False);self.engine.run_next()
        self.assertEqual(self.store.get(t.task_id)["status"],"blocked")
        self.assertEqual(called,[])
    def test_consent_revoked_before_execution_blocks(self):
        called=[]
        self.engine.register("echo3",lambda p:called.append(True))
        self.engine.set_policy("echo3","v1",True)
        t=Task.create("echo3",{},permission_granted=True,user_consented=True)
        self.engine.submit(t);self.engine.revoke_consent(t.task_id);self.engine.run_next()
        self.assertEqual(self.store.get(t.task_id)["status"],"blocked")
        self.assertEqual(called,[])
    def test_expired_consent_blocks_execution(self):
        called=[]
        self.engine.register("echo4",lambda p:called.append(True))
        self.engine.set_policy("echo4","v1",True)
        t=Task.create("echo4",{},permission_granted=True,user_consented=True)
        self.engine.submit(t)
        self.engine.consent_registry.grant(t.task_id,t.action,expires_at=time.time()-1)
        self.engine.run_next()
        self.assertEqual(self.store.get(t.task_id)["status"],"blocked")
        self.assertEqual(called,[])
    def test_payload_validation_happens_at_task_creation(self):
        with self.assertRaises(ValueError):Task.create("bad action",{},permission_granted=True,user_consented=True)
        with self.assertRaises(ValueError):Task.create("safe.action",{"n":float("nan")})

if __name__=="__main__":unittest.main()
