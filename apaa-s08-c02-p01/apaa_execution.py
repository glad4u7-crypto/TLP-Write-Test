"""APAA S08-C02-P02: durable queue, leases, retries and audit journal."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import json, sqlite3, threading, time, uuid
from typing import Any, Callable

class TaskStatus(str, Enum):
    QUEUED="queued"; RUNNING="running"; SUCCEEDED="succeeded"; FAILED="failed"; BLOCKED="blocked"

_ALLOWED={TaskStatus.QUEUED:{TaskStatus.RUNNING,TaskStatus.BLOCKED},
          TaskStatus.RUNNING:{TaskStatus.QUEUED,TaskStatus.SUCCEEDED,TaskStatus.FAILED},
          TaskStatus.SUCCEEDED:set(),TaskStatus.FAILED:set(),TaskStatus.BLOCKED:set()}

@dataclass(frozen=True)
class Task:
    task_id:str
    action:str
    payload:dict[str,Any]
    permission_granted:bool=False
    user_consented:bool=False
    idempotency_key:str|None=None
    max_attempts:int=3
    @classmethod
    def create(cls, action:str, payload:dict[str,Any], *, permission_granted:bool=False,
               user_consented:bool=False, idempotency_key:str|None=None,
               max_attempts:int=3)->"Task":
        if not isinstance(action,str) or not action.strip(): raise ValueError("action required")
        if not isinstance(payload,dict): raise ValueError("payload must be a dictionary")
        if max_attempts<1 or max_attempts>10: raise ValueError("max_attempts must be 1..10")
        if idempotency_key is not None and (not idempotency_key.strip() or len(idempotency_key)>200):
            raise ValueError("invalid idempotency_key")
        return cls(str(uuid.uuid4()),action,payload,permission_granted,user_consented,idempotency_key,max_attempts)

class StateStore:
    """SQLite durable queue. DB transitions are atomic; handlers never run inside DB transactions."""
    def __init__(self,path:str=":memory:")->None:
        self._db=sqlite3.connect(path,check_same_thread=False,timeout=10)
        self._db.row_factory=sqlite3.Row
        self._lock=threading.RLock()
        with self._db:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("""CREATE TABLE IF NOT EXISTS tasks(
              task_id TEXT PRIMARY KEY, action TEXT NOT NULL, payload TEXT NOT NULL,
              status TEXT NOT NULL, result TEXT, error TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL)""")
            cols={r["name"] for r in self._db.execute("PRAGMA table_info(tasks)")}
            additions={"permission_granted":"INTEGER NOT NULL DEFAULT 0","user_consented":"INTEGER NOT NULL DEFAULT 0",
              "idempotency_key":"TEXT","attempts":"INTEGER NOT NULL DEFAULT 0","max_attempts":"INTEGER NOT NULL DEFAULT 3",
              "lease_owner":"TEXT","lease_expires_at":"REAL"}
            for name,decl in additions.items():
                if name not in cols: self._db.execute(f"ALTER TABLE tasks ADD COLUMN {name} {decl}")
            self._db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_idempotency ON tasks(idempotency_key) WHERE idempotency_key IS NOT NULL")
            self._db.execute("""CREATE TABLE IF NOT EXISTS audit_events(
              event_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, event TEXT NOT NULL,
              detail TEXT, created_at REAL NOT NULL)""")
    def _audit(self,task_id:str,event:str,detail:str|None=None)->None:
        self._db.execute("INSERT INTO audit_events(task_id,event,detail,created_at) VALUES(?,?,?,?)",
                         (task_id,event,detail,time.time()))
    def add(self,t:Task)->str:
        now=time.time()
        with self._lock,self._db:
            if t.idempotency_key:
                old=self._db.execute("SELECT task_id FROM tasks WHERE idempotency_key=?",(t.idempotency_key,)).fetchone()
                if old: self._audit(old["task_id"],"duplicate_suppressed",t.task_id); return old["task_id"]
            self._db.execute("""INSERT INTO tasks(task_id,action,payload,status,created_at,updated_at,
              permission_granted,user_consented,idempotency_key,max_attempts)
              VALUES(?,?,?,?,?,?,?,?,?,?)""",(t.task_id,t.action,json.dumps(t.payload,sort_keys=True),
              TaskStatus.QUEUED.value,now,now,int(t.permission_granted),int(t.user_consented),
              t.idempotency_key,t.max_attempts))
            self._audit(t.task_id,"queued")
        return t.task_id
    def _transition(self,task_id:str,target:TaskStatus,*,result:Any=None,error:str|None=None,
                    lease_owner:str|None=None,lease_expires_at:float|None=None)->None:
        row=self._db.execute("SELECT status FROM tasks WHERE task_id=?",(task_id,)).fetchone()
        if row is None: raise KeyError(task_id)
        current=TaskStatus(row["status"])
        if target not in _ALLOWED[current]: raise ValueError(f"invalid transition: {current.value} -> {target.value}")
        self._db.execute("""UPDATE tasks SET status=?,result=?,error=?,updated_at=?,lease_owner=?,lease_expires_at=?
          WHERE task_id=?""",(target.value,json.dumps(result,sort_keys=True,default=str) if result is not None else None,
          error,time.time(),lease_owner,lease_expires_at,task_id))
        self._audit(task_id,target.value,error)
    def claim_next(self,worker_id:str,lease_seconds:float)->dict[str,Any]|None:
        now=time.time()
        with self._lock,self._db:
            row=self._db.execute("SELECT * FROM tasks WHERE status=? ORDER BY created_at,task_id LIMIT 1",
                                 (TaskStatus.QUEUED.value,)).fetchone()
            if row is None:return None
            expires=now+lease_seconds
            self._transition(row["task_id"],TaskStatus.RUNNING,lease_owner=worker_id,lease_expires_at=expires)
            self._db.execute("UPDATE tasks SET attempts=attempts+1 WHERE task_id=?",(row["task_id"],))
            self._audit(row["task_id"],"lease_claimed",worker_id)
            return dict(self._db.execute("SELECT * FROM tasks WHERE task_id=?",(row["task_id"],)).fetchone())
    def finish(self,task_id:str,worker_id:str,target:TaskStatus,*,result:Any=None,error:str|None=None)->None:
        with self._lock,self._db:
            row=self._db.execute("SELECT status,lease_owner FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            if row is None:raise KeyError(task_id)
            if row["status"]!=TaskStatus.RUNNING.value or row["lease_owner"]!=worker_id:
                raise RuntimeError("worker does not own the active lease")
            self._transition(task_id,target,result=result,error=error)
    def retry_or_fail(self,task_id:str,worker_id:str,error:str)->None:
        with self._lock,self._db:
            row=self._db.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            if row is None:raise KeyError(task_id)
            if row["status"]!=TaskStatus.RUNNING.value or row["lease_owner"]!=worker_id:
                raise RuntimeError("worker does not own the active lease")
            target=TaskStatus.QUEUED if row["attempts"]<row["max_attempts"] else TaskStatus.FAILED
            self._transition(task_id,target,error=error)
            self._audit(task_id,"retry_scheduled" if target==TaskStatus.QUEUED else "retry_exhausted",error)
    def recover_expired(self,now:float|None=None)->int:
        now=time.time() if now is None else now
        count=0
        with self._lock,self._db:
            rows=self._db.execute("SELECT * FROM tasks WHERE status=? AND lease_expires_at<=?",
                                  (TaskStatus.RUNNING.value,now)).fetchall()
            for row in rows:
                target=TaskStatus.QUEUED if row["attempts"]<row["max_attempts"] else TaskStatus.FAILED
                self._transition(row["task_id"],target,error="execution lease expired")
                self._audit(row["task_id"],"lease_recovered",target.value);count+=1
        return count
    def get(self,task_id:str)->dict[str,Any]:
        with self._lock:
            row=self._db.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            if row is None:raise KeyError(task_id)
            return dict(row)
    def audit(self,task_id:str)->list[dict[str,Any]]:
        with self._lock:return [dict(r) for r in self._db.execute(
            "SELECT * FROM audit_events WHERE task_id=? ORDER BY event_id",(task_id,)).fetchall()]
    def close(self)->None:
        with self._lock:self._db.close()

class ExecutionEngine:
    """Durable FIFO worker with explicit consent, leases and bounded retries."""
    def __init__(self,store:StateStore|None=None,*,worker_id:str|None=None,lease_seconds:float=30)->None:
        if lease_seconds<=0:raise ValueError("lease_seconds must be positive")
        self.store=store or StateStore();self.worker_id=worker_id or str(uuid.uuid4())
        self.lease_seconds=lease_seconds;self._handlers:dict[str,Callable[[dict[str,Any]],Any]]={}
        self._run_lock=threading.Lock()
    def register(self,action:str,handler:Callable[[dict[str,Any]],Any])->None:
        if not action or not callable(handler):raise ValueError("named callable handler required")
        if action in self._handlers:raise ValueError(f"handler already registered: {action}")
        self._handlers[action]=handler
    def submit(self,task:Task)->str:return self.store.add(task)
    def run_next(self)->str|None:
        if not self._run_lock.acquire(blocking=False):raise RuntimeError("worker already executing")
        try:
            row=self.store.claim_next(self.worker_id,self.lease_seconds)
            if row is None:return None
            tid=row["task_id"];handler=self._handlers.get(row["action"])
            if not row["permission_granted"] or not row["user_consented"] or handler is None:
                self.store.finish(tid,self.worker_id,TaskStatus.BLOCKED,
                                  error="permission, consent, or registered handler missing")
                return tid
            try:output=handler(json.loads(row["payload"]))
            except Exception as exc:
                self.store.retry_or_fail(tid,self.worker_id,f"{type(exc).__name__}: {exc}")
            else:self.store.finish(tid,self.worker_id,TaskStatus.SUCCEEDED,result=output)
            return tid
        finally:self._run_lock.release()
    def run_all(self)->list[str]:
        done=[]
        while True:
            tid=self.run_next()
            if tid is None:return done
            done.append(tid)
