from fastapi import APIRouter, HTTPException
from .core import *
from .schemas import *
router = APIRouter()

@router.post("/tables/{tid}/style")
@locked
def style(tid: str, k: StyleReq):
    d = get(tid); df = d["df"]; n = nrows(d); cols = list(df.columns[k.c0:k.c1 + 1])
    st = {"cells": dict(d["styles"]["cells"]), "cols": dict(d["styles"]["cols"]), "merges": list(d["styles"].get("merges", []))}
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

@router.post("/tables/{tid}/merge")
@locked
def merge(tid: str, k: MergeReq):
    d = get(tid); df = d["df"]; n = nrows(d); cols = list(df.columns[k.c0:k.c1 + 1])
    o = p2o(d, np.arange(max(k.r0, 0), min(k.r1, n - 1) + 1)); o = o[o < len(df)]
    if not cols or not len(o): return view(tid)
    c0 = df.columns.get_loc(cols[0]); c1 = c0 + len(cols) - 1; r0, r1 = int(o.min()), int(o.max())
    def hit(m):
        a = df.columns.get_loc(m["c"]); return a <= c1 and a + m["cs"] - 1 >= c0 and m["r"] <= r1 and m["r"] + m["rs"] - 1 >= r0
    ms = [m for m in d["styles"].get("merges", []) if m["c"] in df.columns and not hit(m)]; work = df
    if not k.unmerge:
        if len(o) * len(cols) < 2: raise HTTPException(400, "Sélectionnez au moins deux cellules")
        if not np.array_equal(o, np.arange(o[0], o[0] + len(o))): raise HTTPException(400, "Lignes non contiguës : retirez d'abord les filtres")
        ms.append({"c": cols[0], "cs": len(cols), "r": r0, "rs": len(o)}); work = df.copy()
        for j, c in enumerate(cols):
            x = work[c].astype(object)
            for i in o:
                if not (j == 0 and i == o[0]): x.iloc[int(i)] = np.nan
            work[c] = x.infer_objects()
    st = {"cells": dict(d["styles"]["cells"]), "cols": dict(d["styles"]["cols"]), "merges": ms}
    return commit(tid, work, None, st)

@router.post("/tables/{tid}/borders")
@locked
def borders(tid: str, k: BorderReq):
    d = get(tid); df = d["df"]; n = nrows(d); cols = list(df.columns[k.c0:k.c1 + 1])
    o = p2o(d, np.arange(max(k.r0, 0), min(k.r1, n - 1) + 1)); o = o[o < len(df)]
    if not cols or not len(o): return view(tid)
    if len(o) * len(cols) > 60000: raise HTTPException(400, "Sélection trop grande pour les bordures (60 000 cellules maximum)")
    st = {"cells": dict(d["styles"]["cells"]), "cols": dict(d["styles"]["cols"]), "merges": list(d["styles"].get("merges", []))}
    TH, TK, p = "thin", "thick", k.preset; add_only = p in ("top", "bottom", "left", "right")
    for j, c in enumerate(cols):
        for i, r in enumerate(o):
            fr, lr, fc, lc = i == 0, i == len(o) - 1, j == 0, j == len(cols) - 1; e = {}
            if p == "all": e = {"bt": TH, "br": TH, "bb": TH, "bl": TH}
            elif p in ("outline", "outline_thick"): w = TH if p == "outline" else TK; e = {"bt": w if fr else None, "bb": w if lr else None, "bl": w if fc else None, "br": w if lc else None}
            elif p == "tight": e = {"bt": TK if fr else TH, "bb": TK if lr else TH, "bl": TK if fc else TH, "br": TK if lc else TH}
            elif p == "header": e = {"bt": TH, "bb": TK if fr else TH, "bl": TH, "br": TH}
            elif p == "horizontal": e = {"bt": TH, "bb": TH}
            elif p == "top": e = {"bt": TH if fr else None}
            elif p == "bottom": e = {"bb": TH if lr else None}
            elif p == "left": e = {"bl": TH if fc else None}
            elif p == "right": e = {"br": TH if lc else None}
            key = f"{c}|{int(r)}"; cell = dict(st["cells"].get(key, {}))
            if not add_only:
                for x in ("bt", "br", "bb", "bl"): cell.pop(x, None)
            cell.update({a: b for a, b in e.items() if b})
            if cell: st["cells"][key] = cell
            else: st["cells"].pop(key, None)
    return commit(tid, d["df"], None, st)
