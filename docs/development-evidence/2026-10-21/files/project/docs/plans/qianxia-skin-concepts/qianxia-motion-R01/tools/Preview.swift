import AppKit
import Foundation

struct Blink: Decodable { var decodedAsset:String; var x:Int;var y:Int;var width:Int;var height:Int;var columns:Int;var frames:[[Int]] }
struct State:Decodable {var id:String;var decodedAsset:String;var columns:Int;var sequence:[Int];var durationsMs:[Int];var loopStart:Int;var mode:String;var blink:Blink?}
struct Manifest:Decodable {var states:[State]}
let root=URL(fileURLWithPath:CommandLine.arguments.count>1 ? CommandLine.arguments[1] : Bundle.main.bundleURL.deletingLastPathComponent().deletingLastPathComponent().path)
let states=try! JSONDecoder().decode(Manifest.self,from:Data(contentsOf:root.appendingPathComponent("motion/motion.json"))).states
func image(_ file:String)->CGImage {let u=root.appendingPathComponent("motion/"+file);let src=CGImageSourceCreateWithURL(u as CFURL,nil)!;return CGImageSourceCreateImageAtIndex(src,0,nil)!}
let sheets=states.map {image($0.decodedAsset)}
let eyelids=states.map {$0.blink.map {image($0.decodedAsset)}}
let names=["idle":"待机","thinking":"思考","read_file":"读文件","view_image":"看图片","write_file":"写文件","verify":"验证","read_web":"浏览网页","default_work":"工作中","respond":"回答","task_complete":"完成","question_for_user":"等待回应","failed":"遇到问题"]
class Player:NSView {
 override var isFlipped:Bool {true}
 var timer:Timer?;var elapsed:Double=0;var previous=ProcessInfo.processInfo.systemUptime;var draws=0;var paused=false;var slow=false;var grid=true;var selected=0;var background=0
 var frames=Array(repeating:Set<Int>(),count:states.count);var lastWrite=0;var start=ISO8601DateFormatter().string(from:Date())
 override var acceptsFirstResponder:Bool {true}
 func startTimer(){timer=Timer.scheduledTimer(withTimeInterval:1/60,repeats:true){[weak self] _ in guard let s=self else{return};let now=ProcessInfo.processInfo.systemUptime;let delta=now-s.previous;s.previous=now;if !s.paused && s.window?.occlusionState.contains(.visible)==true{s.elapsed+=min(delta,0.1)*(s.slow ? 0.25:1)};s.needsDisplay=true}}
 func label(_ value:String,_ x:CGFloat,_ y:CGFloat,_ size:CGFloat=12){(value as NSString).draw(at:NSPoint(x:x,y:y),withAttributes:[.font:NSFont.systemFont(ofSize:size),.foregroundColor:NSColor.white])}
 func frame(_ spec:State,_ t:Double)->(Int,Int) {
  let total=Double(spec.durationsMs.reduce(0,+))/1000
  let enter=Double(spec.durationsMs.prefix(spec.loopStart).reduce(0,+))/1000
  var local=t
  if spec.mode=="enter_then_hold" {local=t.truncatingRemainder(dividingBy:total)}
  else if total>0 {local=t.truncatingRemainder(dividingBy:total)}
  var acc=0.0
  for (i,d) in spec.durationsMs.enumerated(){acc+=Double(d)/1000;if local<acc{return(spec.sequence[i],i)}}
  return(spec.sequence[spec.loopStart],spec.loopStart)
 }
 func bl(_ t:Double,_ i:Int)->Int {let v=(t+Double(i)*0.47).truncatingRemainder(dividingBy:4.7);if v>0.26{return 0};let a=v<0.10 ? v/0.10 : (0.26-v)/0.16;return min(6,max(1,Int(ceil(a*6))))}
 override func draw(_ dirtyRect:NSRect){
  NSColor(calibratedWhite:0.10,alpha:1).setFill();bounds.fill();draws+=1
  label("千夏动画候选 · 192×208 实际尺寸 · QA 实播",14,10,17)
  label("空格 暂停｜S 慢速｜G 总览/放大｜← → 选状态｜B 背景｜R 重测三轮",14,36)
  label(String(format:"已实播 %0.1f 秒 · %@ · %@",elapsed,paused ? "暂停":"播放",slow ? "0.25×":"1×"),14,55)
  let indices=grid ? Array(states.indices):[selected]
  for i in indices {
   let s=states[i];let k=grid ? i:0;let x=CGFloat(k%4)*212+12;let y=CGFloat(k/4)*244+88;let size:CGFloat=grid ? 1:2
   let cell=NSRect(x:x,y:y,width:192*size,height:208*size)
   let colours:[NSColor]=[.init(calibratedRed:0.19,green:0.19,blue:0.25,alpha:1),.black,.white,.magenta]
   colours[background].setFill();cell.fill()
   let (f,_)=frame(s,elapsed);frames[i].insert(f)
   let crop=CGRect(x:(f%s.columns)*384,y:(f/s.columns)*416,width:384,height:416)
   if let cg=sheets[i].cropping(to:crop){NSImage(cgImage:cg,size:NSSize(width:384,height:416)).draw(in:cell,from:.zero,operation:.sourceOver,fraction:1,respectFlipped:true,hints:[.interpolation:NSImageInterpolation.high])}
   let level=bl(elapsed,i)
   if level>0,let b=s.blink,let atlas=eyelids[i] {
    let n=b.frames[f][level-1];let box=CGRect(x:(n%b.columns)*b.width,y:(n/b.columns)*b.height,width:b.width,height:b.height)
    if let cg=atlas.cropping(to:box){let rect=NSRect(x:x+CGFloat(b.x)/2*size,y:y+CGFloat(b.y)/2*size,width:CGFloat(b.width)/2*size,height:CGFloat(b.height)/2*size);NSImage(cgImage:cg,size:NSSize(width:b.width,height:b.height)).draw(in:rect,from:.zero,operation:.copy,fraction:1,respectFlipped:true,hints:[.interpolation:NSImageInterpolation.high])}
   }
   let duration=Double(s.durationsMs.reduce(0,+))/1000
   label("\(names[s.id] ?? s.id) · \(s.mode == "enter_then_hold" ? "测试新事件" : "循环") \(Int(elapsed/duration))",x,y+208*size+3)
  }
  if Int(elapsed)>lastWrite {lastWrite=Int(elapsed);writeReport()}
 }
 func writeReport(){
  let entries=states.enumerated().map {i,s -> [String:Any] in let duration=Double(s.durationsMs.reduce(0,+))/1000;return ["state":s.id,"complete_cycles_or_new_events":Int(elapsed/duration),"displayed_unique_body_frames":frames[i].sorted(),"expected_unique_frames":Set(s.sequence).count,"mode":s.mode]}
  let data:[String:Any] = ["session_start":start,"elapsed_visible_playback_seconds":elapsed,"draw_calls":draws,"speed":slow ? 0.25:1,"grid":grid,"background":background,"states":entries,"note":"Real AppKit draw timestamps; maker/reviewer visual judgement is separate. One-shot repeats here are explicit QA new events."]
  if let d=try? JSONSerialization.data(withJSONObject:data,options:[.prettyPrinted,.sortedKeys]){try? d.write(to:root.appendingPathComponent("review/native-playback.json"))}
 }
 override func keyDown(with e:NSEvent){switch e.charactersIgnoringModifiers?.lowercased(){case " ":paused.toggle();case "s":slow.toggle();case "g":grid.toggle();case "b":background=(background+1)%4;case "r":elapsed=0;frames=Array(repeating:Set<Int>(),count:states.count);start=ISO8601DateFormatter().string(from:Date());default:if e.keyCode==124{selected=(selected+1)%states.count};if e.keyCode==123{selected=(selected+states.count-1)%states.count}};needsDisplay=true}
}
import ImageIO
let app=NSApplication.shared
app.setActivationPolicy(.regular)
let window=NSWindow(contentRect:NSRect(x:100,y:80,width:862,height:836),styleMask:[.titled,.closable,.miniaturizable],backing:.buffered,defer:false)
window.title="千夏动画独立预览（候选，不安装）"
let player=Player(frame:window.contentView!.bounds);window.contentView=player;window.makeKeyAndOrderFront(nil);window.makeFirstResponder(player);player.startTimer();app.activate(ignoringOtherApps:true);app.run()
