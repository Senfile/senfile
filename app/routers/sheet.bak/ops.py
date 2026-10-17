from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
import ast
from .core import *
from .schemas import *
router = APIRouter()

@router.get("/ops")
def ops():
    return [{"id": k, "kind": kind, "cat": v[0], "label": v[1]} for kind, reg in REG for k, v in reg.items()]

@router.post("/tables/{tid}/ops")
def run(tid: str, r: OpReq):
    d = get(tid); df = d["df"]; n = nrows(d)
    if r.sel.c0 is not None:
        cols = list(df.columns[r.sel.c0:(r.sel.c1 if r.sel.c1 is not None else r.sel.c0) + 1])
        if not cols: return {"table": view(tid), "result": None}
    else: cols = [c for c in r.sel.cols if c in df.columns] or list(df.columns)
    r0 = r.sel.r0 or 0; r1 = n - 1 if r.sel.r1 is None else min(r.sel.r1, n - 1)
    o = p2o(d, np.arange(r0, r1 + 1)); idx = pd.Index(o[o < len(df)]); fx = dict(d["formulas"])
    drop = lambda: [fx.pop(f"{c}|{i}", None) for c in cols for i in idx]
    try:
        if r.op in ANALYSIS: return {"table": view(tid), "result": pack(ANALYSIS[r.op][2](df.loc[idx, cols], r.arg))}
        work = df.copy()
        if r.op in TRANSFORM:
            fn = TRANSFORM[r.op][2]
            for c in cols:
                res = fn(df[c], r.arg)
                if r.inplace:
                    col = df[c].astype(object).copy(); col.loc[idx] = res.loc[idx].astype(object); work[c] = col.infer_objects()
                else: work[f"{c}_{r.op}"] = res
            if r.inplace: drop()
        elif r.op in TABLE:
            work = TABLE[r.op][2](df, cols, idx, r.arg)
            if r.op == "fill_down" and len(idx):
                for c in cols:
                    src = fx.get(f"{c}|{idx[0]}"); [fx.pop(f"{c}|{i}", None) for i in idx[1:]]
                    if src: [fx.__setitem__(f"{c}|{i}", shift(src, int(i - idx[0]))) for i in idx[1:]]
            elif r.op == "clear_cells": drop()
            elif r.op in ("insert_row_above", "insert_row_below"):
                k = max(len(idx), 1); q = min((idx[0] if r.op.endswith("above") else idx[-1] + 1) if len(idx) else len(df), len(df))
                fx = remap_fx(fx, lambda x: x + k if x >= q else x)
            elif r.op == "delete_rows":
                gone = np.array(sorted(idx), dtype=int); fx = remap_fx(fx, lambda x: None if x in set(gone.tolist()) else x - int((gone < x).sum()))
            elif r.op not in KEEP: fx = {}
        else: raise HTTPException(404, "Opération inconnue")
    except HTTPException: raise
    except Exception as e: raise HTTPException(400, f"{type(e).__name__}: {e}")
    st = None
    if r.op in TABLE and d["styles"]["cells"]:
        gs = set(int(x) for x in idx)
        if r.op in ("insert_row_above", "insert_row_below"): rm = lambda x: x + k if x >= q else x
        elif r.op == "delete_rows": gone = np.array(sorted(gs)); rm = lambda x: None if x in gs else x - int((gone < x).sum())
        elif work.index.is_unique and work.index.isin(df.index).all(): rm = {int(o): n for n, o in enumerate(work.index)}.get
        else: rm = lambda x: None
        st = remap_styles(d["styles"], rm)
    return {"table": commit(tid, work, fx, st), "result": None}

@router.post("/tables/{tid}/lookup")
def lookup(tid: str, k: Lookup):
    L = get(tid)["df"].copy(); o = get(k.other_id)["df"]
    try:
        nk = lambda s: s.astype("string").str.strip().str.lower()
        R = o[k.bring].copy(); R.columns = [c + "_2" if c in L.columns else c for c in k.bring]
        R["__k"] = nk(o[k.other_key]); R = R.drop_duplicates("__k"); L["__k"] = nk(L[k.key])
        out = L.merge(R, on="__k", how="left").drop(columns="__k")
    except Exception as e: raise HTTPException(400, f"{type(e).__name__}: {e}")
    return commit(tid, out)

@router.get("/formulas")
def formulas(): return [{"name": s.split("(")[0], "sig": s, "desc": d} for s, d in FDOC]

@router.post("/tables/{tid}/calc")
def calc(tid: str, k: Calc):
    d = get(tid); df = d["df"].copy(); env = {}
    def bind(c):
        n = f"c{len(env)}x"; s = df[c]; v = N(s); env[n] = v if v.notna().sum() >= s.notna().sum() * .5 else s; return n
    try:
        e = re.sub(r"\[([^\]]+)\]", lambda m: bind(m.group(1)), k.expr)
        for c in sorted(df.columns, key=len, reverse=True):
            if re.fullmatch(r"\w+", c): e = re.sub(rf"(?<![\w\"]){re.escape(c)}(?![\w\"(])", lambda m, c=c: bind(c), e)
        tree = ast.parse(e.strip().replace("^", "**"), mode="eval")
        ok = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Compare, ast.BoolOp, ast.Load, ast.operator, ast.unaryop, ast.cmpop, ast.boolop)
        if not all(isinstance(n, ok) for n in ast.walk(tree)) or any(isinstance(n, ast.Name) and n.id not in env for n in ast.walk(tree)): raise ValueError("Expression non autorisée : utilisez les noms de colonnes, + - * / ** % et des nombres")
        df[k.name.strip() or "Calcul"] = eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}}, env)
    except HTTPException: raise
    except Exception as x: raise HTTPException(400, f"{type(x).__name__}: {x}")
    return commit(tid, df)
