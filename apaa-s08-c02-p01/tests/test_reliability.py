import os, sqlite3, tempfile, threading, time, unittest
from apaa_reliability import AtomicSQLiteClaimer, ExecutionBudget, validate_result_size

class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=os.path.join(self.tmp.name,"queue.db")
        with sqlite3.connect(self.db) as db:
            db.execute("""CREATE TABLE tasks(task_id TEXT PRIMARY KEY, action TEXT, payload TEXT,
              status TEXT, created_at REAL, updated_at REAL, attempts INTEGER DEFAULT 0,
              lease_owner TEXT, lease_expires_at REAL)""")
            db.execute("INSERT INTO tasks(task_id,action,payload,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                       ("task-1","demo","{}","queued",time.time(),time.time()))
    def tearDown(self): self.tmp.cleanup()
    def test_two_independent_workers_cannot_claim_same_task(self):
        claimers=[AtomicSQLiteClaimer(self.db),AtomicSQLiteClaimer(self.db)]
        barrier=threading.Barrier(2);results=[];errors=[]
        def run(i):
            try:
                barrier.wait()
                results.append(claimers[i].claim_next("worker-"+str(i),30))
            except Exception as exc:errors.append(exc)
        threads=[threading.Thread(target=run,args=(i,)) for i in range(2)]
        [t.start() for t in threads];[t.join(5) for t in threads]
        self.assertFalse(errors)
        self.assertEqual(sum(x is not None for x in results),1)
        claimed=next(x for x in results if x)
        self.assertEqual(claimed["task_id"],"task-1")
        with sqlite3.connect(self.db) as db:
            row=db.execute("SELECT status,attempts FROM tasks WHERE task_id='task-1'").fetchone()
        self.assertEqual(row,("running",1))
    def test_empty_queue_returns_none(self):
        with sqlite3.connect(self.db) as db:db.execute("DELETE FROM tasks")
        self.assertIsNone(AtomicSQLiteClaimer(self.db).claim_next("worker"))
    def test_invalid_lease_rejected(self):
        with self.assertRaises(ValueError):AtomicSQLiteClaimer(self.db).claim_next("worker",0)
    def test_execution_budget_accepts_within_budget(self):
        budget=ExecutionBudget(5,max_steps=3);budget.consume(2);budget.check()
        self.assertEqual(budget.steps,2)
    def test_execution_budget_rejects_excess_steps(self):
        budget=ExecutionBudget(5,max_steps=2)
        with self.assertRaises(RuntimeError):budget.consume(3)
    def test_execution_budget_cancellation(self):
        budget=ExecutionBudget(5);budget.cancel()
        with self.assertRaises(RuntimeError):budget.check()
    def test_execution_budget_rejects_expired_deadline(self):
        budget=ExecutionBudget(0.001);time.sleep(0.01)
        with self.assertRaises(TimeoutError):budget.check()
    def test_result_validation_rejects_nan_and_objects(self):
        for value in (float("nan"),object()):
            with self.assertRaises(ValueError):validate_result_size(value)
    def test_result_validation_enforces_size(self):
        with self.assertRaises(ValueError):validate_result_size("x"*100,20)
    def test_result_validation_accepts_small_json(self):
        validate_result_size({"ok":True},100)

if __name__=="__main__":unittest.main()
