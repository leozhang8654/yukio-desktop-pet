"""Independent gaze and six lid poses, derived from the approved iris masks.

The original iris, pupil and highlights move rigidly together. All coordinates
are measured from this character; no Yukio masks or face transforms are used.
"""
import cv2
import numpy as np
from PIL import Image
from pathlib import Path

def smooth(v):
    v=np.clip(v,0,1);return v*v*(3-2*v)

class Eyes:
    def __init__(self,src,masks,scale):
        self.src=src;self.layers=[];h,w=src.shape[:2]
        root=Path(__file__).resolve().parents[1]
        reference=np.zeros((1306,1205,4),'float32')
        closed=np.array(Image.open(root/'generated/closed-eyes-style-reference.png').convert('RGBA')).astype('float32')/255
        reference[450:610,375:755]=cv2.resize(closed,(380,160),interpolation=cv2.INTER_AREA)
        reference=cv2.resize(reference,(w,h),interpolation=cv2.INTER_AREA)
        self.allowed=np.zeros((h,w),bool)
        for name in ['iris-left','iris-right']:
            if name not in masks:continue
            iris=masks[name]
            ys,xs=np.nonzero(iris>.02)
            x0=max(0,xs.min()-(20 if name=='iris-left' else 8));x1=min(w,xs.max()+(8 if name=='iris-left' else 20))
            y0=max(0,ys.min()-10);y1=min(h,ys.max()+6)
            rgb=src[y0:y1,x0:x1,:3];ir=iris[y0:y1,x0:x1]
            white=(rgb[:,:,2]-rgb[:,:,0]>-.055)&(rgb.min(2)>.67)
            cand=(white|(ir>.03)).astype('uint8')
            _,labels=cv2.connectedComponents(cand)
            selected=int(np.bincount(labels[ir>.5]).argmax())
            aperture=(labels==selected).astype('uint8')
            # Fill the iris and only enclosed gaps inside the actual eye opening.
            cs,_=cv2.findContours(aperture,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(aperture,cs,-1,1,cv2.FILLED)
            yy,xx=np.mgrid[:y1-y0,:x1-x0].astype('float32')
            cols=np.flatnonzero(aperture.any(0)); tops=[]; bottoms=[];inks=[];skins=[]
            for x in cols:
                rows=np.flatnonzero(aperture[:,x]);t=int(rows[0]);b=int(rows[-1]);top=t
                for y in range(t-1,max(t-9,-1),-1):
                    if rgb[y,x]@np.array([.299,.587,.114])<.42:top=y;inks.append(rgb[y,x])
                    else:break
                tops.append(top);bottoms.append(b+.8)
                for y in range(b+2,min(b+5,rgb.shape[0])):
                    px=rgb[y,x]
                    if px[0]>.8 and px[0]-px[2]>.035:skins.append(px)
            top=np.interp(np.arange(rgb.shape[1]),cols,tops)
            bottom=np.interp(np.arange(rgb.shape[1]),cols,bottoms)
            skin=np.median(skins,axis=0) if skins else np.array([1,.89,.85])
            ink=np.median(inks,axis=0) if inks else np.array([.06,.025,.10])
            foot=(xx>=cols[0])&(xx<=cols[-1])&(yy>=top[None,:]-1.3)&(yy<=bottom[None,:]+.5)
            # Sclera comes only from the eye white, not skin/hair/dark eyelashes.
            donors=(aperture>0)&(ir<.01)&white
            rows=np.flatnonzero(donors.any(1))
            if len(rows):
                colours=np.array([np.median(rgb[y][donors[y]],axis=0) for y in rows])
                rowcol=np.stack([np.interp(np.arange(rgb.shape[0]),rows,colours[:,k]) for k in range(3)],1)
                sclera=np.broadcast_to(rowcol[:,None,:],rgb.shape).copy().astype('float32')
            else:sclera=np.broadcast_to(np.array([.97,.96,.98]),rgb.shape).copy().astype('float32')
            layer=np.concatenate([rgb*ir[:,:,None],ir[:,:,None]],2)
            # The approved iris fixes registration. Only the independently made
            # closed-lash layer is reused; the face/head never translates.
            rm=np.array(Image.open(root/f'inputs/masks/question_for_user/{name}.png'))
            ry,rx=np.nonzero(cv2.resize(rm,(w,h),interpolation=cv2.INTER_AREA)>8)
            gainx=(rx.max()-rx.min())/max(1,xs.max()-xs.min());gainy=(ry.max()-ry.min())/max(1,ys.max()-ys.min())
            mapx=(xx+x0-(xs.min()+xs.max())/2)*gainx+(rx.min()+rx.max())/2
            mapy=(yy+y0-(ys.min()+ys.max())/2)*gainy+(ry.min()+ry.max())/2
            shut=cv2.remap(reference,mapx.astype('float32'),mapy.astype('float32'),cv2.INTER_LINEAR)[:,:,:3]
            shutlum=shut@np.array([.299,.587,.114]);shutink=(shutlum<.40)&(yy>4)&(yy<rgb.shape[0]-2)
            # Retain only the closed-lash component, excluding hair/crop edges.
            _,ll,stats,_=cv2.connectedComponentsWithStats(shutink.astype('uint8'))
            candidates=[i for i in range(1,len(stats)) if stats[i,cv2.CC_STAT_WIDTH]>8 and stats[i,cv2.CC_STAT_HEIGHT]<12]
            if candidates:shutink=ll==max(candidates,key=lambda i:stats[i,cv2.CC_STAT_AREA])
            else:shutink[:]=False
            dark=(rgb@np.array([.299,.587,.114])<.48).astype('uint8')
            _,dl=cv2.connectedComponents(dark)
            near=cv2.dilate(aperture,np.ones((5,5),'uint8'))>0
            ids=np.unique(dl[near&(dark>0)]);ids=ids[ids>0]
            oldink=np.isin(dl,ids)
            # One interpolation pixel around actual connected ink, not a box.
            footprint=cv2.dilate((oldink|(aperture>0)|shutink).astype('uint8'),np.ones((3,3),'uint8')).astype(bool)
            green_hair=(rgb[:,:,1]-rgb[:,:,0]>.008)&(rgb[:,:,1]-rgb[:,:,2]>.04)
            nearhair=cv2.GaussianBlur(green_hair.astype('float32'),(5,5),1)>.45
            footprint[(green_hair|nearhair)&(aperture==0)]=False
            # The image-generated asset supplies the lash SHAPE only. Extend
            # this state's own warm skin shading behind its eye; copying the
            # generated forehead would introduce displaced hair or new blush.
            warm=(rgb[:,:,0]-rgb[:,:,2]>.025)&(rgb[:,:,0]-rgb[:,:,1]>.01)&(rgb[:,:,2]>.65)&(rgb[:,:,1]-rgb[:,:,2]<.16)&(rgb[:,:,0]>.75)&~oldink&(aperture==0)&(ir<.001)
            rows=np.flatnonzero(warm.any(1))
            if len(rows):
                colours=np.array([np.median(rgb[y][warm[y]],axis=0) for y in rows])
                rowcol=np.stack([np.interp(np.arange(rgb.shape[0]),rows,colours[:,k]) for k in range(3)],1).astype('float32')
                rowcol=cv2.GaussianBlur(rowcol[:,None,:],(1,7),1.4)
                donor=np.broadcast_to(rowcol,shut.shape).copy()
            else:donor=np.broadcast_to(skin,shut.shape).copy()
            shutalpha=cv2.GaussianBlur(shutink.astype('float32'),(3,3),.35)
            shutlayer=np.concatenate([np.broadcast_to(ink,shut.shape)*shutalpha[:,:,None],shutalpha[:,:,None]],2)
            # Original upper-lash pixels supply every intermediate pose. Keep
            # the entire wing and outer corner, instead of swapping in a new
            # thin glyph at the first closure step.
            upperedge=np.interp(np.arange(rgb.shape[1]),cols,[np.flatnonzero(aperture[:,x])[0] for x in cols])
            upperedge=cv2.GaussianBlur(upperedge.astype('float32')[None,:],(5,1),.8)[0]
            upperzone=(yy<=upperedge[None,:]+.5)&oldink
            lashalpha=np.clip((.67-rgb.max(2))/.42,0,1)*upperzone
            lashalpha=cv2.GaussianBlur(lashalpha.astype('float32'),(3,3),.35)
            # R07: keep the lash's own shading (wine-to-navy) instead of one flat
            # ink colour, so the first lid step does not visibly swap the lash.
            # Teal/yellow iris-tinted edge pixels still take the ink colour so a
            # closed eye never carries iris colour down with the lash.
            irislike=(rgb[:,:,1]-rgb[:,:,0]>.02)|(rgb[:,:,1]-rgb[:,:,2]>.08)
            lashrgb=np.where(irislike[:,:,None],np.broadcast_to(ink,rgb.shape),rgb)*lashalpha[:,:,None]
            lashoriginal=np.concatenate([lashrgb,lashalpha[:,:,None]],2)
            cx=np.arange(rgb.shape[1]); left,right=cols[0],cols[-1]
            u=np.clip((cx-left)/max(1,right-left),0,1)
            # Only the central upper lid descends; the outer eye corners and
            # wing tips remain at their exact original coordinates.
            closededge=upperedge[left]*(1-u)+upperedge[right]*u+1.5*np.sin(np.pi*u)
            travel=np.maximum(0,closededge-upperedge)
            travel[(cx<=left)|(cx>=right)]=0
            footprint=cv2.dilate((oldink|(aperture>0)).astype('uint8'),np.ones((3,3),'uint8')).astype(bool)
            footprint[(green_hair|nearhair)&(aperture==0)]=False
            self.layers.append(dict(box=(int(x0),int(y0),int(x1),int(y1)),iris=ir,layer=layer,aperture=aperture>0,sclera=sclera,top=top,bottom=bottom,foot=footprint,skin=skin,ink=ink,cols=cols,xx=xx,yy=yy,closed_layer=shutlayer,donor=donor,closed_ink=shutink,old_ink=oldink,upperedge=upperedge,lashoriginal=lashoriginal,travel=travel))
            self.allowed[y0:y1,x0:x1]|=footprint|(aperture>0)
        if self.layers:
            b=np.where(self.allowed);self.roi=(int(b[1].min()),int(b[0].min()),int(b[1].max()+1),int(b[0].max()+1))
        else:self.roi=(0,0,1,1)

    def paint(self,frame,gaze=(0,0),level=0):
        result=frame.copy()
        for eye in self.layers:
            x0,y0,x1,y1=eye['box'];rgb=self.src[y0:y1,x0:x1,:3].copy()
            dx,dy=gaze
            if abs(dx)+abs(dy)>.001:
                shifted=cv2.warpAffine(eye['layer'],np.float32([[1,0,dx],[0,1,dy]]),(x1-x0,y1-y0),flags=cv2.INTER_LINEAR)
                neutral=eye['layer'][:,:,:3]+eye['sclera']*(1-eye['iris'][:,:,None])
                moved=shifted[:,:,:3]+eye['sclera']*(1-shifted[:,:,3:4])
                rgb[eye['aperture']]+= (moved-neutral)[eye['aperture']]
            if level:
                a=level/6;xx=eye['xx'];yy=eye['yy']
                upper=eye['upperedge'][None,:]+a*eye['travel'][None,:]
                # The original eye pixels stay rigid behind the descending
                # lid. Smooth coverage removes the old jagged white rim too.
                opening=np.clip(yy-upper+.5,0,1)
                lower=eye['bottom'][None,:]*(1-a)+(eye['upperedge'][None,:]+eye['travel'][None,:])*a
                opening*=np.clip(lower-yy+.5,0,1)
                opening*=eye['aperture']
                if level==6:opening[:]=0
                painted=eye['donor']*(1-opening[:,:,None])+rgb*opening[:,:,None]
                lash=cv2.remap(eye['lashoriginal'],xx,yy-a*eye['travel'][None,:].astype('float32'),cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
                painted=painted*(1-lash[:,:,3:4])+lash[:,:,:3]
                rgb[eye['foot']]=painted[eye['foot']]
            target=result[y0:y1,x0:x1,:3];allowed=eye['foot']|eye['aperture']
            target[allowed]=np.clip(rgb,0,1)[allowed]
        return result
