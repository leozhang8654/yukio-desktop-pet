from pathlib import Path
import json,hashlib
out=Path(__file__).parent;root=out.parent.parent/'qianxia-cutout-R01';ix=json.loads((out/'inspection-index.json').read_text());hashes=json.loads((out/'frozen-hashes.json').read_text());machine=json.loads((out/'independent-machine-checks.json').read_text())
findings=[]
def add(id,targets,sev,kind,region,detail,fix,evidence):
 findings.append(dict(id=id,targets=targets,severity=sev,kind=kind,region=region,description=detail,recommendation=fix,evidence=evidence,requires_rework=True))
irises=[z['state']+'/'+z['part'] for z in ix if z['part'].startswith('iris')]
add('F01',irises,'medium','抗锯齿/轮廓','各虹膜完整外周；每件全图包围框见逐件记录，重点是裸露左右边与底边。','22件均可见阶梯、短横台阶或突出的深色边缘像素；原图柔和过渡被硬选区截断。200%白/洋红背景最清楚，100%也能见到不规则边缘。后读机器数据确认这22个mask只有0/255，导出非零alpha只有253/254，没有选区边缘覆盖率过渡。源图自身253/254透明度不是本问题，也不要求改为255。','逐件沿真实虹膜/高光轮廓精修选区，保留属于虹膜的描边厚度，为暴露边缘提供局部亚像素覆盖率；修掉突刺，不用全局腐蚀、膨胀或模糊替代轮廓判断。固定睫毛、眼白仍留在固定层。',['每件 evidence/{state}-{part}-reference.png','每件 review/{state}/{part}/four-backgrounds-200.png','evidence/backgrounds100-1.png 至 backgrounds100-6.png'])
add('F02',['read_file/iris-left'],'high','漏选高光',[441,526,463,547],'白色高光左侧被切出明显向内的黑/透明凹槽。原图该位置为连续的圆润白高光，候选在黑和洋红底上都呈咬缺。','恢复高光可见轮廓和抗锯齿，重新区分高光与旁边眼白；不能让颜色阈值产生凹洞。',['evidence/issue-detail-12.png'])
add('F03',['write_file/iris-right'],'medium','轮廓突起/凹陷',[614,512,638,549],'左上侧边出现凸出的深色块，靠近白色高光上方又向内缩成凹口，无法连续跟随原图虹膜边缘。','对照源图修正这段侧边，清除额外暗色凸块，恢复高光上方连续边线，再进行局部抗锯齿。',['evidence/issue-detail-13.png'])
add('F04',['idle/touching-hand'],'medium','误选袖口/颜色污染',[420,810,437,829],'下侧指缝与袖口接触位置残留粉色点及细边，黑底能看到粉色碎片；它们来自固定袖口。','沿手部黑色描边外侧清理粉色袖口残留，保留完整手指线，不扩大缺口。',['evidence/issue-detail-01.png'])
add('F05',['failed/hand-and-card'],'medium','误选头发/颜色污染',[346,591,415,643],'卡片左上圆角和斜上边保留浅绿色外缘，与原图邻接头发颜色一致，黑/洋红底成为浅绿描边。','剔除头发混入的像素，按卡片本身黑边保留抗锯齿；不要把整条黑色卡框向内削薄。',['evidence/issue-detail-02.png'])
add('F06',['failed/hand-and-card'],'medium','误选袖口',[326,680,376,760],'手的左外沿有长条粉色袖口残留，局部还有粉色点，已脱离原图语义成为部件外圈。','沿手部与袖口分界清理残留，保留属于手的黑色轮廓。',['evidence/issue-detail-03.png'])
add('F07',['failed/hand-and-card'],'high','漏选可见描边',[387,727,414,760],'手腕右下侧原图明确可见的一段黑色轮廓，在候选中被切掉；皮肤直接接透明背景，边缘形成斜截口。该线在原图中可见，不是隐藏结构。','恢复该段可见黑色描边及过渡，按原手腕曲线连接上下段，避免切进皮肤。',['evidence/failed-wrist.png'])
add('F08',['respond/hand-and-card'],'medium','误选袖口',[300,723,403,780],'手左下外缘带粉色细条；小指上方与卡片下沿之间带粉色袖口三角残片，黑底可明确分辨。','两处分开精修，以真实手部/卡片描边为边界排除固定袖口，不把整个手腕一起侵蚀。',['evidence/issue-detail-04.png'])
add('F09',['read_web/pointing-hand'],'medium','误选袖口/轮廓尖刺',[406,630,436,667],'手右上与袖口/头发交界带粉色片和突出的暗色尖刺，候选右缘不再是单纯手指轮廓。','去除粉袖口及相邻固定线条，保留手指真实外线。手下边被投影遮挡的截面可以保留，不需要补画。',['evidence/issue-detail-05.png'])
add('F10',['verify/hand-and-probe'],'medium','误选头发/颜色污染',[381,602,423,647],'探针装置左上斜边及左侧小凸台外缘带浅绿色头发细条。','排除邻接头发色，保留装置暗色边框的真实厚度与软边。',['evidence/issue-detail-06.png'])
add('F11',['verify/hand-and-probe'],'high','误选固定底座/针尖轮廓截切',[457,713,514,784],'针尖左下带入底座浅青色横弧的一小截；右侧和末端被几何直边截切，形成三角化边缘。源图针尖实际发光边缘与固定底座弧线应分开。','以原图可见探针和其实际发光边缘重新确定局部蒙版，排除固定底座横弧。逐像素核对针尖，不用一个直边多边形同时截取发光探针与底座。',['evidence/issue-detail-07.png','evidence/probe-base-junction.png'])
add('F12',['view_image/hand-and-stylus'],'medium','误选袖口',[437,746,464,777],'手指下端靠笔杆的凹槽中带入粉色袖口细片，黑底可见两小条粉色。','沿手指/笔杆外框精修凹槽，去除袖口残片，保持手和笔完整联动组。',['evidence/issue-detail-08.png'])
add('F13',['write_file/left-hand'],'medium','误选键盘',[367,792,415,819],'两处指尖之间及下沿带入粉色键帽/键盘边，黑底形成粉色尖片，属于固定键盘。','分别清理指缝和指尖下方键盘选区，保留指尖黑色轮廓与真实接触端。',['evidence/issue-detail-09.png'])
add('F14',['write_file/right-hand'],'medium','误选相邻粉色区域',[735,771,758,806],'最左侧手指外沿有粉色条状污染，与原图相邻粉色袖口/键盘区域连续。','对照原图外侧深色轮廓精修此段，排除粉色邻物，不削去手指描边。',['evidence/issue-detail-10.png'])
add('F15',['question_for_user/pressing-hand'],'medium','边缘颜色污染',[788,733,808,776],'手右侧外边带较亮的灰青色边条，源图该处紧邻青色投影/反光区域；候选在黑底产生灰白边。','局部重新判断手部黑边与邻接投影的分界及覆盖率，清理外缘灰青污染，保留皮肤内部原有光照。',['evidence/issue-detail-11.png'])
passnotes={'default_work/trackball-hand':'可见手指和接触端保留；左下斜截是原图设备遮挡边，本阶段允许。四背景未见必须退回的固定邻物误选。','idle/orb':'球体的可见黑边、内部星形标记和色带保留；左侧手指遮挡缺口与原图对应，不要求补画完整球体。','question_for_user/button-cap':'按钮可见上盖与底座分离；上缘手指遮挡缺口对应原图，不按完整椭圆补画。'}
parts=[]
for i,z in enumerate(ix):
 key=z['state']+'/'+z['part'];ids=[f['id'] for f in findings if key in f['targets']];box=z['bbox_with_margin'];bbox=[box[0]+10,box[1]+10,box[2]-10,box[3]-10];src=Path(z['source']).relative_to(root.resolve()).as_posix();mask='masks/'+key+'.png';candidate='parts/'+key+'.png'
 parts.append({'state':z['state'],'part':z['part'],'result':'rework_required' if ids else 'pass_static_visible_only','checked':True,'inspection_scales':[1,2],'additional_details_scales':[4,6] if any(key in f['targets'] and f['id']!='F01' for f in findings) else [],'backgrounds':['checker','black','white','magenta'],'bbox_xyxy':bbox,'finding_ids':ids,'conclusion':'; '.join(ids) if ids else passnotes[key],'source':src,'source_sha256':hashes[src],'mask':mask,'mask_sha256':hashes[mask],'candidate':candidate,'candidate_sha256':hashes[candidate],'reference_evidence':Path(z['reference']).relative_to(out.resolve()).as_posix(),'backgrounds_200':Path(z['backgrounds']).relative_to(root.resolve()).as_posix(),'backgrounds_100':f'evidence/backgrounds100-{i//6+1}.png'})
raw=[]
for k in hashes:raw.append({'path':str((root/k).resolve()),'use':'decoded and visually displayed in full nonzero-mask bounding crop at 100% and 200%' if not k.startswith('source/10-') else 'full original displayed; fixed state, no candidate required'})
preview=[]
for z in ix:
 for fn in ['overlay-200.png','contour-200.png','four-backgrounds-200.png']:preview.append(str((root/'review'/z['state']/z['part']/fn).resolve()))
displayed=[str(p.resolve()) for p in sorted((out/'evidence').glob('*.png'))]+[z['backgrounds'] for z in ix]+[str((root/'source'/n).resolve()) for n in ['01-idle.png','06-verify.png','07-read_web.png','10-task_complete.png','11-question_for_user.png']]
result={'reviewer':'Independent Codex subagent /root/cutout_independent_review; did not create candidates','round':'R01','decision':'退回','scope':'静态可见部件；未做动画/补底/眼皮评审','coordinate_system':'原始1205×1306图像；0-based x向右、y向下；ROI为[x0,y0,x1,y1)；left/right沿用文件名','review_order':'先逐件目视34件100%原图/候选与200%叠加轮廓四背景，再读mask-report.json及独立机器核验；其后补看100%四背景与400/600%细节。','coverage':{'total':34,'checked':34,'unchecked':0,'pass_static_visible_only':3,'rework_required':31},'frozen_hash_binding':hashes,'hash_verification':{'files':80,'mismatches':0},'findings':findings,'parts':parts,'opened_files':{'raw_files':raw,'candidate_review_pngs':preview,'visually_displayed_images':displayed,'machine_report_read_after_visual':str((root/'review/mask-report.json').resolve())},'machine_summary':'制作方报告34件components=1、opaque_hole_pixels=0、background_pixels=0；独立重算34件连通块均1、选入源图alpha=0像素均0、被选像素RGB均未改。22虹膜mask纯二值。拓扑通过不能替代语义与边缘通过。','limitations':['仅认可已露出的部件边界；没有隐藏结构完整性结论。','没有补底、眼皮、动画或原生播放，不作动态通过结论。','3件局部静态通过不等于整套通过。']}
(out/'findings.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
lines=['# R01 独立静态抠图评审','', '**结论：退回。34/34 件完成逐件检查，31 件需返工；3 件仅在本轮静态可见层范围通过。**','', '审查者：独立 Codex 子 Agent `/root/cutout_independent_review`，未参与制作。只读取委派范围内的原图、蒙版、透明部件、逐件 PNG、scope、冻结哈希及最后读取的机器报告；没有读取制作脚本、README、制作理由、聊天历史或旧评分，没有改动候选。','', '按独立评审规程先目视后读机器报告。每件从真实源 PNG 解码并按完整选区包围框裁出原图/原始mask/透明部件，100%显示；原图、选区叠加与轮廓200%逐件显示，棋盘格/黑/白/洋红四背景200%逐件显示。之后独立合成并实际打开全部34件100%四背景，另做400%与600%问题特写。逐件参考图不是缩小总览。完整打开的图像和参与显示的原始文件清单在 findings.json 的 opened_files；记录区分原始文件经裁片显示与直接整图显示。','', '坐标是原始 **1205×1306** 图像，0-based，x向右/y向下；区域写作 `[x0,y0,x1,y1)`。left/right严格沿用文件名。','', '## 冻结与机器核验','', '12张源图、34张mask、34张部件，共80个SHA-256全部与 frozen-hashes.json 一致。逐件的源图、mask及候选SHA-256逐项写入 findings.json，完整清单也内嵌在该文件；本报告只绑定这些字节。','', '制作方机器报告34件拓扑通过；独立重新计算得到全部1连通块、选入源图全透明像素为0、选中部件RGB相对源图无改动。22个虹膜mask均为0/255二值。导出虹膜alpha非零值253/254沿用了原图近不透明alpha，并不能提供选区边缘抗锯齿。机器报告中的“通过”不能消除下面的可见误选、漏选及颜色污染。详细独立核验见 independent-machine-checks.json。','', '## 必须修正的问题','']
for f in findings:
 targets='全部22个虹膜（逐件见下表）' if f['id']=='F01' else '、'.join('`'+t+'`' for t in f['targets'])
 lines += [f"### {f['id']} · {f['severity']} · {f['kind']}", '',f"部件：{targets}。区域：{f['region']}。",'',f['description'],'', '建议：'+f['recommendation'],'']
 for ev in f['evidence']:
  if ev.startswith('evidence/') and (out/ev).exists():lines.append(f'证据：[{ev}]({ev})。')
  else:lines.append('证据：'+ev+'。')
 lines.append('')
lines+=['## 逐件覆盖与结论','','每行均已检查原图、mask、候选、叠加、轮廓及100%/200%四背景。以下包围框只是定位选区，不是把框内每个像素都判为有问题。','', '| 部件 | 原图包围框 | 结论/问题 | 逐件证据 |','|---|---|---|---|']
for p in parts:
 key=p['state']+'/'+p['part'];note='退回：'+', '.join(p['finding_ids']) if p['finding_ids'] else '静态可见层通过：'+passnotes[key]
 lines.append(f"| `{key}` | `{p['bbox_xyxy']}` | {note} | [100/200%对照]({p['reference_evidence']})；[100%四背景]({p['backgrounds_100']})；[200%四背景](../../qianxia-cutout-R01/{p['backgrounds_200']}) |")
lines+=['','## 范围与复审条件','','`idle/orb`、`question_for_user/button-cap` 和 `default_work/trackball-hand` 的真实遮挡边属于当前可见层范围，不要求补画隐藏结构。`read_web/pointing-hand` 下边被投影遮挡本身不作为缺陷；F09针对的是另外一段可见右侧边界。思考/读文件手固定、完成整图固定的约束未被扩大为额外部件要求。','','本轮未进入动画，没有补底、眼皮、动态播放或原生播放器通过结论。请按问题清单另存新轮次，重做对应逐件四背景检查和机器报告，冻结新哈希后复审修改部件并检查关联边缘。3件局部通过不能用于宣布整套完成。','', '附件：完整逐文件SHA-256、逐件结论和实际打开清单见 [findings.json](findings.json)；独立机器复核见 [independent-machine-checks.json](independent-machine-checks.json)。']
(out/'independent-review.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(result['coverage'],ensure_ascii=False));print('findings',len(findings),'displayed_images',len(displayed))
