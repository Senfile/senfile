"""
Convertit le JSON ProseMirror/TipTap stocké en base en HTML, pour l'export PDF.

Point critique : les moteurs d'impression CSS (WeasyPrint inclus) ne gèrent
pas de façon fiable le `position: absolute` d'un élément quand son conteneur
positionné s'étale sur PLUSIEURS pages physiques — l'élément a tendance à se
recaler en haut de la première page, quelle que soit la valeur de `top`
demandée. C'est exactement le bug initialement rapporté (images/formes
déplacées qui « reviennent » en haut de la première page à l'impression).

La correction : on ne laisse plus le moteur paginer un unique conteneur
géant. On calcule NOUS-MÊMES, ici, la pagination :
  1. on estime la hauteur de chaque bloc de texte (paragraphe, titre,
     tableau, liste…) pour savoir sur quelle page il tombe ;
  2. on extrait les éléments flottants (formes, images positionnées) et on
     calcule sur quelle page ILS tombent, à partir de leur seule
     coordonnée `y` (indépendante du flux de texte, exactement comme dans
     l'éditeur) ;
  3. on génère UNE div `.page-surface` par page physique, chacune ne
     contenant QUE le contenu qui lui revient, avec un saut de page HTML
     explicite entre elles.

Ainsi, chaque `.page-surface` ne s'étend jamais sur plus d'une page
physique : le positionnement absolu à l'intérieur reste toujours dans le
cas simple (un seul fragment), qui lui est fiable.
"""
import math
from html import escape

PAGE_WIDTH_PX = 794  # A4 à 96dpi
PAGE_HEIGHT_PX = 1123  # hauteur d'une page A4 à 96dpi
PAGE_PADDING_X = 88
PAGE_PADDING_Y = 96
CONTENT_WIDTH = PAGE_WIDTH_PX - 2 * PAGE_PADDING_X
PAGE_CONTENT_HEIGHT = PAGE_HEIGHT_PX - 2 * PAGE_PADDING_Y

# Constantes d'estimation de hauteur (approximatives mais déterministes :
# suffisantes pour décider sur quelle page bascule chaque bloc).
AVG_CHAR_PX = 7.2
LINE_HEIGHT_BODY = 21
LINE_HEIGHT_H = {1: 34, 2: 25, 3: 20}
MARGIN_H = {1: 14, 2: 32, 3: 26}


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
# Rendu "en flux" : tout SAUF les éléments flottants (formes, images
# positionnées), qui sont gérés séparément et injectés par-dessus.
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
        # Image imbriquée (ex : dans une bulle) : reste dans le flux normal.
        src = escape(attrs.get("src", ""))
        width = attrs.get("width")
        style = "max-width:100%;"
        if width:
            style += f" width:{width}px;"
        return f'<img src="{src}" style="{style}" />'
    if t == "table":
        return f"<table>{children}</table>"
    if t == "tableRow":
        style = ""
        if attrs.get("rowHeight"):
            style = f' style="height:{attrs["rowHeight"]}px;"'
        return f"<tr{style}>{children}</tr>"
    if t == "tableHeader":
        style = ""
        if attrs.get("backgroundColor"):
            style = f' style="background-color:{escape(str(attrs["backgroundColor"]))};"'
        return f"<th{style}>{children}</th>"
    if t == "tableCell":
        style = ""
        if attrs.get("backgroundColor"):
            style = f' style="background-color:{escape(str(attrs["backgroundColor"]))};"'
        return f"<td{style}>{children}</td>"
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
        rows = len(node.get("content", []) or [])
        return rows * 34 + 24
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
                "html": _inline_html(node),
            }
        )
        return  # ne pas descendre : déjà traité globalement

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
    if f["kind"] == "shape":
        border_radius = "50%" if f["shape_type"] == "circle" else "10px"
        size_style = ""
        if f.get("width"):
            size_style += f"width:{f['width']}px;"
        if f.get("height"):
            size_style += f"height:{f['height']}px;"
        style = (
            f"position:absolute; left:{f['x']}px; top:{f['local_y']}px; {size_style} "
            f"border:2px dashed {escape(str(f['border_color']))}; background:{escape(str(f['fill']))}; "
            f"border-radius:{border_radius}; transform:rotate({f['rotation']}deg); "
            f"box-sizing:border-box; display:flex; align-items:center; "
            f"justify-content:center; padding:10px 16px; overflow:hidden; "
            f"text-align:center; font-family:Arial,sans-serif; font-size:12px; color:#1c1b22;"
        )
        return f'<div style="{style}">{f.get("html") or "&nbsp;"}</div>'

    if f["kind"] == "image":
        style = f"position:absolute; left:{f['x']}px; top:{f['local_y']}px; width:{f['width']}px;"
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
    min-height: {PAGE_HEIGHT_PX}px;
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
  /* Marge de page à 0 : tout l'espacement visuel vient de .page-surface,
     pour que les coordonnées x/y correspondent à celles de l'éditeur. */
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

    # 2) Extraire tous les éléments flottants et déterminer leur page à
    # partir de leur seule coordonnée y (indépendante du flux de texte).
    floats: list = []
    for node in top_nodes:
        _collect_floating(node, floats)

    num_pages = len(pages_flow)
    if floats:
        max_float_page = max(int(f["y"] // PAGE_CONTENT_HEIGHT) for f in floats) + 1
        num_pages = max(num_pages, max_float_page)
    while len(pages_flow) < num_pages:
        pages_flow.append([])

    floats_by_page = {i: [] for i in range(num_pages)}
    for f in floats:
        page_index = min(int(f["y"] // PAGE_CONTENT_HEIGHT), num_pages - 1)
        f["local_y"] = f["y"] - page_index * PAGE_CONTENT_HEIGHT
        floats_by_page[page_index].append(f)

    # 3) Construire une div .page-surface par page physique — chacune ne
    # dépasse jamais une page, donc le positionnement absolu à l'intérieur
    # reste fiable.
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
