import uuid
from fastapi import APIRouter, HTTPException
from .core import *
from .schemas import *
router = APIRouter()

@router.get("/tables/{tid}/objects")
def objs(tid: str): return get(tid)["objects"]

@router.post("/tables/{tid}/objects")
@locked
def add_obj(tid: str, o: ObjIn):
    if len(o.src) > 6_000_000: raise HTTPException(413, "Image trop lourde (6 Mo maximum)")
    d = get(tid); ob = {"id": uuid.uuid4().hex[:8], "kind": o.kind, "x": o.x, "y": o.y, "w": o.w, "h": o.h, "src": o.src, "cfg": o.cfg}
    d["objects"].append(ob); save(tid); return ob

@router.patch("/tables/{tid}/objects/{oid}")
@locked
def patch_obj(tid: str, oid: str, p: ObjPatch):
    for ob in get(tid)["objects"]:
        if ob["id"] == oid:
            for f in ("x", "y", "w", "h"):
                if getattr(p, f) is not None: ob[f] = float(getattr(p, f))
    save(tid); return {"ok": True}

@router.delete("/tables/{tid}/objects/{oid}")
@locked
def del_obj(tid: str, oid: str):
    d = get(tid); d["objects"] = [o for o in d["objects"] if o["id"] != oid]; save(tid); return {"ok": True}
