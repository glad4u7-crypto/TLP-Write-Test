from pathlib import Path
from types import SimpleNamespace
import pytest
from core.oci_runtime_backend import OCIWorkerSpec, WorkerLimits
from core.oci_runtime_observer import PodmanWorkerObserver, WorkerObservationError

CID="a"*64
IMAGE="sha256:"+"b"*64

class Runtime:
    def __init__(self, payload): self.payload=payload
    def inspect(self, cid):
        assert cid==CID
        return self.payload

def proc_stat(pid, start=777):
    # Linux /proc stat: comm may contain spaces and ')' characters.
    fields=["S"]+["0"]*18+[str(start)]+["0"]*5
    return f"{pid} (worker process ) name) "+" ".join(fields)

def make_fs(tmp_path, *, cgroup="/apaa/worker1/container", net_inode=123, ns_inode=123, start1=777, start2=777):
    proc=tmp_path/"proc"/"4321"; (proc/"ns").mkdir(parents=True)
    (proc/"stat").write_text(proc_stat(4321,start1))
    (proc/"ns"/"net").symlink_to(tmp_path/"netns-target")
    (tmp_path/"netns-target").write_text("ns")
    (tmp_path/"netns"/"w1").mkdir(parents=True)
    # Symlink inode is the target inode; make a stable namespace inode by hard-linking.
    (tmp_path/"netns"/"w1").rmdir()
    (tmp_path/"netns"/"w1").symlink_to(tmp_path/"netns-target")
    (proc/"cgroup").write_text(f"0::{cgroup}\n")
    (proc/"status").write_text("Name:\tworker\nSeccomp:\t2\nCapEff:\t0000000000000000\n")
    cg=tmp_path/"cgroup"/"apaa"/"worker1"/"container"
    cg.mkdir(parents=True)
    (cg.parent/"cgroup.procs").write_text("")
    (cg/"memory.max").write_text("1073741824")
    (cg/"cpu.max").write_text("100000 100000")
    (cg/"pids.max").write_text("128")
    (cg/"cgroup.procs").write_text("4321\n")
    return tmp_path/"proc",tmp_path/"cgroup",tmp_path/"netns"

def payload():
    return {
      "Id":CID,"Image":IMAGE,
      "HostConfig":{"ReadonlyRootfs":True,"CapDrop":["CAP_CHOWN","CAP_DAC_OVERRIDE","CAP_FOWNER","CAP_FSETID","CAP_KILL","CAP_NET_BIND_SERVICE","CAP_SETFCAP","CAP_SETGID","CAP_SETPCAP","CAP_SETUID","CAP_SYS_CHROOT"],"CapAdd":[],
       "SecurityOpt":["no-new-privileges","seccomp=/profiles/chromium.json"],
       "Memory":1073741824,"PidsLimit":128,"NanoCpus":1000000000,
       "NetworkMode":"ns:/run/netns/w1"},
      "Config":{"User":"65532:65532"},
      "State":{"Running":True,"Pid":4321},
    }

def spec():
    return OCIWorkerSpec(IMAGE,"/run/netns/w1","/profiles/chromium.json","worker1",
                         WorkerLimits(),"/apaa/worker1")

def test_observer_requires_runtime_and_kernel_evidence(tmp_path):
    proc,cg,ns=make_fs(tmp_path)
    observer=PodmanWorkerObserver(Runtime(payload()),proc_root=proc,cgroup_root=cg,namespace_root=ns)
    result=observer.observe(CID,spec())
    assert result.host_pid==4321
    assert result.process_start_time_ticks==777
    assert result.network_namespace_inode==(ns/"w1").stat().st_ino
    assert result.seccomp_mode==2
    assert result.memory_max=="1073741824"

def test_observer_rejects_pid_reuse_during_observation(tmp_path,monkeypatch):
    proc,cg,ns=make_fs(tmp_path)
    original=PodmanWorkerObserver._read
    calls={"stat":0}
    def changing_read(path):
        if path.name=="stat":
            calls["stat"]+=1
            return proc_stat(4321,777 if calls["stat"]==1 else 778)
        return original(path)
    monkeypatch.setattr(PodmanWorkerObserver,"_read",staticmethod(changing_read))
    observer=PodmanWorkerObserver(Runtime(payload()),proc_root=proc,cgroup_root=cg,namespace_root=ns)
    with pytest.raises(WorkerObservationError,match="reused"):
        observer.observe(CID,spec())

@pytest.mark.parametrize("change,match",[
 (lambda p:p["HostConfig"].update(NetworkMode="bridge"),"namespace"),
 (lambda p:p["HostConfig"].update(ReadonlyRootfs=False),"security"),
 (lambda p:p["HostConfig"].update(Memory=999),"resource"),
 (lambda p:p["State"].update(Running=False),"not confirmed running"),
 (lambda p:p["Config"].update(User="0:0"),"non-root"),
 (lambda p:p.update(Image="latest"),"image ID"),
 (lambda p:p.update(Image="sha256:"+"c"*64),"image ID"),
])
def test_observer_rejects_mismatched_runtime_inspect(tmp_path,change,match):
    proc,cg,ns=make_fs(tmp_path)
    p=payload(); change(p)
    observer=PodmanWorkerObserver(Runtime(p),proc_root=proc,cgroup_root=cg,namespace_root=ns)
    with pytest.raises(WorkerObservationError,match=match):
        observer.observe(CID,spec())

def test_observer_rejects_cgroup_escape(tmp_path):
    proc,cg,ns=make_fs(tmp_path,cgroup="/other/container")
    observer=PodmanWorkerObserver(Runtime(payload()),proc_root=proc,cgroup_root=cg,namespace_root=ns)
    with pytest.raises(WorkerObservationError,match="cgroup subtree"):
        observer.observe(CID,spec())

def test_observer_rejects_missing_seccomp_or_wrong_effective_limits(tmp_path):
    proc,cg,ns=make_fs(tmp_path)
    (proc/"4321"/"status").write_text("Name:\tworker\nSeccomp:\t0\n")
    observer=PodmanWorkerObserver(Runtime(payload()),proc_root=proc,cgroup_root=cg,namespace_root=ns)
    with pytest.raises(WorkerObservationError,match="seccomp"):
        observer.observe(CID,spec())


def test_observer_rejects_runtime_capability_additions(tmp_path):
    proc,cg,ns=make_fs(tmp_path)
    p=payload(); p["HostConfig"]["CapAdd"]=["CAP_SYS_ADMIN"]
    observer=PodmanWorkerObserver(Runtime(p),proc_root=proc,cgroup_root=cg,namespace_root=ns)
    with pytest.raises(WorkerObservationError,match="security options"):
        observer.observe(CID,spec())


def test_observer_rejects_nonzero_kernel_effective_capabilities(tmp_path):
    proc,cg,ns=make_fs(tmp_path)
    (proc/"4321"/"status").write_text(
        "Name:\tworker\nSeccomp:\t2\nCapEff:\t0000000000000001\n"
    )
    observer=PodmanWorkerObserver(Runtime(payload()),proc_root=proc,cgroup_root=cg,namespace_root=ns)
    with pytest.raises(WorkerObservationError,match="effective Linux capabilities"):
        observer.observe(CID,spec())


def test_observer_normalizes_proc_cgroup_path_with_mount_prefix(tmp_path):
    proc,cg,ns=make_fs(tmp_path)
    (proc/"4321"/"cgroup").write_text(f"0::{cg}/apaa/worker1/container\n")
    observer=PodmanWorkerObserver(Runtime(payload()),proc_root=proc,cgroup_root=cg,namespace_root=ns)
    result=observer.observe(CID,spec())
    assert result.cgroup_path == "/apaa/worker1/container"


def test_observer_locates_worker_by_kernel_membership_when_proc_path_is_unmapped(tmp_path):
    proc,cg,ns=make_fs(tmp_path)
    (proc/"4321"/"cgroup").write_text("0::/unmapped/private-cgroup-namespace/path\n")
    observer=PodmanWorkerObserver(Runtime(payload()),proc_root=proc,cgroup_root=cg,namespace_root=ns)
    result=observer.observe(CID,spec())
    assert result.cgroup_path == "/apaa/worker1/container"


def test_observer_rejects_worker_pid_not_listed_in_dedicated_cgroup(tmp_path):
    proc,cg,ns=make_fs(tmp_path)
    (cg/"apaa"/"worker1"/"container"/"cgroup.procs").write_text("9999\n")
    observer=PodmanWorkerObserver(Runtime(payload()),proc_root=proc,cgroup_root=cg,namespace_root=ns)
    with pytest.raises(WorkerObservationError,match="not uniquely present"):
        observer.observe(CID,spec())


def test_observer_rejects_worker_pid_in_multiple_cgroups(tmp_path):
    proc,cg,ns=make_fs(tmp_path)
    extra=cg/"apaa"/"worker1"/"other"
    extra.mkdir()
    (extra/"cgroup.procs").write_text("4321\n")
    observer=PodmanWorkerObserver(Runtime(payload()),proc_root=proc,cgroup_root=cg,namespace_root=ns)
    with pytest.raises(WorkerObservationError,match="multiple"):
        observer.observe(CID,spec())
