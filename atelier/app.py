import copy
import json
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox

from .store import Store, BOARDS, project, record, clone
from .board import Board, PLAN, BLOCK
from .forms import ask


class Studio(tk.Tk):
    def __init__(self, store=None):
        super().__init__()
        self.title("Atelier  /  Game design studio")
        self.geometry("1260x800")
        self.minsize(820,520)
        self.store=store or Store()
        projects=self.store.projects()
        self.doc=next((d for d in projects if not d["records"][d["id"]].get("archived")),None) or project("Untitled project")
        self.store.save(self.doc)
        self.active=self.layer=None
        self.selected=self.doc["id"]
        self.past,self.future=[],[]
        self.status=tk.StringVar(value="Saved locally")
        self.viewstatus=tk.StringVar()
        self.snap=tk.BooleanVar(value=True)
        self.query=tk.StringVar()
        self.filter=tk.StringVar(value="All records")
        self.theme=tk.StringVar(value=self.store.setting("theme","System"))
        self.style=ttk.Style(self)
        self.style.theme_use("clam")
        self.menus()
        shell=ttk.Frame(self,padding=(14,9))
        shell.pack(fill="x")
        ttk.Label(shell,text="Atelier",font=("Georgia",23,"italic")).pack(side="left")
        self.heading=ttk.Label(shell,font=("Segoe UI",12))
        self.heading.pack(side="left",padx=28)
        ttk.Button(shell,text="New level",command=self.new_level).pack(side="right")
        self.panes=ttk.Panedwindow(self,orient="horizontal")
        self.panes.pack(fill="both",expand=True)
        left=ttk.Frame(self.panes,padding=9)
        self.panes.add(left,weight=0)
        ttk.Label(left,text="PROJECT EXPLORER").pack(anchor="w",pady=6)
        ttk.Entry(left,textvariable=self.query,width=23).pack(fill="x")
        ttk.Combobox(left,textvariable=self.filter,values=("All records","2D","3D"),state="readonly",width=15).pack(fill="x",pady=5)
        self.tree=ttk.Treeview(left,show="tree",selectmode="browse")
        self.tree.column("#0",width=190)
        self.tree.pack(fill="both",expand=True)
        self.tree.bind("<<TreeviewSelect>>",self.open_tree)
        middle=ttk.Frame(self.panes)
        self.panes.add(middle,weight=5)
        self.toolbar=ttk.Frame(middle,padding=5)
        self.toolbar.pack(fill="x")
        self.canvas=Board(self,middle)
        self.canvas.pack(fill="both",expand=True)
        right=ttk.Frame(self.panes,padding=12)
        self.panes.add(right,weight=0)
        ttk.Label(right,text="INSPECTOR").pack(anchor="w",pady=6)
        self.detail=tk.Text(right,width=25,wrap="word",relief="flat",padx=8,pady=10,font=("Segoe UI",10))
        self.detail.pack(fill="both",expand=True)
        for label,cmd in [("Edit properties",self.edit),("Link record…",self.link),("Follow reference…",self.follow),("Remove selected",self.remove)]:
            ttk.Button(right,text=label,command=cmd).pack(fill="x",pady=2)
        foot=ttk.Frame(self,padding=(12,5))
        foot.pack(fill="x")
        ttk.Label(foot,textvariable=self.status).pack(side="left")
        ttk.Label(foot,textvariable=self.viewstatus).pack(side="right")
        self.query.trace_add("write",lambda *_:self.explorer())
        self.filter.trace_add("write",lambda *_:self.explorer())
        self.bind("<Control-z>",lambda _:self.undo())
        self.bind("<Control-y>",lambda _:self.undo(True))
        self.bind("<Escape>",lambda _:self.tool("Select"))
        self.bind("<Return>",lambda _:self.canvas.finish() if self.focus_get()==self.canvas else None)
        self.palette()
        self.refresh()
        self.after(2500,self.poll_theme)

    @property
    def rows(self):return self.doc["records"]

    def board(self):return self.rows.get(self.active,{})

    def grid_size(self):
        return max(1,float(self.board().get("grid",20)))

    def menus(self):
        bar=tk.Menu(self)
        self.config(menu=bar)
        def menu(title,items):
            m=tk.Menu(bar,tearoff=False)
            bar.add_cascade(label=title,menu=m)
            for label,fn in items:m.add_command(label=label,command=fn)
            return m
        menu("Project",[("New project…",self.new_project),("Open project…",self.open_project),
             ("Duplicate project",self.duplicate),("Archive / restore project",self.archive),
             ("Import archive…",self.import_file),("Export archive…",self.export),("Export JSON…",lambda:self.export(True))])
        menu("Create",[("Level…",self.new_level),("Drawing layer…",self.new_layer)]+
             [(k.title()+"…",lambda k=k:self.new_record(k)) for k in ("graph","character","faction","timeline","event","era","lore")])
        menu("Edit",[("Undo",self.undo),("Redo",lambda:self.undo(True)),("Properties…",self.edit),("Link record…",self.link),("Duplicate placement",self.duplicate_placement),("Frame selection",self.frame_selection)])
        menu("Collaboration",[("Open sync panel…",self.sync_panel)])
        themes=menu("Appearance",[])
        for v in ("System","Light","Dark"):
            themes.add_radiobutton(label=v,variable=self.theme,value=v,command=self.palette)

    def palette(self):
        theme=self.theme.get()
        dark=theme=="Dark"
        if theme=="System" and os.name=="nt":
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                    dark=not winreg.QueryValueEx(k,"AppsUseLightTheme")[0]
            except OSError:pass
        if getattr(self,"_palette_state",None)==(theme,dark):return
        self._palette_state=(theme,dark)
        self.paper,self.ink,self.grid,panel,accent=(
            ("#242722","#ece8df","#363c34","#353930","#637256") if dark else
            ("#f2ede2","#33392f","#dfd8c9","#e6dfd1","#c2cbae"))
        self.style.configure(".",background=panel,foreground=self.ink,fieldbackground=self.paper,font=("Segoe UI",10))
        self.style.configure("Treeview",background=self.paper,fieldbackground=self.paper,foreground=self.ink,rowheight=26)
        self.style.map("Treeview",background=[("selected",accent)],foreground=[("selected",self.ink)])
        self.style.map("TCombobox",fieldbackground=[("readonly",self.paper)],foreground=[("readonly",self.ink)])
        self.detail.configure(bg=self.paper,fg=self.ink)
        if self.store.setting("theme")!=theme:self.store.configure("theme",theme)
        self.canvas.draw()

    def poll_theme(self):
        if self.theme.get()=="System":self.palette()
        self.after(2500,self.poll_theme)

    def report_callback_exception(self,exc,value,tb):
        messagebox.showerror("Atelier",str(value) or exc.__name__,parent=self)

    def change(self,fn):
        prev=copy.deepcopy(self.doc)
        try:
            fn()
            self.store.save(self.doc)
        except Exception:
            self.doc=prev
            raise
        self.past=(self.past+[prev])[-60:]
        self.future=[]
        self.status.set("Saved locally · pending sync")
        self.refresh()

    def undo(self,redo=False):
        source,dest=(self.future,self.past) if redo else (self.past,self.future)
        if source:
            doc=source[-1]
            self.store.save(doc)
            dest.append(self.doc)
            self.doc=source.pop()
            self.status.set("Saved locally · pending sync")
            self.refresh()

    def add(self,row):
        self.selected=row["id"]
        self.change(lambda:self.rows.update({row["id"]:row}))

    def switch(self,doc):
        self.store.save(doc)
        self.doc=doc
        self.past.clear()
        self.future.clear()
        self.active=self.layer=None
        self.selected=doc["id"]
        self.canvas.reset()
        self.status.set("Saved locally")
        self.refresh()

    def new_project(self):
        name=simpledialog.askstring("New project","Project name",parent=self)
        if name and name.strip():self.switch(project(name.strip()))

    def choose(self,title,rows):
        pairs={f"{r['name']}  ·  {r['kind']}  [{r['id'][:8]}]":r["id"] for r in rows}
        if not pairs:
            messagebox.showinfo(title,"No matching records yet.",parent=self)
            return
        result=ask(self,title,[("Record",next(iter(pairs)),list(pairs))])
        return pairs[result["Record"]] if result else None

    def open_project(self):
        docs=self.store.projects()
        key=self.choose("Open project",[dict(d["records"][d["id"]],name=d["records"][d["id"]]["name"]+(" (archived)" if d["records"][d["id"]].get("archived") else "")) for d in docs])
        if key:self.switch(next(d for d in docs if d["id"]==key))

    def duplicate(self):
        doc=clone(self.doc)
        doc["records"][doc["id"]]["name"]+=" (copy)"
        self.switch(doc)

    def archive(self):
        row=self.rows[self.doc["id"]]
        self.change(lambda:row.update(archived=not row.get("archived",False)))

    def export(self,structured=False):
        ext=".json" if structured else ".atelier"
        path=filedialog.asksaveasfilename(defaultextension=ext,filetypes=[("Atelier project","*"+ext)],parent=self)
        if path:
            data=json.dumps(self.doc,indent=2).encode() if structured else self.store.pack(self.doc)
            Path(path).write_bytes(data)

    def import_file(self):
        path=filedialog.askopenfilename(filetypes=[("Atelier archive","*.atelier *.zip")],parent=self)
        if path:self.switch(clone(self.store.unpack(Path(path).read_bytes())))

    def new_level(self):
        val=ask(self,"Create level",[("Name","Untitled level",None),("Design type","2D",["2D","3D"]),("Plan convention","Top-down",["Top-down","Side-view","Isometric"])])
        if not val or not val["Name"]:return
        r=record("level",val["Name"],dimension=val["Design type"],view=val["Plan convention"] if val["Design type"]=="2D" else "Orbit",units="game units",grid=20)
        layer=record("layer","Base geometry",parent=r["id"])
        self.active=self.selected=r["id"]
        self.layer=layer["id"]
        self.canvas.reset()
        self.change(lambda:self.rows.update({r["id"]:r,layer["id"]:layer}))

    def new_layer(self):
        if self.board().get("kind")!="level":return
        name=simpledialog.askstring("Layer","Layer or floor name",parent=self)
        if name:
            r=record("layer",name,parent=self.active)
            self.layer=r["id"]
            self.add(r)

    def new_record(self,kind):
        name=simpledialog.askstring("Create "+kind,kind.title()+" name",parent=self)
        if name:
            r=record(kind,name)
            if kind in BOARDS:
                self.active=r["id"]
                self.canvas.reset()
            self.add(r)
            if kind not in BOARDS:self.edit()

    def locked(self,key):
        row=self.rows.get(key,{})
        return row.get("locked") or self.rows.get(row.get("layer"),{}).get("locked")

    def tool(self,name):
        self.canvas.tool=name
        self.canvas.path=[]
        self.canvas.focus_set()
        self.canvas.draw()
        self.status.set("Route · click waypoints, then Finish" if name=="Route" else name)

    def refresh(self):
        if self.active not in self.rows:self.active=None
        if self.selected not in self.rows:self.selected=self.active or self.doc["id"]
        layers=[r for r in self.rows.values() if r["kind"]=="layer" and r["parent"]==self.active]
        if self.layer not in [r["id"] for r in layers]:self.layer=layers[0]["id"] if layers else None
        self.heading.configure(text=self.rows[self.doc["id"]]["name"]+"   /   "+self.board().get("name","Project notebook"))
        self.explorer()
        self.draw_tools(layers)
        self.select(self.selected)

    def explorer(self):
        self.tree.delete(*self.tree.get_children())
        q=self.query.get().casefold()
        for r in self.rows.values():
            kind=r["kind"]
            if self.filter.get()!="All records" and r.get("dimension")!=self.filter.get():continue
            if q and q not in json.dumps(r,ensure_ascii=False).casefold():continue
            if r.get("parent") and not q and r["parent"]!=self.active:continue
            if kind in ("object","node","entry","edge","track") and not q:continue
            label=r.get("dimension",kind.title())
            self.tree.insert("","end",iid=r["id"],text=f"{label}  ·  {r['name']}")

    def open_tree(self,_):
        keys=self.tree.selection()
        if keys:self.navigate(keys[0])

    def navigate(self,key):
        r=self.rows[key]
        board=key if r["kind"] in BOARDS else r.get("parent")
        if board in self.rows and board!=self.active:
            self.active=board
            self.canvas.reset()
        if r["kind"]=="layer":self.layer=key
        self.selected=key
        self.refresh()

    def select(self,key):
        self.selected=key
        r=self.rows.get(key,{})
        self.detail.configure(state="normal")
        self.detail.delete("1.0","end")
        self.detail.insert("end",r.get("name","")+"\n"+r.get("kind","").upper()+"\n\n")
        for k,v in r.items():
            if k in ("id","kind","name","parent","points","hash"):continue
            if isinstance(v,str) and v in self.rows:v=self.rows[v]["name"]
            if k=="refs":v=", ".join(self.rows[i]["name"] for i in v)
            self.detail.insert("end",f"{k.title()}\n{v}\n\n")
        self.detail.configure(state="disabled")
        self.canvas.draw()

    def draw_tools(self,layers):
        for child in self.toolbar.winfo_children():child.destroy()
        if self.board().get("kind")!="level":
            self.narrative_tools()
            return
        from .contents import show_contents
        ttk.Button(self.toolbar,text="Level contents",command=lambda:show_contents(self)).pack(side="right")
        choices=BLOCK if self.canvas.dimension()=="3D" else PLAN
        def combo(items,current,callback):
            widget=ttk.Combobox(self.toolbar,values=items,width=12,state="readonly")
            widget.set(current)
            widget.pack(side="left",padx=2)
            widget.bind("<<ComboboxSelected>>",lambda _:callback(widget.get()))
        combo(choices,self.canvas.tool,self.tool)
        if self.canvas.dimension()=="3D":
            def view(v):
                self.canvas.cam.view=v
                self.canvas.draw()
            combo(["Orbit","Top","Front","Side"],self.canvas.cam.view,view)
        layer_keys={f"{r['name']} [{r['id'][:4]}]":r["id"] for r in layers}
        if layer_keys:
            combo(list(layer_keys),next(k for k,v in layer_keys.items() if v==self.layer),lambda v:self.navigate(layer_keys[v]))
        ttk.Checkbutton(self.toolbar,text="Snap",variable=self.snap).pack(side="left")
        ttk.Button(self.toolbar,text="Finish route",command=self.canvas.finish).pack(side="left")

    def duplicate_placement(self):
        row=self.rows.get(self.selected,{})
        if row.get("kind")!="object" or self.locked(self.selected):return
        from .store import uid
        duplicate=copy.deepcopy(row)
        duplicate["id"]=uid()
        duplicate["name"]+=" (copy)"
        duplicate["pos"][0]+=self.grid_size()
        self.add(duplicate)

    def frame_selection(self):
        row=self.rows.get(self.selected,{})
        if "pos" not in row:return
        c=self.canvas
        x,y=c.cam.screen(row["pos"])
        c.cam.center[0]+=c.winfo_width()/2-x
        c.cam.center[1]+=c.winfo_height()/2-y
        c.draw()

    def edit(self):
        from .properties import edit_record
        edit_record(self)

    def remove(self):
        key=self.selected
        if key==self.doc["id"] or self.locked(key):return
        pending={key}
        while True:
            extra={r["id"] for r in self.rows.values() if any(r.get(k) in pending for k in ("parent","source","target","entity","layer","asset","track"))}
            if extra<=pending:break
            pending|=extra
        if self.rows[key]["kind"]=="layer" and sum(r.get("kind")=="layer" and r.get("parent")==self.active for r in self.rows.values())<=1:
            messagebox.showinfo("Layer","Keep at least one drawing layer in this level.",parent=self)
            return
        if not messagebox.askyesno("Remove records",f"Remove {len(pending)} record(s) and clear their references? Undo is available.",parent=self):return
        def apply():
            for id_ in pending:del self.rows[id_]
            for r in self.rows.values():
                if "refs" in r:r["refs"]=[i for i in r["refs"] if i not in pending]
        self.change(apply)

    def link(self):
        r=self.rows[self.selected]
        key=self.choose("Link shared record",[v for v in self.rows.values() if v["id"]!=self.selected and v["kind"] in ("character","faction","event","era","level","lore")])
        if key and key not in r.get("refs",[]):self.change(lambda:r.setdefault("refs",[]).append(key))

    def follow(self):
        r=self.rows[self.selected]
        ids=r.get("refs",[])+[r[k] for k in ("entity","source","target","asset") if k in r]
        key=self.choose("Follow reference",[self.rows[i] for i in ids])
        if key:self.navigate(key)

    def choose_asset(self):
        from .assets import choose_asset
        return choose_asset(self)

    def draw_narrative(self,children):
        from .narrative import draw
        draw(self,children)

    def narrative_tools(self):
        if self.active:
            from .narrative import toolbar
            toolbar(self)

    def sync_panel(self):
        from .sync_ui import panel
        panel(self)


