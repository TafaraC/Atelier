import base64
import copy
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from .forms import ask
from .sync import call, merge


def panel(app):
    if getattr(app,"cloud_panel",None) and app.cloud_panel.winfo_exists():
        app.cloud_panel.lift()
        return
    win=tk.Toplevel(app)
    app.cloud_panel=win
    win.title("Atelier · Collaboration")
    frame=ttk.Frame(win,padding=16)
    frame.pack(fill="both",expand=True)
    endpoint=tk.StringVar(value=app.store.setting("endpoint","http://127.0.0.1:8462"))
    account=tk.StringVar(value=app.store.setting("account",""))
    password=tk.StringVar()
    note=tk.StringVar(value="Connect to your Atelier service")
    token=""
    logged_endpoint=""
    for label,var in [("Service URL",endpoint),("Account",account),("Password",password)]:
        ttk.Label(frame,text=label).pack(anchor="w")
        ttk.Entry(frame,textvariable=var,width=48,show="•" if var==password else "").pack(fill="x",pady=(0,5))
    buttons=ttk.Frame(frame)
    buttons.pack(fill="x")
    busy=False
    def request(action,done,**data):
        nonlocal busy
        if busy:return
        url=endpoint.get().strip().rstrip("/")
        if action not in ("register","login","reset") and (not token or logged_endpoint!=url):
            note.set("Sign in to this service first.")
            return
        busy=True
        for w in buttons.winfo_children():w.configure(state="disabled")
        note.set("Synchronising…" if action in ("push","pull","publish") else "Connecting…")
        app.status.set(note.get())
        out=queue.Queue()
        session=token if url==logged_endpoint else ""
        def worker():
            try:out.put((True,call(url,session,action,**data)))
            except Exception as exc:out.put((False,str(exc)))
        def finish():
            nonlocal busy
            if out.empty():
                app.after(80,finish)
                return
            ok,result=out.get()
            busy=False
            if not win.winfo_exists():return
            for w in buttons.winfo_children():w.configure(state="normal")
            try:
                if not ok:raise ValueError(result)
                note.set("Connected")
                app.status.set("Saved locally")
                done(result)
            except Exception as exc:
                note.set(str(exc))
                app.status.set("Sync needs attention · local data retained")
        threading.Thread(target=worker,daemon=True).start()
        app.after(80,finish)

    def auth(action):
        nonlocal token,logged_endpoint
        data=dict(account=account.get(),password=password.get())
        if action=="reset":
            code=simpledialog.askstring("Reset password","Recovery code (password field contains new password)",parent=win)
            if not code:return
            data["recovery"]=code
        url=endpoint.get().strip().rstrip("/")
        def done(result):
            nonlocal token,logged_endpoint
            if action=="login":
                token=result["token"]
                logged_endpoint=url
                app.store.configure("endpoint",url)
                app.store.configure("account",data["account"])
                password.set("")
                note.set("Signed in · "+data["account"])
            else:
                password.set("")
                show_code("Store this private account recovery code",result["recovery"])
                note.set("Enter your password to sign in.")
        request(action,done,**data)

    def show_code(title,value):
        box=tk.Toplevel(win)
        box.title(title)
        ttk.Label(box,text=title,padding=10).pack()
        entry=ttk.Entry(box,width=52)
        entry.insert(0,value)
        entry.configure(state="readonly")
        entry.pack(padx=10,pady=10)
        entry.focus_set()
        entry.selection_range(0,"end")

    def baseline(pid):
        return app.store.db.execute("SELECT revision,doc,endpoint FROM baselines WHERE id=?",(pid,)).fetchone()

    def save_base(doc,rev,url):
        with app.store.db:
            app.store.db.execute("INSERT OR REPLACE INTO baselines VALUES(?,?,?,?)",
                                 (doc["id"],rev,json.dumps(doc),url))

    def encoded(doc):return base64.b64encode(app.store.pack(doc)).decode()

    def publish():
        snap=copy.deepcopy(app.doc)
        url=endpoint.get().strip().rstrip("/")
        def done(result):
            save_base(snap,result["revision"],url)
            note.set("Published · invite a collaborator")
            app.status.set("Synced" if snap==app.doc else "Saved locally · pending sync")
        request("publish",done,id=snap["id"],archive=encoded(snap))

    def sync():
        snap=copy.deepcopy(app.doc)
        pid=snap["id"]
        base=baseline(pid)
        url=endpoint.get().strip().rstrip("/")
        if not base or base[2]!=url:
            note.set("Publish this project or download a shared project first.")
            return
        def pulled(result):
            if app.doc!=snap:
                note.set("Local project changed during transfer. Sync again.")
                return
            remote=app.store.unpack(base64.b64decode(result["archive"]))
            merged,conflicts=merge(json.loads(base[1]),snap,remote)
            if conflicts:
                answers={}
                for key in conflicts:
                    left,right=snap["records"].get(key),remote["records"].get(key)
                    def summary(row):return json.dumps(row,ensure_ascii=False,indent=2) if row else "(deleted)"
                    choice=messagebox.askyesnocancel("Resolve conflict · "+(left or right)["name"],
                        "Keep local version? Choose No for the shared version, or Cancel to keep editing.\n\nLocal\n"+
                        summary(left)[:900]+"\n\nShared\n"+summary(right)[:900],parent=win)
                    if choice is None:
                        note.set("Conflict unresolved · both copies retained")
                        return
                    answers[key]="Local" if choice else "Remote"
                merged,_=merge(json.loads(base[1]),snap,remote,answers)
            def complete(revision):
                if app.doc!=snap:
                    note.set("Local edits continued. Sync again to reconcile.")
                    return
                if app.doc!=merged:app.switch(merged)
                save_base(merged,revision,url)
                note.set(f"Synced · revision {revision}")
                app.status.set(note.get())
            if merged==remote:complete(result["revision"])
            else:request("push",lambda res:complete(res["revision"]),id=pid,revision=result["revision"],archive=encoded(merged))
        request("pull",pulled,id=pid)

    def download():
        def listed(result):
            projects=result["projects"]
            key=app.choose("Download shared project",[dict(r,kind=r["role"]) for r in projects])
            if not key:return
            if any(d["id"]==key for d in app.store.projects()):
                note.set("Already downloaded. Open the local project and choose Sync.")
                return
            url=endpoint.get().strip().rstrip("/")
            def done(result):
                doc=app.store.unpack(base64.b64decode(result["archive"]))
                app.switch(doc)
                save_base(doc,result["revision"],url)
                note.set("Downloaded · available offline")
            request("pull",done,id=key)
        request("list",listed)

    def invite():
        v=ask(win,"Invite collaborator",[("Account","",None),("Role","editor",["viewer","editor","administrator"])])
        if v:request("invite",lambda r:show_code("Share this invitation code with "+v["Account"],r["code"]),
                     id=app.doc["id"],account=v["Account"],role=v["Role"])
    def accept():
        code=simpledialog.askstring("Accept invitation","Invitation code",parent=win)
        if code:request("accept",lambda _:note.set("Invitation accepted · choose Download"),code=code)
    def revoke():
        who=simpledialog.askstring("Revoke access","Collaborator account",parent=win)
        if who:request("revoke",lambda _:note.set("Access updated"),account=who,id=app.doc["id"])
    def signout():
        def done(_):
            nonlocal token
            token=""
            password.set("")
            note.set("Signed out")
        request("logout",done)
    for i,(title,cmd) in enumerate([("Register",lambda:auth("register")),("Sign in",lambda:auth("login")),
        ("Reset password",lambda:auth("reset")),("Publish project",publish),("Download",download),("Sync",sync),
        ("Invite",invite),("Accept invitation",accept),("Revoke access",revoke),("Sign out",signout)]):
        ttk.Button(buttons,text=title,command=cmd).grid(row=i//3,column=i%3,sticky="ew",padx=2,pady=2)
    ttk.Label(frame,textvariable=note,wraplength=400).pack(anchor="w",pady=8)

