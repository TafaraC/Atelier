import base64
import json
import os
import io
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from atelier.server import Handler, initialize
from atelier.store import Store, project, record
from atelier.sync import call,merge


class QuietHandler(Handler):
    def log_message(self,*args):pass


class Devices(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.server=ThreadingHTTPServer(("127.0.0.1",0),QuietHandler)
        self.server.database=str(Path(self.temp.name)/"remote.sqlite")
        initialize(self.server.database)
        self.thread=Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.network=os.getenv("ATELIER_TEST_NETWORK")=="1"
        self.url=f"http://127.0.0.1:{self.server.server_port}"
        self.clients=[Store(Path(self.temp.name)/f"device{i}.sqlite") for i in range(2)]
        self.tokens={}
        for user in ("owner","editor","viewer"):
            creds=dict(account=user,password="correct horse studio")
            self.exchange("","register",**creds)
            self.tokens[user]=self.exchange("","login",**creds)["token"]

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        for client in self.clients:client.db.close()
        self.temp.cleanup()

    def exchange(self,token,action,**data):
        if self.network:return call(self.url,token,action,**data)
        body=json.dumps(dict(action=action,data=data)).encode()
        headers=f"POST /atelier HTTP/1.0\r\nAuthorization: Bearer {token}\r\nContent-Length: {len(body)}\r\n\r\n"
        class Channel:
            def makefile(self,*_):return io.BytesIO(headers.encode()+body)
            def sendall(self,data):response.extend(data)
        response=bytearray()
        QuietHandler(Channel(),("local",0),self.server)
        payload=json.loads(response.split(b"\r\n\r\n",1)[1])
        if "error" in payload:raise ValueError(payload["error"])
        return payload

    def api(self,user,action,**data):return self.exchange(self.tokens[user],action,**data)

    def test_sync_invite_revoke_and_conflicts(self):
        a,b=self.clients
        doc=project("First hunt")
        root=doc["id"]
        char=record("character","Wayfarer")
        doc["records"][char["id"]]=char
        a.save(doc)
        def pack(store,project):return base64.b64encode(store.pack(project)).decode()
        self.api("owner","publish",id=root,archive=pack(a,doc))
        with self.assertRaises(ValueError):self.api("editor","pull",id=root)
        for user in ("editor","viewer"):
            code=self.api("owner","invite",id=root,account=user,role=user)["code"]
            self.api(user,"accept",code=code)
        data=self.api("editor","pull",id=root)
        local=b.unpack(base64.b64decode(data["archive"]))
        b.save(local)
        local["records"][char["id"]]["name"]="Tracker"
        b.save(local)
        remote=a.projects()[0]
        remote["records"][root]["name"]="Second hunt"
        self.api("owner","push",id=root,revision=1,archive=pack(a,remote))
        with self.assertRaises(ValueError):self.api("editor","push",id=root,revision=1,archive=pack(b,local))
        merged,conflicts=merge(doc,local,remote)
        self.assertFalse(conflicts)
        self.assertEqual(merged["records"][root]["name"],"Second hunt")
        self.assertEqual(merged["records"][char["id"]]["name"],"Tracker")
        self.api("editor","push",id=root,revision=2,archive=pack(b,merged))
        with self.assertRaises(ValueError):self.api("viewer","push",id=root,revision=3,archive=pack(b,merged))
        remote["records"][char["id"]]["name"]="Hunter"
        self.assertEqual(merge(doc,local,remote)[1],[char["id"]])
        del remote["records"][char["id"]]
        self.assertEqual(merge(doc,local,remote)[1],[char["id"]])
        self.api("owner","revoke",id=root,account="editor")
        with self.assertRaises(ValueError):self.api("editor","pull",id=root)
        self.assertEqual(b.projects()[0],local)

