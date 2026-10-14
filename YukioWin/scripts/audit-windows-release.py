"""Audit downloaded Windows binaries; all sessions are isolated test fixtures."""
import argparse
import ctypes
from ctypes import wintypes
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import uuid
import zipfile

p = argparse.ArgumentParser()
p.add_argument('--exe', required=True)
p.add_argument('--out', required=True)
p.add_argument('--tag', default='v0.4.6')
a = p.parse_args()
exe = Path(a.exe).resolve()
out = Path(a.out).resolve()
out.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(Path.cwd()))
from PIL import ImageGrab
from yukio.answer_bridge import decode_question
from yukio.question import QuestionCardLayout
from yukio.l10n import set_language
set_language('zh')
u = ctypes.WinDLL('user32', use_last_error=True)
u.SetProcessDPIAware()
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.IsWindowVisible.argtypes = [wintypes.HWND]
u.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
u.SetForegroundWindow.argtypes = [wintypes.HWND]
u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
checks = []

def run(args, **kw):
    print('RUN', ' '.join(map(str,args)), flush=True)
    return subprocess.run(list(map(str,args)), check=True, timeout=kw.pop('timeout',120), **kw)

def wait(fn, label, seconds=20):
    end = time.monotonic()+seconds
    while time.monotonic()<end:
        value = fn()
        if value: return value
        time.sleep(.15)
    raise AssertionError('Timed out: '+label)

def windows(pid):
    rows=[]
    callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    @callback
    def enum(hwnd, _):
        owner=wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
        if owner.value==pid and u.IsWindowVisible(hwnd):
            cls=ctypes.create_unicode_buffer(256);title=ctypes.create_unicode_buffer(1024);rect=wintypes.RECT()
            u.GetClassNameW(hwnd,cls,256);u.GetWindowTextW(hwnd,title,1024);u.GetWindowRect(hwnd,ctypes.byref(rect))
            rows.append(dict(hwnd=hwnd,cls=cls.value,title=title.value,rect=[rect.left,rect.top,rect.right,rect.bottom]))
        return True
    u.EnumWindows(enum,0)
    return rows

def find(pid, cls=None, title=None):
    return next((w for w in windows(pid) if (cls is None or w['cls']==cls) and (title is None or w['title']==title)),None)

def click(x,y):
    u.SetCursorPos(round(x),round(y));time.sleep(.1)
    u.mouse_event(2,0,0,0,0);u.mouse_event(4,0,0,0,0)

def capture(name):
    ctypes.windll.dwmapi.DwmFlush()
    ImageGrab.grab().save(out/(name+'.png'))

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')

def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')

def launch(label):
    root=out/label;root.mkdir(exist_ok=True)
    env=dict(os.environ,YUKIO_HOME=str(root/'home'),DEEPCODE_CONFIG_DIR=str(root/'deepcode'),
             YUKIO_ANSWER_BRIDGE_DIR=str(root/'answers'),YUKIO_STATE_FILE=str(root/'state.txt'))
    write(root/'home/settings.json',dict(source='deepcode',language='zh',scale=1.0,skin='yukio',
        hideWhenIdle=False,automaticUpdates=False,follow=True,petVisible=True,originX=620,originY=450))
    proc=subprocess.Popen([str(exe),'--allow-multiple','--pet-only'],env=env)
    wait(lambda: find(proc.pid,'YukioPet'),'pet visible')
    return root,env,proc

def stop(proc):
    if proc.poll() is None:
        subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True)
        proc.wait(timeout=10)

def audit_assets():
    downloads=out/'downloads';downloads.mkdir(exist_ok=True)
    run(['gh','release','download',a.tag,'--repo','leozhang8654/yukio-desktop-pet',
         '--pattern','YukioDesktop*','--pattern','*win.json','--pattern','SHA256SUMS.txt','--pattern','RELEASES',
         '--dir',downloads],timeout=240)
    sums={name:sha for sha,name in (line.split(None,1) for line in (downloads/'SHA256SUMS.txt').read_text().splitlines() if line.strip())}
    verified={}
    for f in downloads.iterdir():
        if f.name in sums:
            digest=hashlib.sha256(f.read_bytes()).hexdigest()
            assert digest==sums[f.name],f.name
            verified[f.name]=digest
    feed=json.loads((downloads/'releases.win.json').read_text())['Assets']
    latest=next(x for x in feed if x['Version']==a.tag[1:] and x['Type']=='Full')
    payload=downloads/latest['FileName']
    assert latest['SHA256'].lower()==hashlib.sha256(payload.read_bytes()).hexdigest()
    assert latest['SHA1'].lower()==hashlib.sha1(payload.read_bytes()).hexdigest()
    assert latest['Size']==payload.stat().st_size
    portable=out/'portable'
    with zipfile.ZipFile(downloads/'YukioDesktop-win-Portable.zip') as z:z.extractall(portable)
    portable_exe=portable/'current/Yukio.exe'
    assert hashlib.sha256(portable_exe.read_bytes()).digest()==hashlib.sha256(exe.read_bytes()).digest()
    for skin in ('yukio','qianxia'):
        run([portable_exe,'--check','--skin',skin])
        image=out/('portable-'+skin+'-all-states.png')
        run([portable_exe,'--snapshot',image,'--skin',skin])
        assert image.is_file()
    installed=exe.parent/'_internal'
    packed=portable_exe.parent/'_internal'
    for f in packed.rglob('*'):
        if f.is_file():
            relative=f.relative_to(packed)
            assert (installed/relative).is_file(),str(relative)
            assert hashlib.sha256(f.read_bytes()).digest()==hashlib.sha256((installed/relative).read_bytes()).digest(),str(relative)
    write(out/'download-hashes.json',verified)
    return dict(verified_assets=len(verified),feed_version=latest['Version'],portable_matches_installer=True,
                portable_both_skins_all_states=True)

def audit_deepcode():
    root,env,proc=launch('deepcode-states')
    session=str(uuid.uuid4());project=root/'deepcode/projects/audit';project.mkdir(parents=True)
    log=project/(session+'.jsonl')
    observed=[]
    def message(role,**kw):
        obj=dict(id=str(uuid.uuid4()),sessionId=session,role=role,content='',createTime=stamp(),visible=True)
        obj.update(kw)
        with log.open('a',encoding='utf-8') as f:f.write(json.dumps(obj,ensure_ascii=False)+'\n')
    def index(status):
        write(project/'sessions-index.json',dict(originalPath=str(project),entries=[dict(id=session,
            summary='DeepSeek Windows 专项检查',status=status,createTime=stamp(),updateTime=stamp())]))
    def state(expected):
        def current():
            try:return (root/'state.txt').read_text(encoding='utf-8').splitlines()[0]==expected
            except (OSError,IndexError):return False
        wait(current,expected,25)
        observed.append(expected);capture('deepcode-'+expected)
        assert proc.poll() is None
    try:
        message('user',content='开始本机验证');index('processing');state('thinking')
        tools=[('read',{'file_path':'中文目录/说明.txt'},'read_file'),
               ('ReadImage',{'file_path':'test.png'},'view_image'),
               ('edit',{'file_path':'测试.py'},'write_file'),
               ('bash',{'command':'pytest -q'},'verify'),
               ('WebSearch',{'query':'测试'},'read_web'),
               ('unknown_audit_tool',{},'default_work')]
        for name,args,expected in tools:
            call=str(uuid.uuid4())
            message('assistant',messageParams={'tool_calls':[dict(id=call,type='function',function=dict(name=name,arguments=json.dumps(args)))]})
            state(expected)
            message('tool',content='{"ok":true}',messageParams={'tool_call_id':call})
        index('ask_permission');state('question_for_user')
        index('processing');state('thinking')
        index('failed');state('failed')
        index('processing');message('user',content='修复后继续');state('thinking')
        message('assistant',content='已完成本机验证');state('respond');state('task_complete')
        message('user',content='新任务');state('thinking')
        index('interrupted');state('idle')
        text=(root/'home/error.log').read_text(encoding='utf-8')
        assert 'Traceback' not in text,text
        return dict(observed=observed,unique_states=sorted(set(observed)),
                    scope='Downloaded executable reading controlled Deep Code log/index fixtures on Windows')
    finally:stop(proc)

def audit_bridge(scenario):
    root,env,proc=launch('bridge-'+scenario)
    node=None
    try:
        wait(lambda:(root/'answers/listener-deepseek').exists(),'DeepSeek listener')
        result=root/'result.json'
        node=subprocess.Popen(['node',str(Path(__file__).with_name('audit-deepseek-fixture.mjs')),
            str(exe.parent/'_internal/integrations/deepseek/bridge.mjs'),str(root/'answers'),scenario,str(result)],env=env)
        req=wait(lambda:next((root/'answers').glob('*/request.json'),None),'bridge request')
        request=json.loads(req.read_text(encoding='utf-8'))
        question=decode_question(request['questions'][0])
        wait(lambda:find(proc.pid,'YukioQuestion'),'question card')
        time.sleep(.6)
        window=find(proc.pid,'YukioQuestion')
        layout=QuestionCardLayout(question,can_open_chat=False,scale=1)
        x,y,w,h=layout._option_rects[0]
        capture('bridge-'+scenario+'-card')
        card_point=(window['rect'][0]+x+w/2,window['rect'][1]+y+h/2)
        write(root/'click-debug.json',dict(card_window=window,card_point=card_point))
        # Deliver the native card event to the enumerated instance, independent
        # of the hosted runner's terminal stealing foreground mouse input.
        u.SetCursorPos(round(card_point[0]),round(card_point[1]))
        u.PostMessageW(window['hwnd'],0x0202,0,0)
        if scenario!='question':
            review=wait(lambda:find(proc.pid,title=question.header),'approval review')
            # Derive button positions from the same released native widget layout.
            import tkinter as tk
            from tkinter import ttk
            from yukio.approval_review import present
            tkroot=tk.Tk();tkroot.withdraw()
            style=ttk.Style(tkroot);style.theme_use('clam')
            style.configure('TLabel',font=('Segoe UI',10))
            style.configure('TButton',font=('Segoe UI',10),padding=(12,8))
            clone=present(tkroot,question,lambda _:None);clone.update_idletasks()
            label=question.options[0 if scenario=='allow' else 1].label
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)
            button=next(w for w in descendants(clone) if isinstance(w,ttk.Button) and w.cget('text')==label)
            offset=(button.winfo_rootx()-clone.winfo_rootx()+button.winfo_width()/2,
                    button.winfo_rooty()-clone.winfo_rooty()+button.winfo_height()/2)
            clone.destroy();tkroot.destroy()
            review=find(proc.pid,title=question.header)
            origin=wintypes.POINT();u.ClientToScreen(review['hwnd'],ctypes.byref(origin))
            target=(origin.x+offset[0],origin.y+offset[1])
            write(root/'click-debug.json',dict(card_window=window,card_point=card_point,
                review=review,client_origin=[origin.x,origin.y],button_offset=offset,button_point=target))
            capture('bridge-'+scenario+'-review')
            assert not (req.parent/'answer-0.json').exists(),'Approval sent before confirmation'
            u.SetForegroundWindow(review['hwnd']);time.sleep(.3)
            click(*target)
            time.sleep(.8);capture('bridge-'+scenario+'-after-click')
        wait(lambda:result.exists(),'DeepSeek acknowledgement',30)
        report=json.loads(result.read_text(encoding='utf-8'))
        assert node.wait(timeout=5)==0 and report['accepted'],report
        call=report['calls'][0]
        if scenario=='question':
            assert '中文回答：可以' in call['prompt']['text'] and 'permissions' not in call['prompt'],call
        elif scenario=='allow':
            assert call['prompt']['permissions']==[dict(toolCallId='audit-only-1',permission='allow')]
        else:
            assert call['denied'] and report['entry']['status']=='permission_denied'
        assert (req.parent/'receipt-0.json').is_file()
        return dict(accepted=True,scope='Native packaged card click to bundled adapter with controlled manager, no live model')
    finally:
        if node is not None and node.poll() is None:node.terminate();node.wait(timeout=5)
        stop(proc)

for name,fn in [('downloads-portable-update-feed',audit_assets),('deepcode-native-states',audit_deepcode),
                *[(f'deepseek-native-{s}',lambda s=s:audit_bridge(s)) for s in ('question','allow','deny')]]:
    print('AUDIT',name,flush=True)
    try:checks.append(dict(name=name,ok=True,detail=fn()))
    except Exception:checks.append(dict(name=name,ok=False,error=traceback.format_exc()));capture(name+'-failure')
    write(out/'audit-report.json',dict(checks=checks,all_passed=all(c['ok'] for c in checks)))
    print(json.dumps(checks[-1],ensure_ascii=False),flush=True)
sys.exit(0 if all(c['ok'] for c in checks) else 1)
