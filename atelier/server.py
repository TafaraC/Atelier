"""Hosted collaboration service. Bind locally behind HTTPS, or supply a TLS certificate."""
import argparse
from contextlib import closing
import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import ssl
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .store import LIMIT, Store

MAX_BODY= (LIMIT*4//3)+16384


class Problem(Exception):
    def __init__(self,status,message):
        super().__init__(message)
        self.status=status


def secret_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password,salt):
    if not isinstance(password,str) or not 10<=len(password)<=256:
        raise Problem(400,"Use a password of 10–256 characters")
    return hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1)


def initialize(path):
    with closing(sqlite3.connect(path)) as db:
        db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users(name TEXT PRIMARY KEY,salt BLOB,password BLOB,recovery TEXT);
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user TEXT,expires REAL);
            CREATE TABLE IF NOT EXISTS shared(id TEXT PRIMARY KEY,name TEXT,revision INTEGER,data BLOB,author TEXT);
            CREATE TABLE IF NOT EXISTS members(project TEXT,user TEXT,role TEXT,PRIMARY KEY(project,user));
            CREATE TABLE IF NOT EXISTS invites(token TEXT PRIMARY KEY,project TEXT,recipient TEXT,role TEXT,expires REAL);
        """)


def handle(db,action,p,token):
    if action in ("register","login","reset"):
        name=p["account"].strip().casefold()
        if not name or len(name)>200:raise Problem(400,"Enter an account name")
        row=db.execute("SELECT salt,password,recovery FROM users WHERE name=?",(name,)).fetchone()
        if action=="register":
            if row:raise Problem(409,"Account unavailable")
            salt=secrets.token_bytes(16)
            recovery=secrets.token_urlsafe(24)
            db.execute("INSERT INTO users VALUES(?,?,?,?)",(name,salt,password_hash(p["password"],salt),secret_hash(recovery)))
            return {"recovery":recovery}
        if action=="reset":
            if not row or not hmac.compare_digest(row[2],secret_hash(p["recovery"])):raise Problem(403,"Invalid recovery details")
            salt=secrets.token_bytes(16)
            recovery=secrets.token_urlsafe(24)
            db.execute("UPDATE users SET salt=?,password=?,recovery=? WHERE name=?",(salt,password_hash(p["password"],salt),secret_hash(recovery),name))
            db.execute("DELETE FROM sessions WHERE user=?",(name,))
            return {"recovery":recovery}
        if not row or not hmac.compare_digest(password_hash(p["password"],row[0]),row[1]):raise Problem(403,"Invalid sign-in")
        session=secrets.token_urlsafe(32)
        db.execute("INSERT INTO sessions VALUES(?,?,?)",(secret_hash(session),name,time.time()+86400))
        return {"token":session}
    session=db.execute("SELECT user FROM sessions WHERE token=? AND expires>?",(secret_hash(token),time.time())).fetchone()
    if not session:raise Problem(401,"Sign in first")
    user=session[0]
    if action=="logout":
        db.execute("DELETE FROM sessions WHERE token=?",(secret_hash(token),))
        return {}
    if action=="list":
        return {"projects":[dict(id=k,name=n,role=r) for k,n,r in db.execute(
            "SELECT id,name,role FROM shared JOIN members ON members.project=shared.id WHERE user=? ORDER BY name",(user,))]}
    if action=="accept":
        key=secret_hash(p["code"].strip())
        invite=db.execute("SELECT project,recipient,role FROM invites WHERE token=? AND expires>?",(key,time.time())).fetchone()
        if not invite or invite[1]!=user:raise Problem(403,"Invalid invitation for this account")
        db.execute("INSERT OR IGNORE INTO members VALUES(?,?,?)",(invite[0],user,invite[2]))
        db.execute("DELETE FROM invites WHERE token=?",(key,))
        return {"id":invite[0]}
    pid=p["id"]
    row=db.execute("SELECT role FROM members WHERE project=? AND user=?",(pid,user)).fetchone()
    role=row[0] if row else ""
    if action=="publish":
        if db.execute("SELECT 1 FROM shared WHERE id=?",(pid,)).fetchone():raise Problem(409,"Project already exists")
    elif not role:raise Problem(403,"No access to this project")
    if action in ("publish","push"):
        if action=="push" and role=="viewer":raise Problem(403,"Viewer access is read-only")
        blob=base64.b64decode(p["archive"],validate=True)
        temp=Store(":memory:")
        try:doc=temp.unpack(blob)
        finally:temp.db.close()
        if doc["id"]!=pid:raise Problem(400,"Archive project mismatch")
        name=doc["records"][pid]["name"]
        if action=="publish":
            db.execute("INSERT INTO shared VALUES(?,?,1,?,?)",(pid,name,blob,user))
            db.execute("INSERT INTO members VALUES(?,?,'owner')",(pid,user))
            return {"revision":1}
        rev=p["revision"]
        count=db.execute("UPDATE shared SET name=?,data=?,revision=revision+1,author=? WHERE id=? AND revision=?",
                         (name,blob,user,pid,rev)).rowcount
        if not count:raise Problem(409,"Another device synced. Sync again to merge.")
        return {"revision":rev+1}
    if action=="pull":
        rev,blob=db.execute("SELECT revision,data FROM shared WHERE id=?",(pid,)).fetchone()
        return {"revision":rev,"archive":base64.b64encode(blob).decode(),"role":role}
    if action in ("invite","revoke"):
        if role not in ("owner","administrator"):raise Problem(403,"Owner or administrator access required")
        target=p["account"].strip().casefold()
        if not target:raise Problem(400,"Enter the collaborator's account name")
        if action=="revoke":
            db.execute("DELETE FROM members WHERE project=? AND user=? AND role IN ('viewer','editor'"+(",'administrator'" if role=="owner" else "")+")",(pid,target))
            db.execute("DELETE FROM invites WHERE project=? AND recipient=?",(pid,target))
            return {}
        if p["role"] not in (["editor","viewer","administrator"] if role=="owner" else ["viewer","editor"]):raise Problem(403,"Role unavailable")
        code=secrets.token_urlsafe(24)
        db.execute("INSERT INTO invites VALUES(?,?,?,?,?)",(secret_hash(code),pid,target,p["role"],time.time()+7*86400))
        return {"code":code}
    raise Problem(404,"Unknown action")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        status=200
        try:
            if self.path!="/atelier":raise Problem(404,"Unknown endpoint")
            size=int(self.headers.get("Content-Length",0))
            if not 0<size<=MAX_BODY:raise Problem(413,"Request size exceeds project limit")
            body=json.loads(self.rfile.read(size))
            db=sqlite3.connect(self.server.database,timeout=30)
            try:
                with db:
                    db.execute("BEGIN IMMEDIATE")
                    result=handle(db,body["action"],body.get("data",{}),self.headers.get("Authorization","").removeprefix("Bearer "))
            finally:db.close()
        except Problem as exc:status,result=exc.status,{"error":str(exc)}
        except (sqlite3.Error,OSError):status,result=503,{"error":"Service unavailable"}
        except Exception:status,result=400,{"error":"Invalid project or request"}
        data=json.dumps(result).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--database",default="atelier-cloud.sqlite")
    p.add_argument("--bind",default="127.0.0.1")
    p.add_argument("--port",type=int,default=8462)
    p.add_argument("--cert")
    p.add_argument("--key")
    args=p.parse_args()
    if args.bind not in ("127.0.0.1","localhost","::1") and not (args.cert and args.key):
        p.error("Provide --cert and --key for external connections, or put an HTTPS proxy in front of loopback.")
    initialize(args.database)
    server=ThreadingHTTPServer((args.bind,args.port),Handler)
    server.database=args.database
    if args.cert:
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(args.cert,args.key)
        server.socket=ctx.wrap_socket(server.socket,server_side=True)
    print(f"Atelier service listening on {args.bind}:{server.server_port}",flush=True)
    server.serve_forever()


if __name__=="__main__":main()

