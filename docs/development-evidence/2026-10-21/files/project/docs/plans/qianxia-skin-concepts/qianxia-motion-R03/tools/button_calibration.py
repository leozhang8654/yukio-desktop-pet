"""R08 masks; generated concealed background; fixed cuff and button base."""
from pathlib import Path
import json, hashlib
import cv2
import numpy as np
from PIL import Image, ImageDraw

R = Path(__file__).resolve().parents[1]
S = 'question_for_user'
def rgba(p):
    a=np.asarray(Image.open(p).convert('RGBA')).astype('float32')/255
    a[:,:,:3]*=a[:,:,3:4]
    return a
def out(a):
    a=a.copy();a[:,:,:3]/=np.maximum(a[:,:,3:4],1e-7)
    a[a[:,:,3]==0]=0
    return np.clip(a*255+.5,0,255).astype('uint8')
def over(b,t): return t+b*(1-t[:,:,3:4])
def smooth(x):
    x=np.clip(x,0,1);return x*x*(3-2*x)
def render():
    src=rgba(R/'inputs/source/11-question_for_user.png'); h,w=src.shape[:2]
    masks={n:np.asarray(Image.open(R/f'inputs/masks/{S}/{n}.png')).astype('float32')/255 for n in ['pressing-hand','button-cap']}
    masks['button-cap']=np.asarray(Image.open(R/'rigs/question_for_user/button-cap-motion-mask.png')).astype('float32')/255
    donor=rgba(R/'generated/button-empty.png')
    donor=cv2.resize(donor,(230,160),interpolation=cv2.INTER_AREA)
    clean=src.copy();clean[690:850,660:890]=donor
    # Generated pixels are only accessible inside the original moved masks.
    combined=np.maximum(*masks.values())
    erase=cv2.dilate((combined>0).astype('uint8'),np.ones((3,3),'uint8')).astype('float32')
    base=src*(1-erase[:,:,None])+clean*erase[:,:,None]
    yy,xx=np.mgrid[:h,:w].astype('float32')
    layers={n:src*m[:,:,None] for n,m in masks.items()}
    allowed=cv2.dilate((combined>0).astype('uint8'),np.ones((17,17),'uint8'))>0
    # Source wrist/cuff is stationary; pressure grows toward the fingertips.
    weight=smooth((yy-728)/45)
    neutral=over(over(base,layers['button-cap']),layers['pressing-hand'])
    frames=[]; amounts=[]
    for i in range(34):
        t=i/30
        pressure=float(smooth((t-.15)/.25)*(1-smooth((t-.60)/.25)))
        d=5.0*pressure
        f=base.copy()
        # Compress only the movable cap toward its fixed contact with the base.
        sy=834-(834-yy)/(1-d/50)
        cap=cv2.remap(layers['button-cap'],xx,sy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
        hand=cv2.remap(layers['pressing-hand'],xx,yy-d*weight,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
        f=src+over(over(f,cap),hand)-neutral
        f=np.clip(f,0,1)
        f[yy<=728]=src[yy<=728]
        fixed_base=(yy>=833)|((yy>=799)&((xx<757)|(xx>847)))
        f[fixed_base]=src[fixed_base]
        f[~allowed]=src[~allowed]
        # Exact neutral pose, including antialiasing and original composition.
        if pressure==0:f=src.copy()
        frames.append(out(f));amounts.append(pressure)
    p=R/'rigs'/S;p.mkdir(exist_ok=True)
    Image.fromarray(out(base)).save(p/'cleanplate.png')
    Image.fromarray(allowed.astype('uint8')*255).save(p/'allowed-mask.png')
    Image.fromarray((weight*255).astype('uint8')).save(p/'hand-weight.png')
    np.savez_compressed(p/'composition.npz',base=base,hand=layers['pressing-hand'],cap=layers['button-cap'])
    (p/'parameters.json').write_text(json.dumps({'source_crop':[660,690,890,850],'pressure_source_pixels':5,'pressure_display_pixels':5*192/w,'fixed_cuff_y_max':728,'cap_fixed_bottom':834,'duration':1.1,'fps':30,'loop_start':'final stable pose','pressure':amounts},indent=2))
    # Full-resolution lossless export and immediate decoder check.
    ims=[Image.fromarray(f) for f in frames]
    ims[0].save(R/'review/button-calibration.webp',save_all=True,append_images=ims[1:],duration=33,loop=0,lossless=True,exact=True)
    tiles=[]
    for i in [0,8,14,20,26,33]:
        tile=Image.fromarray(frames[i]).crop((690,695,870,854)).resize((540,477))
        bg=Image.new('RGBA',tile.size,'#303040');bg.alpha_composite(tile);tiles.append(bg)
    sheet=Image.new('RGB',(1620,994),'#303040');d=ImageDraw.Draw(sheet)
    for k,tile in enumerate(tiles):sheet.paste(tile,(k%3*540,k//3*497+20));d.text((k%3*540+5,k//3*497+3),f't={ [0,8,14,20,26,33][k]/30:.2f}s',fill='white')
    sheet.save(R/'review/button-keyframes.jpg')
    # PNG frames for a calibrated event player, not an endlessly repeating prompt.
    p=R/'review/button-frames';p.mkdir(exist_ok=True)
    for i,im in enumerate(ims):im.save(p/f'{i:02d}.png')
    changed=np.any(np.stack(frames)!=frames[0],axis=3)
    report={'frames':len(frames),'outside_allowed_changed':int(changed[:,~allowed].sum()),'fixed_head_neck_changed':int(changed[:,:690].sum()),'stationary_base_changed':int(changed[:,842:].sum()),'final_equals_first':bool(np.array_equal(frames[-1],frames[0])),'review':'pending visual and independent review'}
    (R/'review/button-machine.json').write_text(json.dumps(report,indent=2))
    print(report)
if __name__=='__main__':render()
