"""Official JCF Case Reference form replicas.

The source forms are stored as Word documents in ``static/forms/official``.
This module reads the WordprocessingML directly so the online forms stay
anchored to the authoritative templates without adding another dependency.
"""

from __future__ import annotations

import re
import zipfile
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

OFFICIAL_CR_FORM_TYPES = OrderedDict([
    ("CR1", "Investigator's Worksheet"),
    ("CR2", "Action Sheet"),
    ("CR3", "Witness Bio-Data Form"),
    ("CR4", "Stolen Property Form"),
    ("CR5", "Exhibit Chain of Custody Schedule"),
    ("CR6", "Investigator Index Card"),
    ("CR7", "Morning Crime Report"),
    ("CR8", "Question & Answer (Suspect/Witness Interview) Form"),
    ("CR9", "Question & Answer (Accused Written Interview) Form"),
    ("CR11", "Confession Statement of Suspect/Accused"),
    ("CR12", "Major and Minor Case Report Form"),
    ("CR13", "Court Case File Checklist"),
    ("CR14", "JCF Profile Form"),
    ("CR15", "Application for Remand of Accused or Bail Conditions"),
])

_FORM_META = {
    "CR1": {
        "code": "JCF/FW/PL/C&S/0001/2024/F05",
        "filename": "JCF Investigators Worksheet  CR 1.docx",
        "description": "Official Investigator's Worksheet clone from the JCF CR 1 template.",
    },
    "CR2": {
        "code": "JCF/FW/PL/C&S/0001/2024/F06",
        "filename": "JCF Action Sheet  CR 2.docx",
        "description": "Official Action Sheet clone from the JCF CR 2 template.",
    },
    "CR3": {
        "code": "JCF/FW/PL/C&S/0001/2024/F04",
        "filename": "Witness Bio-Data Form CR 3.docx",
        "description": "Official Witness Bio-Data Form clone from the JCF CR 3 template.",
    },
    "CR4": {
        "code": "JCF/FW/PL/C&S/0001/2024/F03",
        "filename": "Stolen Property Form  CR 4.docx",
        "description": "Official Stolen Property Form clone from the JCF CR 4 template.",
    },
    "CR5": {
        "code": "JCF/FW/PL/C&S/0001/2024/F07",
        "filename": "JCF Exhibit Chain of Custody Schedule  CR 5.docx",
        "description": "Official Exhibit Chain of Custody Schedule clone from the JCF CR 5 template.",
    },
    "CR6": {
        "code": "JCF/FW/PL/C&S/0001/2024/F08",
        "filename": "JCF Investigator Index Card CR 6.docx",
        "description": "Official Investigator Index Card clone from the JCF CR 6 template.",
    },
    "CR7": {
        "code": "JCF/FW/PL/C&S/0001/2024/F01",
        "filename": "JCF Morning Crime Report CR7.docx",
        "description": "Official Morning Crime Report clone from the JCF CR 7 template.",
    },
    "CR8": {
        "code": "JCF/FW/PL/C&S/0001/2024/F09",
        "filename": "JCF Question & Answer Suspect or Written Interview Form CR 8.docx",
        "description": "Official Question & Answer Suspect/Witness Interview clone from the JCF CR 8 template.",
    },
    "CR9": {
        "code": "JCF/FW/PL/C&S/0001/2024/F10",
        "filename": "JCF Question & Answer Accused Written Interview Form CR 9.docx",
        "description": "Official Question & Answer Accused Written Interview clone from the JCF CR 9 template.",
    },
    "CR11": {
        "code": "JCF/FW/PL/C&S/0001/2024/F11",
        "filename": "JCF Confession Statement Form CR 11.docx",
        "description": "Official Confession Statement clone from the JCF CR 11 template.",
    },
    "CR12": {
        "code": "JCF/FW/PL/C&S/0001/2024/F12",
        "filename": "JCF Major and Minor Case Report Form CR 12.docx",
        "description": "Official Major and Minor Case Report clone from the JCF CR 12 template.",
    },
    "CR13": {
        "code": "JCF/FW/PL/C&S/0001/2024/F13",
        "filename": "JCF Court Case File Checklist  CR 13.docx",
        "description": "Official Court Case File Checklist clone from the JCF CR 13 template.",
    },
    "CR14": {
        "code": "JCF/FW/PL/C&S/0001/2024/F14",
        "filename": "JCF Profile Form CR 14.docx",
        "description": "Official JCF Profile Form clone from the JCF CR 14 template.",
    },
    "CR15": {
        "code": "JCF/FW/PL/C&S/0001/2024/F15",
        "filename": "JCF Application for Remand of Accused or Bail Conditions CR 15.docx",
        "description": (
            "Official Application for Remand of Accused or Bail Conditions "
            "clone from the JCF CR 15 template."
        ),
    },
}

OFFICIAL_CR_FORM_DEFINITIONS = OrderedDict(
    (
        form_type,
        {
            "name": form_name,
            "description": _FORM_META[form_type]["description"],
            "source_code": _FORM_META[form_type]["code"],
            "source_filename": _FORM_META[form_type]["filename"],
            "official": True,
            "sections": [],
        },
    )
    for form_type, form_name in OFFICIAL_CR_FORM_TYPES.items()
)

_BASE_DIR = Path(__file__).resolve().parent
OFFICIAL_FORM_DIR = _BASE_DIR / "static" / "forms" / "official"
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_UNDERLINE_RE = re.compile(r"_{3,}")
_CHECKBOX_RE = re.compile(r"\(\s{2,}\)")


def source_filename(form_type: str) -> str:
    """Return the bundled official DOCX filename for a CR form."""
    return _FORM_META[form_type]["filename"]


def source_path(form_type: str) -> Path:
    """Return the bundled official DOCX path for a CR form."""
    return OFFICIAL_FORM_DIR / source_filename(form_type)


def is_official_form(form_type: str) -> bool:
    """Return whether a form type has an official cloned template."""
    return form_type in OFFICIAL_CR_FORM_TYPES


@lru_cache(maxsize=None)
def get_form_layout(form_type: str) -> dict:
    """Parse a source DOCX into a renderable layout."""
    if form_type not in OFFICIAL_CR_FORM_TYPES:
        raise KeyError(f"No official CR template for {form_type}")

    path = source_path(form_type)
    if not path.exists():
        raise FileNotFoundError(path)

    fields: list[dict] = []
    field_counts: dict[str, int] = {}
    elements: list[dict] = []

    with zipfile.ZipFile(path) as docx:
        root = ET.fromstring(docx.read("word/document.xml"))

    body = root.find(f"{_W}body")
    if body is None:
        return _empty_layout(form_type)

    page = _page_layout(body)
    table_index = 0
    paragraph_index = 0
    for child in list(body):
        tag = _local_name(child.tag)
        if tag == "p":
            text = _text(child)
            elements.append({
                "kind": "paragraph",
                "class": _paragraph_class(text, paragraph_index),
                "style": _paragraph_style(child),
                "segments": _paragraph_segments(child, text, fields, field_counts, form_type),
                "empty": not text,
            })
            paragraph_index += 1
        elif tag == "tbl":
            table_index += 1
            elements.append(_table(child, table_index, fields, field_counts, form_type))

    return {
        "form_type": form_type,
        "name": OFFICIAL_CR_FORM_TYPES[form_type],
        "source_code": _FORM_META[form_type]["code"],
        "source_filename": _FORM_META[form_type]["filename"],
        "page": page,
        "elements": elements,
        "fields": fields,
    }


def collect_form_data(form_type: str, form) -> dict:
    """Collect posted values for all generated fields in a form layout."""
    layout = get_form_layout(form_type)
    data = {}
    for field in layout["fields"]:
        name = field["name"]
        if field["type"] == "checkbox":
            if form.get(name):
                data[name] = "Yes"
            continue
        value = form.get(name, "")
        if value:
            data[name] = value
    return data


def prefill_form_data(form_type: str, case, existing: dict | None = None) -> dict:
    """Build case-aware default form data, with existing values taking priority."""
    data = {}
    if case is not None:
        for field in get_form_layout(form_type)["fields"]:
            value = _prefill_value(field, case)
            if value:
                data[field["name"]] = value
    if existing:
        data.update({key: value for key, value in existing.items() if value not in (None, "")})
    return data


def printable_field_rows(form_type: str, form_data: dict) -> list[dict]:
    """Flatten fields for the legacy PDF fallback."""
    rows = []
    for field in get_form_layout(form_type)["fields"]:
        rows.append({
            "label": field["label"],
            "value": form_data.get(field["name"], ""),
        })
    return rows


def _empty_layout(form_type: str) -> dict:
    return {
        "form_type": form_type,
        "name": OFFICIAL_CR_FORM_TYPES[form_type],
        "source_code": _FORM_META[form_type]["code"],
        "source_filename": _FORM_META[form_type]["filename"],
        "page": _default_page_layout(),
        "elements": [],
        "fields": [],
    }


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(node) -> str:
    return _compact(_raw_text(node))


def _raw_text(node) -> str:
    pieces = []
    for item in node.iter():
        tag = _local_name(item.tag)
        if tag == "t" and item.text:
            pieces.append(item.text)
        elif tag == "tab":
            pieces.append("\t")
        elif tag == "br":
            pieces.append("\n")
    return "".join(pieces)


def _compact(value: str) -> str:
    return " ".join(value.split())


def _attr(node, local: str, default: str = "") -> str:
    if node is None:
        return default
    return node.attrib.get(f"{_W}{local}", default)


def _twips_to_inches(value: str | int | None, default: float) -> float:
    try:
        return round(int(value) / 1440, 3)
    except (TypeError, ValueError):
        return default


def _twips_to_points(value: str | int | None, default: float = 0) -> float:
    try:
        return round(int(value) / 20, 2)
    except (TypeError, ValueError):
        return default


def _default_page_layout() -> dict:
    return {
        "width_in": 8.5,
        "height_in": 11,
        "margin_top_in": 0.5,
        "margin_right_in": 0.5,
        "margin_bottom_in": 0.5,
        "margin_left_in": 0.5,
    }


def _page_layout(body) -> dict:
    layout = _default_page_layout()
    sect = body.find(f"{_W}sectPr")
    if sect is None:
        return layout
    pg_size = sect.find(f"{_W}pgSz")
    pg_margin = sect.find(f"{_W}pgMar")
    if pg_size is not None:
        layout["width_in"] = _twips_to_inches(_attr(pg_size, "w"), layout["width_in"])
        layout["height_in"] = _twips_to_inches(_attr(pg_size, "h"), layout["height_in"])
    if pg_margin is not None:
        layout["margin_top_in"] = _twips_to_inches(_attr(pg_margin, "top"), layout["margin_top_in"])
        layout["margin_right_in"] = _twips_to_inches(_attr(pg_margin, "right"), layout["margin_right_in"])
        layout["margin_bottom_in"] = _twips_to_inches(_attr(pg_margin, "bottom"), layout["margin_bottom_in"])
        layout["margin_left_in"] = _twips_to_inches(_attr(pg_margin, "left"), layout["margin_left_in"])
    return layout


def _paragraph_class(text: str, index: int) -> str:
    lower = text.lower()
    if not lower:
        return "jcf-form-spacer"
    if index == 0 or lower.startswith("jcf/fw/"):
        return "jcf-form-code"
    if lower == "jamaica constabulary force":
        return "jcf-force-title"
    cr_suffixes = (
        "cr 1", "cr 2", "cr 3", "cr 4", "cr 5", "cr 6", "cr 7",
        "cr 8", "cr 9", "cr 11", "cr 12", "cr 13", "cr 14", "cr 15",
    )
    if " cr " in f" {lower} " or lower.endswith(cr_suffixes):
        return "jcf-form-title"
    if lower.startswith("nb.") or lower.startswith("restricted"):
        return "jcf-form-note"
    return "jcf-form-paragraph"


def _table(tbl, table_index: int, fields: list[dict], counts: dict[str, int], form_type: str) -> dict:
    rows = []
    column_labels: dict[int, str] = {}
    vertical_merges: dict[int, dict] = {}
    grid = _table_grid(tbl)
    for row_index, row_node in enumerate(tbl.findall(f"{_W}tr"), start=1):
        cells = []
        previous_label = ""
        grid_col = 1
        for col_index, cell_node in enumerate(row_node.findall(f"{_W}tc"), start=1):
            raw = _text(cell_node)
            colspan = _grid_span(cell_node)
            vmerge = _vertical_merge(cell_node)
            if vmerge == "continue":
                anchor = vertical_merges.get(grid_col)
                if anchor:
                    anchor["rowspan"] = anchor.get("rowspan", 1) + 1
                grid_col += colspan
                continue
            for merge_col in range(grid_col, grid_col + colspan):
                if vmerge != "restart":
                    vertical_merges.pop(merge_col, None)
            label = _label_for_cell(
                raw, previous_label, column_labels.get(col_index, ""),
                table_index, row_index, col_index,
            )
            if raw:
                previous_label = raw
                column_labels[col_index] = raw
                blocks = _cell_blocks(cell_node, label, fields, counts, form_type)
                segments = []
            else:
                field = _new_field(label, "text", fields, counts, form_type, render="cell")
                segments = [{"kind": "field", "field": field}]
                blocks = []
            cell = {
                "segments": segments,
                "blocks": blocks,
                "colspan": colspan,
                "rowspan": 1,
                "is_blank": not raw,
                "style": _cell_style(cell_node),
            }
            cells.append(cell)
            if vmerge == "restart":
                for merge_col in range(grid_col, grid_col + colspan):
                    vertical_merges[merge_col] = cell
            grid_col += colspan
        rows.append({"cells": cells, "style": _row_style(row_node)})
    return {"kind": "table", "rows": rows, "index": table_index, "grid": grid}


def _table_grid(tbl) -> list[dict]:
    widths = []
    for grid_col in tbl.findall(f"{_W}tblGrid/{_W}gridCol"):
        try:
            widths.append(int(_attr(grid_col, "w")))
        except ValueError:
            pass
    total = sum(widths)
    if not total:
        return []
    return [{"width_pct": round(width / total * 100, 3)} for width in widths]


def _row_style(row_node) -> str:
    height = row_node.find(f"{_W}trPr/{_W}trHeight")
    points = _twips_to_points(_attr(height, "val"), 0)
    if points:
        return f"height: {points}pt;"
    return ""


def _cell_style(cell_node) -> str:
    styles = []
    valign = cell_node.find(f"{_W}tcPr/{_W}vAlign")
    align_map = {"center": "middle", "bottom": "bottom", "top": "top"}
    if valign is not None:
        styles.append(f"vertical-align: {align_map.get(_attr(valign, 'val'), 'top')};")
    shade = cell_node.find(f"{_W}tcPr/{_W}shd")
    fill = _attr(shade, "fill")
    if fill and fill.lower() not in {"auto", "ffffff"}:
        styles.append(f"background-color: #{fill};")
    return " ".join(styles)


def _paragraph_style(paragraph_node) -> str:
    styles = []
    jc = paragraph_node.find(f"{_W}pPr/{_W}jc")
    align = _attr(jc, "val")
    if align in {"center", "right", "both"}:
        styles.append(f"text-align: {'justify' if align == 'both' else align};")
    spacing = paragraph_node.find(f"{_W}pPr/{_W}spacing")
    before = _twips_to_points(_attr(spacing, "before"), 0)
    after = _twips_to_points(_attr(spacing, "after"), 0)
    if before:
        styles.append(f"margin-top: {before}pt;")
    if after:
        styles.append(f"margin-bottom: {after}pt;")
    return " ".join(styles)


def _run_style(run_node) -> str:
    rpr = run_node.find(f"{_W}rPr")
    if rpr is None:
        return ""
    styles = []
    if rpr.find(f"{_W}b") is not None:
        styles.append("font-weight: 700;")
    if rpr.find(f"{_W}i") is not None:
        styles.append("font-style: italic;")
    underline = rpr.find(f"{_W}u")
    if underline is not None and _attr(underline, "val", "single") != "none":
        styles.append("text-decoration: underline;")
    return " ".join(styles)


def _cell_blocks(cell_node, label: str, fields: list[dict], counts: dict[str, int], form_type: str) -> list[dict]:
    blocks = []
    for index, paragraph in enumerate(cell_node.findall(f"{_W}p")):
        text = _text(paragraph)
        if not text and index > 0:
            blocks.append({
                "class": "jcf-cell-spacer",
                "style": _paragraph_style(paragraph),
                "segments": [{"kind": "text", "text": "\u00a0", "style": ""}],
                "empty": True,
            })
            continue
        blocks.append({
            "class": "jcf-cell-paragraph",
            "style": _paragraph_style(paragraph),
            "segments": _paragraph_segments(paragraph, label, fields, counts, form_type),
            "empty": not text,
        })
    return blocks


def _grid_span(cell_node) -> int:
    grid_span = cell_node.find(f".//{_W}gridSpan")
    if grid_span is None:
        return 1
    try:
        return int(grid_span.attrib.get(f"{_W}val", "1"))
    except ValueError:
        return 1


def _vertical_merge(cell_node) -> str | None:
    merge = cell_node.find(f"{_W}tcPr/{_W}vMerge")
    if merge is None:
        return None
    return _attr(merge, "val") or "continue"


def _paragraph_segments(paragraph_node, label: str, fields: list[dict], counts: dict[str, int], form_type: str) -> list[dict]:
    segments = []
    for run in paragraph_node.findall(f"{_W}r"):
        style = _run_style(run)
        for child in list(run):
            tag = _local_name(child.tag)
            if tag == "t":
                segments.extend(_segments(child.text or "", label, fields, counts, form_type, style=style))
            elif tag == "tab":
                segments.append({"kind": "text", "text": "\t", "style": style})
            elif tag == "br":
                segments.append({"kind": "break"})
    return segments or [{"kind": "text", "text": "\u00a0", "style": ""}]


def _segments(
    text: str,
    label: str,
    fields: list[dict],
    counts: dict[str, int],
    form_type: str,
    style: str = "",
) -> list[dict]:
    segments = []
    pos = 0
    for match in re.finditer(r"_{3,}|\(\s{2,}\)", text):
        if match.start() > pos:
            segments.append({"kind": "text", "text": text[pos:match.start()], "style": style})
        token = match.group(0)
        if _CHECKBOX_RE.fullmatch(token):
            field = _new_field(label, "checkbox", fields, counts, form_type)
        else:
            field = _new_field(label, _field_type(label, token), fields, counts, form_type)
        segments.append({"kind": "field", "field": field})
        pos = match.end()
    if pos < len(text):
        segments.append({"kind": "text", "text": text[pos:], "style": style})
    if not segments:
        segments.append({"kind": "text", "text": text, "style": style})
    return segments


def _new_field(
    label: str,
    field_type: str,
    fields: list[dict],
    counts: dict[str, int],
    form_type: str,
    render: str = "inline",
) -> dict:
    base = _slug(label) or "field"
    base = f"{form_type.lower()}_{base}"
    sequence = counts.get(base, 0) + 1
    counts[base] = sequence
    name = f"{base}_{sequence}" if sequence > 1 else base
    field = {
        "name": name,
        "label": _clean_label(label),
        "label_slug": _slug(label),
        "type": field_type,
        "render": render,
    }
    fields.append(field)
    return field


def _label_for_cell(
    raw: str,
    previous_label: str,
    column_label: str,
    table_index: int,
    row_index: int,
    col_index: int,
) -> str:
    if raw:
        before_underline = _UNDERLINE_RE.split(raw, maxsplit=1)[0].strip(" :#.-")
        if before_underline:
            return before_underline
        return raw
    if previous_label:
        return previous_label
    if column_label:
        return column_label
    return f"Table {table_index} row {row_index} column {col_index}"


def _field_type(label: str, token: str) -> str:
    lower = label.lower()
    long_text_words = (
        "statement", "details", "particular", "summary", "remarks",
        "description", "address", "reason", "grounds", "evidence",
    )
    if any(word in lower for word in long_text_words):
        return "textarea"
    if len(token) > 60:
        return "textarea"
    return "text"


def _slug(value: str) -> str:
    value = value.lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:60]


def _clean_label(label: str) -> str:
    label = _UNDERLINE_RE.sub("", label)
    label = _CHECKBOX_RE.sub("", label)
    return " ".join(label.replace(":", " ").split()).strip() or "Field"


def _case_get(case, key: str, default: str = ""):
    try:
        return case[key] or default
    except (KeyError, TypeError, IndexError):
        return getattr(case, key, default) or default


def _prefill_value(field: dict, case) -> str:
    haystack = f"{field['name']} {field['label']} {field['label_slug']}".lower()
    case_id = _case_get(case, "case_id")
    suspect = _case_get(case, "suspect_name")
    suspect_address = _case_get(case, "suspect_address")
    suspect_dob = _case_get(case, "suspect_dob")
    victim = _case_get(case, "victim_name")
    victim_address = _case_get(case, "victim_address")
    offence = _case_get(case, "law_and_section") or _case_get(case, "offence_description")
    investigator = " ".join(part for part in [
        _case_get(case, "oic_rank"),
        _case_get(case, "oic_name"),
        _case_get(case, "oic_badge"),
    ] if part)

    if any(term in haystack for term in ("case_ref", "case_reference", "case ref", "crime_ref")):
        return case_id
    if "division" in haystack:
        return _case_get(case, "division")
    if "station" in haystack and "statement" not in haystack:
        return _case_get(case, "station_code") or "FNID Area 3"
    if "crime_category" in haystack or "classification" in haystack:
        return _case_get(case, "classification")
    if "parish" in haystack:
        return _case_get(case, "parish")
    if "offence" in haystack or "charge" in haystack:
        return offence
    if "date_of_offence" in haystack or "date committed" in haystack:
        return _case_get(case, "registration_date")
    if "date reported" in haystack or haystack.endswith(" date"):
        return _case_get(case, "registration_date")
    if "suspect" in haystack or "accused" in haystack:
        if "address" in haystack:
            return suspect_address
        if "birth" in haystack or "dob" in haystack:
            return suspect_dob
        return suspect
    if "victim" in haystack or "complainant" in haystack:
        if "address" in haystack:
            return victim_address
        return victim
    if "investigator" in haystack or "oic" in haystack or "officer" in haystack:
        return investigator or _case_get(case, "created_by")
    return ""
