"""Opt-in native Windows test; never reports native success from another OS."""
import json,os,platform,tempfile,time,hashlib
from pathlib import Path


def run(destination):
    if os.name != 'nt':
        raise RuntimeError('This check requires a native Windows desktop session')
    from . import app as app_module,win32
    from .settings import Settings
    win32.set_dpi_aware()
    output=Path(destination);output.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='yukio-interaction-'))
    config=temp/'settings.json';config.write_text(json.dumps({'follow':False,'showBubble':False,'showCards':False,'showQuestionCard':False,'throwInteraction':True,'scale':1.0}))
    original_settings=app_module.Settings;original_sources=app_module.default_sources
    app_module.Settings=lambda:Settings(str(config))
    app_module.default_sources=lambda provider:[]

    class CheckApp(app_module.PetApp):
        def __init__(self):
            self.samples=[];self.cases=[];self.started=time.monotonic();self.next_case=0;self.check_done=False
            super().__init__([])
        def _render_throw(self):
            began=time.perf_counter();super()._render_throw();self.samples.append((time.perf_counter()-began)*1000)
        def tick(self):
            super().tick()
            if time.monotonic()-self.started>30:
                self.finish_check('timeout');return
            if self.flight is None:
                if self.next_case>=3:self.finish_check('completed');return
                rect,dpi=win32.monitor_geometry(*win32.cursor_pos())
                self.pet.x=round((rect[0]+rect[2])/2-96*dpi);self.pet.y=round((rect[1]+rect[3])/2-104*dpi)
                self._drag_dpi=dpi;self._drag_began()
                velocity=[(0,0),(900,350),(-1900,1100)][self.next_case]
                self.next_case+=1;self._start_throw(velocity)
        def _finish_throw(self):
            if self.flight is not None:
                self.cases.append({'phase':self.flight.phase,'events':self.flight.event_count,'exhaustions':self.flight.exhaustions,'screen':self._throw_room,'dpi':self._throw_dpi})
                if self._throw_canvas is not None:self._throw_canvas.save(output/f'case-{self.next_case}.png')
            super()._finish_throw()
        def finish_check(self,status):
            if self.check_done:return
            self.check_done=True
            values=sorted(self.samples);assets=Path(self.library.assets_root)
            report={'status':status,'platform':platform.platform(),'python':platform.python_version(),'frames':len(values),'p95Ms':values[int((len(values)-1)*.95)] if values else None,'maxMs':max(values,default=0),'cases':self.cases,'resourceHashes':{str(p.relative_to(assets)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (assets/'interaction').glob('*') if p.is_file()},'manualInputAndOcclusion':'pending; perform checklist in docs/animation-review/throw-and-dizzy/README.md'}
            (output/'windows-native.json').write_text(json.dumps(report,indent=2));win32.quit_loop()
    instance=None
    try:
        instance=CheckApp();instance.control.start_timer(app_module.FRAME_MS)
        win32.run_message_loop(pre_dispatch=instance._pre_dispatch)
        return 0 if instance.check_done and len(instance.cases)==3 else 1
    finally:
        if instance is not None:instance.shutdown()
        app_module.Settings=original_settings;app_module.default_sources=original_sources
