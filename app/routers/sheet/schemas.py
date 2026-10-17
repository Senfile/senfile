from pydantic import BaseModel

class Sel(BaseModel):
    cols: list[str] = []; r0: int | None = None; r1: int | None = None; c0: int | None = None; c1: int | None = None

class OpReq(BaseModel):
    op: str; sel: Sel = Sel(); arg: str = ""; inplace: bool = False

class Cell(BaseModel):
    row: int; col: int; value: str

class Paste(BaseModel):
    row: int; col: int; data: list[list[str]]

class NewReq(BaseModel):
    rows: int = 100; cols: int = 26

class SqlReq(BaseModel):
    url: str; query: str

class Quick(BaseModel):
    r0: int; r1: int; c0: int; c1: int

class Lookup(BaseModel):
    other_id: str; key: str; other_key: str; bring: list[str]

class Filt(BaseModel):
    col: str; op: str = ""; arg: str = ""; values: list[str] | None = None; clear: bool = False

class Pivot(BaseModel):
    rows: str; cols: str = ""; value: str = ""; agg: str = "sum"; save: bool = False

class Summary(BaseModel):
    aggs: dict[str, str]

class Calc(BaseModel):
    name: str; expr: str

class Widget(BaseModel):
    kind: str = "chart"; col: str = ""; by: str = ""; agg: str = "sum"; chart: str = "bar"; title: str = ""

class StyleReq(BaseModel):
    r0: int; r1: int; c0: int; c1: int; patch: dict = {}; clear: bool = False

class MergeReq(BaseModel):
    r0: int; r1: int; c0: int; c1: int; unmerge: bool = False
class ObjIn(BaseModel):
    kind: str; x: float = 60; y: float = 80; w: float = 320; h: float = 220; src: str = ""; cfg: dict = {}
class ObjPatch(BaseModel):
    x: float | None = None; y: float | None = None; w: float | None = None; h: float | None = None

class Rename(BaseModel):
    name: str

class EvalReq(BaseModel):
    formula: str
class BorderReq(BaseModel):
    r0: int; r1: int; c0: int; c1: int; preset: str
