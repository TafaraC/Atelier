"""Graph and timeline placements reference shared profiles and historical records."""
from tkinter import ttk, simpledialog, messagebox
from .store import record
from .forms import ask


def toolbar(app):
    if app.board()["kind"]=="graph":
        commands=[("Place profile",lambda:place_profile(app)),("Relationship",lambda:relationship(app))]
    else:
        commands=[("Add track",lambda:add_track(app)),("Place event / era",lambda:place_event(app))]
    for label,cmd in commands:ttk.Button(app.toolbar,text=label,command=cmd).pack(side="left",padx=2)


def children(a,kind):
    return [r for r in a.rows.values() if r["kind"]==kind and r.get("parent")==a.active]


def place_profile(a):
    key=a.choose("Place character or faction",[r for r in a.rows.values() if r["kind"] in ("character","faction")])
    if not key:return
    nodes=children(a,"node")
    for node in nodes:
        if node["entity"]==key:
            a.select(node["id"])
            return
    n=len(nodes)
    a.add(record("node","Profile placement",entity=key,parent=a.active,pos=[(n%3-1)*150,(n//3)*90]))


def relationship(a):
    nodes=children(a,"node")
    choices={a.rows[n["entity"]]["name"]+" ["+n["id"][:6]+"]":n["entity"] for n in nodes}
    if len(choices)<2:
        messagebox.showinfo("Relationship","Place two profiles on this graph first.",parent=a)
        return
    names=list(choices)
    v=ask(a,"Relationship",[("From",names[0],names),("To",names[1],names),("Relationship","Allegiance",None),
                             ("Direction","Directed",["Directed","Mutual","Undirected"])])
    if v and v["From"]!=v["To"]:
        a.add(record("edge",v["Relationship"],parent=a.active,source=choices[v["From"]],
                     target=choices[v["To"]],category=v["Relationship"],direction=v["Direction"]))


def add_track(a):
    name=simpledialog.askstring("Track","Track name",parent=a)
    if name:a.add(record("track",name,parent=a.active))


def place_event(a):
    tracks=children(a,"track")
    if not tracks:
        add_track(a)
        tracks=children(a,"track")
    if not tracks:return
    event=a.choose("Select event or era",[r for r in a.rows.values() if r["kind"] in ("event","era")])
    if not event:return
    names={r["name"]+" ["+r["id"][:5]+"]":r["id"] for r in tracks}
    v=ask(a,"Timeline placement",[("Track",next(iter(names)),list(names)),("Start (calendar units)","0",None),
                                  ("End (optional)","",None)])
    if v:
        import math
        start=float(v["Start (calendar units)"])
        end=float(v["End (optional)"] or start)
        if not all(map(math.isfinite,(start,end))) or end<start:raise ValueError("Enter a valid interval.")
        a.add(record("entry","Event placement",parent=a.active,entity=event,track=names[v["Track"]],start=start,end=end))


def draw(a,items):
    c=a.canvas
    if a.board()["kind"]=="graph":
        nodes={r["entity"]:r for r in items if r["kind"]=="node"}
        counts={}
        for e in items:
            if e["kind"]!="edge" or e["source"] not in nodes or e["target"] not in nodes:continue
            x,y=c.cam.screen(nodes[e["source"]]["pos"])
            u,v=c.cam.screen(nodes[e["target"]]["pos"])
            pair=tuple(sorted((e["source"],e["target"])))
            offset=counts.get(pair,0)
            counts[pair]=offset+1
            mid=((x+u)/2,(y+v)/2-24-offset*30)
            tags=("id:"+e["id"],)
            c.create_line(x,y,*mid,u,v,fill=c.outline(e),smooth=True,width=2,tags=tags)
            c.create_text(mid[0],mid[1]-5,text=e["name"]+{"Directed":" →","Mutual":" ↔"}.get(e.get("direction"),""),fill=c.outline(e),tags=tags)
        for key,n in nodes.items():
            x,y=c.cam.screen(n["pos"])
            tags=("id:"+n["id"],)
            c.create_rectangle(x-66,y-26,x+66,y+26,fill=a.paper,outline=c.outline(n),width=2,tags=tags)
            c.create_text(x,y-8,text=a.rows[key]["kind"].upper(),font=("Consolas",8),fill=a.ink,tags=tags)
            c.create_text(x,y+9,text=a.rows[key]["name"],width=126,fill=a.ink,tags=tags)
    else:
        tracks=[r for r in items if r["kind"]=="track"]
        board=a.board()
        origin=float(board.get("origin",0))
        spacing=float(board.get("spacing",30))
        unit=board.get("unit","years")
        for i,track in enumerate(tracks):
            _,y=c.cam.screen([0,(i-1)*100])
            c.create_line(0,y,c.winfo_width(),y,fill=a.ink,dash=(3,4))
            c.create_text(12,y-22,text=track["name"],anchor="w",fill=a.ink,font=("Georgia",14),tags=("id:"+track["id"],))
            for e in (r for r in items if r["kind"]=="entry" and r["track"]==track["id"]):
                x,_=c.cam.screen([(e["start"]-origin)*spacing,0])
                end,_=c.cam.screen([(e["end"]-origin)*spacing,0])
                tags=("id:"+e["id"],)
                ev=a.rows[e["entity"]]
                c.create_rectangle(x-4,y-6,max(end,x)+4,y+6,fill="#a67758",outline=c.outline(e),tags=tags)
                c.create_text(x,y+16,text=ev["name"],anchor="w",fill=c.outline(e),tags=tags)
                c.create_text(x,y+33,text=ev.get("date") or f"{e['start']:g} {unit}",anchor="w",fill=a.ink,tags=tags)

