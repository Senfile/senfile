from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from .core import *
from .schemas import *
router = APIRouter()

@router.post("/tables/{tid}/filter")
@locked
def filt(tid: str, k: Filt):
    d = get(tid)
    if k.clear: d["filters"].pop(k.col, None)
    else: d["filters"][k.col] = {"op": k.op, "arg": k.arg, "values": k.values}
    apply_filters(d); save(tid); return view(tid)

@router.post("/tables/{tid}/filters/clear")
@locked
def filters_clear(tid: str):
    d = get(tid); d["filters"] = {}; apply_filters(d); save(tid); return view(tid)

@router.get("/tables/{tid}/distinct")
def distinct(tid: str, col: str):
    vc = sv(get(tid)["df"][col]).fillna("").value_counts().head(300)
    return [{"v": k, "n": int(n)} for k, n in sorted(vc.items(), key=lambda kv: kv[0].lower())]
