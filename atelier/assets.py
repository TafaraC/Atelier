import base64
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from .store import record


def choose_asset(app):
    items=[r for r in app.rows.values() if r["kind"]=="asset"]
    if items and messagebox.askyesno("Reference image","Use an existing project image?",parent=app):
        return app.choose("Project images",items)
    path=filedialog.askopenfilename(filetypes=[("Images","*.png *.gif")],parent=app)
    if not path:return
    data=Path(path).read_bytes()
    digest=app.store.put(data)
    tk.PhotoImage(master=app,data=base64.b64encode(data))
    r=record("asset",Path(path).name,hash=digest)
    app.add(r)
    return r["id"]

