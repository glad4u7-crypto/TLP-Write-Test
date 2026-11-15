"""APAA S08-C02-P04 security controls: validation, policy, consent, signed backup."""
from __future__ import annotations
import hashlib, hmac, json, os, re, sqlite3, tempfile, time
from pathlib import Path
from typing import Any

MAX_PAYLOAD_BYTES=64*1024
MAX_NESTING_DEPTH=12
_ACTION_RE=re.compile(r"^[a-z][a-z0-9_.-]{0,79}$")

def validate_task_input(action:str,payload:dict[str,Any],*,max_bytes:int=MAX_PAYLOAD_BYTES,
                        max_depth:int=MAX_NESTING_DEPTH)->dict[str,Any]:
    """Return a detached JSON-safe payload or reject it before it reaches durable storage."""
    if not isinstance(action,str) or not _ACTION_RE.fullmatch(action):
        raise ValueError("action must be a normalized allowlist-style identifier")
    if not isinstance(payload,dict):raise ValueError("payload must be a JSON object")
    try: encoded=json.dumps(payload,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")
    except (TypeError,ValueError) as exc:raise ValueError("payload must contain finite JSON values only") from exc
    if len(encoded)>max_bytes:raise ValueError("payload exceeds configured byte limit")
    def depth(value:Any,level:int)->None:
        if level>max_depth:raise ValueError("payload nesting exceeds configured depth")
        if isinstance(value,dict):
            for k,v in value.items():
                if not isinstance(k,str):raise ValueError("JSON object keys must be strings")
                depth(v,level+1)
        elif isinstance(value,list):
            for v in value:depth(v,level+1)
    depth(payload,0)
    return json.loads(encoded)

class PolicyRegistry:
    """Explicit, versioned action policy. Missing policy means deny."""
    def __init__(self,path:str=":memory:")->None:
        self.db=sqlite3.connect(path,check_same_thread=False)
        self.db.execute("""CREATE TABLE IF NOT EXISTS action_policy(
          action TEXT NOT NULL,version TEXT NOT NULL,enabled INTEGER NOT NULL,updated_at REAL NOT NULL,
          PRIMARY KEY(action,version))""")
    def set_policy(self,action:str,version:str,enabled:bool)->None:
        validate_task_input(action,{})
        if not version or len(version)>64:raise ValueError("invalid policy version")
        with self.db:self.db.execute("""INSERT INTO action_policy VALUES(?,?,?,?)
          ON CONFLICT(action,version) DO UPDATE SET enabled=excluded.enabled,updated_at=excluded.updated_at""",
          (action,version,int(enabled),time.time()))
    def allows(self,action:str,version:str)->bool:
        row=self.db.execute("SELECT enabled FROM action_policy WHERE action=? AND version=?",
                            (action,version)).fetchone()
        return bool(row and row[0])
    def close(self)->None:self.db.close()

class ConsentRegistry:
    """Durable, expiring, revocable user-consent ledger."""
    def __init__(self,path:str=":memory:")->None:
        self.db=sqlite3.connect(path,check_same_thread=False)
        self.db.execute("""CREATE TABLE IF NOT EXISTS consent(
          task_id TEXT PRIMARY KEY,granted_at REAL NOT NULL,expires_at REAL,revoked_at REAL,scope TEXT NOT NULL)""")
    def grant(self,task_id:str,scope:str,*,expires_at:float|None=None,now:float|None=None)->None:
        if not task_id or not scope:raise ValueError("task_id and consent scope required")
        now=time.time() if now is None else now
        if expires_at is not None and expires_at<=now:raise ValueError("consent expiry must be in the future")
        with self.db:self.db.execute("INSERT OR REPLACE INTO consent VALUES(?,?,?,?,?)",
          (task_id,now,expires_at,None,scope))
    def revoke(self,task_id:str,*,now:float|None=None)->bool:
        now=time.time() if now is None else now
        with self.db:
            cur=self.db.execute("UPDATE consent SET revoked_at=? WHERE task_id=? AND revoked_at IS NULL",(now,task_id))
            return cur.rowcount==1
    def is_valid(self,task_id:str,scope:str,*,now:float|None=None)->bool:
        now=time.time() if now is None else now
        row=self.db.execute("SELECT scope,expires_at,revoked_at FROM consent WHERE task_id=?",(task_id,)).fetchone()
        return bool(row and row[0]==scope and row[2] is None and (row[1] is None or row[1]>now))
    def close(self)->None:self.db.close()

class SignedBackup:
    """SQLite-consistent backup plus external HMAC checkpoint; key is supplied, never stored."""
    @staticmethod
    def _mac(path:Path,key:bytes)->str:
        if not isinstance(key,bytes) or len(key)<32:raise ValueError("signing key must be at least 32 bytes")
        digest=hmac.new(key,digestmod=hashlib.sha256)
        with path.open("rb") as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b""):digest.update(chunk)
        return digest.hexdigest()
    @classmethod
    def create(cls,source:str,destination:str,key:bytes)->str:
        src=Path(source).resolve();dst=Path(destination).resolve()
        if src==dst:raise ValueError("backup destination must differ from source")
        if not src.is_file():raise FileNotFoundError(source)
        dst.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp_name=tempfile.mkstemp(prefix=dst.name+".",suffix=".tmp",dir=str(dst.parent));os.close(fd)
        tmp=Path(tmp_name)
        try:
            with sqlite3.connect(str(src)) as source_db,sqlite3.connect(str(tmp)) as target_db:
                source_db.backup(target_db)
                check=target_db.execute("PRAGMA integrity_check").fetchone()[0]
                if check!="ok":raise sqlite3.DatabaseError("backup integrity check failed")
            signature=cls._mac(tmp,key)
            os.replace(tmp,dst)
            sig_tmp=dst.with_suffix(dst.suffix+".sig.tmp")
            sig_tmp.write_text(signature+"\n",encoding="ascii")
            os.replace(sig_tmp,dst.with_suffix(dst.suffix+".sig"))
            return signature
        finally:
            if tmp.exists():tmp.unlink()
    @classmethod
    def restore(cls,backup:str,target:str,key:bytes)->None:
        src=Path(backup).resolve();dst=Path(target).resolve()
        if src==dst:raise ValueError("restore source and target must differ")
        sig_path=src.with_suffix(src.suffix+".sig")
        expected=sig_path.read_text(encoding="ascii").strip()
        actual=cls._mac(src,key)
        if not hmac.compare_digest(expected,actual):raise ValueError("backup signature verification failed")
        with sqlite3.connect(str(src)) as check_db:
            if check_db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise sqlite3.DatabaseError("backup integrity check failed")
        dst.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(str(src)) as source_db,sqlite3.connect(str(dst)) as target_db:
            source_db.backup(target_db)
            if target_db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise sqlite3.DatabaseError("restored database integrity check failed")
