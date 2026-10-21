from pathlib import Path
import json,zipfile,hashlib
r=Path(__file__).resolve().parents[1];q=json.loads((r/'qa.json').read_text());q['status']='本轮静态对齐自检通过；原生UI和动态项未测';q['visual_review']={'opened':['candidates/10-task_complete.png','review/10-position-comparison.png','review/10-contact-aligned-200.png','review/10-five-backgrounds-192.png','review/12-state-pairs-192-dark.png'],'conclusion':'趴桌遮脸、叠袖接触、对号牌、桌椅双腿完整；五背景目标画框无新增裁切或接缝','reviewer':'执行代理自检，非独立评审'}
q['series_limit']='消除完成状态约5预览像素的整体偏移；原绘制的家具边角仍有数个源图像素差异，不声称所有状态共用同一家具层。'
q['source_limit']='线上最新版本未重新验证；沿用有哈希记录的本地第九轮及R01修正。'
(r/'qa.json').write_text(json.dumps(q,ensure_ascii=False,indent=2))
(r/'changes.md').write_text('''# 千夏静态底图 R02：完成状态位置对齐

本轮仅改变 task_complete。将整张RGBA图层向下平移31个整数像素；不缩放、不插值、不重绘。其余11张与修正后的R01逐字节相同，包含已修正按钮黑边的 question_for_user。

## 为什么这样修

以其他11状态的家具位置共识为依据，没有默认把idle设为共享模板。完成状态灯条中心y=908.5，其他状态中位y=940；挡板下沿y=979，其他中位y=1010。箱子、桌脚和摆件的边缘匹配也主要支持约31–34像素的向下偏移。匹配中的低分和错配保留在 scene-landmarks.json，不把它们当作精确坐标。

最终取31像素：挡板下沿对齐到1010，灯条到939.5。人物、头发、袖子、对号牌和桌椅一起移动，保留原本的趴桌接触与有意遮脸。仅移动桌子会破坏袖口接触，因此没有拼接其他状态的家具。

## 已执行的检查

- 重新读取导出的1205×1306 RGBA PNG。反向位移后，对应RGBA像素差异为0；没有图像重采样。
- 原图底部31行没有可见像素。裁失像素为0；alpha总和与非零alpha像素数量不变，透明光晕随主体原样移动。
- 允许区域由原图和位移后非零alpha支持区域的并集预先定义；区域外可见像素及alpha变化为0。固定坐标上的alpha会随整体位移改变，不能称其“整图alpha位置不变”。
- 实际打开最终全图、位置对比、200%接触点图；查看192×208等比五背景预览与十二状态深灰对照。
- 其余11张输出哈希与R01输入一致。ZIP内12张PNG与交付文件哈希一致。

## 保留与限制

保留完成状态的埋头休息、脸部遮挡、袖子层次、对号牌、完整挡板和自然露出的双腿。其他状态的问号、多面板、设备及上轮按钮修复保持不变。

本轮消除的是整体位置偏移。原图家具细节还存在几像素绘制差异，例如完成状态桌脚最低不透明位置为1268，其他状态中位1265；在目标画框中小于1像素。本轮未统一这些原始轮廓，不声称已有像素完全相同的共享桌椅底层。

真实task bubble、系统缩放、原生播放、独立评审、分层补底与动态循环仍未测或未制作。本轮没有程序修改、正式资源替换、安装或发布。

## 使用

打开 index.html 比较R01和R02；qianxia-refine-R02-12-png.zip含当前整套12张PNG。上一轮R01目录保留可回退。input-manifest.json / qa.json记录输入输出哈希与检查，edit-regions/记录平移和允许范围，review/保存证据，tools/可复现本轮测量与输出。
''')
labels=['待机','思考','读文件','看图片','写文件','验证','浏览网页','工作中','回答','完成','等待回应','遇到问题']
html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>千夏 R02 · 完成状态对齐</title><style>*{box-sizing:border-box}body{margin:0;background:#171923;color:#edf0f7;font:15px/1.6 system-ui}main{max-width:1440px;margin:auto;padding:30px}h1{margin:0;font-size:30px}p,small{color:#bdc4d5}.tag{font-size:12px;letter-spacing:.14em;color:#8de1d5}.note{padding:14px 18px;background:#28343d;border-left:3px solid #8de1d5}nav{display:flex;gap:8px;flex-wrap:wrap;margin:22px 0}button,select,a{font:inherit;border-radius:8px;border:1px solid #465068;background:#2a3040;color:#edf0f7;padding:8px 12px;text-decoration:none}button{cursor:pointer}button.active{background:#415961;border-color:#8de1d5}label{margin-right:18px}.panels{display:grid;grid-template-columns:1fr 1fr;gap:16px}.panel{padding:12px;border:1px solid #414a5c;border-radius:10px;max-height:80vh;overflow:auto}h2{font-size:16px;margin:0 0 12px}.canvas{width:max-content;margin:auto;background:#35353d}.canvas img{display:block;object-fit:contain}.links{display:flex;gap:10px;flex-wrap:wrap;margin:24px 0}details{margin:20px 0}details img{max-width:100%}@media(max-width:650px){.panels{grid-template-columns:1fr}main{padding:15px}}</style><main><div class="tag">QIANXIA · R02 · STATIC ART</div><h1>保留趴桌姿态，对齐桌面位置。</h1><p>完成状态整体下移31像素 · 无重绘或插值 · 其余11张保持R01文件</p><div class="note">按钮黑边修正已继承。本轮对齐挡板下沿，保留所有人物与道具接触；原家具轮廓的细微绘制差异仍在。</div><nav id="states"></nav><label>背景 <select id="bg"><option value="#35353d">深灰</option><option value="#fff">白</option><option value="#000">黑</option><option value="#ff00ff">洋红</option><option value="checker">棋盘格</option></select></label><label>尺寸 <select id="scale"><option value="fit">192 × 208</option><option value="1">原图100%</option><option value="2">原图200%</option></select></label><label><input type="checkbox" id="diff">固定坐标差异</label><p id="info"></p><div class="panels"><section class="panel"><h2>R01 / 修正前</h2><div class="canvas"><img id="before" alt="R01"></div></section><section class="panel"><h2>R02 / 当前候选</h2><div class="canvas"><img id="after" alt="R02或固定坐标差异"></div></section></div><div class="links"><a href="qianxia-refine-R02-12-png.zip">下载12张PNG</a><a href="changes.md">修改记录</a><a href="qa.json">检查报告</a><a href="input-manifest.json">输入与哈希</a><a href="../qianxia-refine-R01/index.html">上一轮R01</a></div><details open><summary>位置对照 · 左为参照状态，中为旧完成，右为本轮完成</summary><p>思考状态仅用于展示坐标差异；位移依据来自11状态的测量共识。</p><img src="review/10-position-comparison.png" alt="对齐前后"></details><details><summary>完成状态 · 五背景192×208</summary><img src="review/10-five-backgrounds-192.png" alt="五背景检查"></details><details><summary>十二状态对照 · 左R01 / 右R02</summary><img src="review/12-state-pairs-192-dark.png" alt="十二状态"></details><small>源画布尺寸不变；原图全部可见像素保留。实际UI、系统缩放、原生播放及动态验收未测。本轮只交付静态底图。</small></main><script>
const records=RECORDS,labels=LABELS;let selected=9;const el=id=>document.getElementById(id);records.forEach((r,i)=>{const b=document.createElement('button');b.textContent=String(i+1).padStart(2,'0')+' '+labels[i];b.onclick=()=>{selected=i;render()};el('states').append(b)});
function render(){const r=records[selected],f=r.file;el('before').src='source/'+f;el('after').src=(el('diff').checked?'review/'+f.replace('.png','-diff.png'):'candidates/'+f)+'?v='+r.output_sha256.slice(0,12);let scale=el('scale').value;for(const id of ['before','after']){el(id).style.width=(scale==='fit'?192:r.size[0]*Number(scale))+'px';el(id).style.height=(scale==='fit'?208:r.size[1]*Number(scale))+'px'}for(const c of document.querySelectorAll('.canvas')){const bg=el('bg').value;c.style.background=bg==='checker'?'conic-gradient(#aaa 25%,#ddd 0 50%,#aaa 0 75%,#ddd 0) 0 0 / 16px 16px':bg}el('info').textContent=r.changed_vs_R01?'整图下移31px。按相同内容坐标比较，RGBA差异0；裁失0。差异模式显示的是固定画布坐标上的位移变化。':'与R01逐字节一致。'+(selected===10?' 已包含按钮黑边接缝修正。':'');[...el('states').children].forEach((b,i)=>b.classList.toggle('active',i===selected))}['bg','scale','diff'].forEach(id=>el(id).onchange=render);render();</script></html>'''
(r/'index.html').write_text(html.replace('RECORDS',json.dumps(q['files'],ensure_ascii=False)).replace('LABELS',json.dumps(labels,ensure_ascii=False)))
with zipfile.ZipFile(r/'qianxia-refine-R02-12-png.zip','w',zipfile.ZIP_DEFLATED) as z:
 for f in q['files']:z.write(r/f['output_file'],f['file'])
 for name in ['changes.md','qa.json','input-manifest.json']:z.write(r/name,name)
with zipfile.ZipFile(r/'qianxia-refine-R02-12-png.zip') as z:
 assert z.testzip() is None
 for f in q['files']:assert hashlib.sha256(z.read(f['file'])).hexdigest()==f['output_sha256']
assert sum(x['changed_vs_R01'] for x in q['files'])==1
assert q['files'][9]['transported_rgba_mismatches']==0 and q['files'][9]['clipped_visible_pixels']==0
assert all(x['outside_allowed_visible_or_alpha_changes']==0 for x in q['files'])
print('12 ZIP PNG hashes match; CRC pass; 11 unchanged; task_complete integer translation verified.')
