from pathlib import Path
from PIL import Image
import json,hashlib,numpy as np,cv2
out=Path(__file__).parent;root=out.parent.parent/'qianxia-cutout-R02';ix=json.loads((out/'inspection-index.json').read_text());frozen=json.loads((out/'frozen-hashes.json').read_text());frozen={Path(k).relative_to(root.resolve()).as_posix() if Path(k).is_absolute() else k:v for k,v in frozen.items()};actual={k:hashlib.sha256((root/k).read_bytes()).hexdigest() for k in frozen}
assert actual==frozen
issues=[
('E01','default_work/iris-left',[[437,559,462,579]],'左下角选入眼白楔片；从原图的白色眼白沿深色虹膜线外侧延入选区，黑底呈白色角点，底部还形成小突出。',['default-left-bottom.png','default_work-iris-left-bottom600.png']),
('E02','default_work/iris-right',[[623,566,642,584]],'左下角保留一条白色眼白及淡肤色边片；它位于虹膜深色外线的外侧，黑底呈较亮短竖边。',['default_work-iris-right-bottom600.png']),
('E03','failed/iris-left',[[438,545,460,562]],'左下角带入下眼角红/肤色像素，黑底出现红灰小边片；原图相应颜色连接固定下眼角，不属于虹膜本体。',['failed-left-bottom.png','failed-iris-left-bottom600.png']),
('E04','idle/iris-right',[[625,563,644,581]],'左下拐角有白色眼白细条伸在虹膜深色描边外侧，黑底呈亮色竖片。',['idle-iris-right-bottom600.png']),
('E05','read_web/iris-left',[[428,493,450,513],[434,552,456,566]],'左上原图虹膜轮廓是圆弧转角，选区以方角跨入眼白，候选留下白色三角。左下角也带入眼白与下眼角红色小片。',['web-left-top.png','read_web-iris-left-bottom600.png']),
('E06','read_web/iris-right',[[672,503,693,525]],'右上原图圆弧转角之外的眼白被方角选区带入；候选黑/洋红底均出现白色角点。',['web-right-top.png']),
('E07','respond/iris-left',[[489,544,511,563]],'右下角选入肤色区域，形成棕粉色小片和偏方的下角；源图该色在虹膜深色轮廓外、与脸部连接。',['respond-left-bottom.png','respond-iris-left-bottom600.png']),
('E08','respond/iris-right',[[625,551,644,569]],'左下角同时带入一段白色眼白边及其下方肤色，黑底呈白粉色短边条。',['respond-iris-right-bottom600.png']),
('E09','view_image/iris-left',[[443,555,464,574]],'左下角深色轮廓外有窄白色眼白楔片，黑底局部亮边与原图眼白对应。',['view_image-iris-left-bottom600.png']),
('E10','write_file/iris-left',[[438,555,463,575]],'左下角保留白色眼白楔片，深色轮廓外出现亮片及较直的角点；与原图虹膜侧缘的弯曲过渡不一致。',['write-left-bottom.png','write_file-iris-left-bottom600.png'])]
findings=[]
for id,key,rois,detail,evs in issues:
 findings.append(dict(id=id,part=key,severity='medium',requires_rework=True,kind='局部邻接色误选/角点轮廓',regions_xyxy=rois,description=detail,recommendation='仅在所列角点沿真实虹膜深色轮廓外侧精修局部蒙版与亚像素覆盖率，排除眼白/肤色残片；保留虹膜描边厚度及已修好的高光，不用全局腐蚀或整体缩小清理。圆弧处不要用方角跨过真实边界。',evidence=['evidence/'+e for e in evs]))
parts=[];checks=[]
for z in ix:
 key=z['state']+'/'+z['part'];ids=[a['id'] for a in findings if a['part']==key];src=Path(z['source']).relative_to(root.resolve()).as_posix();mask='masks/'+key+'.png';candidate='parts/'+key+'.png';m=np.array(Image.open(z['mask']).convert('L'));s=np.array(Image.open(z['source']).convert('RGBA'));p=np.array(Image.open(z['candidate']).convert('RGBA'));num,_=cv2.connectedComponents((m>0).astype('uint8'),connectivity=8)
 check={'part':key,'components':int(num-1),'soft_mask_pixels':int(((m>0)&(m<255)).sum()),'selected_source_alpha_zero_pixels':int(((m>0)&(s[:,:,3]==0)).sum()),'changed_selected_rgb_pixels':int(((p[:,:,:3]!=s[:,:,:3]).any(axis=2)&(m>0)).sum())};checks.append(check)
 note='退回：'+','.join(ids) if ids else '通过：可见虹膜/瞳孔/高光轮廓与原图对应，100/200%四背景未见必须退回的误选、漏选、突刺或颜色污染。'
 if key=='read_file/iris-left':note+=' R01 F02高光凹缺已修复。'
 if key=='write_file/iris-right':note+=' R01 F03左上暗色凸块和凹口已修复。'
 parts.append(dict(state=z['state'],part=z['part'],checked=True,result='rework_required' if ids else 'pass_static_visible_only',bbox_xyxy=z['bbox'],inspection_scales=[1,2,6],backgrounds=['checker','black','white','magenta'],finding_ids=ids,conclusion=note,source=src,source_sha256=frozen[src],mask=mask,mask_sha256=frozen[mask],candidate=candidate,candidate_sha256=frozen[candidate],reference_evidence='evidence/'+Path(z['reference']).name,backgrounds_200=Path(z['backgrounds']).relative_to(root.resolve()).as_posix(),lower_edge_evidence='evidence/'+z['state']+'-'+z['part']+'-bottom600.png'))
displayed=[str(p.resolve()) for p in sorted((out/'evidence').glob('*.png'))]+[z['backgrounds'] for z in ix];reviewpng=[]
for z in ix:
 for n in ['overlay-200.png','contour-200.png','four-backgrounds-200.png']:reviewpng.append(str((root/'review'/z['state']/z['part']/n).resolve()))
obj={'reviewer':'Independent Codex subagent /root/cutout_independent_review, same reviewer as R01; did not make either candidate','round':'R02-eyes','decision':'退回（仅虹膜范围）','scope':'22个虹膜可见层；11张原图；手/道具/动画/补底/眼皮不在此次复审范围。','coordinate_system':'原始1205×1306像素坐标，0-based，x向右/y向下，区域为[x0,y0,x1,y1)。','coverage':{'submitted':22,'checked':22,'unchecked':0,'pass_static_visible_only':12,'rework_required':10},'review_order':'先逐件原始PNG解码并显示100%原图/mask/候选及100%四背景，再原图/叠加/轮廓200%及四背景200%；22件全部完成后才读machine-report.json和核验哈希；之后逐眼补充600%下缘回归及7张局部特写。','prior_findings':{'R01-F01':'普遍二值硬边已改善：22件均有局部软覆盖率，原先毛刺/台阶显著消除。该修正本身确认；但10件仍有本轮列出的角点邻接色误选，不能整体通过。','R01-F02':'已修复；read_file/iris-left高光连续完整，无原先的内凹咬缺。','R01-F03':'已修复；write_file/iris-right左上侧边的突出暗块和高光上方凹口消除。'},'frozen_hash_binding':frozen,'hash_verification':{'count':55,'mismatches':0},'findings':findings,'parts':parts,'independent_machine_checks':checks,'opened_files':{'raw_pngs_decoded_and_visually_displayed_in_full_candidate_bbox_crops':[str((root/k).resolve()) for k in frozen],'candidate_review_pngs_displayed_directly_or_in_reference_boards':reviewpng,'visually_displayed_images':displayed,'machine_report_read_after_visual':str((out/'machine-report.json').resolve())},'limits':['只审查本轮可见虹膜层，不要求补画隐藏结构。','未检查任何R02手/道具新版本，不能据此宣称全部34件通过。','未制作或检查眼皮、补底、动画与原生运行。','报告只绑定55个冻结文件，修正后另存新轮次并重新冻结。']}
(out/'findings.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
(out/'independent-machine-checks.json').write_text(json.dumps({'hashes_match':True,'file_count':55,'parts':checks},ensure_ascii=False,indent=2)+'\n')
lines=['# R02 虹膜独立复审','','**结论：退回（仅限22个虹膜可见层）。22/22件已逐件检查，12件通过、10件需局部返工，无未检查项。**','','审查者：独立 Codex 子 Agent `/root/cutout_independent_review`，与R01为同一审查者，未参与候选制作。只读取本次限定的虹膜素材、scope、冻结哈希、对应逐件PNG，以及目视完成后读取的 machine-report.json；没有查看/评价R02手或道具素材，也没有读取制作脚本、reference参数、制作方自检理由或评分。','','## 已确认的修复','','- **R01 F01：** 22个虹膜普遍硬台阶已改善，选区现在有软覆盖率；原先明显突刺与硬台阶消除。但10件角点仍有眼白/肤色误选，见新问题清单。','- **R01 F02：** `read_file/iris-left` 高光左缘凹缺已修复，当前白色高光连续；该件本轮通过。','- **R01 F03：** `write_file/iris-right` 左上暗色凸块及高光上方凹口已修复；该件本轮通过。','','## 审查方法与哈希','','逐件从真实source、mask、part PNG解码，按完整候选包围框显示100%原图、原始mask和候选；逐件检查100%棋盘格/黑/白/洋红背景。逐件显示原图、选区叠加与轮廓200%，并单独打开对应200%四背景。22件全部完成后才读取机器报告与核验数据；随后逐件补看600%下缘，并看7张局部600%对照。没有以缩小总览替代逐件检查。','','实际显示73张图像，原始文件、叠加/轮廓文件及显示图的完整清单在 findings.json 的 opened_files。该清单区分原始文件经裁片显示和实际展示图像。','','11张源图、22张mask、22张part共**55个SHA-256全部匹配**。本报告绑定 frozen-hashes.json 的字节；findings.json 另内嵌完整清单及每件三类哈希。独立重新计算22件均1连通块、选入源图alpha=0像素为0、所选RGB与源图相同，软mask像素数215–257。拓扑与RGB来源正确不能证明角点选区语义正确。','','## 本轮必须修正的问题','','以下坐标均为原始1205×1306图像的0-based坐标；x向右、y向下，区域为 `[x0,y0,x1,y1)`。left/right沿用文件名。所有问题严重度为medium，局部误选需要修正；不能因像素面积小直接放行。','']
for f in findings:
 lines += [f"### {f['id']} · `{f['part']}`",'',f"区域：`{f['regions_xyxy']}`。",'',f['description'],'','建议：'+f['recommendation'],'']
 for ev in f['evidence']:lines.append(f'证据：[{Path(ev).name}]({ev})。')
 lines.append('')
lines+=['## 逐件结论','','| 部件 | 结论 | 证据 |','|---|---|---|']
for p in parts:
 lines.append(f"| `{p['state']}/{p['part']}` | {p['conclusion']} | [100/200%原图、mask、四背景]({p['reference_evidence']})；[200%四背景](../../qianxia-cutout-R02/{p['backgrounds_200']})；[600%下缘]({p['lower_edge_evidence']}) |")
lines+=['','## 复审边界','','仅通过表中12件静态可见虹膜；不包含其他10件、不包含任何手/道具，也不包含补底、眼皮或动画。原图真实遮挡保持，不要求补画不可见虹膜。','','建议按10件问题的局部ROI精修后另存新轮次，保留已经确认的高光与抗锯齿修复，再冻结文件复审修改位置及关联轮廓。不要通过整体侵蚀或批量缩小去掉角点邻接色，因为这会削薄真实虹膜描边。','','完整数据：[findings.json](findings.json)。独立机器复核：[independent-machine-checks.json](independent-machine-checks.json)。']
(out/'independent-review.md').write_text('\n'.join(lines)+'\n');print(obj['coverage']);print('displayed images',len(displayed));print('soft range',min(x['soft_mask_pixels'] for x in checks),max(x['soft_mask_pixels'] for x in checks))
