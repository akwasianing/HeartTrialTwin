"""UI environment stays separate from the verified ML environment."""
import json,os,subprocess,time
from identity import *

def request(payload,runner=None):
    start=time.perf_counter()
    env={k:v for k,v in os.environ.items() if k in {'PATH','HOME','LANG','LC_ALL','TMPDIR'}}
    env.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    try:
        process=(runner or subprocess.run)([str(ROOT/'.venv-vector-rag/bin/python'),'-B',str(PACKAGE/'src/worker.py')],
            input=json.dumps(payload),cwd=ROOT,env=env,text=True,capture_output=True,timeout=60,check=False)
        require(process.returncode==0 and len(process.stdout.encode())<=12_000_000,'Worker failed')
        result=json.loads(process.stdout);require(type(result) is dict,'Invalid worker response')
    except subprocess.TimeoutExpired:
        result={'status':'ABSTAIN','error_code':'LOCAL_WORKER_TIMEOUT','answer':'The local operation exceeded 60 seconds. No automatic retry or fabricated result.'}
    except Exception:
        result={'status':'ABSTAIN','error_code':'LOCAL_WORKER_FAILURE','answer':'The local evidence/model environment is unavailable or failed integrity checks. No result was fabricated.'}
    result['client_elapsed_seconds']=time.perf_counter()-start
    return result
