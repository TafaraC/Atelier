import math
import re
import tkinter as tk
from tkinter import ttk, messagebox

FIELDS = {
    "level":"description location environment atmosphere objectives mechanics loot narrative difficulty progression status references notes",
    "object":"description category mechanics loot narrative conditions prerequisites notes",
    "project":"description tags notes",
    "character":"aliases description appearance personality motivations background affiliations abilities role arc secrets status notes",
    "faction":"description history motivations hierarchy notes",
    "lore":"category description public_account actual_account revelation notes",
    "event":"date end_date dating location description causes consequences significance public_account actual_account discovery notes",
    "era":"date end_date dating description significance notes",
    "edge":"category direction description motivation public_perception visibility start end historical_state notes",
    "timeline":"description calendar unit origin spacing notes",
    "track":"description notes",
    "entry":"start end notes",
}
VECTORS=("pos","size","rotation")


def edit_record(a):
    r=a.rows[a.selected]
    if a.locked(a.selected) and r["kind"]!="layer":return
    win=tk.Toplevel(a)
    win.title("Properties · "+r["name"])
    win.transient(a)
    tabs=ttk.Notebook(win)
    tabs.pack(fill="both",expand=True,padx=10,pady=10)
    keys=["name"]+FIELDS.get(r["kind"],"description notes").split()
    if r["kind"]=="level":keys+=["grid","units"]
    if r["kind"]=="object":keys+=["colour"]+[k for k in VECTORS if k in r]
    if r.get("shape")=="Route":keys+=["points"]
    if r["kind"]=="layer":keys+=["hidden","locked"]
    values={}
    for index,k in enumerate(keys):
        if index%6==0:
            frame=ttk.Frame(tabs,padding=12)
            tabs.add(frame,text=k.replace("_"," ").title())
        label=k.replace("_"," ").title()
        val=r.get(k,"")
        if k in VECTORS:val=", ".join(str(round(n,3)) for n in val)
        if k=="points":
            import json
            val=json.dumps(val)
            label="Waypoints (relative to position, JSON)"
        if k in ("hidden","locked"):
            var=tk.BooleanVar(value=bool(val))
            ttk.Checkbutton(frame,text=label,variable=var).pack(anchor="w")
        else:
            ttk.Label(frame,text=label).pack(anchor="w")
            var=tk.StringVar(value=val)
            ttk.Entry(frame,textvariable=var,width=58).pack(fill="x",pady=(0,6))
        values[k]=var
    def save():
        try:
            data={k:v.get() for k,v in values.items()}
            if not data["name"].strip():raise ValueError("Enter a name.")
            for k in VECTORS:
                if k in data:
                    nums=[float(s) for s in data[k].split(",")]
                    if len(nums)!=len(r[k]) or not all(map(math.isfinite,nums)):
                        raise ValueError("Use comma-separated coordinates for each axis.")
                    if k=="size" and min(nums)<=0:raise ValueError("Dimensions must be positive.")
                    data[k]=nums
            for k in ("grid","origin","spacing"):
                if k in data:
                    data[k]=float(data[k] or (0 if k=="origin" else 20))
                    if not math.isfinite(data[k]) or (k!="origin" and data[k]<=0):raise ValueError("Invalid scale")
            if "colour" in data and not re.fullmatch("#[0-9a-fA-F]{6}",data["colour"]):raise ValueError("Use a colour such as #82927b.")
            if r["kind"]=="entry":
                data["start"]=float(data["start"])
                data["end"]=float(data["end"])
                if not all(math.isfinite(data[k]) for k in ("start","end")) or data["end"]<data["start"]:
                    raise ValueError("Enter a finite interval with the end at or after the start.")
            if "points" in data:
                import json
                data["points"]=json.loads(data["points"])
                if len(data["points"])<2:raise ValueError("A route needs two waypoints.")
            a.change(lambda:r.update(data))
        except (ValueError,TypeError) as exc:
            messagebox.showerror("Properties",str(exc),parent=win)
            return
        win.destroy()
    ttk.Button(win,text="Save properties",command=save).pack(anchor="e",padx=12,pady=8)
    win.bind("<Escape>",lambda _:win.destroy())
    win.grab_set()

