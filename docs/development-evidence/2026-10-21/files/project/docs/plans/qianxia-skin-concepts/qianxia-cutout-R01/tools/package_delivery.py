from pathlib import Path
from PIL import Image,ImageDraw
import json,hashlib,zipfile,html,numpy as np,shutil
r=Path(__file__).resolve().parents[1]
if (r/"REWORK_REQUIRED.md").exists():
 raise SystemExit("R01 is rejected and frozen; create a new round for fixes.")
labels={'idle':'待机','thinking':'思考','read_file':'读文件','view_image':'看图片','write_file':'写文件','verify':'验证','read_web':'浏览网页','default_work':'工作中','respond':'回答','task_complete':'完成','question_for_user':'等待回应','failed':'遇到问题'}
partnames={'touching-hand':'拨球的手','orb':'悬浮球（可见部分）','hand-and-stylus':'手与检查笔','left-hand':'画面左手','right-hand':'画面右手','hand-and-probe':'手与探针','pointing-hand':'点按手（投影遮挡处保留）','trackball-hand':'轨迹球上的手','hand-and-card':'手与卡片','pressing-hand':'按按钮的手','button-cap':'按钮顶面（可见部分）','iris-left':'画面左眼：虹膜、瞳孔与高光','iris-right':'画面右眼：虹膜、瞳孔与高光'}
notes={'idle':'球的缺口是手指遮住的位置，确认选区后补齐隐藏球面。底座固定。','thinking':'托腮手和节点投影固定，只准备眼部。','read_file':'三张投影与交叠双手固定，只准备眼部。','read_web':'手的下沿被投影遮住；保留可见截口，后续用固定投影遮挡。','default_work':'掌根与球的接触边界保留，球体和控制台暂不移动。','task_complete':'按设计整张静止，不拆袖子，不补眼睛。','question_for_user':'手和按钮顶面已分别提取，底座保留原位；遮挡处和移动露底在确认选区后补。'}
reports=json.loads((r/'review/mask-report.json').read_text());assert len(reports)==34;assert all(x['passed'] for x in reports)
manifest=[];sections=[]
for p in sorted((r/'source').glob('*.png')):
 state=p.stem.split('-',1)[1];ref=r.parent/'qianxia-refine-R02/candidates'/p.name;assert p.read_bytes()==ref.read_bytes();im=Image.open(p).convert('RGBA');a=np.array(im);union=np.zeros(a.shape[:2],np.uint8);items=[]
 for mp in sorted((r/'masks'/state).glob('*.png')):
  part=mp.stem;m=np.array(Image.open(mp));union=np.maximum(union,m);cut=np.array(Image.open(r/'parts'/state/(part+'.png')));assert np.array_equal(cut[:,:,:3],a[:,:,:3]);assert np.array_equal(cut[:,:,3],((a[:,:,3].astype(np.uint16)*m.astype(np.uint16)+127)//255).astype('uint8'))
  row=next(x for x in reports if x['state']==state and x['part']==part);row['visual_review']='static candidate inspected; user approval pending';row['dynamic_review']='not started';d=f'review/{state}/{part}'
  items.append(f'<details {"open" if not part.startswith("iris") else ""}><summary>{partnames[part]} <span>待你验收</span></summary><div class="pair"><figure><figcaption>原图选区 · 200%</figcaption><img src="{d}/overlay-200.png"></figure><figure><figcaption>轮廓 · 200%</figcaption><img src="{d}/contour-200.png"></figure></div><a href="{d}/four-backgrounds-200.png"><img class="four" src="{d}/four-backgrounds-200.png" alt="棋盘格、黑、白、洋红背景"></a><p><a href="{d}/source-100.png">局部原图 100%</a> · <a href="parts/{state}/{part}.png">透明部件 PNG</a> · <a href="masks/{state}/{part}.png">蒙版 PNG</a></p></details>')
 out=r/'review'/state;out.mkdir(exist_ok=True);base=Image.new('RGBA',im.size,'#777781');base.alpha_composite(im);t=Image.new('RGBA',im.size,(0,235,120,0));t.putalpha(Image.fromarray((union.astype(float)*.38).astype('uint8')));base.alpha_composite(t);base.save(out/'all-selections.png')
 sections.append(f'<section id="{state}" data-state="{state}"><h2>{labels[state]}</h2><p>{notes.get(state,"手与握持道具作为一个联动组；头颈、家具及设备底座保持固定。")}</p><div class="pair overview"><figure><figcaption>R02 原图（等比展示）</figcaption><img src="source/{p.name}"></figure><figure><figcaption>本轮全部选区（绿色）</figcaption><img src="review/{state}/all-selections.png"></figure></div>{"".join(items) if items else "<p>此状态没有待移动部件，不需要抠图。</p>"}</section>')
 manifest.append({'state':state,'source':str(p.relative_to(r)),'size':list(im.size),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'unchanged_from_R02':True,'parts':[x['part'] for x in reports if x['state']==state]})
(r/'review/mask-report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2))
# Complete unscaled 200% eye evidence pages, row spacing computed from image height.
files=sorted((r/'review').glob('*/iris-*/four-backgrounds-200.png'))
for page in range(4):
 items=files[page*6:(page+1)*6];cw=max(Image.open(p).width for p in items)+20;rh=max(Image.open(p).height for p in items)+30;canvas=Image.new('RGB',(cw*2,rh*3),'#dedee3');draw=ImageDraw.Draw(canvas)
 for j,p in enumerate(items):x=(j%2)*cw;y=(j//2)*rh;canvas.paste(Image.open(p),(x,y+24));draw.text((x+3,y+3),p.parts[-3]+'/'+p.parts[-2],fill='black')
 canvas.save(r/'review'/f'eyes-inspection-{page+1}.png')
(r/'input-manifest.json').write_text(json.dumps({'source_round':'R02','design_sha256':hashlib.sha256((r/'reference/animation-design.md').read_bytes()).hexdigest(),'files':manifest},ensure_ascii=False,indent=2))
qa={'status':'awaiting_user_cutout_review','operation_parts':12,'iris_parts':22,'structure':'34/34 single-component, zero opaque holes, zero transparent-background selections','source_images_unchanged':12,'part_rgb_is_exact_source_rgb':True,'user_approval':False,'eyelids_made':False,'background_repair_made':False,'animation_encoded':False,'playback_review':False,'app_installed':False,'scope_notes':notes}
(r/'qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2))
readme='''# 千夏抠图候选 R01 · 等待用户检查

本轮完成 34 个可见部件候选：12 个操作部件（手、手持道具、悬浮球、按钮顶面）及 22 个虹膜层（十一种露脸状态，每种两眼，含瞳孔与高光）。本轮没有制作动画、眼皮、隐藏区域补画或安装。

[打开逐状态验收页](index.html)。每个部件提供原图、绿色选区、轮廓、棋盘格／黑／白／洋红背景，支持点击打开大图。反馈时说“状态＋部位＋哪里多了或少了”即可。

## 目前检查

- 十二张输入与 R02 原文件逐字节一致。透明部件的 RGB 逐像素来自原图，只按蒙版改变 alpha，没有重画人物或道具。
- 34 个候选均为一个连通块，内部不透明漏选孔洞为 0，误选全透明背景像素为 0。数字只说明结构，不代替你的选区验收。
- 已查看手部原图、轮廓及 200% 多背景；查看十一状态眼部原图及提取结果。后续移动和闭眼效果未测，不能以本报告宣布动画通过。
- 保留 SAM 2.1 初选参数与原始候选，以及手工描边及局部修正记录。首次手部 SAM 档案来自 ../qianxia-animation-R01/rigs/；本包 reference/hand-sam/ 保存对应记录及初选蒙版。

## 请重点检查

1. 手指是否完整，黑边是否顺畅，有没有夹入袖子或头发颜色。
2. 手与检查笔、探针和卡片是否选成了正确的一组。
3. 眼部层是否包含完整虹膜、瞳孔、高光，是否带入不应移动的眼白或睫毛。
4. 球和按钮的缺口、网页手部的截口是原图遮挡，不是这轮凭空补画。请对照原图判断可见选区；隐藏部分待确认后补。

思考的托腮手、读文件的双手和三张投影、完成状态整体按新设计保持固定。完成状态没有眼部层。头颈、家具、投影及符号不做整体漂移。

## 已记录的后续任务与顺序

**当前关口：用户先检查抠图。未经确认，不开始制作动画。**

1. 确认选区后，以按钮手部做第一套校准：补出手移开后露出的袖子和按钮背景，修复被手挡住的按钮轮廓，设置固定袖口和短行程按压；按钮顶面运动，底座固定。
2. 根据本次反馈修选区并制作补底与遮挡：笔与手、探针与手、卡片与手联动；键盘双手错开；轨迹球手保持接触。读文件与完成状态主体固定。
3. 在已确认的眼部选区基础上制作眼白补底、固定眼框与独立眼皮。完成状态不补眼睛。头颈与家具固定。
4. 按《千夏十二状态动画设计方案》制作。按钮校准后，以写文件、验证、等待回应三个状态作为首轮节奏标尺，再完成其他状态。一次性动作不反复播放；完成状态保持静止。
5. 编码后回读，检查最大位移、接缝、允许区域外变化、循环。循环状态实际播放至少三轮；一次性状态检查进入、长时间停留、新事件重触发，完成状态检查持续静止及切换。
6. 动画通过后才进入接入、安装的独立交付。当前没有更换桌面 App、正式资源或发布内容。

设计方案已按原文件复制到 [reference/animation-design.md](reference/animation-design.md)，哈希写入 input-manifest.json。用户最新要求优先，五项后续工作均保留，没有因先验收抠图而取消。
'''
(r/'README.md').write_text(readme)
options=''.join(f'<option value="{k}">{v}</option>' for k,v in labels.items())
page='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>千夏抠图验收 R01</title><style>*{box-sizing:border-box}body{margin:0;background:#171925;color:#e9eaf5;font:16px/1.65 system-ui}main{max-width:1120px;margin:auto;padding:30px}a{color:#98d9ff}h1{margin:0}header p{max-width:850px}.notice{border-left:4px solid #ffc082;padding:12px 20px;background:#302c32}.toolbar{position:sticky;top:0;z-index:2;background:#171925ef;padding:14px 0;border-bottom:1px solid #42465c}select,button{font:inherit;border:1px solid #555b77;background:#2b3046;color:white;border-radius:6px;padding:7px 12px;margin-right:8px}section{border-top:1px solid #42465c;padding:25px 0}section h2{margin-top:0}.pair{display:flex;gap:20px;flex-wrap:wrap}.pair figure{margin:0;flex:1;min-width:240px;overflow:auto}.pair img{max-width:100%;height:auto}.overview img{width:288px}.four{max-width:100%;height:auto}figcaption{color:#b8c5e2;margin-bottom:8px}details{background:#252a3d;border-radius:10px;padding:18px;margin:18px 0}summary{cursor:pointer;font-size:18px;font-weight:600}summary span{font-size:13px;color:#ffc082;margin-left:12px}details .pair{margin-top:20px}.note{color:#bdc6dc}.stats{display:flex;gap:25px;color:#a3dfca;margin:20px 0}footer{padding:24px 0}</style><main><header><h1>千夏抠图验收 · R01</h1><p>34 个可见部件候选：12 个手／道具／按钮部件，以及 22 个虹膜层。先检查选区，再补底和制作动画。</p><div class="notice">请重点看：手指与黑边有没有缺失，有没有带入袖子颜色，手和道具是否完整。回复“状态＋部位＋问题”即可。当前等待你检查，尚未开始动画。</div><div class="stats"><span>12 张原图保持不变</span><span>34 个部件结构检查通过</span><span>用户验收：待确认</span></div><p><a href="README.md">任务记录与后续顺序</a> · <a href="reference/animation-design.md">动画设计方案</a> · <a href="qa.json">检查记录</a> · <a href="qianxia-cutout-review-R01.zip">下载抠图包</a></p></header><div class="toolbar"><label>查看状态 <select id="state"><option value="all">全部十二状态</option>'''+options+'''</select></label><button id="expand">展开所有部件</button><button id="collapse">收起部件</button></div>'''+''.join(sections)+'''<footer>下一步：你确认抠图 → 按钮补底和按压校准 → 其余手部联动、眼皮 → 三状态打样与十二状态制作 → 编码回读和实际播放验收 → 接入安装。完成状态按方案静止，不人为增加循环。</footer></main><script>document.querySelector('#state').onchange=e=>document.querySelectorAll('section[data-state]').forEach(s=>s.hidden=e.target.value!=='all'&&s.dataset.state!==e.target.value);document.querySelector('#expand').onclick=()=>document.querySelectorAll('details').forEach(d=>d.open=true);document.querySelector('#collapse').onclick=()=>document.querySelectorAll('details').forEach(d=>d.open=false);</script></html>'''
(r/'index.html').write_text(page)
# Keep original hand SAM evidence local to the handoff package.
old=r.parent/'qianxia-animation-R01'
for state in labels:
 for folder in (old/'rigs'/state).glob('*'):
  if not folder.is_dir():continue
  dest=r/'reference/hand-sam'/state/folder.name;dest.mkdir(parents=True,exist_ok=True)
  for name in ['initial-candidate-mask.png','segmentation.json']:
   if (folder/name).exists():shutil.copy2(folder/name,dest/name)
shutil.copy2(old/'review/sam-initial-report.json',r/'reference/hand-sam-model-report.json')
archive=r/'qianxia-cutout-review-R01.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(r.rglob('*')):
  if p.is_file() and p.suffix!='.zip' and '__pycache__' not in p.parts:z.write(p,p.relative_to(r))
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for row in reports:
  key=f'masks/{row["state"]}/{row["part"]}.png';assert hashlib.sha256(z.read(key)).hexdigest()==row['mask_sha256']
print(json.dumps({'parts':len(reports),'zip_bytes':archive.stat().st_size,'status':'awaiting user review'},ensure_ascii=False))
