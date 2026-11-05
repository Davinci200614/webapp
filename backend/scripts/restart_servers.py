"""Gracefully stop verified webapp server trees; never kill by port alone."""
import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import signal
import time


@dataclass(frozen=True)
class Process:
    pid: int
    parent: int
    state: str
    started: str
    cwd: Path
    args: tuple[str, ...]


def read_process(pid):
    try:
        folder=Path('/proc')/str(pid)
        if folder.stat().st_uid!=os.getuid():return None
        fields=(folder/'stat').read_text().rsplit(')',1)[1].split()
        args=tuple(arg.decode(errors='replace') for arg in (folder/'cmdline').read_bytes().split(b'\0') if arg)
        return Process(pid,int(fields[1]),fields[0],fields[19],(folder/'cwd').resolve(strict=True),args)
    except (OSError,ValueError,IndexError):return None


def snapshot():
    result={}
    for folder in Path('/proc').glob('[0-9]*'):
        process=read_process(int(folder.name))
        if process:result[process.pid]=process
    return result


def option(args,name,default):
    for index,arg in enumerate(args):
        if arg.startswith(name+'='):return arg.split('=',1)[1]
        if arg==name:return args[index+1] if index+1<len(args) else None
    return default


def role(process,root,frontend):
    args=process.args
    uvicorn_command=(any(Path(arg).name=='uvicorn' for arg in args[:2])
                     or any(args[index:index+2]==('-m','uvicorn') for index in range(len(args)-1)))
    if (process.cwd==(root/'backend').resolve() and 'app.main:app' in args
            and uvicorn_command
            and option(args,'--port','8000')=='8000'):
        return 'backend'
    if frontend and process.cwd==(root/'frontend').resolve():
        command=' '.join(args)
        is_vite=any(Path(arg).name in {'vite','vite.js'} for arg in args)
        is_npm=command.startswith('npm run dev') or ('npm' in command and 'run' in args and 'dev' in args)
        if (is_vite or is_npm) and option(args,'--port','5173')=='5173':return 'frontend'
    return None


def select_processes(processes,root,frontend=False):
    roots={pid:role(process,root,frontend) for pid,process in processes.items()}
    roots={pid:name for pid,name in roots.items() if name}
    selected=set(roots)
    while True:
        children={pid for pid,process in processes.items() if process.parent in selected}
        if children<=selected:break
        selected.update(children)
    return {pid:processes[pid] for pid in selected},roots


def same_process(process):
    current=read_process(process.pid)
    return current is not None and current.started==process.started and current.state!='Z'


def send(process,sig):
    # A reused PID must not inherit the earlier process's shutdown request.
    if same_process(process):
        try:os.kill(process.pid,sig)
        except ProcessLookupError:pass


def stop_servers(root,frontend=False,timeout=15):
    if not Path('/proc').is_dir():
        raise RuntimeError('Verified restart requires Linux /proc; stop the existing server manually on this platform.')
    selected,roots=select_processes(snapshot(),root.resolve(),frontend)
    if not roots:
        print('No existing server from this webapp was found; continuing startup.')
        return
    for pid,name in sorted(roots.items()):print(f'Restarting webapp {name}: stopping PID {pid}.',flush=True)
    # Queue termination first, then resume Ctrl+Z-suspended processes so they can exit.
    for process in selected.values():send(process,signal.SIGTERM)
    for process in selected.values():
        if process.state in {'T','t'}:send(process,signal.SIGCONT)
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if not any(same_process(process) for process in selected.values()):
            print('Previous webapp servers stopped. Existing separate tunnels are unchanged.')
            return
        time.sleep(.1)
    survivors=[process for process in selected.values() if same_process(process)]
    print('Graceful shutdown timed out; forcing verified remaining webapp processes to stop.',flush=True)
    for process in survivors:send(process,signal.SIGKILL)
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        if not any(same_process(process) for process in survivors):
            print('Previous webapp servers stopped.')
            return
        time.sleep(.1)
    raise RuntimeError('Verified webapp processes remain after forced shutdown.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--frontend',action='store_true')
    args=parser.parse_args()
    try:stop_servers(args.root,args.frontend)
    except (RuntimeError,PermissionError) as exc:raise SystemExit(str(exc))

if __name__=='__main__':main()
