import threading
import unittest

from apaa_execution import (
    ExecutionEngine, StateStore, Task, TaskStatus
)


class ExecutionEngineTests(unittest.TestCase):
    def setUp(self):
        self.store = StateStore()
        self.engine = ExecutionEngine(self.store)
        self.engine.register("echo", lambda payload: {"echo": payload["value"]})

    def tearDown(self):
        self.store.close()

    def test_approved_task_runs_and_persists_result(self):
        task = Task.create("echo", {"value": "ok"},
                           permission_granted=True, user_consented=True)
        self.engine.submit(task)
        self.assertEqual(self.engine.run_next(), task.task_id)
        row = self.store.get(task.task_id)
        self.assertEqual(row["status"], TaskStatus.SUCCEEDED.value)
        self.assertEqual(row["result"], '{"echo": "ok"}')

    def test_missing_consent_blocks_before_handler(self):
        called = []
        self.engine.register("never", lambda p: called.append(True))
        task = Task.create("never", {}, permission_granted=True)
        self.engine.submit(task)
        self.engine.run_next()
        self.assertEqual(self.store.get(task.task_id)["status"], "blocked")
        self.assertEqual(called, [])

    def test_unknown_action_is_blocked(self):
        task = Task.create("not-registered", {}, permission_granted=True,
                           user_consented=True)
        self.engine.submit(task)
        self.engine.run_next()
        self.assertEqual(self.store.get(task.task_id)["status"], "blocked")

    def test_handler_failure_is_recorded(self):
        self.engine.register("explode", lambda p: 1 / 0)
        task = Task.create("explode", {}, permission_granted=True,
                           user_consented=True)
        self.engine.submit(task)
        self.engine.run_next()
        row = self.store.get(task.task_id)
        self.assertEqual(row["status"], "failed")
        self.assertIn("ZeroDivisionError", row["error"])

    def test_fifo_order(self):
        seen = []
        self.engine.register("record", lambda p: seen.append(p["n"]))
        tasks = [Task.create("record", {"n": n}, permission_granted=True,
                             user_consented=True) for n in range(3)]
        for task in tasks:
            self.engine.submit(task)
        self.engine.run_all()
        self.assertEqual(seen, [0, 1, 2])

    def test_invalid_transition_rejected(self):
        task = Task.create("echo", {"value": "x"})
        self.engine.submit(task)
        with self.assertRaises(ValueError):
            self.store.transition(task.task_id, TaskStatus.SUCCEEDED)

    def test_concurrent_execution_is_rejected(self):
        entered = threading.Event()
        release = threading.Event()
        self.engine.register("slow", lambda p: (entered.set(), release.wait(2)))
        task = Task.create("slow", {}, permission_granted=True,
                           user_consented=True)
        self.engine.submit(task)
        worker = threading.Thread(target=self.engine.run_next)
        worker.start()
        self.assertTrue(entered.wait(1))
        with self.assertRaises(RuntimeError):
            self.engine.run_next()
        release.set()
        worker.join(2)
        self.assertFalse(worker.is_alive())


if __name__ == "__main__":
    unittest.main()
