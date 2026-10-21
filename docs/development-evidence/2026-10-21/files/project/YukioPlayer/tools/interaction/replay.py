"""Export deterministic Python solver traces for the shared cross-language suite."""
import sys,json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'YukioWin'))
from yukio.throw_physics import ThrowPhysics,load_config

def replay():
 c=load_config(ROOT/'YukioPlayer/Resources/Assets');cases=json.loads((ROOT/'tests/interaction/scenarios.json').read_text())['cases'];out=[]
 for case in cases:
  p=ThrowPhysics(c,**{k:v for k,v in case.items() if k!='id'});rows=[];events=[]
  for i in range(960):
   p.advance(1/120)
   if i%4==0:rows.append({'step':i+1,'x':p.x,'y':p.y,'angle':p.angle,'phase':p.phase,'vx':p.vx,'vy':p.vy})
   events += [{'time':e.time,'normal':list(e.normal),'speed':e.speed} for e in p.events]
  out.append({'id':case['id'],'rows':rows,'events':events,'exhaustions':p.exhaustions})
 return {'version':1,'cases':out}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args();args.out.write_text(json.dumps(replay(),indent=2)+'\n')
