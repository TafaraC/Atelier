"""Versioned project documents and content-addressed image storage."""
import copy
import hashlib
import io
import json
import os
import sqlite3
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

KINDS = {"project", "level", "graph", "timeline", "character", "faction", "lore",
         "event", "era", "layer", "object", "node", "edge", "track", "entry", "asset"}
BOARDS = {"level", "graph", "timeline"}
LIMIT = 64 * 1024 * 1024


def uid():
    return uuid.uuid4().hex


def record(kind, name, **fields):
    return dict(id=uid(), kind=kind, name=name, **fields)


def project(name):
    root = record("project", name)
    return {"version": 1, "id": root["id"], "records": {root["id"]: root}}


def validate(doc):
    if not isinstance(doc, dict) or doc.get("version") != 1:
        raise ValueError("Unsupported project format")
    rows = doc["records"]
    if rows[doc["id"]]["kind"] != "project":
        raise ValueError("Missing project header")
    for key, row in rows.items():
        if row["id"] != key or row["kind"] not in KINDS or not isinstance(row["name"], str):
            raise ValueError("Invalid project record")
        for field in ("parent", "entity", "source", "target", "layer", "asset", "track"):
            if row.get(field) and row[field] not in rows:
                raise ValueError(f"Missing {field} for {row['name']}")
        if any(ref not in rows for ref in row.get("refs", [])):
            raise ValueError("Missing referenced record")
        if row["kind"] == "level" and row.get("dimension") not in ("2D", "3D"):
            raise ValueError("Invalid level type")
        if row["kind"] == "object":
            level = rows[row["parent"]]
            if level["kind"] != "level" or row["dimension"] != level["dimension"]:
                raise ValueError("Geometry does not match level")
            count = 3 if level["dimension"] == "3D" else 2
            import math
            for point in [row["pos"], row["size"], row["rotation"], *row.get("points", [])]:
                if len(point) != count or not all(isinstance(v, (float, int)) and math.isfinite(v) for v in point):
                    raise ValueError("Invalid geometry")


def clone(doc):
    result = copy.deepcopy(doc)
    ids = {key: uid() for key in result["records"]}
    for row in result["records"].values():
        for field in ("id", "parent", "entity", "source", "target", "layer", "asset", "track"):
            if row.get(field):
                row[field] = ids[row[field]]
        if "refs" in row:
            row["refs"] = [ids[key] for key in row["refs"]]
    result["id"] = ids[result["id"]]
    result["records"] = {r["id"]: r for r in result["records"].values()}
    return result


class Store:
    def __init__(self, path=None):
        if path is None:
            home = Path(os.environ.get("ATELIER_HOME") or Path.home() / ".atelier")
            home.mkdir(parents=True, exist_ok=True)
            path = home / "studio.sqlite"
        self.db = sqlite3.connect(path)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, doc TEXT NOT NULL, modified TEXT);
            CREATE TABLE IF NOT EXISTS assets(hash TEXT PRIMARY KEY, data BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS baselines(id TEXT PRIMARY KEY, revision INTEGER, doc TEXT, endpoint TEXT);
        """)

    def save(self, doc):
        validate(doc)
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO projects VALUES(?,?,?)",
                            (doc["id"], json.dumps(doc), datetime.now(timezone.utc).isoformat()))

    def projects(self):
        return [json.loads(s) for s, in self.db.execute("SELECT doc FROM projects ORDER BY modified DESC")]

    def setting(self, key, default=None):
        row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def configure(self, key, value):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (key, value))

    def blob(self, digest):
        row = self.db.execute("SELECT data FROM assets WHERE hash=?", (digest,)).fetchone()
        if row is None:
            raise ValueError("Missing image data")
        return row[0]

    def put(self, data):
        if len(data) > LIMIT or not data.startswith((b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a")):
            raise ValueError("Choose a PNG or GIF image under 64 MiB")
        digest = hashlib.sha256(data).hexdigest()
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO assets VALUES(?,?)", (digest, data))
        return digest

    def pack(self, doc):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("project.json", json.dumps(doc, ensure_ascii=False))
            for digest in sorted({r["hash"] for r in doc["records"].values() if r["kind"] == "asset"}):
                archive.writestr("assets/" + digest, self.blob(digest))
        return stream.getvalue()

    def unpack(self, data):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(i.file_size for i in archive.infolist()) > LIMIT:
                raise ValueError("Archive exceeds the 64 MiB project limit")
            doc = json.loads(archive.read("project.json"))
            validate(doc)
            for row in doc["records"].values():
                if row["kind"] == "asset" and self.put(archive.read("assets/" + row["hash"])) != row["hash"]:
                    raise ValueError("Image checksum mismatch")
        return doc

