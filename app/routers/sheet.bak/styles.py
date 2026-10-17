from fastapi import APIRouter, HTTPException
from .core import *
from .schemas import *
router = APIRouter()

@router.post("/tables/{tid}/style")
def style(tid: str, k: StyleReq):
    d = get(tid); df = d["df"]; n = nrows(d); cols = list(df.columns[k.c0:k.c1 + 1])
    st = {"cells": dict(d["styles"]["cells"]), "cols": dict(d["styles"]["cols"])}
    if not cols or n == 0: return view(tid)
    def upd(old):
        if k.clear: return {}
        new = {**old, **{a: b for a, b in k.patch.items() if b is not None}}
        for a, b in k.patch.items():
            if b is None: new.pop(a, None)
        return new
    if k.r0 <= 0 and k.r1 >= n - 1:
        for c in cols:
            v = upd(st["cols"].get(c, {})); st["cols"][c] = v
            if not v: st["cols"].pop(c)
        for key in [x for x in st["cells"] if x.rsplit("|", 1)[0] in cols]:
            cell = {a: b for a, b in st["cells"][key].items() if not k.clear and a not in k.patch}
            if cell: st["cells"][key] = cell
            else: st["cells"].pop(key)
    else:
        o = p2o(d, np.arange(max(k.r0, 0), min(k.r1, n - 1) + 1)); o = o[o < len(df)]
        if len(o) * len(cols) > 20000: raise HTTPException(400, "Sélection trop grande : sélectionnez des colonnes entières")
        for c in cols:
            for r in o:
                key = f"{c}|{int(r)}"; v = upd(st["cells"].get(key, {}))
                if v: st["cells"][key] = v
                else: st["cells"].pop(key, None)
    return commit(tid, d["df"], None, st)
