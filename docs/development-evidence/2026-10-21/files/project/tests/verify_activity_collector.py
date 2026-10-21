"""Real Swift/Python CLI integration using explicitly synthetic local sessions."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = [[str(ROOT/'YukioPlayer/.build/debug/YukioPlayer')], [sys.executable,'-m','yukio']]


def line(**values): return json.dumps(values)+'\n'


def run(i, args, ok=True):
    p = subprocess.run(COMMANDS[i]+list(map(str,args)),cwd=ROOT/'YukioWin',capture_output=True,text=True,timeout=20)
    assert (p.returncode==0)==ok,(i,p.returncode,p.stderr)
    return [json.loads(s) for s in p.stdout.splitlines()] if ok else p


def await_status(paths, condition):
    end=time.monotonic()+20
    while time.monotonic()<end:
        try:
            values=[json.loads(p.read_text()) for p in paths]
            if all(condition(v) for v in values):return values
        except (OSError, ValueError):pass
        time.sleep(.05)
    raise AssertionError('Timed out waiting for collector status')


def canonical(rows):
    return sorted([{k:v for k,v in row.items() if k!='sequence'} for row in rows],key=lambda r:r['event_id'])


def main():
    processes=[]
    with tempfile.TemporaryDirectory(prefix='yukio-collector-integration-') as directory:
        d=Path(directory);sessions=d/'sessions';sessions.mkdir()
        dbs=[d/'swift.db',d/'python.db'];statuses=[d/'swift.json',d/'python.json']
        args=lambda i:['--activity-collect',dbs[i],'--sessions-dir',sessions,'--status-file',statuses[i]]
        try:
            for i in range(2):
                processes.append(subprocess.Popen(COMMANDS[i]+list(map(str,args(i))),cwd=ROOT/'YukioWin',stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True))
            await_status(statuses,lambda s:s['state']=='waiting')
            # Reject duplicate DB writers, including the other implementation, and shared status owners.
            for i in range(2):
                run(1-i,args(i)+['--seconds','.1'],ok=False)
                run(1-i,['--activity-collect',d/('extra%d.db'%i),'--sessions-dir',sessions,'--status-file',statuses[i],'--seconds','.1'],ok=False)
            a=sessions/'a.jsonl'
            a.write_text(line(type='session_meta',id='synthetic-a')+line(type='task_started',turn_id='ta')+line(type='function_call',name='shell',call_id='same'))
            (sessions/'b.jsonl').write_text(line(type='session_meta',id='synthetic-b')+line(type='item_completed',item={'type':'CommandExecution','id':'same','exit_code':1}))
            values=await_status(statuses,lambda s:s['events_saved_this_run']==5)
            with a.open('a') as f:f.write(line(type='function_call_output',call_id='same',output={'success':True})[:-1])
            old_times={s['backend']:s['updated_at'] for s in values}
            await_status(statuses,lambda s:s['updated_at']!=old_times[s['backend']] and s['state']=='waiting')
            assert all(len(run(i,['--activity-history',dbs[i]]))==5 for i in range(2))
            with a.open('a') as f:f.write('\n')
            (sessions/'c.jsonl').write_text(line(type='session_meta',id='synthetic-c'))
            await_status(statuses,lambda s:s['events_saved_this_run']==7)
            for p in processes:p.send_signal(signal.SIGTERM)
            for p in processes:
                out,err=p.communicate(timeout=10);assert p.returncode==0,err
                assert json.loads(out.splitlines()[-1])['state']=='stopped'
            rows=[run(i,['--activity-history',dbs[i]]) for i in range(2)]
            assert canonical(rows[0])==canonical(rows[1])
            assert [r for r in rows[0] if r.get('session_id')=='synthetic-a'][-1]['result']['call_outcome']=='succeeded'
            assert [r for r in rows[0] if r.get('session_id')=='synthetic-b'][-1]['result']['association']=='unlinked'
            for i in range(2):
                result=run(i,args(i)+['--seconds','.1'])[-1]
                assert result['events_saved_this_run']==0
            (sessions/'d.jsonl').write_text(line(type='session_meta',id='synthetic-d'))
            # Resume using the opposite implementation against the same DB and cursor.
            for i in range(2):
                assert run(1-i,args(i)+['--seconds','.1'])[-1]['events_saved_this_run']==1
                assert len(run(i,['--activity-history',dbs[i]]))==8
            for i in range(2):
                important=d/('important%d.json'%i);important.write_text('important user file')
                run(i,['--activity-collect',d/('unused%d.db'%i),'--sessions-dir',sessions,'--status-file',important,'--seconds','.1'],ok=False)
                assert important.read_text()=='important user file'
            print(json.dumps({'synthetic':True,'native_windows':False,'implementations':2,'matching_evidence_rows':8,
                'verified':['live discovery of new files','partial-line wait','results remain in their own session','graceful SIGTERM writes stopped','restart has no duplicate evidence','cross-implementation cursor resume','exclusive DB and status leases','unrelated status file preserved']},indent=2))
        finally:
            for p in processes:
                if p.poll() is None:
                    p.terminate()
                    try:p.communicate(timeout=10)
                    except subprocess.TimeoutExpired:p.kill();p.communicate()

if __name__=='__main__':main()
