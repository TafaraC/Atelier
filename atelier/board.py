"""Interactive drafting canvas. All edits go through the studio transaction boundary."""
import base64
import math
import tkinter as tk
from tkinter import simpledialog
from .geometry import Camera, faces
from .store import record

PLAN = ("Select","Room","Wall","Platform","Ellipse","Region","Marker","Route","Sketch","Text","Image")
BLOCK = ("Select","Box","Cylinder","Ramp","Plane","Platform","Region","Marker","Route","Text","Image")
COLOURS = {"Region":"#7b906c","Marker":"#b77a55","Route":"#597a90","Ramp":"#af8264",
           "Cylinder":"#82927b","Room":"#9aa892","Platform":"#b19878"}


class Board(tk.Canvas):
    def __init__(self, app, parent):
        super().__init__(parent,highlightthickness=0)
        self.app=app
        self.cam=Camera()
        self.tool="Select"
        self.gesture=None
        self.path=[]
        self.images={}
        self.bind("<Configure>",lambda _:self.draw())
        self.bind("<ButtonPress-1>",self.press)
        self.bind("<B1-Motion>",self.move)
        self.bind("<ButtonRelease-1>",self.release)
        self.bind("<ButtonPress-2>",lambda e:self.start_nav(e,"pan"))
        self.bind("<B2-Motion>",self.nav)
        self.bind("<ButtonPress-3>",lambda e:self.start_nav(e,"orbit" if self.dimension()=="3D" else "pan"))
        self.bind("<B3-Motion>",self.nav)
        self.bind("<MouseWheel>",self.wheel)
        self.bind("<Double-1>",lambda _:self.app.edit() if self.tool=="Select" else None)

    def reset(self):
        self.cam=Camera()
        self.cam.center=[max(200,self.winfo_width()/2),max(160,self.winfo_height()/2)]
        self.path=[]
        self.gesture=None
        self.tool="Select"

    def dimension(self):
        return self.app.board().get("dimension","2D")

    def start_nav(self,e,mode):
        self.gesture=(mode,e.x,e.y)

    def nav(self,e):
        if not self.gesture:return
        mode,x,y=self.gesture
        if mode=="pan":
            self.cam.center[0]+=e.x-x
            self.cam.center[1]+=e.y-y
        else:
            self.cam.view="Orbit"
            self.cam.yaw+=(e.x-x)/150
            self.cam.pitch=max(.12,min(1.5,self.cam.pitch+(e.y-y)/150))
        self.gesture=(mode,e.x,e.y)
        self.draw()

    def wheel(self,e):
        old=self.cam.zoom
        self.cam.zoom=max(.15,min(6,old*(1.13 if e.delta>0 else 1/1.13)))
        self.cam.center=[p+(c-p)*self.cam.zoom/old for p,c in zip((e.x,e.y),self.cam.center)]
        self.draw()

    def world(self,e):
        p=self.cam.pick(e.x,e.y,self.dimension())
        unit=self.app.grid_size() if self.app.snap.get() else 1
        return [round(v/unit)*unit for v in p]

    def hit(self,e):
        for item in reversed(self.find_overlapping(e.x-4,e.y-4,e.x+4,e.y+4)):
            for tag in self.gettags(item):
                if tag.startswith("id:"):return tag[3:]
        return None

    def press(self,e):
        a=self.app
        if not a.active:return
        p=self.world(e)
        if self.tool=="Select":
            key=self.hit(e)
            a.select(key or a.active)
            if key and not a.locked(key):
                self.gesture=("drag",key,p)
            return
        if a.board()["kind"]!="level" or a.locked(a.layer):return
        if self.tool=="Route":
            self.path.append(p)
            self.draw()
            return
        self.gesture=("create",p)
        self.path=[p]

    def move(self,e):
        if not self.gesture:return
        if self.gesture[0]=="create":
            p=self.world(e)
            if self.tool=="Sketch":self.path.append(p)
            else:self.path=[self.gesture[1],p]
            self.draw()
        elif self.gesture[0]=="drag":
            self.delete("guide")
            x,y=self.cam.screen(self.gesture[2])
            self.create_line(x,y,e.x,e.y,dash=(3,3),fill=self.app.ink,tags="guide")

    def release(self,e):
        g,self.gesture=self.gesture,None
        if not g:return
        a=self.app
        p=self.world(e)
        if g[0]=="drag":
            row=a.rows.get(g[1],{})
            if "pos" in row and p!=g[2]:
                new=[v+b-c for v,b,c in zip(row["pos"],p,g[2])]
                a.change(lambda:row.update(pos=new))
            self.delete("guide")
        elif g[0]=="create":
            self.make(g[1],p)

    def finish(self):
        if self.tool=="Route" and len(self.path)>=2:self.make(self.path[0],self.path[-1])

    def make(self,start,end):
        a=self.app
        points=self.path
        self.path=[]
        dim=self.dimension()
        shape=self.tool
        span=[abs(v-u) for u,v in zip(start,end)]
        size=([max(20,span[0]),max(20,span[1])] if dim=="2D" else
              [max(40,span[0]),4 if shape=="Plane" else max(30,span[1]),max(40,span[2])])
        pos=[(x+y)/2 for x,y in zip(start,end)]
        if dim=="3D" and shape not in ("Route","Text","Marker"):pos[1]+=size[1]/2
        obj=record("object",shape,parent=a.active,layer=a.layer,dimension=dim,shape=shape,
                   pos=pos,size=size,rotation=[0]*len(pos),colour=COLOURS.get(shape,"#9d9782"))
        if shape in ("Sketch","Route"):
            if len(points)<2:return
            obj["points"]=[[v-u for v,u in zip(pt,pos)] for pt in points]
        if shape in ("Text","Marker"):
            name=simpledialog.askstring(shape,"Label",parent=a)
            if not name:return
            obj["name"]=name
        if shape=="Image":
            asset=a.choose_asset()
            if not asset:return
            obj["asset"]=asset
        a.add(obj)

    def draw(self):
        a=self.app
        self.delete("all")
        self.configure(bg=a.paper)
        w,h=self.winfo_width(),self.winfo_height()
        if not a.active:
            self.create_text(32,40,text="Project notebook",anchor="nw",font=("Georgia",25),fill=a.ink)
            self.create_text(32,98,text="Create or open a level, relationship graph or timeline in the explorer.",anchor="nw",width=max(100,w-70),fill=a.ink)
            return
        if self.dimension()=="3D":
            step=a.grid_size()*4
            for n in range(-12,13):
                for line in [([n*step,0,-12*step],[n*step,0,12*step]),([-12*step,0,n*step],[12*step,0,n*step])]:
                    self.create_line(*self.cam.screen(line[0]),*self.cam.screen(line[1]),fill=a.grid)
        else:
            step=max(10,a.grid_size()*self.cam.zoom)
            for axis,lim in enumerate((w,h)):
                v=self.cam.center[axis]%step
                while v<lim:
                    self.create_line(*( (v,0,v,h) if axis==0 else (0,v,w,v)),fill=a.grid)
                    v+=step
        children=[r for r in a.rows.values() if r.get("parent")==a.active and
                  not a.rows.get(r.get("layer"),{}).get("hidden")]
        if a.board()["kind"]!="level":
            a.draw_narrative(children)
        else:
            polys=[]
            overlays=[]
            for row in children:
                if row["kind"]!="object":continue
                if self.dimension()=="3D" and row["shape"] not in ("Text","Marker","Route","Image"):
                    for face in faces(row):
                        polys.append((sum(self.cam.axes(p)[2] for p in face)/len(face),row,face))
                else:overlays.append(row)
            for _,r,face in sorted(polys,key=lambda x:-x[0]):
                self.create_polygon([v for p in face for v in self.cam.screen(p)],fill=r["colour"],
                                    outline=self.outline(r),tags=("id:"+r["id"],))
            for row in overlays:self.paint(row)
        if len(self.path)>1:
            self.create_line([v for p in self.path for v in self.cam.screen(p)],fill=a.ink,width=2,dash=(4,3))
        if self.path:
            x,y=self.cam.screen(self.path[0])
            self.create_oval(x-3,y-3,x+3,y+3,fill=a.ink)
        a.viewstatus.set(f"{self.cam.view if self.dimension()=='3D' else 'Plan'}   ·   {round(self.cam.zoom*100)}%")

    def outline(self,r):
        return "#c85b29" if self.app.selected==r["id"] else self.app.ink

    def paint(self,r):
        x,y=self.cam.screen(r["pos"])
        w,h=[v*self.cam.zoom/2 for v in r["size"][:2]]
        opts=dict(tags=("id:"+r["id"],))
        colour=r["colour"]
        shape=r["shape"]
        if shape in ("Route","Sketch"):
            pts=[self.cam.screen([a+b for a,b in zip(p,r["pos"])]) for p in r["points"]]
            if len(pts)>1:self.create_line(pts,fill=self.outline(r) if self.app.selected==r["id"] else colour,width=3,
                                           arrow="last" if shape=="Route" else "none",**opts)
        elif shape=="Image":
            key=r["asset"]
            if key not in self.images:
                data=self.app.store.blob(self.app.rows[key]["hash"])
                photo=tk.PhotoImage(data=base64.b64encode(data))
                self.images[key]=photo.subsample(max(1,math.ceil(max(photo.width(),photo.height())/240)))
            self.create_image(x,y,image=self.images[key],**opts)
        elif shape=="Text":
            self.create_text(x,y,text=r["name"],fill=self.outline(r),font=("Georgia",14),**opts)
        elif shape in ("Ellipse","Marker"):
            if shape=="Marker":w=h=7
            self.create_oval(x-w,y-h,x+w,y+h,fill=colour,outline=self.outline(r),width=2,**opts)
            if shape=="Marker":self.create_text(x+12,y,text=r["name"],anchor="w",fill=self.app.ink,**opts)
        else:
            ang=math.radians(r["rotation"][0])
            corners=[(x+u*math.cos(ang)-v*math.sin(ang),y+u*math.sin(ang)+v*math.cos(ang)) for u,v in [(-w,-h),(w,-h),(w,h),(-w,h)]]
            self.create_polygon(corners,fill=colour,outline=self.outline(r),width=2,**opts)

