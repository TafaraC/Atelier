"""Transport and three-way merge, including local or remote deletion."""
import json
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError
from .store import validate


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args):return None


def call(endpoint,token,action,**data):
    url=urlsplit(endpoint)
    if url.username or url.password or not url.hostname or not (
        url.scheme=="https" or (url.scheme=="http" and url.hostname in ("127.0.0.1","localhost","::1"))):
        raise ValueError("Use HTTPS, or HTTP on localhost for testing")
    req=Request(endpoint.rstrip("/")+"/atelier",data=json.dumps(dict(action=action,data=data)).encode(),
                headers={"Content-Type":"application/json","Authorization":"Bearer "+token})
    try:
        with build_opener(NoRedirect()).open(req,timeout=30) as resp:return json.load(resp)
    except HTTPError as exc:
        try:message=json.load(exc)["error"]
        except (ValueError,KeyError):message=f"Service returned HTTP {exc.code}"
        raise ValueError(message) from exc


def merge(base,local,remote,choices=None):
    rows={}
    conflicts=[]
    for key in sorted(base["records"].keys()|local["records"].keys()|remote["records"].keys()):
        b,l,r=(d["records"].get(key) for d in (base,local,remote))
        if l==r or r==b:value=l
        elif l==b:value=r
        else:
            if not choices or key not in choices:
                conflicts.append(key)
                continue
            value=l if choices[key]=="Local" else r
        if value is not None:rows[key]=value
    doc=dict(local,records=rows)
    if not conflicts:validate(doc)
    return doc,conflicts

