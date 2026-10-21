from pathlib import Path
import json,hashlib,html,zipfile,importlib.util
import numpy as np
from PIL import Image,ImageDraw,ImageFont
r=Path(__file__).resolve().parents[1]
mod=importlib.util.spec_from_file_location('maskqa','/Users/developer/.codex/skills/cutout-animation-qa/scripts/check_masks.py');qa=importlib.util.module_from_spec(mod);mod.loader.exec_module(qa)
rows=[]
for p in sorted(r.glob('rigs/*/*/initial-candidate-mask.png')):
 state=p.parent.parent.name;part=p.parent.name;src=next((r/'source').glob('*-'+state+'.png'));a=np.array(Image.open(src).convert('RGBA'));m=np.array(Image.open(p));result,_=qa.inspect(a,m,1,0)
 result.update(state=state,part=part,status='initial candidate only; not approved',source_sha256=hashlib.sha256(src.read_bytes()).hexdigest());rows.append(result)
(r/'review/all-initial-mask-topology.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
checks=[]
for src in sorted((r/'source').glob('*.png')):
 ref=r.parent/'qianxia-refine-R02/candidates'/src.name
 checks.append({'file':src.name,'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'identical_to_R02':src.read_bytes()==ref.read_bytes()})
assert all(x['identical_to_R02'] for x in checks)
button=json.loads((r/'review/button-mask-05/report.json').read_text())
report={'stage':'native static display and animation preparation; no animation delivered','source_checks':checks,'native':{'platform':'macOS','mode':'real player offscreen renderer','all_12_decoded_and_drawn':True,'display_points':[192,208],'bubble_states':['write_file','verify','thinking','failed','question_for_user','task_complete'],'bubble_languages':['en','zh'],'bubble_overlaps_seen':False,'actual_desktop_install':False,'system_scaling_tested':False,'windows_tested':False,'held':'idle duplicate to satisfy diagnostic catalog, not a held-animation candidate'},'button_mask':{'round':'refinement-05','topology':button['masks'][0],'visual_review':'Reviewed original grid, contour and checker/black/white/magenta cutout at 500%; exterior outline preserved and stray pink island removed. Static candidate only; wrist attachment and moved-frame review pending.'},'other_masks':{'count':13,'status':'initial candidates not approved; includes rejected crop-refinement experiment'},'animation':{'background_plates':False,'eyelid_layers':False,'encoded_motion':False,'three_cycle_review':False,'independent_review':False},'production_resources_replaced':False}
(r/'qa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
# Repack native-rendered cells for readability. Image pixels are copied, not rerendered.
im=Image.open(r/'review/native-all-states.png');order=['idle','thinking','read_file','view_image','write_file','verify','read_web','respond','default_work','failed','question_for_user','task_complete'];sheet=Image.new('RGB',(4*208,3*244),'#f3f3f5');draw=ImageDraw.Draw(sheet)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',13)
for i,state in enumerate(order):
 x=(i%4)*208;y=(i//4)*244;draw.text((x+8,y+5),state,font=font,fill='#23232c');sheet.paste(im.crop((0,i*234+26,192,(i+1)*234)),(x+8,y+27))
sheet.save(r/'review/native-twelve-contact-sheet.png')
readme='''# 千夏：实际显示检查与动画准备 R01

本目录是动画准备材料，尚不是可安装的十二状态动画。静态成品仍以 ../qianxia-refine-R02/ 为准。

## 本轮完成

- 十二张 R02 底图原样归档，哈希逐一相同。没有再次改脸、改设备或移动按钮。
- 用当前 YukioPlayer 源码在独立构建目录编译，通过 YUKIO_ASSETS 加载候选；十二状态实际解码并按 192×208 点绘制。查看了原生截图，没有发现画布裁掉人物或桌椅。
- 查看六种状态的中英文真实 BubbleLayout 绘制结果：写文件、验证、思考、失败、等待回应、完成。未看到气泡遮住人物和设备；长文字按播放器现有规则截断。
- 使用本机 SAM 2.1 tiny 对十二状态做了 14 个部件初选，保存模型哈希、原图哈希、点、框、三个选项与诊断。自动结果均未直接作为成品。
- 单独精修等待回应的按压手部选区。最初选择遗漏部分黑边、夹带旁边粉色块；第三轮先移除独立的 41 像素误选，仍有描边缺失与 4 像素内部漏洞。随后按原图人工描边。第五轮采用局部 8 倍面积采样，得到 1 连通块、0 不透明漏洞、0 全透明背景像素；已查看轮廓与四背景 500% 图。

## 实际发现与取舍

- SAM 放大裁切复选并未改善所有部件，部分出现更多碎点或丢掉卡片。该实验另存 refinement-02，并标记退回，不能以模型分数高代替检查。
- 读文件的可见手与粉色半透明卡片已烘焙在同一张图里。初选把投影文字带进手部，不能直接做独立运动层。保持交叠双手和三张投影；动画应先完成投影/手的遮挡方案。
- 完成状态的袖子紧贴头发及桌面，初选还包含中间衣服。当前不移动这层，不增加被遮住的眼睛。
- 看图片、回答状态有背后拇指；写文件的小块也可能属于手指，不能一律删除小连通块。其余 13 个选区尚未批准。
- 按钮手部通过的是静态选区检查，尚未证明移动时袖口、按钮接触和补底正确。

## 后续任务（按顺序）

1. 以按钮手部作为第一套动作校准：补出手移开后露出的袖子和按钮背景，分离按钮顶面与固定底座，设置固定袖口和短行程按压。
2. 精修其余真正需要运动的手/道具选区：笔与手、探针与手、卡片与手分别联动；键盘两手错开动作；轨迹球与手保持接触。读文件与完成状态先固定主体，避免无意义运动。
3. 为露脸状态制作独立眼睛/眼皮层；完成状态不补眼睛。头颈与家具保持固定。
4. 编码后重新读取资源，检查最大位移、接缝、允许区域外变化及循环；每个状态实际播放至少三轮后再判定通过。
5. 动画完成后，才进入接入和安装的独立交付。当前没有更换桌面 App、正式资源或发布内容。

## 证据入口

- [十二状态原生绘制](review/native-twelve-contact-sheet.png)
- [真实中文气泡六状态](review/native-bubbles-zh.png)
- [按钮手部四背景放大](review/button-mask-05/01-candidate-mask/four-backgrounds-500.png)
- [检查记录](qa.json)
- [候选浏览页](index.html)

## 复现与限制

`tools/prepare_native.py` 准备独立诊断资源；`tools/segment.py` 保留首次 SAM 过程；`tools/refine_selections.py` 是退回的局部裁切实验；`tools/trace_button_hand.py` 复现第五轮手部选区。工具路径只对应本机实际环境。

native/Assets 的 held 是为满足目录校验而复制的待机占位，绝不能当作拖拽动画安装。原生检查为 macOS 离屏绘制，不等于桌面交互、不同系统缩放或 Windows 实机验收。尚未制作补底、眼皮、编码动画；未做独立评审。构建缓存不包含在准备材料 ZIP 内。
'''
(r/'README.md').write_text(readme)
labels={'idle':'待机','thinking':'思考','read_file':'读文件','view_image':'看图片','write_file':'写文件','verify':'验证','read_web':'浏览网页','default_work':'工作中','respond':'回答','task_complete':'完成','question_for_user':'等待回应','failed':'遇到问题'}
cards=''.join(f'<article><h3>{labels[p.stem.split("-",1)[1]]}</h3><img src="source/{p.name}" width="192" height="208"><p>R02 原图 · 未修改</p></article>' for p in sorted((r/'source').glob('*.png')))
page='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>千夏 · 动画准备 R01</title><style>body{margin:0;background:#171925;color:#e9eaf2;font:16px/1.7 system-ui}main{max-width:1100px;margin:auto;padding:32px}h1{margin-bottom:8px}a{color:#9cdcff}section{padding:24px 0;border-top:1px solid #363a50}img{max-width:100%;height:auto}article img{width:192px;height:208px;object-fit:contain}article{background:#282c40;border-radius:12px;text-align:center;padding:16px}article p{font-size:13px;color:#c4c9d9}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(224px,1fr));gap:16px}.note{color:#b9c7e4}.evidence{background:#fff;border-radius:12px;display:block}.button{max-width:750px}</style><main><h1>千夏 · 动画准备 R01</h1><p>已完成十二状态原生静态显示检查、六种气泡排版检查，以及按钮手部选区精修。</p><p class="note">本页不是动画成品。其余部件仍在准备，补底、眨眼和循环尚未制作。静态成品沿用 R02。</p><p><a href="README.md">详细记录与后续任务</a> · <a href="qa.json">检查数据</a> · <a href="../qianxia-refine-R02/index.html">静态底图 R02</a></p><section><h2>App 实际绘制</h2><p>macOS 原生离屏绘制；已查看十二张图，下面展示六状态的真实中文气泡。</p><img class="evidence" src="review/native-bubbles-zh.png"><p class="note">这些是诊断示例文字。尚未更换桌面 App，未测试 Windows 与系统缩放。</p></section><section><h2>按钮手部：保住描边，清除误选</h2><p>已按原图精修手的外轮廓，静态检查通过；移动后的接触与补底仍待检查。</p><img class="evidence button" src="review/button-mask-05/01-candidate-mask/four-backgrounds-500.png"></section><section><h2>十二张原尺寸预览</h2><p>192×208 等比例展示，全部与 R02 文件相同。</p><div class="grid">'''+cards+'''</div></section><section><h2>后续顺序</h2><ol><li>补齐按钮手部背后的袖子和按钮背景，制作第一套按压校准。</li><li>逐个修好手、笔、探针和卡片选区，保持握持与接触。</li><li>制作独立眨眼与轻动作，保持头颈、桌椅稳定。</li><li>编码后检查，并逐状态实际观看至少三轮，再进入接入交付。</li></ol></section></main></html>'''
(r/'index.html').write_text(page)
archive=r/'qianxia-animation-preparation-R01.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for folder in ['source','rigs','review','tools','prompts']:
  for p in sorted((r/folder).rglob('*')):
   if p.is_file() and '__pycache__' not in p.parts:z.write(p,p.relative_to(r))
 for n in ['README.md','index.html','qa.json','input-manifest.json']:z.write(r/n,n)
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for f in checks:assert hashlib.sha256(z.read('source/'+f['file'])).hexdigest()==f['sha256']
print(json.dumps({'source_unchanged':len(checks),'button_topology_passed':button['passed'],'zip_files':len(z.namelist()),'zip_bytes':archive.stat().st_size},ensure_ascii=False))
