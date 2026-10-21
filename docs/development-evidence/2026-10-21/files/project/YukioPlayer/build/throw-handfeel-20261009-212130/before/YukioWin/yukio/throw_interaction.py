"""Win32 integration. Desktop pixels are converted relative to ONE monitor."""
import math,time
from .throw_physics import ThrowPhysics,load_config,impact_duration
from .drag_velocity import DragVelocityTracker,release_velocity
from .catalog import SpriteTimeline


class ThrowInteraction:
    def _init_throw(self,assets):
        self.throw_config=load_config(assets)
        self.flight=None; self._throw_caught=False; self._throw_canvas=None
        self._throw_hit=None; self._throw_source=None; self._throw_pose=('interaction_airborne',0)
        self._throw_last=time.monotonic(); self._throw_tracker=DragVelocityTracker()
        self._input_point=None; self._input_logical=(0.,0.)
        self._drag_dpi=None; self._throw_session_id=0

    def _sample_pointer(self,reset=False):
        point=self.win32.cursor_pos(); dpi=self.win32.monitor_geometry(*point)[1]
        if reset:
            self._throw_tracker=DragVelocityTracker(); self._input_point=point; self._input_logical=(0.,0.)
            self._drag_dpi=dpi
        if self._input_point is not None:
            # Integrate physical deltas in the monitor's own scale. Never divide
            # the entire virtual desktop coordinate by a changing DPI factor.
            dx,dy=point[0]-self._input_point[0],point[1]-self._input_point[1]
            self._input_logical=(self._input_logical[0]+dx/dpi,self._input_logical[1]-dy/dpi)
        self._input_point=point
        self._throw_tracker.add(time.monotonic(),*self._input_logical)

    def _catch_throw(self):
        if self.flight is None:return False
        self._throw_caught=True
        return True

    def _start_throw(self,pointer):
        c=self.throw_config
        room,dpi=self.win32.monitor_geometry(*self.win32.cursor_pos())
        left,top,right,bottom=room
        tangent=(0.,0.); carry=None
        if self.flight is not None:
            olddpi=self._throw_dpi; side=360*self.flight.scale*olddpi
            cx=self.pet.x+side/2; cy=self.pet.y+side/2
            cy-=getattr(self,"_throw_draw_shift",0)*olddpi
            angle=getattr(self,"_throw_draw_angle",self.flight.angle); rate=0.
            carry=self._throw_pose
        elif self.swing is not None:
            geo,sw=self.hang_geo,self.swing
            sx,sy,_,_=geo.sprite_rect; px,py=geo.pivot
            # The existing held geometry is frozen at gesture start DPI.
            render_scale=self.user_scale*(self._drag_dpi or dpi)
            dx=sx+c['center'][0]*render_scale-px
            dy=-(sy+c['center'][1]*render_scale+sw.sag-py)
            co,si=math.cos(sw.angle),math.sin(sw.angle)
            rx,ry=dx*co-dy*si,dx*si+dy*co
            cx=self.pet.x+px+rx; cy=self.pet.y+py-ry
            angle,rate=sw.angle,sw.rate
            tangent=((-sw.rate*ry+sw.sag_rate*si)/dpi,(sw.rate*rx-sw.sag_rate*co)/dpi)
        else:return
        velocity=release_velocity(pointer,tangent,c)
        # Keep the currently visible physical size at release across mixed DPI.
        s=self.user_scale*(self._drag_dpi or dpi)/dpi
        self._throw_session_id+=1
        self.flight=ThrowPhysics(c,((right-left)/dpi,(bottom-top)/dpi),((cx-left)/dpi,(bottom-cy)/dpi),velocity,angle,rate,s,str(room),self._throw_session_id)
        self._throw_room=room; self._throw_dpi=dpi; self._throw_carry=carry
        self._throw_caught=False; self.swing=None; self.hang_geo=None; self.held_timeline=None; self._released_at=None
        self._throw_last=time.monotonic(); self._painted=None
        self.win32.user32.SetTimer(self.control.hwnd,2,16,None)
        self.bubble.hide()
        self._render_throw()

    def _throw_tick(self):
        if self.flight is None:return
        now=time.monotonic(); dt=now-self._throw_last; self._throw_last=now
        if not self._throw_caught:self.flight.advance(dt)
        if self.flight.phase=='normal':self._finish_throw();return
        self._render_throw()

    def _interaction_pose(self):
        p=self.flight; name='airborne'; sec=p.time
        if p.phase=='dizzy':
            name='dizzy-intro' if p.phase_time<p.c['dizzyIntroSeconds'] else 'dizzy-loop'
            sec=p.phase_time
            if name=='dizzy-loop':
                span=max(.1,p.dizzy_duration-p.c['dizzyIntroSeconds'])
                loops=max(1,math.floor(span/.9+.5))
                sec=(p.phase_time-p.c['dizzyIntroSeconds'])*loops*.9/span
        elif p.phase=='recover':name='recover';sec=p.phase_time
        elif p.last_impact:
            hit=p.last_impact; age=p.time-hit.time
            if age<impact_duration(p.c,hit):
                name='landing-impact' if hit.normal[1]>0 else 'wall-impact'
                name+=('_light' if hit.strength<1/3 else '_medium' if hit.strength<2/3 else '')
                sec=age*(.24 if hit.normal[1]>0 else .14)/impact_duration(p.c,hit)
        if name=='airborne' and self._throw_carry:return self._throw_carry
        spec=self.catalog.specs['interaction_'+name]; tl=SpriteTimeline(spec,0);tl.advance(max(0,sec)*1000)
        return spec.id,tl.frame

    def _render_throw(self):
        from PIL import Image,ImageDraw
        p=self.flight
        if p is None:return
        if self._throw_caught:
            if self._throw_canvas is not None:self.pet.show_image(self._throw_canvas,self.pet.x,self.pet.y)
            return
        dpi=self._throw_dpi;s=p.scale*dpi;side=max(1,round(360*s));co=side/2
        x,y,a=p.display_position
        if p.phase=='dizzy':a*=max(0,1-p.phase_time/p.c['dizzyIntroSeconds'])
        if p.phase=='recover':a=0
        shift=p.bounds()[1]-p.bounds(a)[1] if p.ground else 0
        self._throw_draw_angle=a;self._throw_draw_shift=shift
        pose=self._interaction_pose();self._throw_pose=pose
        # Only decode when the selected frame changes. Pillow's RGBa mode keeps
        # transparent edge colour premultiplied through resampling and rotation.
        key=(*pose,self.blink_level if self.catalog.specs[pose[0]].blink else 0)
        if self._throw_source is None or self._throw_source[0]!=key:
            if self._throw_source is not None:self._throw_source[1].close()
            self._throw_source=(key,self.library.frame(*key).image)
        source=self._throw_source[1]
        sprite=source.convert('RGBa').resize((round(216*s),round(264*s)),Image.Resampling.BICUBIC)
        canvas=Image.new('RGBa',(side,side))
        cx,cy=self.throw_config['center'];px=round(co-(cx+12)*s);py=round(co-(cy+12)*s-shift*dpi)
        hit=p.last_impact
        if p.phase=='airborne' and hit is not None and hit.normal[1]<=0:
            u=(p.time-hit.time)/impact_duration(p.c,hit)
            if 0<=u<1:
                pulse=1.5*s*hit.strength*math.sin(math.pi*u)
                px+=round(hit.normal[0]*pulse);py-=round(hit.normal[1]*pulse)
        canvas.paste(sprite,(px,py));sprite.close()
        rotated=canvas.rotate(math.degrees(a),Image.Resampling.BICUBIC,center=(co,co-shift*dpi));canvas.close()
        image=rotated.convert('RGBA');rotated.close()
        left,top,right,bottom=self._throw_room
        ox=round(left+x*dpi-co);oy=round(bottom-y*dpi-co)
        hits=self.catalog.specs[pose[0]].hit_runs
        if hits is not None:
            mask=Image.new('L',(432,528));draw=ImageDraw.Draw(mask)
            for row,start,end in hits[pose[1]]:draw.line((start,row,end-1,row),fill=255)
            mask=mask.resize((round(216*s),round(264*s)),Image.Resampling.NEAREST)
            field=Image.new('L',(side,side));field.paste(mask,(px,py));mask.close()
            field=field.rotate(math.degrees(a),Image.Resampling.NEAREST,center=(co,co-shift*dpi))
            if self._throw_hit is not None:self._throw_hit.close()
            self._throw_hit=field
            box=field.getbbox()
            if box:
                ox=max(left-box[0],min(right-box[2],ox))
                oy=bottom-box[3] if p.ground else max(top-box[1],min(bottom-box[3],oy))
            mx,my=self.win32.cursor_pos();lx,ly=mx-ox,my-oy
            body=0<=lx<side and 0<=ly<side and field.getpixel((lx,ly))>0
            self.win32.set_click_through(self.pet.hwnd,not body and not self._drag_pending)
        self.pet.show_image(image,ox,oy)
        if self._throw_canvas is not None:self._throw_canvas.close()
        self._throw_canvas=image

    def _finish_throw(self):
        if getattr(self,'flight',None) is None:return
        p=self.flight;dpi=self._throw_dpi
        self.win32.user32.KillTimer(self.control.hwnd,2)
        side=360*p.scale*dpi;cx=self.pet.x+side/2
        ground=(self.pet.y+side/2-p.bounds()[1]*dpi) if self._throw_caught else self._throw_room[3]-(p.y+p.bounds()[1])*dpi
        image=self.library.frame(self.timeline.spec.id,self.timeline.frame).image
        box=image.getbbox();inset=(image.height-box[3])/image.height*self.pet_size[1] if box else 0;image.close()
        self.win32.set_click_through(self.pet.hwnd,False)
        self.flight=None; self._throw_caught=False;self._drag_dpi=None
        self.pet.x=round(cx-self.pet_size[0]/2);self.pet.y=round(ground+inset-self.pet_size[1])
        for name in ['_throw_canvas','_throw_hit']:
            im=getattr(self,name,None)
            if im is not None:im.close();setattr(self,name,None)
        if self._throw_source is not None:self._throw_source[1].close();self._throw_source=None
        self._painted=None;self._save_position();self._render(time.time()*1000)
        self._position_bubble();self._position_cards();self._position_question()

    def _cancel_throw(self):
        captured=getattr(self,"_drag_pending",False)
        self._drag_pending=False;self._dragging=False
        if captured:self.win32.user32.ReleaseCapture()
        self._finish_throw();self._finish_hang()
        self._throw_tracker=DragVelocityTracker();self._drag_dpi=None

    def _set_throw_enabled(self,value):
        self.settings.set('throwInteraction',bool(value))
        if not value:self._cancel_throw()
