"""Launcher process lifecycle tests without sockets, package installs or credentials."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'app with spaces';self.root.mkdir()
        shutil.copy2(Path(__file__).resolve().parents[2]/'start.sh',self.root/'start.sh')
        for directory in ['backend/.venv/bin','frontend/node_modules/.bin','frontend/dist','bin']:
            (self.root/directory).mkdir(parents=True,exist_ok=True)
        (self.root/'backend/.env').write_text('PRIVATE_EXISTING_SETTING=preserve-me\n')
        (self.root/'frontend/dist/index.html').write_text('<div id="root"></div>')
        for name in ['vite','tsc']:
            p=self.root/'frontend/node_modules/.bin'/name;p.touch();p.chmod(0o755)
        fake='''#!/usr/bin/env python3
import os,sys,time,subprocess
from pathlib import Path
root=Path(os.environ['LAUNCHER_TEST_ROOT'])
name=Path(sys.argv[0]).name
if name=='node':sys.exit(0)
if name=='npm':
    if sys.argv[1:3]==['run','build']:
        (root/'built').touch();sys.exit(0)
    if os.environ.get('FAIL_FRONTEND')=='1':sys.exit(7)
    mode='frontend'
elif sys.argv[1:2]==['-c']:
    if 'print(sys.executable)' in sys.argv[2]:print(sys.argv[0])
    sys.exit(0)
elif sys.argv[1:3]==['-m','scripts.check_config']:
    print('Configuration checked without printing secrets.');sys.exit(0)
elif sys.argv[1:3]==['-m','scripts.ngrok_url']:
    print('https://launcher-test.ngrok.app');sys.exit(0)
elif sys.argv[1:3]==['-m','scripts.restart_servers']:
    (root/'restart-request').write_text(' '.join(sys.argv[3:]));sys.exit(0)
elif sys.argv[1:3]==['-m','uvicorn']:
    if os.environ.get('FINISH_BACKEND')=='1':
        (root/'backend-args').write_text(' '.join(sys.argv[1:]));sys.exit(0)
    mode='backend'
else:sys.exit(0)
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
(root/(mode+'-pids')).write_text(str(os.getpid())+' '+str(child.pid))
time.sleep(60)
'''
        for p in [self.root/'backend/.venv/bin/python',self.root/'bin/node',self.root/'bin/npm',self.root/'bin/ngrok']:
            p.write_text(fake);p.chmod(0o755)
        self.env={**os.environ,'PATH':str(self.root/'bin')+os.pathsep+os.environ['PATH'],
                  'LAUNCHER_TEST_ROOT':str(self.root)}
        self.env.pop('WEBAPP_PYTHON',None)

    def invoke(self,*args,**updates):
        return subprocess.run(['bash',str(self.root/'start.sh'),*args],env={**self.env,**updates},
                              cwd=self.temp.name,text=True,capture_output=True,timeout=12)

    def test_check_never_builds_starts_or_overwrites_environment(self):
        original=(self.root/'backend/.env').read_bytes()
        result=self.invoke('--check','--restart')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse((self.root/'built').exists())
        self.assertFalse((self.root/'restart-request').exists())
        self.assertFalse((self.root/'backend-pids').exists())
        self.assertEqual((self.root/'backend/.env').read_bytes(),original)
        self.assertNotIn('preserve-me',result.stdout+result.stderr)

    def test_default_builds_and_starts_one_worker_from_backend_directory(self):
        result=self.invoke(FINISH_BACKEND='1')
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertTrue((self.root/'built').exists())
        self.assertIn('--port 8000 --workers 1',(self.root/'backend-args').read_text())
        self.assertIn('http://localhost:8000',result.stdout)

    def test_existing_bundle_mode_skips_build_and_unknown_options_fail(self):
        result=self.invoke('--no-build',FINISH_BACKEND='1')
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertFalse((self.root/'built').exists())
        self.assertEqual(self.invoke('--dev','--no-build').returncode,2)
        self.assertEqual(self.invoke('--unknown').returncode,2)

    @staticmethod
    def stopped(pid):
        try:
            # Reparented grandchildren can briefly remain as zombies after a group signal.
            return Path(f'/proc/{pid}/stat').read_text().split()[2]=='Z'
        except FileNotFoundError:return True

    def test_dev_shutdown_stops_both_servers_and_their_children(self):
        if not shutil.which('setsid'):self.skipTest('setsid not available')
        process=subprocess.Popen(['bash',str(self.root/'start.sh'),'--dev'],env=self.env,
                                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            deadline=time.monotonic()+4
            while time.monotonic()<deadline:
                if all((self.root/(name+'-pids')).exists() for name in ['backend','frontend']):break
                time.sleep(.03)
            else:self.fail('Servers did not start')
            pids=[int(pid) for name in ['backend','frontend'] for pid in (self.root/(name+'-pids')).read_text().split()]
            process.terminate();self.assertEqual(process.wait(timeout=8),143)
            deadline=time.monotonic()+2
            while time.monotonic()<deadline and not all(self.stopped(pid) for pid in pids):time.sleep(.03)
            self.assertTrue(all(self.stopped(pid) for pid in pids),'A server or grandchild was left running')
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=8)

    def test_ctrl_z_shuts_down_servers_instead_of_suspending_launcher(self):
        import signal
        if not shutil.which('setsid'):self.skipTest('setsid not available')
        process=subprocess.Popen(['bash',str(self.root/'start.sh'),'--dev'],env=self.env,
                                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            deadline=time.monotonic()+4
            while time.monotonic()<deadline:
                if all((self.root/(name+'-pids')).exists() for name in ['backend','frontend']):break
                time.sleep(.03)
            else:self.fail('Servers did not start')
            pids=[int(pid) for name in ['backend','frontend'] for pid in (self.root/(name+'-pids')).read_text().split()]
            os.kill(process.pid,signal.SIGTSTP)
            self.assertEqual(process.wait(timeout=8),148)
            deadline=time.monotonic()+2
            while time.monotonic()<deadline and not all(self.stopped(pid) for pid in pids):time.sleep(.03)
            self.assertTrue(all(self.stopped(pid) for pid in pids),'Ctrl+Z left a server running')
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=8)

    def test_dev_frontend_failure_stops_backend(self):
        if not shutil.which('setsid'):self.skipTest('setsid not available')
        result=self.invoke('--dev',FAIL_FRONTEND='1')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('shutting down managed services',result.stderr)

    def test_restart_requests_verified_shutdown_before_starting(self):
        result=self.invoke('--restart','--no-build',FINISH_BACKEND='1')
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertIn(str(self.root),(self.root/'restart-request').read_text())
        self.assertTrue((self.root/'backend-args').exists())


class PortProbeTests(unittest.TestCase):
    def probe(self,port):
        import sys
        launcher=(Path(__file__).resolve().parents[2]/'start.sh').read_text()
        script=launcher.split("<<'PY'\n",1)[1].split('\nPY\n',1)[0]
        return subprocess.run([sys.executable,'-',str(port)],input=script,text=True,capture_output=True,timeout=3)

    def listener(self):
        import socket
        try:sock=socket.socket()
        except PermissionError:self.skipTest('Local sockets denied by this environment')
        self.addCleanup(sock.close)
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try:sock.bind(('127.0.0.1',0))
        except PermissionError:self.skipTest('Local sockets denied by this environment')
        sock.listen()
        return sock

    def test_probe_rejects_an_actual_listener(self):
        listener=self.listener()
        result=self.probe(listener.getsockname()[1])
        self.assertEqual(result.returncode,1)
        self.assertIn('already occupied',result.stderr)

    def test_probe_accepts_recently_closed_server_connections(self):
        import socket
        listener=self.listener();port=listener.getsockname()[1]
        client=socket.create_connection(('127.0.0.1',port),timeout=2)
        self.addCleanup(client.close)
        accepted,_=listener.accept();self.addCleanup(accepted.close)
        accepted.shutdown(socket.SHUT_WR)
        self.assertEqual(client.recv(1),b'')
        client.close();accepted.close();listener.close()
        result=self.probe(port)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_probe_uses_address_reuse_before_binding(self):
        import socket
        import sys
        from unittest.mock import MagicMock,patch,call
        launcher=(Path(__file__).resolve().parents[2]/'start.sh').read_text()
        script=launcher.split("<<'PY'\n",1)[1].split('\nPY\n',1)[0]
        probe=MagicMock()
        probe.__enter__.return_value=probe
        with patch.object(socket,'socket',return_value=probe),patch.object(sys,'argv',['probe','8000']):
            exec(compile(script,'launcher-port-probe','exec'),{})
        calls=probe.mock_calls
        self.assertLess(calls.index(call.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)),calls.index(call.bind(('127.0.0.1',8000))))
