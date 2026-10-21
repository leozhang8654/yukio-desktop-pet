from pathlib import Path
from PIL import Image
import numpy as np,cv2,json,hashlib
out=Path(__file__).resolve().parent;root=out.parents[1]/'qianxia-motion-R02'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
frozen=json.loads((root/'review/frozen-hashes.json').read_text());actual={p:sha(root/p) for p in frozen};mismatches=[p for p in frozen if frozen[p]!=actual[p]]
manifest=json.loads((root/'motion/motion.json').read_text());report={'frozen_manifest_sha256':sha(root/'review/frozen-hashes.json'),'frozen_count':len(frozen),'hash_mismatches':mismatches,'actual_sha256':actual,'states':[]}
opened=[]
def read(p):
 opened.append(str(p));return np.array(Image.open(p).convert('RGBA'))
def tile(a,i,w,h,c):return a[(i//c)*h:(i//c+1)*h,(i%c)*w:(i%c+1)*w]
for s in manifest['states']:
 n=s['id'];srcpath=next((root/'inputs/source').glob('*-'+n+'.png'));src=read(srcpath).astype('float32')/255;src[:,:,:3]*=src[:,:,3:4];src=cv2.resize(src,(384,416),interpolation=cv2.INTER_AREA);src[:,:,:3]/=np.maximum(src[:,:,3:4],1e-8);src[src[:,:,3]==0]=0;src=np.clip(src*255+.5,0,255).astype('uint8');stored=read(root/'rigs'/n/'source-2x.png')
 a=read(root/'motion'/s['asset']);dec=read(root/'motion'/s['decodedAsset']);allow=np.array(Image.open(root/'rigs'/n/'allowed-mask-2x.png'))>0;opened.append(str(root/'rigs'/n/'allowed-mask-2x.png'));w,h=384,416;frames=[tile(a,i,w,h,s['columns']) for i in range(max(s['sequence'])+1)]
 outside=max(int(np.any(f!=stored,axis=2)[~allow].sum()) for f in frames)
 # deliberately conservative independent fixed regions: upper head y<140; bottom furniture y>=300
 fixed=np.zeros((416,384),bool);fixed[:140]=True;fixed[300:]=True
 fixedchange=max(int(np.any(f!=stored,axis=2)[fixed].sum()) for f in frames)
 r={'state':n,'source_raw_path':str(srcpath),'raw_source_matches_normalized_source':bool(np.array_equal(src,stored)),'webp_equals_decoded_png':bool(np.array_equal(a,dec)),'body_frame_count':len(frames),'sequence_count':len(s['sequence']),'duration_ms':sum(s['durationsMs']),'sequence_duration_lengths_match':len(s['sequence'])==len(s['durationsMs']),'positive_durations':min(s['durationsMs'])>0,'loopStart_valid':0<=s['loopStart']<len(s['sequence']),'loop_seam_pixels_equal':bool(np.array_equal(frames[s['sequence'][-1]],frames[s['sequence'][s['loopStart']]])),'outside_allowed_max_changed_pixels':outside,'independent_fixed_head_top_and_lower_furniture_changed_pixels':fixedchange,'enter_hold_single_frame_tail':len(set(s['sequence'][s['loopStart']:]))==1 if s.get('mode')=='enter_then_hold' else None,'first_time_frame24_ms':sum(s['durationsMs'][:s['sequence'].index(24)]) if n=='respond' else None}
 b=s.get('blink')
 if b:
  e=read(root/'motion'/b['asset']);edec=read(root/'motion'/b['decodedAsset']);r['eyes_webp_equals_decoded_png']=bool(np.array_equal(e,edec));ea=np.array(Image.open(root/'rigs'/n/'eyes-allowed-2x.png'))>0;opened.append(str(root/'rigs'/n/'eyes-allowed-2x.png'));x,y,bw,bh=b['x'],b['y'],b['width'],b['height'];eo=al=0;valid=True
  for fi,row in enumerate(b['frames']):
   for ei in row:
    t=tile(e,ei,bw,bh,b['columns']);valid &= t.shape==(bh,bw,4)
    baseline=frames[fi][y:y+bh,x:x+bw];diff=np.any(t!=baseline,axis=2);eo=max(eo,int(diff[~ea[y:y+bh,x:x+bw]].sum()));al=max(al,int((t[:,:,3]!=baseline[:,:,3]).sum()))
  r.update({'eye_bounds':[x,y,x+bw,y+bh],'blink_body_mapping_valid':len(b['frames'])==len(frames) and all(len(v)==6 for v in b['frames']) and bool(valid),'eyes_outside_allowed_max_changed_pixels':eo,'eyes_alpha_max_changed_pixels':al})
 report['states'].append(r)
report['R08_input_hash_mismatches']=[p for p in actual if p.startswith('inputs/') and ((root.parent/'qianxia-cutout-R08'/p.removeprefix('inputs/')).exists()) and sha(root.parent/'qianxia-cutout-R08'/p.removeprefix('inputs/'))!=actual[p]]
# numerical reports read only after complete source/candidate visual inspection
machine={p.name:json.loads(p.read_text()) for p in (root/'review').glob('*-machine.json')};machine['encoded-validation.json']=json.loads((root/'review/encoded-validation.json').read_text());report['maker_machine_reports_read']=list(machine);report['maker_machine_summary_not_visual_approval']=machine['encoded-validation.json']['all_machine_checks_passed'];report['read_and_decoded_images']=opened
report['additional_read_sha256']={str(p.relative_to(root)):sha(p) for p in [root/'tools/eyes.py',root/'tools/build_motion.py',root/'tools/Preview.swift',root/'index.html',root/'reference/animation-design.md']}
(out/'resource-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['actual_sha256','read_and_decoded_images']},ensure_ascii=False,indent=2))
