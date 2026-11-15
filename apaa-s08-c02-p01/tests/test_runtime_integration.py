import os, tempfile, threading, time, unittest
from apaa_execution import ExecutionEngine, StateStore, Task

class RuntimeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=os.path.join(self.tmp.name,"shared.sqlite")
        self.store=StateStore(self.path)
    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()
    def test_independent_runtime_stores_claim_only_once(self):
        task=Task.create("read.safe",{},permission_granted=True,user_consented=True)
        self.store.add(task)
        second=StateStore(self.path)
        barrier=threading.Barrier(2);results=[];errors=[]
        def claim(store,worker):
            try:
                barrier.wait()
                results.append(store.claim_next(worker,20))
            except Exception as exc:errors.append(exc)
        a=threading.Thread(target=claim,args=(self.store,"worker-A"))
        b=threading.Thread(target=claim,args=(second,"worker-B"))
        a.start();b.start();a.join(5);b.join(5)
        self.assertFalse(errors)
        self.assertEqual(sum(x is not None for x in results),1)
        row=self.store.get(task.task_id)
        self.assertEqual(row["status"],"running")
        self.assertEqual(row["attempts"],1)
        second.close()
    def test_runtime_recovery_then_authorized_execution(self):
        engine=ExecutionEngine(self.store,worker_id="worker-final")
        engine.set_policy("read.safe","v1",True)
        called=[]
        engine.register("read.safe",lambda p:called.append("ran") or {"ok":True})
        task=Task.create("read.safe",{},permission_granted=True,user_consented=True)
        engine.submit(task)
        claimed=self.store.claim_next("crashed-worker",1)
        self.assertEqual(claimed["status"],"running")
        self.assertEqual(self.store.recover_expired(claimed["lease_expires_at"]+1),1)
        engine.run_next()
        self.assertEqual(called,["ran"])
        self.assertEqual(self.store.get(task.task_id)["status"],"succeeded")
        self.assertTrue(self.store.verify_audit_chain())
    def test_policy_revocation_blocks_after_queueing(self):
        engine=ExecutionEngine(self.store)
        calls=[]
        engine.register("sensitive.read",lambda p:calls.append(1))
        engine.set_policy("sensitive.read","v1",True)
        task=Task.create("sensitive.read",{},permission_granted=True,user_consented=True)
        engine.submit(task)
        engine.set_policy("sensitive.read","v1",False)
        engine.run_next()
        self.assertEqual(calls,[])
        self.assertEqual(self.store.get(task.task_id)["status"],"blocked")
    def test_expired_consent_blocks_before_side_effect(self):
        engine=ExecutionEngine(self.store)
        calls=[]
        engine.register("read.expired",lambda p:calls.append(1))
        engine.set_policy("read.expired","v1",True)
        task=Task.create("read.expired",{},permission_granted=True,user_consented=True)
        engine.submit(task)
        engine.consent_registry.grant(task.task_id,task.action,expires_at=time.time()-1,now=time.time()-2)
        engine.run_next()
        self.assertEqual(calls,[])
        self.assertEqual(self.store.get(task.task_id)["status"],"blocked")
    def test_failure_injection_dead_letters_after_retry_limit(self):
        engine=ExecutionEngine(self.store)
        engine.register("unstable",lambda p:(_ for _ in ()).throw(OSError("injected")))
        engine.set_policy("unstable","v1",True)
        task=Task.create("unstable",{},permission_granted=True,user_consented=True,max_attempts=2)
        engine.submit(task);engine.run_next();engine.run_next()
        self.assertEqual(self.store.get(task.task_id)["status"],"dead_letter")
        self.assertEqual(len(self.store.dead_letters()),1)
    def test_audit_chain_covers_complete_runtime_lifecycle(self):
        engine=ExecutionEngine(self.store)
        engine.register("audit.read",lambda p:{"ok":True})
        engine.set_policy("audit.read","v1",True)
        task=Task.create("audit.read",{},permission_granted=True,user_consented=True)
        engine.submit(task);engine.run_next()
        events=[r["event"] for r in self.store.audit(task.task_id)]
        self.assertIn("queued",events);self.assertIn("running",events);self.assertIn("succeeded",events)
        self.assertTrue(self.store.verify_audit_chain())

if __name__=="__main__":unittest.main()
