# core/marquee_selector.py - QT UYUMLU VERSİYON
import numpy as np
import glm
import logging

logger = logging.getLogger(__name__)

class MarqueeSelector:
    DRAG_THRESHOLD = 5.0
    
    def __init__(self, engine, selection_manager, selection_policy):
        self.engine = engine  # Qt widget (RenderEngineWidget)
        self.sel = selection_manager
        self.policy = selection_policy
        self.is_active = False
        self.start = self.end = None
        self.win_w = self.win_h = 0
    
    def start_selection(self, x, y):
        self.start = self.end = (x, y)
        self.is_active = True
    
    def update_selection(self, x, y):
        if self.is_active: 
            self.end = (x, y)
    
    def end_selection(self):
        if not self.is_active or not self.start or not self.end:
            self._reset()
            return []
        
        selected = []
        if self._is_drag_valid():
            selected = self._get_elements()
            if selected:
                mode = self.policy.get_marquee_mode() if self.policy else None
                if mode is not None:
                    self.sel.select_multiple(selected, mode=mode)
        
        self._reset()
        return selected
    
    def cancel_selection(self):
        self._reset()
    
    def get_box_coords(self):
        if self.is_active and self.start and self.end:
            return (*self.start, *self.end)
        return None
    
    def _reset(self):
        self.is_active = False
        self.start = self.end = None
    
    def _is_drag_valid(self):
        if not self.start or not self.end: 
            return False
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        return (dx*dx + dy*dy)**0.5 > self.DRAG_THRESHOLD
    
    def _get_fb_scale(self):
        """Qt widget'ından framebuffer boyutlarını al - GLFW yerine Qt kullan"""
        # Qt widget'ından doğrudan boyutları al
        if hasattr(self.engine, 'width') and hasattr(self.engine, 'height'):
            self.win_w = self.engine.width()
            self.win_h = self.engine.height()
        else:
            self.win_w = getattr(self.engine, 'w', 800)
            self.win_h = getattr(self.engine, 'h', 600)
        
        # Qt'de framebuffer scale genelde 1'dir (HighDPI için devicePixelRatio kullanılabilir)
        fb_w = self.win_w
        fb_h = self.win_h
        
        return 1.0, 1.0, fb_w, fb_h
    
    def _get_rect(self):
        sx, sy, fb_w, fb_h = self._get_fb_scale()
        x1, y1 = self.start[0]*sx, self.start[1]*sy
        x2, y2 = self.end[0]*sx, self.end[1]*sy
        return (min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2), x2<x1, fb_w, fb_h)
    
    def _get_elements(self):
        rect = self._get_rect()
        if not rect: 
            return []
        x1,y1,x2,y2,cross,fb_w,fb_h = rect
        
        cam = self.engine.cam
        mvp = cam.get_projection_matrix() @ cam.get_view_matrix()
        
        # Scene'den tüm elementleri al
        scene = getattr(self.engine, 'scene', None)
        if not scene:
            return []
        
        elements = []
        for e in scene.all_elements.values():
            if self._in_rect(e, (x1,y1), (x2,y2), mvp, fb_w, fb_h, cross):
                elements.append(e)
        
        return elements
    
    def _in_rect(self, e, minp, maxp, mvp, fb_w, fb_h, cross):
        from domain.element import Node, Frame, Area, Link
        
        if isinstance(e, Node): 
            return self._node_in(e, *minp, *maxp, mvp)
        if isinstance(e, (Frame, Link)): 
            return self._line_in(e.node_i, e.node_j, *minp, *maxp, mvp, cross)
        if isinstance(e, Area): 
            return self._area_in(e, *minp, *maxp, mvp, cross)
        return False
    
    def _node_in(self, n, x1,y1,x2,y2, mvp):
        p = self._project(n.x,n.y,n.z, mvp)
        return p and x1<=p[0]<=x2 and y1<=p[1]<=y2
    
    def _line_in(self, ni, nj, x1,y1,x2,y2, mvp, cross):
        p1 = self._project(ni.x,ni.y,ni.z, mvp)
        p2 = self._project(nj.x,nj.y,nj.z, mvp)
        if not p1 or not p2: 
            return False
        in1 = x1<=p1[0]<=x2 and y1<=p1[1]<=y2
        in2 = x1<=p2[0]<=x2 and y1<=p2[1]<=y2
        return (in1 and in2) if not cross else (in1 or in2 or self._line_rect(p1,p2,x1,y1,x2,y2))
    
    def _area_in(self, a, x1,y1,x2,y2, mvp, cross):
        pts = [self._project(n.x,n.y,n.z, mvp) for n in a.nodes]
        pts = [p for p in pts if p]
        if not pts: 
            return False
        if not cross: 
            return all(x1<=p[0]<=x2 and y1<=p[1]<=y2 for p in pts)
        if any(x1<=p[0]<=x2 and y1<=p[1]<=y2 for p in pts): 
            return True
        n = len(pts)
        return any(self._line_rect(pts[i], pts[(i+1)%n], x1,y1,x2,y2) for i in range(n))
    
    def _project(self, x,y,z, mvp):
        try:
            clip = mvp * glm.vec4(x,y,z,1.0)
            if clip.w <= 0: 
                return None
            ndc = glm.vec3(clip) / clip.w
            w = getattr(self.engine, 'w', 800)
            h = getattr(self.engine, 'h', 600)
            return ((ndc.x+1)*w/2, (1-ndc.y)*h/2)
        except: 
            return None
    
    def _line_rect(self, p1,p2, x1,y1,x2,y2):
        xa,ya = p1
        xb,yb = p2
        if (x1<=xa<=x2 and y1<=ya<=y2) or (x1<=xb<=x2 and y1<=yb<=y2): 
            return True
        if max(xa,xb)<x1 or min(xa,xb)>x2 or max(ya,yb)<y1 or min(ya,yb)>y2: 
            return False
        return True