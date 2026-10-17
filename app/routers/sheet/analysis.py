from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
import ast
from .core import *
from .schemas import *
router = APIRouter()

@router.post("/tables/{tid}/pivot")
def pivot(tid: str, p: Pivot):
    w = vdf(get(tid)).copy()
    try:
        if p.agg == "count" or not p.value: w["Nombre"] = 1; val, agg = "Nombre", "sum"
        else: w[p.value] = N(w[p.value]); val, agg = p.value, p.agg
        pt = pd.pivot_table(w, index=p.rows, columns=p.cols or None, values=val, aggfunc=agg, margins=True, margins_name="Total").reset_index()
        pt.columns = [str(c) for c in pt.columns]
    except Exception as e: raise HTTPException(400, f"{type(e).__name__}: {e}")
    return put(pt, f"Croisé {p.rows}") if p.save else pack(pt)

@router.post("/tables/{tid}/summary")
def summary(tid: str, k: Summary):
    df = vdf(get(tid)); out = {}
    for c, g in k.aggs.items():
        if c not in df.columns: continue
        v = df[c].notna().sum() if g == "count" else STATS[g][1](N(df[c])) if g in STATS else None
        out[c] = None if v is None or v != v else float(v)
    return out

LAB = {"sum": "Somme", "mean": "Moyenne", "count": "Nombre", "min": "Minimum", "max": "Maximum", "median": "Médiane"}
def compute(w, df):
    t = w.get("title")
    try:
        if w["kind"] == "kpi":
            g = w["agg"] if w["agg"] in LAB else "sum"
            v = float(len(df)) if not w["col"] or g == "count" else float(getattr(N(df[w["col"]]), g)())
            return {"type": "kpi", "title": t or (f"{LAB[g]} de {w['col']}" if w["col"] else "Nombre de lignes"), "value": None if v != v else v, "cfg": w}
        by, col, g = w["by"], w["col"], w["agg"] if w["agg"] in LAB else "sum"
        if g == "count" or not col: s = df.groupby(by).size()
        else: x = df[[by, col]].copy(); x[col] = N(x[col]); s = x.groupby(by)[col].agg(g)
        s = (s.sort_index() if w["chart"] == "line" else s.sort_values(ascending=False)).head(20)
        return {"type": "chart", "chart": w["chart"], "title": t or f"{LAB[g]} de {col or 'lignes'} par {by}", "labels": [str(i) for i in s.index], "series": [{"name": col or "Nombre", "values": [0 if v != v else float(v) for v in s.values]}], "cfg": w}
    except Exception as e: return {"type": "error", "title": f"{t or w.get('by')} : {e}", "cfg": w}

@router.get("/tables/{tid}/dashboard")
def dashboard(tid: str):
    d = get(tid); df = vdf(d); head = df.head(5000)
    numc = [c for c in df.columns if N(head[c]).notna().sum() > .8 * max(head[c].notna().sum(), 1) and head[c].notna().any()]
    catc = [c for c in df.columns if c not in numc and 2 <= df[c].nunique() <= 30]
    auto = [{"kind": "kpi", "col": "", "agg": "count"}] + [{"kind": "kpi", "col": c, "agg": g} for c in numc[:3] for g in ("sum", "mean")]
    if numc: auto += [{"kind": "chart", "by": c, "col": numc[0], "agg": "sum", "chart": ch} for c, ch in zip(catc[:2], ("bar", "pie"))]
    return {"auto": [compute({"title": "", "by": "", "chart": "bar", **w}, df) for w in auto], "custom": [compute(w, df) for w in d["widgets"]]}

@router.post("/tables/{tid}/widgets")
@locked
def add_widget(tid: str, w: Widget):
    d = get(tid); d["widgets"].append({"kind": w.kind, "col": w.col, "by": w.by, "agg": w.agg, "chart": w.chart, "title": w.title}); save(tid); return {"ok": True}

@router.delete("/tables/{tid}/widgets/{i}")
@locked
def del_widget(tid: str, i: int):
    d = get(tid)
    if 0 <= i < len(d["widgets"]): d["widgets"].pop(i); save(tid)
    return {"ok": True}
