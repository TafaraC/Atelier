import tkinter as tk
from tkinter import ttk


def ask(parent, title, fields):
    """Fields are (label, initial, choices); a None choice list is free text."""
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.resizable(True, True)
    win.columnconfigure(1, weight=1)
    inputs = {}
    result = {}
    for index,(label,value,choices) in enumerate(fields):
        ttk.Label(win,text=label).grid(row=index,column=0,padx=12,pady=5,sticky="w")
        var = tk.StringVar(win,value=value)
        widget = (ttk.Combobox(win,textvariable=var,values=choices,state="readonly") if choices
                  else ttk.Entry(win,textvariable=var,width=44))
        widget.grid(row=index,column=1,padx=12,pady=5,sticky="ew")
        inputs[label] = var
        if index==0: widget.focus_set()
    def accept(*_):
        result.update({k:v.get().strip() for k,v in inputs.items()})
        win.destroy()
    ttk.Button(win,text="Apply",command=accept).grid(row=len(fields),column=1,sticky="e",padx=12,pady=12)
    win.bind("<Return>",accept)
    win.bind("<Escape>",lambda _:win.destroy())
    win.grab_set()
    parent.wait_window(win)
    return result or None

