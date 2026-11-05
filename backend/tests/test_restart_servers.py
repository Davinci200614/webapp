"""Verified restart selection, PID identity and real suspended-tree shutdown."""
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from scripts import restart_servers as restart


class RestartSelectionTests(unittest.TestCase):
    root=Path('/tmp/test-webapp')

    def process(self,pid,parent=1,cwd=None,args=None,state='S',started='123'):
        return restart.Process(pid,parent,state,started,cwd or self.root/'backend',
            args or ('python','-m','uvicorn','app.main:app','--port','8000'))

    def test_only_matching_project_and_port_are_selected_with_reload_children(self):
        processes={
            10:self.process(10),
            11:self.process(11,parent=10,args=('python','-c','multiprocessing.spawn')),
            20:self.process(20,cwd=Path('/tmp/hakathon/backend')),
            30:self.process(30,args=('python','-m','uvicorn','app.main:app','--port','9000')),
            40:self.process(40,args=('python','unrelated.py')),
            41:self.process(41,args=('python','unrelated.py','uvicorn','app.main:app')),
        }
        selected,roots=restart.select_processes(processes,self.root)
        self.assertEqual(set(selected),{10,11});self.assertEqual(roots,{10:'backend'})

    def test_frontend_is_only_selected_when_requested(self):
        frontend=self.process(50,cwd=self.root/'frontend',args=('node','/tmp/vite/bin/vite.js','--port','5173'))
        self.assertEqual(restart.select_processes({50:frontend},self.root)[0],{})
        self.assertEqual(set(restart.select_processes({50:frontend},self.root,True)[0]),{50})

    def test_pid_reuse_prevents_signal_to_replacement_process(self):
        previous=self.process(10)
        replacement=self.process(10,started='456')
        with patch.object(restart,'read_process',return_value=replacement),patch.object(restart.os,'kill') as kill:
            restart.send(previous,signal.SIGTERM)
        kill.assert_not_called()

    def test_timeout_escalates_only_verified_survivors(self):
        process=self.process(10)
        with patch.object(restart,'snapshot',return_value={10:process}),patch.object(restart,'same_process',side_effect=[True,True,True,False]),patch.object(restart.os,'kill') as kill,patch.object(restart.time,'monotonic',side_effect=[0,2,2,2]),redirect_stdout(io.StringIO()):
            restart.stop_servers(self.root,timeout=1)
        self.assertEqual([call.args[1] for call in kill.call_args_list],[signal.SIGTERM,signal.SIGKILL])

    def test_real_suspended_server_and_child_are_stopped(self):
        if not Path('/proc').is_dir():self.skipTest('Linux /proc required')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);backend=root/'backend';backend.mkdir();marker=root/'child'
            code="""import subprocess,sys,os,signal
from pathlib import Path
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
Path(sys.argv[1]).write_text(str(child.pid))
os.kill(os.getpid(),signal.SIGSTOP)
"""
            executable=backend/'uvicorn';executable.write_text(code)
            server=subprocess.Popen([sys.executable,str(executable),str(marker),'app.main:app','--port','8000'],cwd=backend)
            child=None
            try:
                deadline=time.monotonic()+3
                while time.monotonic()<deadline:
                    if marker.exists():
                        process=restart.read_process(server.pid)
                        if process and process.state=='T':break
                    time.sleep(.02)
                else:self.fail('Test server did not suspend')
                child=restart.read_process(int(marker.read_text()))
                self.assertIsNotNone(child)
                with redirect_stdout(io.StringIO()):restart.stop_servers(root,timeout=3)
                server.wait(timeout=3)
                self.assertFalse(restart.same_process(child))
            finally:
                if server.poll() is None:
                    os.kill(server.pid,signal.SIGCONT);server.terminate();server.wait(timeout=3)
                if child and restart.same_process(child):os.kill(child.pid,signal.SIGTERM)
