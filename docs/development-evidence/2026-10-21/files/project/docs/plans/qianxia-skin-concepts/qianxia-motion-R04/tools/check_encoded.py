"""Read the files on disk, including all body frames and six-level eye atlases."""
from pathlib import Path
import json,hashlib
import numpy as np
from PIL import Image
import cv2
R=Path(__file__).resolve().parents[1]
data=json.loads((R/'motion/motion.json').read_text());results=[]
assert len(data['states'])==12
for s in data['states']:
    state=s['id'];src=np.array(Image.open(R/f'rigs/{state}/source-2x.png'));allow=np.array(Image.open(R/f'rigs/{state}/allowed-mask-2x.png'))>0
    sheet=Image.open(R/'motion'/s['asset']).convert('RGBA');decoded=Image.open(R/'motion'/s['decodedAsset']).convert('RGBA')
    cols=s['columns'];n=max(s['sequence'])+1;assert len(s['sequence'])==len(s['durationsMs'])
    assert 0<=s['loopStart']<len(s['sequence']);assert min(s['durationsMs'])>0
    frames=[np.array(sheet.crop((i%cols*384,i//cols*416,(i%cols+1)*384,(i//cols+1)*416))) for i in range(n)]
    outside=sum(int(np.any(f!=src,axis=2)[~allow].sum()) for f in frames)
    limits={'write_file':2.5,'question_for_user':3};timeline=json.loads((R/f'rigs/{state}/timeline.json').read_text())
    peak=timeline['maximum_displacement_display_px'];checks={'webp_equals_native_decoded_png':np.array_equal(np.array(sheet),np.array(decoded)),'outside_allowed_zero':outside==0,'motion_within_design_limit':peak<=limits.get(state,5),'loop_tail_matches_start':np.array_equal(frames[s['sequence'][-1]],frames[s['sequence'][s['loopStart']]])}
    eyelid_outside=0;alpha_errors=0;closed_iris=0
    if s['blink']:
        b=s['blink'];eyes=Image.open(R/'motion'/b['asset']).convert('RGBA');assert np.array_equal(np.array(eyes),np.array(Image.open(R/'motion'/b['decodedAsset']).convert('RGBA')))
        permitted=np.array(Image.open(R/f'rigs/{state}/eyes-allowed-2x.png'))>0
        irismasks=[]
        for p in (R/f'inputs/masks/{state}').glob('iris-*.png'):irismasks.append(cv2.resize(np.array(Image.open(p)),(384,416),interpolation=cv2.INTER_AREA)>192)
        iris=np.logical_or.reduce(irismasks)
        assert len(b['frames'])==n
        for f,row in zip(frames,b['frames']):
            assert len(row)==6
            for level,index in enumerate(row,1):
                x=index%b['columns']*b['width'];y=index//b['columns']*b['height'];patch=np.array(eyes.crop((x,y,x+b['width'],y+b['height'])))
                frame=f.copy();x0,y0=b['x'],b['y'];frame[y0:y0+b['height'],x0:x0+b['width']]=patch
                eyelid_outside+=int(np.any(frame!=f,axis=2)[~permitted].sum());alpha_errors+=int((frame[:,:,3]!=f[:,:,3]).sum())
                if level==6:
                    rgb=frame[:,:,:3].astype(float)/255;r,g,blue=rgb.transpose(2,0,1)
                    saturated_iris=((g-r>.035)&(g>.35))|((r-g>.04)&(g-blue>.20)&(g>.40))
                    closed_iris+=int((saturated_iris&iris).sum())
        checks.update(eyelids_outside_eye_zero=eyelid_outside==0,eyelids_alpha_unchanged=alpha_errors==0,closed_no_coloured_iris=closed_iris==0)
    else:checks['complete_no_eye_asset']=state=='task_complete'
    if state=='task_complete':checks['complete_fully_static']=n==1 and np.array_equal(frames[0],src)
    if s['mode']=='enter_then_hold':checks['entry_not_in_hold_loop']=s['loopStart']==len(s['sequence'])-1
    rec={'state':state,'checks':{k:bool(v) for k,v in checks.items()},'passed':all(checks.values()),'outside_changed_pixels':outside,'eyelid_outside_changed_pixels':eyelid_outside,'eyelid_alpha_changed_pixels':alpha_errors,'closed_coloured_iris_pixels':closed_iris,'maximum_displacement_display_px':peak,'unique_body_frames':n,'real_playback':'pending: new larger-amplitude round','independent_review':'pending'}
    results.append(rec)
    print(state,'PASS' if rec['passed'] else 'FAIL',[(k,v) for k,v in checks.items() if not v],flush=True)
input_hashes=json.loads((R/'reference/input-hashes.json').read_text())
assert all(hashlib.sha256((R/p).read_bytes()).hexdigest()==h for p,h in input_hashes.items())
report={'scope':'encoded resources and numerical invariants only','all_machine_checks_passed':all(x['passed'] for x in results),'approved_R08_inputs_unchanged':True,'states':results,'real_playback':'not yet completed','visual_quality_not_implied':True}
(R/'review/encoded-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
