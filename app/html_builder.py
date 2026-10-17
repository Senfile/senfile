"""
Convertit le JSON ProseMirror/TipTap stocké en base en HTML, pour l'export PDF.

Pagination calculée par nous (une .page-surface par page physique) : le
positionnement absolu reste ainsi toujours dans le cas simple et fiable.

ORIGINE DES COORDONNÉES : x/y des éléments flottants sont relatifs au COIN
DE LA PAGE (padding compris), comme dans l'éditeur (.page[data-page-surface]).
Si un léger décalage résiduel subsiste, ajuster FLOAT_ORIGIN_X / _Y.
"""
import math
from html import escape
import io
import math
from html import escape

from pypdf import PdfReader, PdfWriter

PAGE_WIDTH_PX = 794  # A4 à 96dpi
PAGE_HEIGHT_PX = 1123  # hauteur d'une page A4 à 96dpi
PAGE_PADDING_X = 88
PAGE_PADDING_Y = 96
CONTENT_WIDTH = PAGE_WIDTH_PX - 2 * PAGE_PADDING_X
PAGE_CONTENT_HEIGHT = PAGE_HEIGHT_PX - 2 * PAGE_PADDING_Y

# Décalage global des éléments flottants (0 = même origine que l'éditeur).
FLOAT_ORIGIN_X = 0
FLOAT_ORIGIN_Y = 0
# Pas vertical entre deux pages pour les éléments flottants. À passer à
# PAGE_HEIGHT_PX si l'éditeur est une surface continue découpée toutes les
# 1123px ; à laisser à PAGE_CONTENT_HEIGHT si y est compté dans le contenu.
FLOAT_PAGE_STEP = PAGE_CONTENT_HEIGHT

AVG_CHAR_PX = 7.2
LINE_HEIGHT_BODY = 21
LINE_HEIGHT_H = {1: 34, 2: 25, 3: 20}
MARGIN_H = {1: 14, 2: 32, 3: 26}
DEFAULT_ROW_HEIGHT = 34


def _attrs_style(attrs: dict) -> str:
    styles = []
    if attrs.get("textAlign"):
        styles.append(f"text-align:{attrs['textAlign']}")
    return f' style="{";".join(styles)}"' if styles else ""


def _render_marks(text: str, marks: list) -> str:
    out = escape(text)
    for mark in marks or []:
        t = mark.get("type")
        if t == "bold":
            out = f"<strong>{out}</strong>"
        elif t == "italic":
            out = f"<em>{out}</em>"
        elif t == "underline":
            out = f"<u>{out}</u>"
        elif t == "link":
            href = escape(mark.get("attrs", {}).get("href", "#"))
            out = f'<a href="{href}">{out}</a>'
        elif t == "textStyle":
            style_parts = []
            a = mark.get("attrs", {}) or {}
            if a.get("color"):
                style_parts.append(f"color:{escape(str(a['color']))}")
            if a.get("fontSize"):
                style_parts.append(f"font-size:{escape(str(a['fontSize']))}")
            if a.get("fontFamily"):
                style_parts.append(f"font-family:{escape(str(a['fontFamily']))}")
            if style_parts:
                out = f'<span style="{";".join(style_parts)}">{out}</span>'
    return out


# ---------------------------------------------------------------------------
# Tableaux : largeurs de colonnes, fusions, couleurs, hauteurs de lignes
# ---------------------------------------------------------------------------

def _table_col_widths(table: dict):
    """Largeurs (px) de colonnes issues de l'éditeur, ou None si inconnues."""
    rows = table.get("content") or []
    if not rows:
        return None
    widths = []
    for cell in rows[0].get("content") or []:
        a = cell.get("attrs") or {}
        cw = a.get("colwidth")
        span = a.get("colspan") or 1
        if not cw or len(cw) != span:
            return None
        widths.extend(cw)
    return widths or None


def _cell_html(tag: str, attrs: dict, children: str) -> str:
    extra = ""
    if (attrs.get("colspan") or 1) > 1:
        extra += f' colspan="{attrs["colspan"]}"'
    if (attrs.get("rowspan") or 1) > 1:
        extra += f' rowspan="{attrs["rowspan"]}"'
    if attrs.get("backgroundColor"):
        extra += f' style="background-color:{escape(str(attrs["backgroundColor"]))};"'
    return f"<{tag}{extra}>{children}</{tag}>"


# ---------------------------------------------------------------------------
# Rendu "en flux" : tout SAUF les éléments flottants
# ---------------------------------------------------------------------------

def _render_flow_node(node: dict) -> str:
    t = node.get("type")
    attrs = node.get("attrs", {}) or {}

    if t == "shapeBlock":
        return ""  # toujours flottante : rendue séparément
    if t == "image" and attrs.get("x") is not None:
        return ""  # image flottante : rendue séparément

    children = "".join(_render_flow_node(c) for c in node.get("content", []) or [])

    if t == "paragraph":
        return f"<p{_attrs_style(attrs)}>{children or '&nbsp;'}</p>"
    if t == "heading":
        level = attrs.get("level", 1)
        return f"<h{level}{_attrs_style(attrs)}>{children}</h{level}>"
    if t == "bulletList":
        return f"<ul>{children}</ul>"
    if t == "orderedList":
        return f"<ol>{children}</ol>"
    if t == "listItem":
        return f"<li>{children}</li>"
    if t == "blockquote":
        return f"<blockquote>{children}</blockquote>"
    if t == "image":
        src = escape(attrs.get("src", ""))
        width = attrs.get("width")
        style = "max-width:100%;"
        if width:
            style += f" width:{width}px;"
        return f'<img src="{src}" style="{style}" />'
    # if t == "table":
    #     widths = _table_col_widths(node)
    #     if widths:
    #         cols = "".join(f'<col style="width:{w}px" />' for w in widths)
    #         return (
    #             f'<table style="width:{sum(widths)}px;table-layout:fixed;">'
    #             f"<colgroup>{cols}</colgroup>{children}</table>"
    #         )
    #     return f"<table>{children}</table>"
    if t == "table":
        widths = _table_col_widths(node)
        if widths:
            cols = "".join(f'<col style="width:{w}px" />' for w in widths)
            return (
                f'<table style="width:{sum(widths)}px;max-width:100%;table-layout:fixed;">'
                f"<colgroup>{cols}</colgroup>{children}</table>"
            )
        return f"<table>{children}</table>"
    if t == "tableRow":
        style = ""
        if attrs.get("rowHeight"):
            style = f' style="height:{attrs["rowHeight"]}px;"'
        return f"<tr{style}>{children}</tr>"
    if t == "tableHeader":
        return _cell_html("th", attrs, children)
    if t == "tableCell":
        return _cell_html("td", attrs, children)
    if t == "text":
        return _render_marks(node.get("text", ""), node.get("marks", []))
    if t == "hardBreak":
        return "<br/>"
    return children


def _inline_html(node: dict) -> str:
    """Rendu du contenu inline d'une forme (texte/retours à la ligne)."""
    return "".join(_render_flow_node(c) for c in node.get("content", []) or [])


# ---------------------------------------------------------------------------
# Estimation de hauteur (pour décider où placer les sauts de page)
# ---------------------------------------------------------------------------

def _text_length(node: dict) -> int:
    if node.get("type") == "text":
        return len(node.get("text", ""))
    total = 0
    for c in node.get("content", []) or []:
        total += _text_length(c)
    return total


def _estimate_lines(chars: int, width: float = CONTENT_WIDTH) -> int:
    if not chars:
        return 1
    chars_per_line = max(20, width / AVG_CHAR_PX)
    return max(1, math.ceil(chars / chars_per_line))


def _estimate_height(node: dict) -> float:
    t = node.get("type")
    attrs = node.get("attrs", {}) or {}

    if t == "shapeBlock" or (t == "image" and attrs.get("x") is not None):
        return 0.0  # flottant : ne pousse pas le flux de texte

    if t == "paragraph":
        return _estimate_lines(_text_length(node)) * LINE_HEIGHT_BODY + 10
    if t == "heading":
        level = attrs.get("level", 1)
        return LINE_HEIGHT_H.get(level, 25) + MARGIN_H.get(level, 20)
    if t == "blockquote":
        return _estimate_lines(_text_length(node), CONTENT_WIDTH - 14) * LINE_HEIGHT_BODY + 10
    if t in ("bulletList", "orderedList"):
        total = 0.0
        for item in node.get("content", []) or []:
            for c in item.get("content", []) or []:
                total += _estimate_height(c)
        return total + 6
    if t == "table":
        rows = node.get("content", []) or []
        total = 0.0
        for r in rows:
            total += ((r.get("attrs") or {}).get("rowHeight")) or DEFAULT_ROW_HEIGHT
        return total + 24
    if t == "image":
        width = attrs.get("width") or 400
        height = attrs.get("height") or (width * 0.66)
        return height + 16
    return 24.0


# ---------------------------------------------------------------------------
# Extraction des éléments flottants (formes, images positionnées)
# ---------------------------------------------------------------------------

def _collect_floating(node: dict, floats: list) -> None:
    if not isinstance(node, dict):
        return
    t = node.get("type")
    attrs = node.get("attrs", {}) or {}

    if t == "shapeBlock":
        floats.append(
            {
                "kind": "shape",
                "x": attrs.get("x", 0) or 0,
                "y": attrs.get("y", 0) or 0,
                "width": attrs.get("width"),
                "height": attrs.get("height") or 60,
                "rotation": attrs.get("rotation", 0) or 0,
                "fill": attrs.get("fill", "transparent"),
                "border_color": attrs.get("borderColor", "#4b3f72"),
                "shape_type": attrs.get("shapeType", "rectangle"),
                "text_align": attrs.get("textAlign") or "center",
                "hide_border": bool(attrs.get("hideBorder")),
                "radius": attrs.get("radius"),
                "html": _inline_html(node),
            }
        )
        return

    if t == "image" and attrs.get("x") is not None:
        width = attrs.get("width") or 300
        height = attrs.get("height") or (width * 0.66)
        floats.append(
            {
                "kind": "image",
                "x": attrs.get("x", 0) or 0,
                "y": attrs.get("y", 0) or 0,
                "width": width,
                "height": height,
                "src": attrs.get("src", ""),
            }
        )
        return

    for child in node.get("content", []) or []:
        _collect_floating(child, floats)


def _render_floating(f: dict) -> str:
    left = f["x"] + FLOAT_ORIGIN_X
    top = f["local_y"] + FLOAT_ORIGIN_Y

    if f["kind"] == "shape":
        if f["shape_type"] == "circle":
            border_radius = "50%"
        else:
            r = f.get("radius")
            border_radius = f"{r if r is not None else 10}px"
        border = (
            "none"
            if f["hide_border"]
            else f"2px dashed {escape(str(f['border_color']))}"
        )
        size_style = ""
        if f.get("width"):
            size_style += f"width:{f['width']}px;"
        if f.get("height"):
            size_style += f"height:{f['height']}px;"
        style = (
            f"position:absolute; left:{left}px; top:{top}px; {size_style} "
            f"border:{border}; background:{escape(str(f['fill']))}; "
            f"border-radius:{border_radius}; transform:rotate({f['rotation']}deg); "
            f"box-sizing:border-box; display:flex; align-items:center; "
            f"justify-content:center; padding:10px 16px; overflow:hidden; "
            f"font-family:Arial,sans-serif; font-size:12px; color:#1c1b22;"
        )
        inner = (
            f'<div style="width:100%; text-align:{escape(str(f["text_align"]))};">'
            f'{f.get("html") or "&nbsp;"}</div>'
        )
        return f'<div style="{style}">{inner}</div>'

    if f["kind"] == "image":
        # margin:0 est indispensable : la règle globale `img { margin: 8px 0 }`
        # décalerait sinon l'image de 8px vers le bas.
        style = (
            f"position:absolute; left:{left}px; top:{top}px; "
            f"width:{f['width']}px; height:auto; margin:0;"
        )
        return f'<img src="{escape(f["src"])}" style="{style}" />'

    return ""


# ---------------------------------------------------------------------------
# Pagination + construction du document HTML final
# ---------------------------------------------------------------------------

PDF_STYLES = f"""
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 0; font-family: 'Georgia', serif; color: #1c1b22; font-size: 13px; line-height: 1.6; }}
  .page-surface {{
    position: relative;
    width: {PAGE_WIDTH_PX}px;
    min-height: {PAGE_HEIGHT_PX - 1}px;
    padding: {PAGE_PADDING_Y}px {PAGE_PADDING_X}px;
  }}
  h1 {{ font-size: 26px; margin: 0 0 14px; }}
  h2 {{ font-size: 19px; margin: 22px 0 10px; }}
  h3 {{ font-size: 15px; margin: 18px 0 8px; }}
  p {{ margin: 0 0 10px; }}
  blockquote {{ border-left: 3px solid #4b3f72; margin: 0 0 10px; padding-left: 14px; color: #4a4852; font-style: italic; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; font-family: sans-serif; font-size: 11px; }}
  td, th {{ border: 1px solid #dedad2; padding: 6px 8px; text-align: left; }}
  th {{ background: #f3f2ef; }}
  img {{ display: block; margin: 8px 0; }}
  @page {{ size: A4; margin: 0; }}
"""


def build_html(title: str, doc: dict) -> str:
    top_nodes = (doc or {}).get("content", []) or []

    # 1) Regrouper les nœuds de flux (texte) par page, selon la hauteur estimée.
    pages_flow: list = [[]]
    cursor_y = LINE_HEIGHT_H.get(1, 34) + MARGIN_H.get(1, 14)  # place pour le <h1> titre

    for node in top_nodes:
        h = _estimate_height(node)
        if h > 0 and cursor_y + h > PAGE_CONTENT_HEIGHT and pages_flow[-1]:
            pages_flow.append([])
            cursor_y = 0.0
        pages_flow[-1].append(node)
        cursor_y += h

    # 2) Éléments flottants : page déterminée par leur seule coordonnée y.
    floats: list = []
    for node in top_nodes:
        _collect_floating(node, floats)

    num_pages = len(pages_flow)
    if floats:
        max_float_page = max(int(f["y"] // FLOAT_PAGE_STEP) for f in floats) + 1
        num_pages = max(num_pages, max_float_page)
    while len(pages_flow) < num_pages:
        pages_flow.append([])

    floats_by_page = {i: [] for i in range(num_pages)}
    for f in floats:
        page_index = min(int(f["y"] // FLOAT_PAGE_STEP), num_pages - 1)
        f["local_y"] = f["y"] - page_index * FLOAT_PAGE_STEP
        floats_by_page[page_index].append(f)

    # 3) Une div .page-surface par page physique.
    pages_html = []
    for i in range(num_pages):
        flow_html = "".join(_render_flow_node(n) for n in pages_flow[i])
        title_html = f"<h1>{escape(title)}</h1>" if i == 0 else ""
        floats_html = "".join(_render_floating(f) for f in floats_by_page[i])
        break_style = "" if i == num_pages - 1 else "break-after: page; page-break-after: always;"
        pages_html.append(
            f'<div class="page-surface" style="{break_style}">{title_html}{flow_html}{floats_html}</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8" />
<title>{escape(title)}</title>
<style>{PDF_STYLES}</style>
</head>
<body>
{''.join(pages_html)}
</body>
</html>"""


# ---------------------------------------------------------------------------
# Constantes (identiques à l'éditeur / à l'aperçu)
# ---------------------------------------------------------------------------
PW = 794
PH = 1123
SAFE = 30  # espace libre minimum en haut et en bas de chaque page
DEFAULT_MARGIN = 72


def _num(v, default=0.0) -> float:
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def _esc(v) -> str:
    return escape(str(v if v is not None else ""), quote=True)


# ---------------------------------------------------------------------------
# 1) PDF du TEXTE : WeasyPrint pagine, @page impose la zone de sécurité
# ---------------------------------------------------------------------------

def _text_styles(ml: int, mr: int) -> str:
    return f"""
  @page {{ size: {PW}px {PH}px; margin: {SAFE}px {mr}px {SAFE}px {ml}px; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: 'Georgia', serif; color: #1c1b22; font-size: 13px; line-height: 1.6; }}
  h1 {{ font-size: 26px; margin: 0 0 14px; }}
  h2 {{ font-size: 19px; margin: 22px 0 10px; }}
  h3 {{ font-size: 15px; margin: 18px 0 8px; }}
  p {{ margin: 0 0 10px; }}
  ul, ol {{ margin: 0 0 10px; padding-left: 24px; }}
  blockquote {{ border-left: 3px solid #4b3f72; margin: 0 0 10px; padding-left: 14px; color: #4a4852; font-style: italic; }}
  table {{ border-collapse: collapse; margin: 12px 0; font-family: sans-serif; font-size: 11px; }}
  td, th {{ border: 1px solid #dedad2; padding: 6px 8px; text-align: left; }}
  th {{ background: #f3f2ef; }}
  tr {{ break-inside: avoid; }}
  h1, h2, h3, p, li, blockquote {{ break-inside: avoid; orphans: 2; widows: 2; }}
  img {{ display: block; margin: 8px 0; max-width: 100%; }}
  /* première page : 72px en haut dans l'éditeur, dont 30px viennent déjà de @page */
  .flow {{ padding-top: {DEFAULT_MARGIN - SAFE}px; }}
"""


def build_text_html(doc: dict, margins: dict) -> str:
    nodes = (doc or {}).get("content", []) or []
    flow = "".join(_render_flow_node(n) for n in nodes)
    ml = int(_num(margins.get("left"), DEFAULT_MARGIN))
    mr = int(_num(margins.get("right"), DEFAULT_MARGIN))
    return (
        '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8" />'
        f"<style>{_text_styles(ml, mr)}</style></head>"
        f'<body><div class="flow">{flow}</div></body></html>'
    )


# ---------------------------------------------------------------------------
# 2) PDF des OBJETS : mêmes formules que ShapeView / safeObjects (front)
# ---------------------------------------------------------------------------

def _clean_object(o: dict) -> dict | None:
    if not isinstance(o, dict) or o.get("type") not in ("image", "shape"):
        return None
    c = dict(o)
    c["x"] = _num(o.get("x"))
    c["y"] = _num(o.get("y"))
    c["w"] = max(1.0, _num(o.get("w"), 100))
    c["h"] = max(1.0, _num(o.get("h"), 100))
    c["rotation"] = _num(o.get("rotation"))
    c["z"] = _num(o.get("z"))
    c["opacity"] = min(1.0, max(0.0, _num(o.get("opacity"), 1.0)))
    return c


def _bounds(o: dict):
    r = math.radians(o["rotation"])
    h = abs(o["w"] * math.sin(r)) + abs(o["h"] * math.cos(r))
    cy = o["y"] + o["h"] / 2
    return cy - h / 2, cy + h / 2, h


def _safe(o: dict) -> dict:
    """Ne modifie que le rendu PDF, jamais les positions stockées."""
    top, bottom, h = _bounds(o)
    if h > PH - 2 * SAFE:
        return o
    start = math.floor(max(0, top) / PH) * PH
    dy = 0.0
    if bottom > start + PH - SAFE:
        dy = start + PH + SAFE - top  # poussé à la page suivante
    elif top < start + SAFE:
        dy = start + SAFE - top  # écarté du bord haut
    return {**o, "y": round(o["y"] + dy)} if dy else o


def _fmt(n: float) -> str:
    return f"{n:.2f}".rstrip("0").rstrip(".")


def _shape_svg(o: dict) -> str:
    w, h = o["w"], o["h"]
    sw = _num(o.get("strokeWidth"), 2)
    i = sw / 2
    fill = _esc(o.get("fill") or "#e8e4fb")
    stroke = _esc(o.get("stroke") or "#4b3f72") if sw else "none"
    common = f'fill="{fill}" stroke="{stroke}" stroke-width="{_fmt(sw)}" stroke-linejoin="round"'
    kind = o.get("shape", "rectangle")
    radius = _num(o.get("radius"), 16)

    if kind == "ellipse":
        node = (
            f'<ellipse cx="{_fmt(w/2)}" cy="{_fmt(h/2)}" rx="{_fmt(max(1,(w-sw)/2))}" '
            f'ry="{_fmt(max(1,(h-sw)/2))}" {common}/>'
        )
    elif kind == "triangle":
        pts = f"{w/2},{i} {w-i},{h-i} {i},{h-i}"
        node = f'<polygon points="{pts}" {common}/>'
    elif kind == "diamond":
        pts = f"{w/2},{i} {w-i},{h/2} {w/2},{h-i} {i},{h/2}"
        node = f'<polygon points="{pts}" {common}/>'
    elif kind == "star":
        rx, ry = (w - sw) / 2, (h - sw) / 2
        pts = []
        for k in range(10):
            a = -math.pi / 2 + k * math.pi / 5
            r = 0.45 if k % 2 else 1
            pts.append(f"{_fmt(w/2 + rx*r*math.cos(a))},{_fmt(h/2 + ry*r*math.sin(a))}")
        node = f'<polygon points="{" ".join(pts)}" {common}/>'
    elif kind == "arrow":
        pts = (
            f"{i},{h*0.3} {w*0.6},{h*0.3} {w*0.6},{i} {w-i},{h/2} "
            f"{w*0.6},{h-i} {w*0.6},{h*0.7} {i},{h*0.7}"
        )
        node = f'<polygon points="{pts}" {common}/>'
    elif kind == "bubble":
        bh = h * 0.82
        r = max(0, min(radius, bh / 2, w / 2))
        d = (
            f"M{r+i},{i} H{w-r-i} Q{w-i},{i} {w-i},{r+i} V{bh-r} "
            f"Q{w-i},{bh-i} {w-r-i},{bh-i} H{w*0.38} L{w*0.2},{h-i} L{w*0.22},{bh-i} "
            f"H{r+i} Q{i},{bh-i} {i},{bh-r} V{r+i} Q{i},{i} {r+i},{i} Z"
        )
        node = f'<path d="{d}" {common}/>'
    else:  # rectangle
        r = max(0, min(radius, (w - sw) / 2, (h - sw) / 2))
        node = (
            f'<rect x="{_fmt(i)}" y="{_fmt(i)}" width="{_fmt(w-sw)}" height="{_fmt(h-sw)}" '
            f'rx="{_fmt(r)}" {common}/>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_fmt(w)}" height="{_fmt(h)}" '
        f'viewBox="0 0 {_fmt(w)} {_fmt(h)}" style="position:absolute;left:0;top:0;overflow:visible">'
        f"{node}</svg>"
    )


def _object_html(o: dict, offset_y: float) -> str:
    style = (
        f"position:absolute;left:{_fmt(o['x'])}px;top:{_fmt(o['y'] - offset_y)}px;"
        f"width:{_fmt(o['w'])}px;height:{_fmt(o['h'])}px;"
        f"transform:rotate({_fmt(o['rotation'])}deg);transform-origin:50% 50%;"
        f"opacity:{o['opacity']};"
    )
    if o["type"] == "image":
        inner = (
            f'<img src="{_esc(o.get("src"))}" '
            f'style="display:block;width:100%;height:100%;margin:0;max-width:none;" />'
        )
    else:
        align = o.get("textAlign", "center")
        just = {"left": "flex-start", "right": "flex-end"}.get(align, "center")
        text = _esc(o.get("text")).replace("\n", "<br/>")
        inner = _shape_svg(o) + (
            f'<div style="position:absolute;left:0;top:0;width:100%;height:100%;'
            f"display:flex;align-items:center;justify-content:{just};padding:10px 14px;"
            f"overflow:hidden;line-height:1.25;white-space:pre-wrap;word-break:break-word;"
            f"font-family:Arial,sans-serif;color:{_esc(o.get('textColor') or '#2a2340')};"
            f"font-size:{_fmt(_num(o.get('fontSize'), 18))}px;text-align:{_esc(align)};"
            f'">{text}</div>'
        )
    return f'<div style="{style}">{inner}</div>'


def build_objects_html(objects: list, n_pages: int) -> str:
    ordered = sorted(objects, key=lambda o: o["z"])
    pages = []
    for i in range(n_pages):
        lo, hi = i * PH, (i + 1) * PH
        items = []
        for o in ordered:
            top, bottom, _ = _bounds(o)
            if bottom > lo and top < hi:  # tout objet qui touche cette page
                items.append(_object_html(o, lo))
        pages.append(
            f'<div class="pg" style="{"" if i == n_pages - 1 else "break-after:page;"}">'
            f'{"".join(items)}</div>'
        )
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8" /><style>'
        f"@page {{ size: {PW}px {PH}px; margin: 0; }}"
        "* { box-sizing: border-box; } body { margin: 0; background: transparent; }"
        f".pg {{ position: relative; width: {PW}px; height: {PH - 1}px; overflow: hidden; }}"
        f"</style></head><body>{''.join(pages)}</body></html>"
    )


# ---------------------------------------------------------------------------
# 3) Assemblage : texte dessous, objets dessus, page par page
# ---------------------------------------------------------------------------

def build_pdf(title: str, content: dict | None, base_url: str | None = None) -> bytes:
    from weasyprint import HTML  # import différé : dépendance lourde

    content = content or {}
    margins = content.get("margins") or {}
    objects = [c for c in (_clean_object(o) for o in content.get("objects") or []) if c]
    objects = [_safe(o) for o in objects]

    text_pdf = HTML(
        string=build_text_html(content, margins), base_url=base_url
    ).write_pdf()
    if not objects:
        return text_pdf

    needed = max(_bounds(o)[1] + SAFE for o in objects)
    n_obj_pages = max(1, math.ceil(needed / PH))
    obj_pdf = HTML(
        string=build_objects_html(objects, n_obj_pages), base_url=base_url
    ).write_pdf()

    text = PdfReader(io.BytesIO(text_pdf))
    over = PdfReader(io.BytesIO(obj_pdf))
    writer = PdfWriter()
    for i in range(max(len(text.pages), len(over.pages))):
        if i < len(text.pages) and i < len(over.pages):
            page = text.pages[i]
            page.merge_page(over.pages[i])  # objets au-dessus du texte
            writer.add_page(page)
        elif i < len(text.pages):
            writer.add_page(text.pages[i])
        else:
            writer.add_page(over.pages[i])

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()