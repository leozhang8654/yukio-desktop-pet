import json,math,unittest
from pathlib import Path
from yukio.throw_physics import ThrowPhysics,load_config
from yukio.drag_velocity import DragVelocityTracker,release_velocity,should_throw
ROOT=Path(__file__).resolve().parents[2]
C=load_config(ROOT/'YukioPlayer/Resources/Assets')
CASES=json.loads((ROOT/'tests/interaction/scenarios.json').read_text())['cases']

def make(case):
 return ThrowPhysics(C,**{k:v for k,v in case.items() if k!='id'})

class ThrowTests(unittest.TestCase):
 def test_only_a_deliberate_flick_throws(self):
  for v in ((0,0),(180,150),(-420,0),(float('nan'),0)):
   self.assertFalse(should_throw(v,C))
  for v in ((850,0),(-850,0),(0,-850),(500,500)):
   self.assertTrue(should_throw(v,C))
  tracker=DragVelocityTracker()
  for i in range(11):tracker.add(i*.01,i*12,0)
  self.assertTrue(should_throw(tracker.velocity(.1),C))
  tracker.add(.25,120,0)
  self.assertFalse(should_throw(tracker.velocity(.25),C))
 def test_shared_scenarios_containment_and_single_dizzy(self):
  for case in CASES:
   p=make(case); phases=[]; ids=[]
   for _ in range(1200):
    p.advance(1/120); phases.append(p.phase); ids.extend(e.event_id for e in p.events)
    l,b,r,t=p.bounds()
    self.assertGreaterEqual(min(p.x+l,p.y+b,p.room[0]-p.x-r,p.room[1]-p.y-t),-0.0001,case['id'])
    self.assertTrue(all(math.isfinite(v) for v in [p.x,p.y,p.vx,p.vy]))
   self.assertEqual(p.phase,'normal',case['id']); self.assertEqual(p.exhaustions,0,case['id'])
   self.assertEqual(len(ids),len(set(ids)))
   self.assertEqual(sum(a!='dizzy' and b=='dizzy' for a,b in zip(phases,phases[1:])),1)
 def test_analytic_freefall_and_impact_time(self):
  p=make(CASES[0]); floor=-p.bounds()[1]
  for _ in range(24): p.advance(1/120)
  self.assertAlmostEqual(p.y,650-0.5*2400*0.2**2,places=8)
  self.assertEqual(p.phase,'airborne')
  events=[]
  for _ in range(100): p.advance(1/120); events+=p.events
  hit=next(e for e in events if e.normal==(0,1))
  self.assertAlmostEqual(hit.time,math.sqrt(2*(650-floor)/2400),places=6)
  self.assertAlmostEqual(hit.speed,math.sqrt(2*2400*(650-floor)),places=4)
 def test_render_rate_independence(self):
  results=[]
  for hz in (30,60,120,144):
   p=make(CASES[1])
   for _ in range(hz): p.advance(1/hz)
   results.append((p.x,p.y,p.time,p.phase,p.event_count))
  for row in results[1:]:
   for a,b in zip(row[:3],results[0][:3]): self.assertAlmostEqual(a,b,places=7)
   self.assertEqual(row[3:],results[0][3:])
 def test_floor_support_no_contact_storm(self):
  p=make(CASES[0]); p.y=-p.bounds()[1]
  for _ in range(60): p.advance(1/120)
  self.assertTrue(p.ground); self.assertEqual(p.event_count,1); self.assertEqual(p.phase,'dizzy')
 def test_wall_does_not_trigger_dizzy(self):
  p=make(CASES[1])
  for _ in range(45):
   p.advance(1/120)
   if any(e.normal[0] for e in p.events):
    self.assertFalse(p.ground); self.assertEqual(p.phase,'airborne'); return
  self.fail('wall missing')
 def test_energy_and_sleep_and_grab(self):
  p=make(CASES[5]); before=.5*(p.vx**2+p.vy**2)+C['gravity']*p.y
  for _ in range(400):
   p.advance(1/120)
   energy=.5*(p.vx**2+p.vy**2)+C['gravity']*p.y
   self.assertLessEqual(energy,before+0.001); before=energy
  pos=(p.x,p.y); p.advance(10); self.assertEqual((p.x,p.y),pos); self.assertGreater(p.dropped_time,9)
  p.grab(); p.advance(.1); self.assertEqual((p.x,p.y),pos); self.assertEqual(p.phase,'held')
 def test_strength_changes_duration_and_finishes_landing_pose(self):
  lengths=[]
  for down in (0,-600,-1200):
   p=make(CASES[0]);p.y=-p.bounds()[1];p.vy=down
   entered=None
   for _ in range(600):
    p.advance(1/120)
    if p.phase=='dizzy' and entered is None:
     entered=p.time
     self.assertGreaterEqual(entered-p.last_landing_time+1e-8,p.last_landing_duration)
    if p.phase=='recover':
     lengths.append(p.time-entered);break
  self.assertLess(lengths[0],lengths[1]);self.assertLess(lengths[1],lengths[2])
 def test_velocity_samples(self):
  t=DragVelocityTracker()
  for i in range(11): t.add(i*.01,i*10,0)
  self.assertAlmostEqual(t.velocity(.1)[0],1000,places=6)
  t.add(.25,100,0); self.assertEqual(t.velocity(.25),(0,0))
  t=DragVelocityTracker()
  for i in range(11): t.add(i*.01,i*10 if i<6 else 100-i*10,0)
  self.assertLess(t.velocity(.1)[0],0)
  t.add(.1,1e9,1e9); t.add(float('nan'),0,0)
  self.assertLess(t.velocity(.1)[0],0)
  self.assertEqual(DragVelocityTracker().velocity(0),(0,0))
  v=release_velocity((9000,9000),(0,0),C)
  self.assertAlmostEqual(math.hypot(*v),2600); self.assertEqual(v[0],v[1])

if __name__=='__main__': unittest.main()
