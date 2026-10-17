from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from .core import *
from .schemas import *
router = APIRouter()

@router.get("/tables")
def tables():
    ids = sorted(T, key=lambda t: (DATA / f"{t}.pkl").stat().st_mtime, reverse=True)
    return [view(i) for i in ids]

@router.post("/tables/new")
def new(r: NewReq):
    return put(pd.DataFrame(np.nan, index=range(r.rows), columns=[colname(i) for i in range(r.cols)]), "Nouveau tableau")

@router.post("/tables/upload")
async def upload(file: UploadFile = File(...)):
    b, n = await file.read(), (file.filename or "").lower()
    try:
        if n.endswith((".xlsx", ".xlsm", ".xls")): df = pd.read_excel(io.BytesIO(b))
        elif n.endswith(".json"): df = pd.read_json(io.BytesIO(b))
        elif n.endswith(".parquet"): df = pd.read_parquet(io.BytesIO(b))
        else: df = pd.read_csv(io.BytesIO(b), sep=None, engine="python")
    except Exception as e: raise HTTPException(400, f"Import impossible : {e}")
    return put(df, file.filename)

@router.post("/import/sql")
def import_sql(r: SqlReq):
    try: return put(pd.read_sql(r.query, create_engine(r.url)), "Import SQL")
    except Exception as e: raise HTTPException(400, str(e))

@router.delete("/tables/{tid}")
def delete(tid: str):
    get(tid); T.pop(tid); (DATA / f"{tid}.pkl").unlink(missing_ok=True); return {"ok": True}

@router.get("/tables/{tid}/rows")
def rows(tid: str, off: int = 0, lim: int = 200, idx: int = 0):
    d = get(tid); a, b = off, off + min(lim, 200000)
    pos = d["view"][a:b] if d["view"] is not None else np.arange(a, min(b, len(d["df"])))
    out = clean(d["df"].iloc[pos])
    if not idx: return out
    pm = {int(p): k for k, p in enumerate(pos)}; cols = list(d["df"].columns); fm = {}
    for key, src in d["formulas"].items():
        cn, rw = key.rsplit("|", 1)
        if int(rw) in pm and cn in cols: fm[f"{a + pm[int(rw)]}:{cols.index(cn)}"] = src
    sm = {}
    for key, v in d["styles"]["cells"].items():
        cn, rw = key.rsplit("|", 1)
        if int(rw) in pm and cn in cols: sm[f"{a + pm[int(rw)]}:{cols.index(cn)}"] = v
    cs = {str(cols.index(cn)): v for cn, v in d["styles"]["cols"].items() if cn in cols}
    return {"rows": out, "idx": [int(p) for p in pos], "f": fm, "s": sm, "cs": cs}

@router.get("/tables/{tid}/export")
def export(tid: str, fmt: str = "csv"):
    df = vdf(get(tid)); buf = io.BytesIO()
    if fmt == "xlsx": df.to_excel(buf, index=False); mt = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else: buf.write(df.to_csv(index=False).encode()); mt = "text/csv"
    buf.seek(0)
    return StreamingResponse(buf, media_type=mt, headers={"Content-Disposition": f'attachment; filename="sheetly.{fmt}"'})

@router.post("/tables/{tid}/undo")
def undo(tid: str):
    d = get(tid)
    if d["hist"]: d["df"], d["formulas"], d["styles"] = d["hist"].pop(); apply_filters(d); save(tid)
    return view(tid)
