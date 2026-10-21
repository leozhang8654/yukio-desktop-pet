from pathlib import Path
import json,hashlib,html,argparse
p=argparse.ArgumentParser();p.add_argument('--round',required=True);p.add_argument('--eyes',required=True);p.add_argument('--hands',required=True);args=p.parse_args();b=Path(__file__).resolve().parents[2];r=b/args.round;reviews=[b/'qianxia-independent-review'/args.eyes,b/'qianxia-independent-review'/args.hands]
# Delivery requires real independent decisions, complete coverage, and exact reviewed bytes.
for d,n in zip(reviews,[22,12]):
 j=json.loads((d/'findings.json').read_text());assert '通过' in j['decision'] and '退回' not in j['decision'],d
 c=j['coverage'];assert c['total_assessed']==n and c['pass_static_visible_only']==n and c['rework_required']==0,d
 hs=json.loads((d/'frozen-hashes.json').read_text())
 for f,h in hs.items():
  old=Path(f);assert hashlib.sha256(old.read_bytes()).hexdigest()==h,old
  for folder in ['source','masks','parts']:
   if folder in old.parts:
    q=r.joinpath(*old.parts[old.parts.index(folder):]);assert hashlib.sha256(q.read_bytes()).hexdigest()==h,q;break
names={'idle':'待机','thinking':'思考','read_file':'读文件','read_web':'浏览网页','view_image':'查看图片','write_file':'输入文字','default_work':'常规工作','verify':'核验','respond':'回复','question_for_user':'等待回答','failed':'失败提示','task_complete':'完成'}
partnames={'iris-left':'左侧虹膜','iris-right':'右侧虹膜','touching-hand':'触球手','orb':'球体可见部分','hand-and-stylus':'手与笔','left-hand':'左侧手','right-hand':'右侧手','hand-and-probe':'手与探针','pointing-hand':'指向手','trackball-hand':'轨迹球上的手','hand-and-card':'手与卡片','pressing-hand':'按键手','button-cap':'按钮顶面可见部分'}
head='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>千夏 · 抠图待验收</title><style>*{box-sizing:border-box}body{margin:0;background:#151823;color:#eef0f8;font:16px/1.65 system-ui,sans-serif}header,main{max-width:1240px;margin:auto;padding:28px}h1{margin:0;font-size:30px}p{color:#bec8dd}nav{display:flex;gap:10px;flex-wrap:wrap}a{color:#80d9e4}nav a{padding:7px 12px;background:#252d42;border-radius:8px;text-decoration:none}section{padding:28px 0;border-bottom:1px solid #343c50}.state{display:flex;align-items:flex-start;gap:24px}.portrait{width:240px;height:auto;background:repeating-conic-gradient(#dce0e8 0% 25%,#f4f5f8 0% 50%) 50%/20px 20px;border-radius:12px}.parts{flex:1;min-width:0}article{background:#22283a;padding:18px;margin-bottom:16px;border-radius:12px}h3{margin:0 0 8px}.compare{display:flex;align-items:flex-start;gap:18px;overflow:auto}.compare img{max-width:none;image-rendering:pixelated}.compare figure{margin:0}.compare figcaption{color:#bdc5d8;margin-bottom:7px}details{margin-top:10px}details img{max-width:100%;image-rendering:pixelated}.badge{display:inline-block;padding:4px 10px;color:#ffe0ab;background:#57462e;border-radius:6px}footer{padding:30px;color:#c5cbdb}@media(max-width:700px){.state{display:block}.portrait{width:192px}.compare{display:block}.compare img{max-width:100%}}</style><header><h1>千夏 · 抠图检查</h1><p class="badge">内部独立评审已通过 · 等待你验收</p><p>请看手指和道具的黑色边线、指缝，以及不同底色下是否残留杂色。这里是静态可见部件；被手挡住的按钮、袖子和其他隐藏部分，要在你确认后再补全并制作动画。</p><nav>'''
body=[]
for src in sorted((r/'source').glob('*.png')):
 state=next((s for s in names if src.stem.endswith('-'+s)),None)
 if not state:continue
 head+=f'<a href="#{state}">{names[state]}</a>';parts=[]
 for m in sorted((r/'masks'/state).glob('*.png')):
  key=f'{state}/{m.stem}';label=partnames.get(m.stem,m.stem);parts.append(f'<article><h3>{label}</h3><div class="compare"><figure><figcaption>原图局部 · 100%</figcaption><img loading="lazy" src="review/{key}/source-100.png"></figure><figure><figcaption>抠图 · 200% · 棋盘格 / 黑 / 白 / 洋红</figcaption><img loading="lazy" src="review/{key}/four-backgrounds-200.png"></figure></div><details><summary>查看选区和描边对照</summary><img loading="lazy" src="review/{key}/overlay-200.png"><img loading="lazy" src="review/{key}/contour-200.png"></details><p><a href="parts/{key}.png">透明部件原文件</a> · <a href="masks/{key}.png">选区原文件</a></p></article>')
 if not parts:parts=['<p>完成状态保持整张静态原图，不补眼睛。</p>']
 body.append(f'<section id="{state}"><h2>{names[state]}</h2><div class="state"><a href="source/{src.name}"><img class="portrait" loading="lazy" src="source/{src.name}"></a><div class="parts">'+''.join(parts)+'</div></div></section>')
foot='<footer><p>确认抠图后，下一步是按钮手部动作校准，再依次处理其他手与道具、眼皮和动画检查。接入与安装另行交付。</p>'
for d,label in zip(reviews,['虹膜独立评审','手与道具独立评审']):foot+=f'<a href="../qianxia-independent-review/{d.name}/independent-review.md">{label}</a>　'
(r/'index.html').write_text(head+'</nav></header><main>'+''.join(body)+foot+'</footer></main></html>');print(r/'index.html')
