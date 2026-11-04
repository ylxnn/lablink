"""Start only LabLink on localhost. No Docker, LLM or background package installs."""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
url = 'http://127.0.0.1:42112'
try:
    with urllib.request.urlopen(url + '/api/health', timeout=2) as response:
        if response.status == 200:
            print('LabLink is already available:', url)
            sys.exit(0)
except OSError:
    pass
if not (root/'backend/app/frontend/index.html').exists():
    raise SystemExit('Build frontend first: cd frontend; npm ci --workspaces=false; npm run build')
data = root/'.local'
data.mkdir(exist_ok=True)
env = dict(os.environ, PYTHONPATH=str(root/'backend'), SEED_DEMO='true')
args = [sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','42112']
with (data/'server.log').open('a', encoding='utf-8') as log:
    process = subprocess.Popen(args,cwd=root,env=env,stdout=log,stderr=log,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
for _ in range(40):
    time.sleep(.25)
    if process.poll() is not None:
        raise SystemExit('Startup failed. See .local/server.log')
    try:
        with urllib.request.urlopen(url+'/api/health',timeout=1):
            (data/'server.pid').write_text(str(process.pid))
            print('LabLink started:',url)
            print('Demo login: student@lablink.local / LabLink2026!')
            sys.exit(0)
    except OSError:
        pass
raise SystemExit('Startup timeout. See .local/server.log')
