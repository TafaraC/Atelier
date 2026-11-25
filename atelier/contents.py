"""Searchable inventory of a level and its placed objects."""
import tkinter as tk
from tkinter import ttk


def show_contents(app):
    level = app.board()
    window = tk.Toplevel(app)
    window.title(f"{level['name']} | Level contents")
    window.transient(app)
    window.geometry("900x460")
    frame = ttk.Frame(window, padding=12)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Search level contents").pack(anchor="w")
    query = tk.StringVar(master=window)
    search = ttk.Entry(frame, textvariable=query)
    search.pack(fill="x", pady=(2, 8))

    columns = ("type", "layer", "mechanics", "loot", "narrative")
    table = ttk.Treeview(frame, columns=columns, selectmode="browse")
    table.heading("#0", text="Name")
    table.column("#0", width=185)
    for key, label in zip(columns, ("Type", "Layer", "Mechanics", "Loot", "Plot relevance")):
        table.heading(key, text=label)
        table.column(key, width=110)
    scroll = ttk.Scrollbar(frame, command=table.yview)
    table.configure(yscrollcommand=scroll.set)
    actions = ttk.Frame(frame)
    actions.pack(side="bottom", fill="x", pady=(8, 0))
    scroll.pack(side="right", fill="y")
    table.pack(fill="both", expand=True)

    def refresh(*_):
        table.delete(*table.get_children())
        term = query.get().casefold().strip()
        for row in app.rows.values():
            if row["id"] != level["id"] and (row.get("parent") != level["id"] or row["kind"] != "object"):
                continue
            layer = app.rows.get(row.get("layer"), {}).get("name", "")
            values = (row.get("shape", level["dimension"]), layer, row.get("mechanics", ""),
                      row.get("loot", ""), row.get("narrative", ""))
            searchable = [row["name"], *values, row.get("notes", ""), row.get("description", ""),
                          row.get("category", ""), row.get("conditions", ""), row.get("prerequisites", "")]
            if term in " ".join(map(str, searchable)).casefold():
                table.insert("", "end", iid=row["id"], text=row["name"], values=values)
        items = table.get_children()
        if items:
            table.selection_set(app.selected if app.selected in items else items[0])
        open_button.configure(state="normal" if items else "disabled")

    def inspect(_=None):
        selected = table.selection()
        if selected:
            window.destroy()
            app.navigate(selected[0])

    open_button = ttk.Button(actions, text="Show in inspector", command=inspect)
    open_button.pack(side="right")
    table.bind("<Double-1>", lambda event: inspect() if table.identify_row(event.y) else None)
    table.bind("<Return>", inspect)
    window.bind("<Escape>", lambda _: window.destroy())
    query.trace_add("write", refresh)
    refresh()
    window.grab_set()
    search.focus_set()
