from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from .core import *
from .schemas import *
router = APIRouter()

@router.patch("/tables/{tid}/cell")
def cell(tid: str, c: Cell):
    d = get(tid); row = int(p2o(d, [c.row])[0]); df = grow(d["df"], row + 1, c.col + 1); name = df.columns[c.col]
    fx = dict(d["formulas"]); key = f"{name}|{row}"; v = c.value.strip()
    if v.startswith("="): fx[key] = v; val = np.nan
    else: fx.pop(key, None); val = parse(c.value)
    col = df[name].astype(object); col.iloc[row] = val; df[name] = col.infer_objects()
    return commit(tid, df, fx)

@router.post("/tables/{tid}/paste")
def paste(tid: str, p: Paste):
    d = get(tid); w = max((len(r) for r in p.data), default=0); n = len(p.data)
    mapped = p2o(d, np.arange(p.row, p.row + n)); df = grow(d["df"], int(mapped.max()) + 1 if n else 0, p.col + w); fx = dict(d["formulas"])
    for j in range(w):
        name = df.columns[p.col + j]; col = df[name].astype(object); vals = []
        for k, rw in enumerate(p.data):
            v = rw[j].strip() if j < len(rw) else ""; key = f"{name}|{int(mapped[k])}"
            if v.startswith("="): fx[key] = v; vals.append(np.nan)
            else: fx.pop(key, None); vals.append(parse(v) if j < len(rw) else np.nan)
        col.iloc[mapped] = vals; df[name] = col.infer_objects()
    return commit(tid, df, fx)

@router.get("/tables/{tid}/search")
def search(tid: str, q: str):
    m = vdf(get(tid)).astype("string").apply(lambda s: s.str.contains(q, case=False, regex=False, na=False))
    return np.argwhere(m.values)[:5000].tolist()

@router.post("/tables/{tid}/quick")
def quick(tid: str, k: Quick):
    sub = vdf(get(tid)).iloc[k.r0:k.r1 + 1, k.c0:k.c1 + 1].apply(N)
    v = sub.values.ravel().astype(float); v = v[~np.isnan(v)]
    return {"n": int(v.size), "sum": float(v.sum()) if v.size else None, "mean": float(v.mean()) if v.size else None,
            "min": float(v.min()) if v.size else None, "max": float(v.max()) if v.size else None}
