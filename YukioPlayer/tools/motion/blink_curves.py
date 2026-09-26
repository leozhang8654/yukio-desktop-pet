"""Local, source-sampled eyelids; never rescales the eyes or changes the face."""
import numpy as np
import cv2
from motionlib import eye_outline, unpremul_rgb, ease

SUPERSAMPLE = 8
# Endpoints and sag in 2x working pixels; positive sag is a relaxed closed lid.
CLOSED_CURVES = [(175.,131.,199.,132.,4.), (221.,121.5,249.,120.5,5.5)]

def paint_curve_blink(plate, eyes, amount, curves=None, cover_margin=.5, warm_skin_only=False,
                      eye_apertures=None):
 if amount <= 0:return plate
 out=plate.copy();S=SUPERSAMPLE
 for eye_index,(eye,closed) in enumerate(zip(eyes,CLOSED_CURVES if curves is None else curves)):
  geo=eye_outline(eye);xs=np.array(sorted(geo));xa,xb=xs[0],xs[-1]+1
  y0=max(0,min(v[0] for v in geo.values())-2)
  y1=min(plate.shape[0],int(np.ceil(max(v[2] for v in geo.values())))+4)
  opening=None
  if eye_apertures is not None:
   opening=eye_apertures[eye_index]
   bx0,by0,bx1,by1=opening.box
   xa,xb=min(xa,bx0),max(xb,bx1)
   y0,y1=min(y0,by0),max(y1,by1)
  region=plate[y0:y1,xa:xb];skin_samples=[];inks=[]
  for x in xs[2:-2]:
   top,lash,bottom=geo[x]
   for y in range(int(np.ceil(bottom))+1,int(np.ceil(bottom))+3):
    if y<plate.shape[0]:
     p=plate[y,x]
     if p[3]>.95 and p[:3]@np.array([.299,.587,.114])>.72 and (not warm_skin_only or p[0]-p[2]>.04):skin_samples.append(p)
   inks.extend(plate[top:top+lash,x])
  skin=np.median(skin_samples,axis=0).astype('float32')
  inks=sorted(inks,key=lambda p:p[:3]@np.array([.299,.587,.114]))
  ink=np.median(inks[:max(1,len(inks)*2//5)],axis=0).astype('float32')
  up=cv2.resize(region,((xb-xa)*S,(y1-y0)*S),interpolation=cv2.INTER_CUBIC)
  xx=xa+(np.arange(up.shape[1])+.5)/S-.5
  yy=y0+(np.arange(up.shape[0])+.5)/S-.5
  tops=np.array([geo[x][0] for x in xs]);bottoms=np.array([geo[x][2] for x in xs])
  # The cover footprint follows the source; the moving lash is a single smooth
  # parametric curve, not separately drawn pixel columns.
  top=np.interp(xx,xs,tops);bottom=np.interp(xx,xs,bottoms)
  u=np.clip((xx-closed[0])/(closed[2]-closed[0]),0,1)
  shut=closed[1]*(1-u)+closed[3]*u+4*closed[4]*u*(1-u)
  fit=np.polynomial.Polynomial.fit(xs,tops+1.1,3)
  open_lid=fit(xx)
  upper=open_lid*(1-amount)+shut*amount
  lower=bottom*(1-amount)+shut*amount
  footprint=((yy[:,None]>=top[None,:]-cover_margin)&(yy[:,None]<=bottom[None,:]+1.0)).astype('float32')
  footprint*=((xx>=xs[0]-.5)&(xx<xs[-1]+.5))[None,:]
  if opening is not None:
   # A translated iris can reach an eye-white pixel the old column detector
   # omitted. The unchanged eyelid curve must cover that entire fixed opening,
   # otherwise a blue sliver survives at the corner during a full blink.
   extra=np.zeros((y1-y0,xb-xa),'float32')
   extra[by0-y0:by1-y0,bx0-xa:bx1-xa]=opening.aperture
   extra=cv2.resize(extra,(up.shape[1],up.shape[0]),interpolation=cv2.INTER_NEAREST)
   footprint=np.maximum(footprint,extra)
  # Cover, don't squash: visible iris pixels always retain their source location.
  aperture=np.clip((yy[:,None]-upper[None,:]-.7)*S+.5,0,1)*np.clip((lower[None,:]-yy[:,None])*S+.5,0,1)
  patch=skin[None,None,:]*(1-aperture[:,:,None])+up*aperture[:,:,None]
  half=(1.45*(1-amount)+.82*amount)*np.power(np.clip(np.sin(np.pi*u),0,1),.4)
  stroke=np.clip((half[None,:]-np.abs(yy[:,None]-upper[None,:]))*S+.5,0,1)
  patch=ink[None,None,:]*stroke[:,:,None]+patch*(1-stroke[:,:,None])
  coverage=footprint*ease(min(1,amount/.12))
  new=up*(1-coverage[:,:,None])+patch*coverage[:,:,None]
  down=cv2.resize(new,(xb-xa,y1-y0),interpolation=cv2.INTER_AREA)
  changed=cv2.resize(coverage,(xb-xa,y1-y0),interpolation=cv2.INTER_AREA)>0
  target=out[y0:y1,xa:xb];target[changed]=down[changed]
 out=np.clip(out,0,1);out[:,:,:3]=np.minimum(out[:,:,:3],out[:,:,3:4])
 return out
