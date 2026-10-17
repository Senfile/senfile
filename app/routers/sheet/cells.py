from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from .core import *
from .schemas import *
router = APIRouter()

@router.patch("/tables/{tid}/cell")
@router.post("/tables/{tid}/cell")
@locked
def cell(tid: str, c: Cell):
    d = get(tid); row = int(p2o(d, [c.row])[0]); df = grow(d["df"], row + 1, c.col + 1); name = df.columns[c.col]
    fx = dict(d["formulas"]); key = f"{name}|{row}"; v = c.value.strip()
    if v.startswith("="): fx[key] = v; val = np.nan
    else: fx.pop(key, None); val = parse(c.value)
    col = df[name].astype(object); col.iloc[row] = val; df[name] = col.infer_objects()
    return commit(tid, df, fx)

@router.post("/tables/{tid}/paste")
@locked
def paste(tid: str, p: Paste):
    d = get(tid); w = max((len(r) for r in p.data), default=0); n = len(p.data); promoted = False; head = []
    if p.row == 0 and p.col == 0 and n >= 2 and not d["formulas"] and d["df"].isna().all().all() and looks_like_header(p.data):
        head = [h.strip() for h in p.data[0]]; p = Paste(row=0, col=0, data=p.data[1:]); n = len(p.data); promoted = True
    mapped = p2o(d, np.arange(p.row, p.row + n)); df = grow(d["df"], int(mapped.max()) + 1 if n else 0, p.col + w); fx = dict(d["formulas"])
    if promoted: df.columns = uniq([head[i] if i < len(head) and head[i] else c for i, c in enumerate(df.columns)])
    for j in range(w):
        name = df.columns[p.col + j]; col = df[name].astype(object); vals = []
        for k, rw in enumerate(p.data):
            v = rw[j].strip() if j < len(rw) else ""; key = f"{name}|{int(mapped[k])}"
            if v.startswith("="): fx[key] = v; vals.append(np.nan)
            else: fx.pop(key, None); vals.append(parse(v) if j < len(rw) else np.nan)
        col.iloc[mapped] = vals; df[name] = col.infer_objects()
    m = commit(tid, df, fx); m["promoted"] = promoted
    return m

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

@router.post("/tables/{tid}/eval")
def evalf(tid: str, k: EvalReq):
    return {"value": evaluate(k.formula, get(tid)["df"])}

@router.get("/tables/{tid}/edge")
def edge(tid: str, r: int, c: int, dir: str):
    df = vdf(get(tid)); n, m = df.shape
    if n == 0 or m == 0: return {"r": r, "c": c}
    filled = lambda s: (s.notna() & (s.astype("string").fillna("").str.strip() != "")).values
    if dir in ("up", "down"):
        if c >= m: return {"r": r, "c": c}
        mask, pos, lim, step = filled(df.iloc[:, c]), r, n, (1 if dir == "down" else -1)
    else:
        if r >= n: return {"r": r, "c": c}
        mask, pos, lim, step = filled(df.iloc[r, :]), c, m, (1 if dir == "right" else -1)
    nxt = pos + step
    if 0 <= nxt < lim and 0 <= pos < lim and mask[pos] and mask[nxt]:
        while 0 <= pos + step < lim and mask[pos + step]: pos += step
    else:
        pos = nxt
        while 0 <= pos < lim and not mask[pos]: pos += step
        pos = min(max(pos, 0), lim - 1)
    return {"r": pos, "c": c} if dir in ("up", "down") else {"r": r, "c": pos}
