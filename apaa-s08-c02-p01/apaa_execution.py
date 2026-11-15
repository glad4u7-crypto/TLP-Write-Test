"""APAA S08-C02-P03: durable queue, dead-letter handling and tamper-evident audit."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import hashlib, json, sqlite3, threading, time, uuid
from typing import Any, Callable
from apaa_security import validate_task_input, PolicyRegistry, ConsentRegistry

class TaskStatus(str, Enum):
    QUEUED="queued"; RUNNING="running"; SUCCEEDED="succeeded"; FAILED="failed"
    BLOCKED="blocked"; CANCELLED="cancelled"; DEAD_LETTER="dead_letter"

_ALLOWED={
    TaskStatus.QUEUED:{TaskStatus.RUNNING,TaskStatus.BLOCKED,TaskStatus.CANCELLED},
    TaskStatus.RUNNING:{TaskStatus.QUEUED,TaskStatus.SUCCEEDED,TaskStatus.FAILED,TaskStatus.BLOCKED,TaskStatus.DEAD_LETTER},
    TaskStatus.FAILED:{TaskStatus.DEAD_LETTER},
    TaskStatus.SUCCEEDED:set(),TaskStatus.BLOCKED:set(),TaskStatus.CANCELLED:set(),TaskStatus.DEAD_LETTER:set()
}
_GENESIS="0"*64

@dataclass(frozen=True)
class Task:
    task_id:str
    action:str
    payload:dict[str,Any]
    permission_granted:bool=False
    user_consented:bool=False
    idempotency_key:str|None=None
    max_attempts:int=3
    policy_version:str="v1"
    @classmethod
    def create(cls,action:str,payload:dict[str,Any],*,permission_granted:bool=False,
               user_consented:bool=False,idempotency_key:str|None=None,max_attempts:int=3,
               policy_version:str="v1")->"Task":
        payload=validate_task_input(action,payload)
        if max_attempts<1 or max_attempts>10: raise ValueError("max_attempts must be 1..10")
        if not isinstance(policy_version,str) or not policy_version or len(policy_version)>64:
            raise ValueError("invalid policy_version")
        if idempotency_key is not None and (not idempotency_key.strip() or len(idempotency_key)>200):
            raise ValueError("invalid idempotency_key")
        return cls(str(uuid.uuid4()),action,payload,permission_granted,user_consented,idempotency_key,max_attempts,policy_version)

class StateStore:
    """SQLite queue with atomic state transitions and a hash-chained audit journal."""
    def __init__(self,path:str=":memory:")->None:
        self._db=sqlite3.connect(path,check_same_thread=False,timeout=10)
        self._db.row_factory=sqlite3.Row; self._lock=threading.RLock()
        with self._db:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("""CREATE TABLE IF NOT EXISTS tasks(
              task_id TEXT PRIMARY KEY,action TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,
              result TEXT,error TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL)""")
            cols={r["name"] for r in self._db.execute("PRAGMA table_info(tasks)")}
            additions={"permission_granted":"INTEGER NOT NULL DEFAULT 0","user_consented":"INTEGER NOT NULL DEFAULT 0",
              "idempotency_key":"TEXT","attempts":"INTEGER NOT NULL DEFAULT 0","max_attempts":"INTEGER NOT NULL DEFAULT 3",
              "lease_owner":"TEXT","lease_expires_at":"REAL","policy_version":"TEXT NOT NULL DEFAULT 'v1'"}
            for name,decl in additions.items():
                if name not in cols:self._db.execute(f"ALTER TABLE tasks ADD COLUMN {name} {decl}")
            self._db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_idempotency ON tasks(idempotency_key) WHERE idempotency_key IS NOT NULL")
            self._db.execute("""CREATE TABLE IF NOT EXISTS audit_events(
              event_id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT NOT NULL,event TEXT NOT NULL,
              detail TEXT,created_at REAL NOT NULL,prev_hash TEXT NOT NULL DEFAULT '',event_hash TEXT NOT NULL DEFAULT '')""")
            acols={r["name"] for r in self._db.execute("PRAGMA table_info(audit_events)")}
            if "prev_hash" not in acols:self._db.execute("ALTER TABLE audit_events ADD COLUMN prev_hash TEXT NOT NULL DEFAULT ''")
            if "event_hash" not in acols:self._db.execute("ALTER TABLE audit_events ADD COLUMN event_hash TEXT NOT NULL DEFAULT ''")
            self._db.execute("""CREATE TABLE IF NOT EXISTS dead_letters(
              task_id TEXT PRIMARY KEY,final_error TEXT NOT NULL,attempts INTEGER NOT NULL,
              created_at REAL NOT NULL,FOREIGN KEY(task_id) REFERENCES tasks(task_id))""")
    @staticmethod
    def _event_digest(event_id:int,task_id:str,event:str,detail:str|None,created_at:float,prev_hash:str)->str:
        body=json.dumps({"event_id":event_id,"task_id":task_id,"event":event,"detail":detail,
                         "created_at":created_at,"prev_hash":prev_hash},
                        sort_keys=True,separators=(",",":"),ensure_ascii=False)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()
    def _audit(self,task_id:str,event:str,detail:str|None=None)->None:
        last=self._db.execute("SELECT event_hash FROM audit_events ORDER BY event_id DESC LIMIT 1").fetchone()
        prev=last["event_hash"] if last and last["event_hash"] else _GENESIS
        now=time.time()
        cur=self._db.execute("INSERT INTO audit_events(task_id,event,detail,created_at,prev_hash,event_hash) VALUES(?,?,?,?,?,?)",
                             (task_id,event,detail,now,prev,""))
        eid=cur.lastrowid; digest=self._event_digest(eid,task_id,event,detail,now,prev)
        self._db.execute("UPDATE audit_events SET event_hash=? WHERE event_id=?",(digest,eid))
    def add(self,t:Task)->str:
        now=time.time()
        with self._lock,self._db:
            if t.idempotency_key:
                old=self._db.execute("SELECT task_id FROM tasks WHERE idempotency_key=?",(t.idempotency_key,)).fetchone()
                if old:self._audit(old["task_id"],"duplicate_suppressed",t.task_id);return old["task_id"]
            self._db.execute("""INSERT INTO tasks(task_id,action,payload,status,created_at,updated_at,
              permission_granted,user_consented,idempotency_key,max_attempts,policy_version) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
              (t.task_id,t.action,json.dumps(t.payload,sort_keys=True),TaskStatus.QUEUED.value,now,now,
               int(t.permission_granted),int(t.user_consented),t.idempotency_key,t.max_attempts,t.policy_version))
            self._audit(t.task_id,"queued")
        return t.task_id
    def _transition(self,task_id:str,target:TaskStatus,*,result:Any=None,error:str|None=None,
                    lease_owner:str|None=None,lease_expires_at:float|None=None)->None:
        row=self._db.execute("SELECT status FROM tasks WHERE task_id=?",(task_id,)).fetchone()
        if row is None:raise KeyError(task_id)
        current=TaskStatus(row["status"])
        if target not in _ALLOWED[current]:raise ValueError(f"invalid transition: {current.value} -> {target.value}")
        self._db.execute("""UPDATE tasks SET status=?,result=?,error=?,updated_at=?,lease_owner=?,lease_expires_at=?
          WHERE task_id=?""",(target.value,json.dumps(result,sort_keys=True,default=str) if result is not None else None,
          error,time.time(),lease_owner,lease_expires_at,task_id))
        self._audit(task_id,target.value,error)
    def claim_next(self,worker_id:str,lease_seconds:float)->dict[str,Any]|None:
        if not worker_id or lease_seconds<=0:raise ValueError("worker_id and positive lease required")
        now=time.time()
        with self._lock,self._db:
            row=self._db.execute("SELECT * FROM tasks WHERE status=? ORDER BY created_at,task_id LIMIT 1",
                                 (TaskStatus.QUEUED.value,)).fetchone()
            if row is None:return None
            self._transition(row["task_id"],TaskStatus.RUNNING,lease_owner=worker_id,lease_expires_at=now+lease_seconds)
            self._db.execute("UPDATE tasks SET attempts=attempts+1 WHERE task_id=?",(row["task_id"],))
            self._audit(row["task_id"],"lease_claimed",worker_id)
            return dict(self._db.execute("SELECT * FROM tasks WHERE task_id=?",(row["task_id"],)).fetchone())
    def finish(self,task_id:str,worker_id:str,target:TaskStatus,*,result:Any=None,error:str|None=None)->None:
        with self._lock,self._db:
            row=self._db.execute("SELECT status,lease_owner,attempts,max_attempts FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            if row is None:raise KeyError(task_id)
            if row["status"]!=TaskStatus.RUNNING.value or row["lease_owner"]!=worker_id:
                raise RuntimeError("worker does not own the active lease")
            if target==TaskStatus.FAILED and row["attempts"]>=row["max_attempts"]:
                target=TaskStatus.DEAD_LETTER
            self._transition(task_id,target,result=result,error=error)
            if target==TaskStatus.DEAD_LETTER:self._record_dead_letter(task_id,error or "attempt limit reached",row["attempts"])
    def _record_dead_letter(self,task_id:str,error:str,attempts:int)->None:
        self._db.execute("INSERT OR REPLACE INTO dead_letters(task_id,final_error,attempts,created_at) VALUES(?,?,?,?)",
                         (task_id,error,attempts,time.time()))
        self._audit(task_id,"dead_lettered",error)
    def retry_or_fail(self,task_id:str,worker_id:str,error:str)->None:
        with self._lock,self._db:
            row=self._db.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            if row is None:raise KeyError(task_id)
            if row["status"]!=TaskStatus.RUNNING.value or row["lease_owner"]!=worker_id:
                raise RuntimeError("worker does not own the active lease")
            target=TaskStatus.QUEUED if row["attempts"]<row["max_attempts"] else TaskStatus.DEAD_LETTER
            self._transition(task_id,target,error=error)
            if target==TaskStatus.QUEUED:self._audit(task_id,"retry_scheduled",error)
            else:self._record_dead_letter(task_id,error,row["attempts"])
    def recover_expired(self,now:float|None=None)->int:
        now=time.time() if now is None else now;count=0
        with self._lock,self._db:
            rows=self._db.execute("SELECT * FROM tasks WHERE status=? AND lease_expires_at<=?",
                                  (TaskStatus.RUNNING.value,now)).fetchall()
            for row in rows:
                target=TaskStatus.QUEUED if row["attempts"]<row["max_attempts"] else TaskStatus.DEAD_LETTER
                self._transition(row["task_id"],target,error="execution lease expired")
                if target==TaskStatus.QUEUED:self._audit(row["task_id"],"lease_recovered",target.value)
                else:self._record_dead_letter(row["task_id"],"execution lease expired",row["attempts"])
                count+=1
        return count
    def cancel(self,task_id:str,reason:str="cancelled by user")->bool:
        """Cancel only queued work. Running handlers cannot be forcibly interrupted safely."""
        with self._lock,self._db:
            row=self._db.execute("SELECT status FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            if row is None:raise KeyError(task_id)
            if row["status"]!=TaskStatus.QUEUED.value:return False
            self._transition(task_id,TaskStatus.CANCELLED,error=reason)
            self._audit(task_id,"cancelled",reason)
            return True
    def dead_letters(self)->list[dict[str,Any]]:
        with self._lock:return [dict(r) for r in self._db.execute(
          """SELECT d.*,t.action,t.payload,t.idempotency_key FROM dead_letters d
             JOIN tasks t ON t.task_id=d.task_id ORDER BY d.created_at""").fetchall()]
    def get(self,task_id:str)->dict[str,Any]:
        with self._lock:
            row=self._db.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            if row is None:raise KeyError(task_id)
            return dict(row)
    def audit(self,task_id:str)->list[dict[str,Any]]:
        with self._lock:return [dict(r) for r in self._db.execute(
          "SELECT * FROM audit_events WHERE task_id=? ORDER BY event_id",(task_id,)).fetchall()]
    def verify_audit_chain(self)->bool:
        """Verify every event and the global previous-hash linkage; detects edits, deletion and reordering."""
        with self._lock:
            rows=self._db.execute("SELECT * FROM audit_events ORDER BY event_id").fetchall()
            prev=_GENESIS
            for row in rows:
                if row["prev_hash"]!=prev:return False
                expected=self._event_digest(row["event_id"],row["task_id"],row["event"],
                    row["detail"],row["created_at"],row["prev_hash"])
                if row["event_hash"]!=expected:return False
                prev=row["event_hash"]
            return True
    def close(self)->None:
        with self._lock:self._db.close()

class ExecutionEngine:
    """Explicitly consent-gated worker; no implicit external adapters."""
    def __init__(self,store:StateStore|None=None,*,worker_id:str|None=None,lease_seconds:float=30,
                 policy_registry:PolicyRegistry|None=None,consent_registry:ConsentRegistry|None=None,
                 consent_ttl_seconds:float=900)->None:
        if lease_seconds<=0 or consent_ttl_seconds<=0:raise ValueError("lease and consent TTL must be positive")
        self.store=store or StateStore();self.worker_id=worker_id or str(uuid.uuid4())
        self.lease_seconds=lease_seconds;self._handlers:dict[str,Callable[[dict[str,Any]],Any]]={}
        self.policy_registry=policy_registry or PolicyRegistry()
        self.consent_registry=consent_registry or ConsentRegistry()
        self.consent_ttl_seconds=consent_ttl_seconds
        self._run_lock=threading.Lock()
    def set_policy(self,action:str,version:str,enabled:bool)->None:
        self.policy_registry.set_policy(action,version,enabled)
    def grant_consent(self,task_id:str,scope:str,*,expires_at:float|None=None)->None:
        self.consent_registry.grant(task_id,scope,expires_at=expires_at)
    def revoke_consent(self,task_id:str)->bool:
        return self.consent_registry.revoke(task_id)
    def register(self,action:str,handler:Callable[[dict[str,Any]],Any])->None:
        if not action or not callable(handler):raise ValueError("named callable handler required")
        if action in self._handlers:raise ValueError(f"handler already registered: {action}")
        self._handlers[action]=handler
    def submit(self,task:Task)->str:
        # The caller's explicit consent flag creates a short-lived persisted grant.
        tid=self.store.add(task)
        if task.user_consented:
            self.consent_registry.grant(tid,task.action,expires_at=time.time()+self.consent_ttl_seconds)
        return tid
    def cancel(self,task_id:str,reason:str="cancelled by user")->bool:return self.store.cancel(task_id,reason)
    def run_next(self)->str|None:
        if not self._run_lock.acquire(blocking=False):raise RuntimeError("worker already executing")
        try:
            row=self.store.claim_next(self.worker_id,self.lease_seconds)
            if row is None:return None
            tid=row["task_id"];action=row["action"];handler=self._handlers.get(action)
            # Re-check live policy and consent immediately before invoking a handler.
            policy_ok=self.policy_registry.allows(action,row["policy_version"])
            consent_ok=self.consent_registry.is_valid(tid,action)
            if not row["permission_granted"] or not row["user_consented"] or not policy_ok or not consent_ok or handler is None:
                reasons=[]
                if not row["permission_granted"]:reasons.append("permission flag missing")
                if not row["user_consented"] or not consent_ok:reasons.append("consent missing, expired, revoked, or wrong scope")
                if not policy_ok:reasons.append("policy missing or disabled")
                if handler is None:reasons.append("handler not registered")
                self.store.finish(tid,self.worker_id,TaskStatus.BLOCKED,error="; ".join(reasons))
                return tid
            try:output=handler(validate_task_input(action,json.loads(row["payload"])))
            except Exception as exc:self.store.retry_or_fail(tid,self.worker_id,f"{type(exc).__name__}: {exc}")
            else:self.store.finish(tid,self.worker_id,TaskStatus.SUCCEEDED,result=output)
            return tid
        finally:self._run_lock.release()
    def run_all(self)->list[str]:
        done=[]
        while True:
            tid=self.run_next()
            if tid is None:return done
