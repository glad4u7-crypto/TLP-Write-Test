import os, tempfile, threading, unittest
from apaa_execution import ExecutionEngine, StateStore, Task, TaskStatus

class DurableQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.db=os.path.join(self.tmp.name,"queue.sqlite")
        self.store=StateStore(self.db); self.engine=ExecutionEngine(self.store,worker_id="worker-A",lease_seconds=10)
        self.engine.register("echo",lambda p:{"echo":p["value"]})
    def tearDown(self): self.store.close(); self.tmp.cleanup()
    def task(self,**kw):
        return Task.create("echo",{"value":"ok"},permission_granted=True,user_consented=True,**kw)
    def test_success_and_persisted_audit(self):
        t=self.task(); self.engine.submit(t); self.engine.run_next()
        self.assertEqual(self.store.get(t.task_id)["status"],"succeeded")
        self.assertIn("lease_claimed",[x["event"] for x in self.store.audit(t.task_id)])
    def test_duplicate_idempotency_key_returns_original(self):
        a=self.task(idempotency_key="same-request"); b=self.task(idempotency_key="same-request")
        self.assertEqual(self.engine.submit(a),self.engine.submit(b))
        self.assertEqual(len(self.store.audit(a.task_id)),2)
    def test_restart_recovers_expired_running_task(self):
        t=self.task(); self.engine.submit(t)
        row=self.store.claim_next("dead-worker",1)
        self.assertEqual(row["status"],"running")
        self.assertEqual(self.store.recover_expired(now=row["lease_expires_at"]+1),1)
        self.assertEqual(self.store.get(t.task_id)["status"],"queued")
        self.engine.run_next(); self.assertEqual(self.store.get(t.task_id)["status"],"succeeded")
    def test_retry_is_bounded(self):
        calls=[]
        self.engine.register("flaky",lambda p: calls.append(1) or (_ for _ in ()).throw(ValueError("no")))
        t=Task.create("flaky",{},permission_granted=True,user_consented=True,max_attempts=2)
        self.engine.submit(t); self.engine.run_next()
        self.assertEqual(self.store.get(t.task_id)["status"],"queued")
        self.engine.run_next()
        row=self.store.get(t.task_id)
        self.assertEqual(row["status"],"failed"); self.assertEqual(row["attempts"],2)
    def test_expired_lease_at_retry_limit_fails(self):
        t=self.task(max_attempts=1); self.engine.submit(t)
        row=self.store.claim_next("lost-worker",1)
        self.store.recover_expired(now=row["lease_expires_at"]+1)
        self.assertEqual(self.store.get(t.task_id)["status"],"failed")
    def test_worker_cannot_finish_another_workers_lease(self):
        t=self.task(); self.engine.submit(t); self.store.claim_next("owner",30)
        with self.assertRaises(RuntimeError):
            self.store.finish(t.task_id,"intruder",TaskStatus.SUCCEEDED,result="forged")
    def test_concurrent_claims_only_one_gets_task(self):
        t=self.task(); self.engine.submit(t)
        one=self.store.claim_next("one",30); two=self.store.claim_next("two",30)
        self.assertEqual(one["task_id"],t.task_id); self.assertIsNone(two)
    def test_missing_consent_blocks(self):
        t=Task.create("echo",{"value":"x"},permission_granted=True)
        self.engine.submit(t); self.engine.run_next()
        self.assertEqual(self.store.get(t.task_id)["status"],"blocked")
    def test_fifo_order(self):
        seen=[]; self.engine.register("record",lambda p:seen.append(p["n"]))
        ts=[Task.create("record",{"n":n},permission_granted=True,user_consented=True) for n in range(3)]
        for t in ts:self.engine.submit(t)
        self.engine.run_all(); self.assertEqual(seen,[0,1,2])

if __name__=="__main__":unittest.main()
