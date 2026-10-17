from fastapi import HTTPException
import io, uuid
import numpy as np, pandas as pd
from sqlalchemy import create_engine

T: dict = {}  # id -> {df, name, hist}

N = lambda s: pd.to_numeric(s, errors="coerce")
D = lambda s: pd.to_datetime(s, errors="coerce")
S = lambda s: s.astype("string")
def f(a, d=0.0):
    try: return float(a)
    except Exception: return d
def add(reg, cat, items, prefix=""):
    for k, (label, fn) in items.items(): reg[prefix + k] = (cat, label, fn)

# ---------- Transformations colonne (s, arg) -> Series ----------
TRANSFORM = {}
add(TRANSFORM, "Texte", {
 "upper": ("MAJUSCULES", lambda s,a: S(s).str.upper()),
 "lower": ("minuscules", lambda s,a: S(s).str.lower()),
 "title": ("Chaque Mot En Capitale", lambda s,a: S(s).str.title()),
 "capitalize": ("Première lettre en capitale", lambda s,a: S(s).str.capitalize()),
 "strip": ("Supprimer espaces autour", lambda s,a: S(s).str.strip()),
 "no_space": ("Supprimer tous les espaces", lambda s,a: S(s).str.replace(" ", "", regex=False)),
 "no_digit": ("Supprimer les chiffres", lambda s,a: S(s).str.replace(r"\d", "", regex=True)),
 "no_punct": ("Supprimer la ponctuation", lambda s,a: S(s).str.replace(r"[^\w\s]", "", regex=True)),
 "digits_only": ("Garder les chiffres", lambda s,a: S(s).str.replace(r"\D", "", regex=True)),
 "length": ("Longueur", lambda s,a: S(s).str.len()),
 "word_count": ("Nombre de mots", lambda s,a: S(s).str.split().str.len()),
 "reverse": ("Inverser", lambda s,a: S(s).str[::-1]),
 "first_word": ("Premier mot", lambda s,a: S(s).str.split().str[0]),
 "last_word": ("Dernier mot", lambda s,a: S(s).str.split().str[-1]),
 "left": ("Gauche (arg = n)", lambda s,a: S(s).str[:int(f(a,1))]),
 "right": ("Droite (arg = n)", lambda s,a: S(s).str[-int(f(a,1)):]),
 "replace": ("Remplacer (arg = ancien=>nouveau)", lambda s,a: S(s).str.replace(a.split("=>")[0], a.split("=>")[1] if "=>" in a else "", regex=False)),
 "prefix": ("Ajouter préfixe", lambda s,a: a + S(s)),
 "suffix": ("Ajouter suffixe", lambda s,a: S(s) + a),
 "contains": ("Contient (arg)", lambda s,a: S(s).str.contains(a, regex=False)),
 "startswith": ("Commence par (arg)", lambda s,a: S(s).str.startswith(a)),
 "endswith": ("Finit par (arg)", lambda s,a: S(s).str.endswith(a)),
 "email": ("Extraire l'email", lambda s,a: S(s).str.extract(r"([\w.+-]+@[\w-]+\.[\w.]+)")[0]),
 "slug": ("Slug URL", lambda s,a: S(s).str.lower().str.replace(r"[^a-z0-9]+", "-", regex=True).str.strip("-")),
 "pad": ("Compléter de zéros (arg = n)", lambda s,a: S(s).str.zfill(int(f(a,5)))),
 "to_number": ("Convertir en nombre", lambda s,a: N(s)),
 "to_text": ("Convertir en texte", lambda s,a: S(s)),
})
add(TRANSFORM, "Nombres", {
 "round": ("Arrondir (arg = décimales)", lambda s,a: N(s).round(int(f(a,0)))),
 "abs": ("Valeur absolue", lambda s,a: N(s).abs()),
 "sqrt": ("Racine carrée", lambda s,a: np.sqrt(N(s))),
 "square": ("Carré", lambda s,a: N(s)**2),
 "cube": ("Cube", lambda s,a: N(s)**3),
 "log": ("Logarithme népérien", lambda s,a: np.log(N(s))),
 "log10": ("Logarithme base 10", lambda s,a: np.log10(N(s))),
 "exp": ("Exponentielle", lambda s,a: np.exp(N(s))),
 "ceil": ("Arrondi supérieur", lambda s,a: np.ceil(N(s))),
 "floor": ("Arrondi inférieur", lambda s,a: np.floor(N(s))),
 "sign": ("Signe", lambda s,a: np.sign(N(s))),
 "neg": ("Opposé", lambda s,a: -N(s)),
 "inverse": ("Inverse (1/x)", lambda s,a: 1 / N(s)),
 "add": ("Ajouter (arg)", lambda s,a: N(s) + f(a)),
 "sub": ("Soustraire (arg)", lambda s,a: N(s) - f(a)),
 "mul": ("Multiplier (arg)", lambda s,a: N(s) * f(a,1)),
 "div": ("Diviser (arg)", lambda s,a: N(s) / f(a,1)),
 "pow": ("Puissance (arg)", lambda s,a: N(s) ** f(a,1)),
 "mod": ("Modulo (arg)", lambda s,a: N(s) % f(a,1)),
 "cumsum": ("Somme cumulée", lambda s,a: N(s).cumsum()),
 "cumprod": ("Produit cumulé", lambda s,a: N(s).cumprod()),
 "cummax": ("Maximum cumulé", lambda s,a: N(s).cummax()),
 "cummin": ("Minimum cumulé", lambda s,a: N(s).cummin()),
 "diff": ("Différence avec la ligne précédente", lambda s,a: N(s).diff()),
 "pct_change": ("Variation en %", lambda s,a: N(s).pct_change() * 100),
 "rank": ("Rang", lambda s,a: N(s).rank()),
 "zscore": ("Score Z", lambda s,a: (N(s) - N(s).mean()) / N(s).std()),
 "minmax": ("Normaliser 0-1", lambda s,a: (N(s) - N(s).min()) / (N(s).max() - N(s).min())),
 "pct_total": ("Part du total en %", lambda s,a: N(s) / N(s).sum() * 100),
 "clip": ("Borner (arg = min,max)", lambda s,a: N(s).clip(*[float(x) for x in a.split(",")])),
 "roll_mean": ("Moyenne mobile (arg = fenêtre)", lambda s,a: N(s).rolling(int(f(a,3)), min_periods=1).mean()),
 "roll_sum": ("Somme mobile", lambda s,a: N(s).rolling(int(f(a,3)), min_periods=1).sum()),
 "roll_max": ("Maximum mobile", lambda s,a: N(s).rolling(int(f(a,3)), min_periods=1).max()),
 "roll_min": ("Minimum mobile", lambda s,a: N(s).rolling(int(f(a,3)), min_periods=1).min()),
 "ewm": ("Moyenne exponentielle", lambda s,a: N(s).ewm(span=f(a,3)).mean()),
 "shift": ("Décaler (arg = n lignes)", lambda s,a: N(s).shift(int(f(a,1)))),
 "outlier": ("Marquer valeurs aberrantes", lambda s,a: (lambda n: (n < n.quantile(.25) - 1.5*(n.quantile(.75)-n.quantile(.25))) | (n > n.quantile(.75) + 1.5*(n.quantile(.75)-n.quantile(.25))))(N(s))),
 "bin": ("Classes (arg = nb)", lambda s,a: pd.cut(N(s), int(f(a,5))).astype("string")),
})
add(TRANSFORM, "Dates", {
 "to_date": ("Normaliser en date", lambda s,a: D(s).dt.strftime("%Y-%m-%d")),
 "year": ("Année", lambda s,a: D(s).dt.year),
 "month": ("Mois", lambda s,a: D(s).dt.month),
 "day": ("Jour", lambda s,a: D(s).dt.day),
 "weekday": ("Jour de semaine (0=lundi)", lambda s,a: D(s).dt.dayofweek),
 "quarter": ("Trimestre", lambda s,a: D(s).dt.quarter),
 "week": ("Semaine ISO", lambda s,a: D(s).dt.isocalendar().week.astype("Int64")),
 "dayofyear": ("Jour de l'année", lambda s,a: D(s).dt.dayofyear),
 "month_name": ("Nom du mois", lambda s,a: D(s).dt.month_name()),
 "day_name": ("Nom du jour", lambda s,a: D(s).dt.day_name()),
 "hour": ("Heure", lambda s,a: D(s).dt.hour),
 "days_ago": ("Jours écoulés", lambda s,a: (pd.Timestamp.now() - D(s)).dt.days),
 "is_weekend": ("Est un week-end", lambda s,a: D(s).dt.dayofweek >= 5),
})
add(TRANSFORM, "Nettoyage", {
 "fill_zero": ("Remplir vides par 0", lambda s,a: s.fillna(0)),
 "fill_mean": ("Remplir vides par la moyenne", lambda s,a: N(s).fillna(N(s).mean())),
 "fill_median": ("Remplir vides par la médiane", lambda s,a: N(s).fillna(N(s).median())),
 "fill_mode": ("Remplir vides par le mode", lambda s,a: s.fillna(s.mode().iloc[0]) if s.notna().any() else s),
 "ffill": ("Propager vers le bas", lambda s,a: s.ffill()),
 "bfill": ("Propager vers le haut", lambda s,a: s.bfill()),
 "fill_value": ("Remplir vides par (arg)", lambda s,a: s.fillna(a)),
 "blank_to_null": ("Textes vides → vide", lambda s,a: s.replace(r"^\s*$", np.nan, regex=True)),
 "is_null": ("Est vide", lambda s,a: s.isna()),
 "not_null": ("N'est pas vide", lambda s,a: s.notna()),
 "is_dup": ("Est un doublon", lambda s,a: s.duplicated()),
})

# ---------- Opérations sur le tableau (df, cols, idx, arg) -> df ----------
def grp(fn):
    return lambda df,c,i,a: df.groupby(c[0], as_index=False)[c[1:]].agg(fn) if len(c) > 1 else df.groupby(c[0], as_index=False).size()
TABLE = {}
add(TABLE, "Tableau", {
 "sort_asc": ("Trier A→Z", lambda df,c,i,a: df.sort_values(c, kind="stable")),
 "sort_desc": ("Trier Z→A", lambda df,c,i,a: df.sort_values(c, ascending=False, kind="stable")),
 "dedupe": ("Supprimer doublons", lambda df,c,i,a: df.drop_duplicates(subset=c)),
 "dropna": ("Supprimer lignes vides", lambda df,c,i,a: df.dropna(subset=c)),
 "drop_cols": ("Supprimer colonnes", lambda df,c,i,a: df.drop(columns=c)),
 "keep_cols": ("Garder seulement ces colonnes", lambda df,c,i,a: df[c]),
 "rename": ("Renommer la colonne (arg)", lambda df,c,i,a: df.rename(columns={c[0]: a})),
 "filter": ("Filtrer (arg = ex. age > 30)", lambda df,c,i,a: df.query(a)),
 "formula": ("Formule (arg = ex. total = prix * qte)", lambda df,c,i,a: df.eval(a)),
 "transpose": ("Transposer", lambda df,c,i,a: df.T.reset_index().rename(columns=str)),
 "shuffle": ("Mélanger", lambda df,c,i,a: df.sample(frac=1)),
 "sample": ("Échantillon (arg = n)", lambda df,c,i,a: df.sample(min(int(f(a,10)), len(df)))),
 "head": ("Garder n premières lignes", lambda df,c,i,a: df.head(int(f(a,10)))),
 "tail": ("Garder n dernières lignes", lambda df,c,i,a: df.tail(int(f(a,10)))),
 "split": ("Scinder colonne (arg = séparateur)", lambda df,c,i,a: pd.concat([df, S(df[c[0]]).str.split(a or ",", expand=True).add_prefix(c[0] + "_")], axis=1)),
 "merge_cols": ("Fusionner colonnes (arg = séparateur)", lambda df,c,i,a: df.assign(**{"+".join(c): df[c].astype("string").fillna("").apply(lambda r: a.join(r), axis=1)})),
 "add_col": ("Ajouter colonne (arg = nom)", lambda df,c,i,a: df.assign(**{a or "nouvelle": np.nan})),
 "add_row": ("Ajouter ligne", lambda df,c,i,a: pd.concat([df, pd.DataFrame([{}])], ignore_index=True)),
 "dup_col": ("Dupliquer colonnes", lambda df,c,i,a: df.assign(**{x + "_copie": df[x] for x in c})),
 "delete_rows": ("Supprimer lignes sélectionnées", lambda df,c,i,a: df.drop(index=i)),
 "group_sum": ("Grouper : somme (1re col = clé)", grp("sum")),
 "group_mean": ("Grouper : moyenne", grp("mean")),
 "group_count": ("Grouper : effectif", grp("count")),
 "group_max": ("Grouper : maximum", grp("max")),
 "group_min": ("Grouper : minimum", grp("min")),
 "group_median": ("Grouper : médiane", grp("median")),
})

# ---------- 30+ analyses (df sélection, arg) -> Series | DataFrame ----------
q = lambda n, p: n.quantile(p)
def _out(n):
    i = q(n,.75) - q(n,.25); return int(((n < q(n,.25) - 1.5*i) | (n > q(n,.75) + 1.5*i)).sum())
STATS = {
 "sum": ("Somme", lambda n: n.sum()), "mean": ("Moyenne", lambda n: n.mean()), "median": ("Médiane", lambda n: n.median()),
 "std": ("Écart-type", lambda n: n.std()), "var": ("Variance", lambda n: n.var()),
 "min": ("Minimum", lambda n: n.min()), "max": ("Maximum", lambda n: n.max()), "range": ("Étendue", lambda n: n.max() - n.min()),
 "count": ("Nombre de valeurs", lambda n: n.count()), "nulls": ("Valeurs vides", lambda n: n.isna().sum()),
 "q1": ("1er quartile", lambda n: q(n,.25)), "q3": ("3e quartile", lambda n: q(n,.75)), "iqr": ("Écart interquartile", lambda n: q(n,.75) - q(n,.25)),
 "p5": ("Percentile 5", lambda n: q(n,.05)), "p95": ("Percentile 95", lambda n: q(n,.95)),
 "skew": ("Asymétrie", lambda n: n.skew()), "kurt": ("Aplatissement", lambda n: n.kurt()), "sem": ("Erreur standard", lambda n: n.sem()),
 "cv": ("Coefficient de variation", lambda n: n.std() / n.mean()), "mad": ("Écart moyen absolu", lambda n: (n - n.mean()).abs().mean()),
 "gmean": ("Moyenne géométrique", lambda n: np.exp(np.log(n[n > 0]).mean())),
 "hmean": ("Moyenne harmonique", lambda n: n.count() / (1 / n[n != 0]).sum()),
 "sumsq": ("Somme des carrés", lambda n: (n**2).sum()), "first": ("Première valeur", lambda n: n.dropna().iloc[0]),
 "last": ("Dernière valeur", lambda n: n.dropna().iloc[-1]), "outliers": ("Nb valeurs aberrantes", _out),
 "zeros": ("Nb de zéros", lambda n: (n == 0).sum()), "pos": ("Nb de positifs", lambda n: (n > 0).sum()), "neg": ("Nb de négatifs", lambda n: (n < 0).sum()),
}
ANALYSIS = {}
for k, (lab, fn) in STATS.items():
    ANALYSIS["stat_" + k] = ("Analyse", lab, (lambda fn: lambda df,a: df.apply(lambda s: fn(N(s))))(fn))
add(ANALYSIS, "Analyse", {
 "nunique": ("Valeurs distinctes", lambda df,a: df.nunique()),
 "mode": ("Mode", lambda df,a: df.apply(lambda s: s.mode().iloc[0] if len(s.mode()) else None)),
 "corr": ("Corrélation (Pearson)", lambda df,a: df.apply(N).corr()),
 "spearman": ("Corrélation (Spearman)", lambda df,a: df.apply(N).corr(method="spearman")),
 "cov": ("Covariance", lambda df,a: df.apply(N).cov()),
 "describe": ("Résumé statistique complet", lambda df,a: df.describe(include="all").T),
 "value_counts": ("Fréquences (1re colonne)", lambda df,a: df.iloc[:, 0].value_counts().head(50).rename("effectif")),
 "top": ("Top n valeurs (arg = n)", lambda df,a: N(df.iloc[:, 0]).nlargest(int(f(a,5))).rename("valeur")),
 "bottom": ("Bottom n valeurs (arg = n)", lambda df,a: N(df.iloc[:, 0]).nsmallest(int(f(a,5))).rename("valeur")),
}, prefix="stat_")
REG = [("transform", TRANSFORM), ("table", TABLE), ("analysis", ANALYSIS)]

# ---------- Helpers ----------
import re
from pathlib import Path
DATA = Path(__file__).parent / "data"; DATA.mkdir(exist_ok=True)
NUMRE = re.compile(r"^-?\d+([.,]\d+)?$")

def colname(i):
    s, i = "", i + 1
    while i: i, r = divmod(i - 1, 26); s = chr(65 + r) + s
    return s
def _num(s):
    s = re.sub(r"[\s\u00a0\u202f']", "", s)
    if not re.fullmatch(r"[+-]?[\d.,]+", s): return None
    d, k = s.count("."), s.count(",")
    if d and k: dec = "." if s.rfind(".") > s.rfind(",") else ","
    elif d + k == 1: dec = "." if d else ","
    elif d + k == 0 or re.fullmatch(r"[+-]?\d{1,3}([.,]\d{3})+", s): dec = None
    else: return None
    if dec: ip, _, fp = s.rpartition(dec); t = re.sub(r"[.,]", "", ip) + "." + fp
    else: t = re.sub(r"[.,]", "", s)
    try: x = float(t)
    except ValueError: return None
    return x if dec else int(x)
def parse(v):
    v = str(v).strip()
    if v == "": return np.nan
    if len(v) > 1 and v[0] == "0" and v[1].isdigit(): return v
    s = re.sub(r"[€$£]", "", v).strip(); pct = s.endswith("%"); s = s.rstrip("%").strip(); neg = s.startswith("(") and s.endswith(")")
    x = _num(s[1:-1] if neg else s)
    if x is None: return v
    x = -x if neg else x
    return x / 100 if pct else x
def clean(x):
    x = x.replace([np.inf, -np.inf], np.nan)
    return x.astype(object).where(x.notna(), None).values.tolist()
import ast, operator as op, math, fnmatch, statistics, datetime
class NA(Exception): pass
B = lambda x: x.fillna(False).astype(bool)
def sv(s): return s.map(lambda v: None if v is None or v != v else (str(int(v)) if isinstance(v, float) and v.is_integer() else str(v))).astype("string")
def apply_filters(d):
    df = d["df"]; m = pd.Series(True, index=df.index)
    for col, sp in d["filters"].items():
        if col not in df.columns: continue
        s = df[col]; st = sv(s).fillna(""); o, a = sp.get("op", ""), sp.get("arg", "")
        if o == "contains": m &= B(st.str.contains(a, case=False, regex=False))
        elif o in ("eq", "ne"):
            e = B(st.str.strip().str.lower() == a.strip().lower())
            try: e = e | (N(s) == float(a.replace(",", ".")))
            except ValueError: pass
            m &= e if o == "eq" else ~e
        elif o == "gt": m &= N(s) > f(a)
        elif o == "lt": m &= N(s) < f(a)
        elif o == "empty": m &= B(st.str.strip() == "")
        elif o == "notempty": m &= ~B(st.str.strip() == "")
        if sp.get("values") is not None: m &= B(st.isin(sp["values"]))
    d["view"] = np.flatnonzero(m.values) if d["filters"] else None
def nrows(d): return len(d["view"]) if d["view"] is not None else len(d["df"])
def vdf(d): return d["df"] if d["view"] is None else d["df"].iloc[d["view"]]
def p2o(d, pos):
    pos = np.asarray(pos, dtype=int); v = d["view"]
    if v is None: return pos
    n = len(v); return np.where(pos < n, v[np.minimum(pos, n - 1)] if n else 0, len(d["df"]) + pos - n)

# ----- Formules -----
FN, REF = {}, {}
def colidx(s):
    n = 0
    for ch in s: n = n * 26 + ord(ch) - 64
    return n - 1
def val(x):
    if x is None or (isinstance(x, float) and x != x): return None
    return x.item() if hasattr(x, "item") else x
def flat(x): return [z for y in x for z in flat(y)] if isinstance(x, list) else [x]
def num(x):
    if isinstance(x, list): x = (flat(x) or [0])[0]
    if x is None or x == "": return 0
    if isinstance(x, (int, float)): return x
    try: return float(str(x).replace(",", "."))
    except ValueError: raise ValueError("#VALEUR!")
def nums(args):
    out = []
    for a in args: out += [y for y in flat(a) if isinstance(y, (int, float)) and not isinstance(y, bool)] if isinstance(a, list) else [num(a)]
    return out
def txt(x):
    if x is None: return ""
    return str(int(x)) if isinstance(x, float) and x.is_integer() else str(x)
def truthy(x): return x.upper() in ("TRUE", "VRAI") if isinstance(x, str) else bool(x)
def same(a, b):
    try: return float(a) == float(b)
    except (TypeError, ValueError): return txt(a).strip().lower() == txt(b).strip().lower()
def crit(c):
    if not isinstance(c, str): return lambda y: y == c
    m = re.match(r"^(>=|<=|<>|>|<|=)?(.*)$", c); o, v = m.group(1) or "=", m.group(2)
    try: x, isn = float(v.replace(",", ".")), True
    except ValueError: x, isn = v.lower(), False
    O = {"=": op.eq, "<>": op.ne, ">": op.gt, "<": op.lt, ">=": op.ge, "<=": op.le}[o]
    def t(y):
        if isn:
            try: return O(float(y), x)
            except (TypeError, ValueError): return o == "<>"
        k = fnmatch.fnmatch(txt(y).lower(), x); return k if o == "=" else (not k) if o == "<>" else False
    return t
def pairs(r, c, s=None):
    t = crit(c); rr = flat(r); ss = flat(s) if s is not None else rr
    return [y for x, y in zip(rr, ss) if t(x)]
def lookup(v, k, r):
    for x, y in zip(flat(k), flat(r)):
        if x not in (None, "") and same(x, v): return y
    raise NA
def vlookup(v, t, i, exact=True):
    for row in t:
        if row and same(row[0], v): return row[int(i) - 1]
    raise NA
def reg(names, fn):
    for n in names.split(): FN[n] = fn
def need(l):
    if not l: raise ZeroDivisionError
    return l
reg("SOMME SUM", lambda *a: sum(nums(a))); reg("MOYENNE AVERAGE", lambda *a: statistics.fmean(need(nums(a))))
reg("MIN", lambda *a: min(nums(a), default=0)); reg("MAX", lambda *a: max(nums(a), default=0))
reg("MEDIANE MEDIAN", lambda *a: statistics.median(need(nums(a)))); reg("ECARTYPE STDEV", lambda *a: statistics.stdev(nums(a)))
reg("NB COUNT", lambda *a: len(nums(a))); reg("NBVAL COUNTA", lambda *a: sum(x not in (None, "") for x in flat(list(a))))
reg("NB_VIDE COUNTBLANK", lambda *a: sum(x in (None, "") for x in flat(list(a))))
reg("ET AND", lambda *a: all(map(truthy, flat(list(a))))); reg("OU OR", lambda *a: any(map(truthy, flat(list(a))))); reg("NON NOT", lambda x: not truthy(x))
reg("SOMME_SI SUMIF", lambda r, c, s=None: sum(nums([pairs(r, c, s)]))); reg("NB_SI COUNTIF", lambda r, c: len(pairs(r, c)))
reg("MOYENNE_SI AVERAGEIF", lambda r, c, s=None: statistics.fmean(need(nums([pairs(r, c, s)]))))
reg("RECHERCHE LOOKUP RECHERCHEX XLOOKUP", lookup); reg("RECHERCHEV VLOOKUP", vlookup)
reg("CONCAT CONCATENER CONCATENATE", lambda *a: "".join(txt(x) for x in flat(list(a))))
reg("GAUCHE LEFT", lambda t, n=1: txt(t)[:int(n)]); reg("DROITE RIGHT", lambda t, n=1: txt(t)[-int(n):] if int(n) else "")
reg("MAJUSCULE UPPER", lambda t: txt(t).upper()); reg("MINUSCULE LOWER", lambda t: txt(t).lower())
reg("SUPPRESPACE TRIM", lambda t: " ".join(txt(t).split())); reg("NBCAR LEN", lambda t: len(txt(t)))
reg("SUBSTITUE SUBSTITUTE", lambda t, o, n: txt(t).replace(txt(o), txt(n)))
reg("ARRONDI ROUND", lambda x, n=0: round(num(x), int(n))); reg("ABS", lambda x: abs(num(x)))
reg("AUJOURDHUI TODAY", lambda: datetime.date.today().isoformat())
reg("ANNEE YEAR", lambda x: pd.to_datetime(x).year); reg("MOIS MONTH", lambda x: pd.to_datetime(x).month)
REF["CEL"] = lambda df, c, r: val(df.iat[r - 1, colidx(c)]) if 0 <= r - 1 < len(df) and colidx(c) < df.shape[1] else None
REF["RNG"] = lambda df, c1, r1, c2, r2: [[val(v) for v in row] for row in df.iloc[(r1 - 1 if r1 else 0):(r2 if r2 else len(df)), colidx(c1):colidx(c2) + 1].values.tolist()]
def _col(df, n):
    if n not in df.columns: raise ValueError("#NOM?")
    return [[val(v)] for v in df[n].tolist()]
REF["COL"] = _col
FDOC = [("SOMME(plage)", "Additionne les nombres"), ("MOYENNE(plage)", "Moyenne"), ("MIN(plage)", "Plus petite valeur"), ("MAX(plage)", "Plus grande valeur"), ("MEDIANE(plage)", "Médiane"),
 ("NB(plage)", "Compte les nombres"), ("NBVAL(plage)", "Compte les cellules non vides"), ("NB.VIDE(plage)", "Compte les cellules vides"), ("SI(test; si_vrai; si_faux)", "Condition"),
 ("ET(a; b…)", "Vrai si tout est vrai"), ("OU(a; b…)", "Vrai si l'un est vrai"), ("SIERREUR(calcul; sinon)", "Remplace une erreur"),
 ("SOMME.SI(plage; critère; [somme])", "Somme conditionnelle, ex. \">10\""), ("NB.SI(plage; critère)", "Compte conditionnel"), ("MOYENNE.SI(plage; critère; [moyenne])", "Moyenne conditionnelle"),
 ("RECHERCHE(valeur; colonne_clé; colonne_résultat)", "Retrouve la correspondance, sans numéro de colonne"), ("RECHERCHEV(valeur; table; n°colonne)", "RECHERCHEV classique"),
 ("CONCAT(a; b…)", "Assemble des textes (ou a & b)"), ("GAUCHE(texte; n)", "n premiers caractères"), ("DROITE(texte; n)", "n derniers caractères"),
 ("MAJUSCULE(texte)", "MAJUSCULES"), ("MINUSCULE(texte)", "minuscules"), ("SUPPRESPACE(texte)", "Retire les espaces en trop"), ("NBCAR(texte)", "Longueur"),
 ("SUBSTITUE(texte; ancien; nouveau)", "Remplace du texte"), ("ARRONDI(nombre; décimales)", "Arrondit"), ("ABS(nombre)", "Valeur absolue"), ("AUJOURDHUI()", "Date du jour"), ("ANNEE(date)", "Année d'une date")]

def xlate(e):
    def tr(p):
        bs = []
        p = re.sub(r"\[([^\]]+)\]", lambda m: (bs.append(m.group(1)), f"__{len(bs) - 1}__")[1], p)
        p = re.sub(r"\b([A-Za-z]{2,})\.([A-Za-z]+)\b", r"\1_\2", p)
        p = re.sub(r"\$?([A-Z]{1,3})\$?(\d+):\$?([A-Z]{1,3})\$?(\d+)", r'RNG("\1",\2,"\3",\4)', p)
        p = re.sub(r"\$?\b([A-Z]{1,3}):([A-Z]{1,3})\b", r'RNG("\1",0,"\2",0)', p)
        p = re.sub(r"(?<![\w\"])\$?([A-Z]{1,3})\$?(\d+)\b(?!\()", r'CEL("\1",\2)', p)
        p = p.replace(";", ",").replace("<>", "!=").replace("^", "**").replace("&", "@")
        p = re.sub(r"(?<![<>=!])=(?!=)", "==", p)
        return re.sub(r"__(\d+)__", lambda m: f'COL("{bs[int(m.group(1))]}")', p)
    return "".join(tr(p) if i % 2 == 0 else p for i, p in enumerate(re.split(r'("(?:[^"]|"")*")', e)))
BIN = {ast.Add: lambda a, b: num(a) + num(b), ast.Sub: lambda a, b: num(a) - num(b), ast.Mult: lambda a, b: num(a) * num(b), ast.Div: lambda a, b: num(a) / num(b),
       ast.Pow: lambda a, b: num(a) ** num(b), ast.MatMult: lambda a, b: txt(a) + txt(b)}
CMP = {ast.Eq: op.eq, ast.NotEq: op.ne, ast.Lt: op.lt, ast.LtE: op.le, ast.Gt: op.gt, ast.GtE: op.ge}
def norm(a, b):
    if a is None: a = "" if isinstance(b, str) else 0
    if isinstance(a, str) and isinstance(b, str): return a.lower()
    return a
def ev(n, df):
    if isinstance(n, ast.Constant): return n.value
    if isinstance(n, ast.Name):
        if n.id.upper() in ("TRUE", "VRAI"): return True
        if n.id.upper() in ("FALSE", "FAUX"): return False
        raise ValueError("#NOM?")
    if isinstance(n, ast.UnaryOp):
        v = ev(n.operand, df); return -num(v) if isinstance(n.op, ast.USub) else num(v)
    if isinstance(n, ast.BinOp) and type(n.op) in BIN: return BIN[type(n.op)](ev(n.left, df), ev(n.right, df))
    if isinstance(n, ast.Compare):
        l = ev(n.left, df)
        for o, c in zip(n.ops, n.comparators):
            r = ev(c, df)
            if not CMP[type(o)](norm(l, r), norm(r, l)): return False
            l = r
        return True
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
        k, a = n.func.id.upper(), n.args
        if k in ("SI", "IF"): return ev(a[1], df) if truthy(ev(a[0], df)) else (ev(a[2], df) if len(a) > 2 else False)
        if k in ("SIERREUR", "IFERROR"):
            try: v = ev(a[0], df)
            except Exception: return ev(a[1], df)
            return ev(a[1], df) if isinstance(v, str) and v.startswith("#") else v
        args = [ev(x, df) for x in a]
        if k in REF: return REF[k](df, *args)
        if k in FN: return FN[k](*args)
    raise ValueError("#NOM?")
def evaluate(src, df):
    try:
        v = ev(ast.parse(xlate(src.strip()[1:]), mode="eval").body, df)
        v = (flat(v) or [None])[0] if isinstance(v, list) else v
        return "#NUM!" if isinstance(v, float) and (v != v or abs(v) == math.inf) else v
    except ZeroDivisionError: return "#DIV/0!"
    except NA: return "#N/A"
    except ValueError as x: return str(x) if str(x).startswith("#") else "#ERREUR!"
    except Exception: return "#ERREUR!"
def recalc(d):
    fx, df = d["formulas"], d["df"]
    if not fx: return
    for key in [k for k in fx if k.rsplit("|", 1)[0] not in df.columns or int(k.rsplit("|", 1)[1]) >= len(df)]: fx.pop(key)
    for c in {k.rsplit("|", 1)[0] for k in fx}: df[c] = df[c].astype(object)
    for _ in range(3):
        for key, src in fx.items():
            c, r = key.rsplit("|", 1); v = evaluate(src, df); df.iat[int(r), df.columns.get_loc(c)] = np.nan if v is None else v
    for c in {k.rsplit("|", 1)[0] for k in fx}: df[c] = df[c].infer_objects()
def shift(src, dr):
    ps = re.split(r'("(?:[^"]|"")*")', src)
    ps[::2] = [re.sub(r"(\$?)\b([A-Z]{1,3})(\$?)(\d+)\b(?!\()", lambda m: m.group(0) if m.group(3) else f"{m.group(1)}{m.group(2)}{int(m.group(4)) + dr}", p) for p in ps[::2]]
    return "".join(ps)
KEEP = {"clear_cells", "fill_down", "add_col", "dup_col", "insert_col_left", "insert_col_right"}

def save(tid):
    d = T[tid]; pd.to_pickle({"df": d["df"], "name": d["name"], "formulas": d["formulas"], "filters": d["filters"], "widgets": d["widgets"], "styles": d["styles"]}, DATA / f"{tid}.pkl")
def view(tid):
    d = T[tid]; df = d["df"]
    return {"id": tid, "name": d["name"], "columns": list(df.columns), "total": nrows(d), "real_total": len(df), "filters": d["filters"], "can_undo": bool(d["hist"])}
for _p in sorted(DATA.glob("*.pkl"), key=lambda p: p.stat().st_mtime):
    T[_p.stem] = {"formulas": {}, "filters": {}, "widgets": [], "styles": {"cells": {}, "cols": {}}, **pd.read_pickle(_p), "hist": [], "view": None}; apply_filters(T[_p.stem])
def get(tid):
    if tid not in T: raise HTTPException(404, "Tableau introuvable")
    return T[tid]
def commit(tid, new, fx=None, st=None):
    d = T[tid]; d["hist"].append((d["df"], dict(d["formulas"]), d["styles"])); d["hist"][:] = d["hist"][-10:]
    d["df"] = new.reset_index(drop=True)
    if fx is not None: d["formulas"] = fx
    if st is not None: d["styles"] = st
    recalc(d); apply_filters(d); save(tid); return view(tid)
def uniq(cols):
    seen, out = set(), []
    for c in map(str, cols):
        n = c
        while n in seen: n += "_"
        seen.add(n); out.append(n)
    return out
def put(df, name):
    tid = uuid.uuid4().hex[:8]; df.columns = uniq(df.columns)
    T[tid] = {"df": df.reset_index(drop=True), "name": name, "hist": [], "formulas": {}, "filters": {}, "widgets": [], "styles": {"cells": {}, "cols": {}}, "view": None}; save(tid); return view(tid)
def grow(df, nr, nc):
    df = df.copy()
    while len(df.columns) < nc:
        n = colname(len(df.columns))
        while n in df.columns: n += "_"
        df[n] = np.nan
    if nr > len(df): df = pd.concat([df, pd.DataFrame(np.nan, index=range(len(df), nr), columns=df.columns)])
    return df
def pack(x):
    if isinstance(x, pd.Series):
        x = x.rename(x.name or "valeur"); x.index.name = x.index.name or "colonne"; x = x.reset_index()
    elif not isinstance(x.index, pd.RangeIndex): x = x.reset_index()
    x = x.round(4); x.columns = [str(c) for c in x.columns]
    return {"columns": list(x.columns), "rows": clean(x)}

def _hdr(df, c, i, a):
    h, seen = [], set()
    for k, v in enumerate(df.iloc[0]):
        n = str(v) if pd.notna(v) else colname(k)
        while n in seen: n += "_"
        seen.add(n); h.append(n)
    x = df.iloc[1:].copy(); x.columns = h; return x.infer_objects()
def _clear(df, c, i, a):
    df = df.copy(); df[c] = df[c].astype(object); df.loc[i, c] = np.nan; return df.apply(lambda s: s.infer_objects())
def _autoclean(df, c, i, a):
    x = df.apply(lambda s: s.map(lambda v: v.strip() if isinstance(v, str) else v) if s.dtype == object else s)
    return x.replace(r"^\s*$", np.nan, regex=True).dropna(how="all").drop_duplicates()
def _has(df, c, a): return df[c].astype("string").apply(lambda s: s.str.contains(a, case=False, regex=False, na=False)).any(axis=1)
add(TABLE, "Actions faciles", {
 "autoclean": ("Nettoyer en 1 clic (espaces, lignes vides, doublons)", _autoclean),
 "first_row_header": ("Utiliser la 1re ligne comme en-têtes", _hdr),
 "clear_cells": ("Effacer la sélection", _clear),
 "filter_text": ("Garder les lignes contenant (arg)", lambda df,c,i,a: df[_has(df, c, a)]),
 "exclude_text": ("Retirer les lignes contenant (arg)", lambda df,c,i,a: df[~_has(df, c, a)]),
 "filter_gt": ("Garder valeurs supérieures à (arg)", lambda df,c,i,a: df[N(df[c[0]]) > f(a)]),
 "filter_lt": ("Garder valeurs inférieures à (arg)", lambda df,c,i,a: df[N(df[c[0]]) < f(a)]),
 "replace_all": ("Remplacer partout (arg = ancien=>nouveau)", lambda df,c,i,a: df.apply(lambda s: S(s).str.replace(a.split("=>")[0], a.split("=>")[1] if "=>" in a else "", regex=False) if s.dtype == object else s)),
})

def _ins_rows(where):
    def fn(df, c, i, a):
        k = max(len(i), 1); p = min((i[0] if where == "above" else i[-1] + 1) if len(i) else len(df), len(df))
        return pd.concat([df.iloc[:p], pd.DataFrame(np.nan, index=range(k), columns=df.columns), df.iloc[p:]])
    return fn
def _ins_col(side):
    def fn(df, c, i, a):
        pos = df.columns.get_loc(c[0]) if side == "left" else df.columns.get_loc(c[-1]) + 1
        df = df.copy()
        for k in range(len(c)):
            n = colname(len(df.columns) + k)
            while n in df.columns: n += "_"
            df.insert(pos + k, n, np.nan)
        return df
    return fn
def _fill_down(df, c, i, a):
    df = df.copy()
    if len(i):
        for col in c: x = df[col].astype(object); x.loc[i] = x.loc[i[0]]; df[col] = x.infer_objects()
    return df
add(TABLE, "Lignes et colonnes", {
 "insert_row_above": ("Insérer des lignes au-dessus", _ins_rows("above")), "insert_row_below": ("Insérer des lignes en dessous", _ins_rows("below")),
 "insert_col_left": ("Insérer des colonnes à gauche", _ins_col("left")), "insert_col_right": ("Insérer des colonnes à droite", _ins_col("right")),
 "fill_down": ("Remplir vers le bas", _fill_down),
})



def remap_fx(fx, rm):
    def fix(src):
        def sub(m):
            x = rm(int(m.group(2)) - 1); return m.group(1) + str(m.group(2) if x is None else x + 1)
        ps = re.split(r'("(?:[^"]|"")*")', src)
        ps[::2] = [re.sub(r"(?<![\w\[])(\$?[A-Z]{1,3}\$?)(\d+)\b(?!\()", sub, p) for p in ps[::2]]
        return "".join(ps)
    out = {}
    for k, src in fx.items():
        c, r = k.rsplit("|", 1); nr = rm(int(r))
        if nr is not None: out[f"{c}|{nr}"] = fix(src)
    return out

def remap_styles(st, rm):
    cells = {}
    for k, v in st["cells"].items():
        cn, r = k.rsplit("|", 1); nr = rm(int(r))
        if nr is not None: cells[f"{cn}|{nr}"] = v
    return {"cells": cells, "cols": st["cols"]}
