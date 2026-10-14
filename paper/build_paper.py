"""Assemble the section drafts in paper/sections into one IEEE Access style
Word file. Run from the repository root:

    python3 paper/build_paper.py

Reads 00-front.json, every NN-*.md that is not a claims file, and every
NN-refs.json. Writes paper/EV-PIL-mock-paper-IEEE-Access.docx.
"""
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "paper"
SEC = PAPER / "sections"
EQ_DIR = PAPER / "figures" / "_eq"
OUT = PAPER / "EV-PIL-mock-paper-IEEE-Access.docx"

SERIF = "Times New Roman"
SANS = "Arial"
BLUE = RGBColor(0x00, 0x62, 0x9B)
COL_W = 3.5
PAGE_W = 7.16
GAP = 0.16

GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "eta": "η", "theta": "θ", "lambda": "λ", "mu": "μ", "rho": "ρ",
    "sigma": "σ", "tau": "τ", "phi": "φ", "omega": "ω", "Delta": "Δ",
    "Sigma": "Σ", "Omega": "Ω", "kappa": "κ", "nu": "ν", "xi": "ξ",
    "zeta": "ζ", "psi": "ψ", "pi": "π",
}
ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
         "XI", "XII", "XIII", "XIV"]


# ---------------------------------------------------------------- parsing

def load_blocks():
    """Return a list of blocks from all section files, in file order."""
    blocks = []
    files = sorted(p for p in SEC.glob("[0-9][0-9]-*.md")
                   if not p.name.endswith("-claims.md"))
    for path in files:
        lines = path.read_text().splitlines()
        i = 0
        para = []

        def flush():
            if para:
                blocks.append({"t": "p", "text": " ".join(s.strip() for s in para)})
                para.clear()

        while i < len(lines):
            ln = lines[i].rstrip()
            s = ln.strip()
            if not s:
                flush()
            elif s.startswith("#"):
                flush()
                m = re.match(r"^(#+)\s+(.*?)\s*(\{#(sec:[\w-]+)\})?\s*$", s)
                blocks.append({"t": "h", "level": len(m.group(1)),
                               "text": m.group(2).strip(), "id": m.group(4)})
            elif s.startswith("$$"):
                flush()
                m = re.match(r"^\$\$(.*)\$\$\s*(\{#(eq:[\w-]+)\})?\s*$", s)
                if not m:
                    raise SystemExit(f"{path.name}:{i+1}: bad equation line")
                blocks.append({"t": "eq", "tex": m.group(1).strip(), "id": m.group(3)})
            elif s.startswith("!["):
                flush()
                m = re.match(r"^!\[(fig:[\w-]+)\]\(([^)]+)\)\s*(\{width=(\w+)\})?", s)
                if not m:
                    raise SystemExit(f"{path.name}:{i+1}: bad figure line")
                cap = ""
                if i + 1 < len(lines) and lines[i + 1].strip().startswith("Caption:"):
                    cap = lines[i + 1].strip()[len("Caption:"):].strip()
                    i += 1
                blocks.append({"t": "fig", "id": m.group(1), "path": m.group(2),
                               "width": m.group(4) or "col", "cap": cap})
            elif s.startswith("Table:"):
                flush()
                parts = [x.strip() for x in s[len("Table:"):].split("|")]
                tid, cap = parts[0], parts[1]
                width = "col"
                for x in parts[2:]:
                    if x.startswith("width="):
                        width = x.split("=")[1]
                rows = []
                i += 1
                while i < len(lines) and lines[i].strip().startswith("|"):
                    r = lines[i].strip()
                    if not re.match(r"^\|[\s:|-]+\|$", r):
                        rows.append([c.strip() for c in r.strip("|").split("|")])
                    i += 1
                i -= 1
                blocks.append({"t": "tab", "id": tid, "cap": cap,
                               "width": width, "rows": rows})
            elif re.match(r"^[-*]\s+", s):
                flush()
                blocks.append({"t": "li", "text": re.sub(r"^[-*]\s+", "", s)})
            else:
                para.append(s)
            i += 1
        flush()
    return blocks


def load_refs():
    refs = {}
    for path in sorted(SEC.glob("[0-9][0-9]-refs.json")):
        for r in json.loads(path.read_text()):
            refs.setdefault(r["key"], r)
    return refs


# -------------------------------------------------------------- numbering

class Numbers:
    def __init__(self, blocks):
        self.fig, self.tab, self.eq, self.sec = {}, {}, {}, {}
        self.cites = []
        nsec = nsub = 0
        for b in blocks:
            if b["t"] == "fig":
                self.fig[b["id"]] = len(self.fig) + 1
            elif b["t"] == "tab":
                self.tab[b["id"]] = len(self.tab) + 1
            elif b["t"] == "eq" and b["id"]:
                self.eq[b["id"]] = len(self.eq) + 1
            elif b["t"] == "h" and b["level"] == 1:
                nsec += 1
                nsub = 0
                if b["id"]:
                    self.sec[b["id"]] = ROMAN[nsec]
            elif b["t"] == "h" and b["level"] == 2:
                nsub += 1
                if b["id"]:
                    self.sec[b["id"]] = f"{ROMAN[nsec]}-{chr(64 + nsub)}"
        for b in blocks:
            texts = [b.get("text", ""), b.get("cap", "")]
            for row in b.get("rows", []):
                texts.extend(row)
            for t in texts:
                for grp in re.findall(r"\[(@[^\]]+)\]", t):
                    for k in re.findall(r"@([\w-]+)", grp):
                        if k not in self.cites:
                            self.cites.append(k)
        self.missing = set()

    def cite(self, keys):
        nums = sorted(self.cites.index(k) + 1 for k in keys)
        out, i = [], 0
        while i < len(nums):
            j = i
            while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
                j += 1
            if j - i >= 2:
                out.append(f"[{nums[i]}]\u2013[{nums[j]}]")
            else:
                out.extend(f"[{n}]" for n in nums[i:j + 1])
            i = j + 1
        return ", ".join(out)

    def resolve(self, text):
        def ref(kind, table, fmt):
            def f(m):
                key = m.group(1)
                if key not in table:
                    self.missing.add(key)
                    return "??"
                return fmt(table[key])
            return f
        text = re.sub(r"\[(@[^\]]+)\]",
                      lambda m: self.cite(re.findall(r"@([\w-]+)", m.group(1))), text)
        text = re.sub(r"@(fig:[\w-]+)", ref("fig", self.fig, str), text)
        text = re.sub(r"@(tab:[\w-]+)", ref("tab", self.tab, str), text)
        text = re.sub(r"@(eq:[\w-]+)", ref("eq", self.eq, str), text)
        text = re.sub(r"@(sec:[\w-]+)", ref("sec", self.sec, str), text)
        return text


# ----------------------------------------------------------------- maths

def tex_clean(tex):
    tex = re.sub(r"\\text\{([^}]*)\}", lambda m: r"\mathrm{" + m.group(1).replace(" ", r"\ ") + "}", tex)
    tex = tex.replace(r"\left", "").replace(r"\right", "")
    tex = tex.replace(r"\dfrac", r"\frac").replace(r"\tfrac", r"\frac")
    tex = tex.replace(r"\,", r"\ ").replace(r"\;", r"\ ").replace(r"\!", "")
    tex = tex.replace(r"\lvert", "|").replace(r"\rvert", "|")
    tex = tex.replace(r"\top", r"\mathrm{T}")
    return tex


def eq_image(tex, fontsize=10):
    EQ_DIR.mkdir(parents=True, exist_ok=True)
    tex = tex_clean(tex)
    name = hashlib.md5(f"{tex}{fontsize}".encode()).hexdigest()[:12] + ".png"
    out = EQ_DIR / name
    with plt.rc_context({"mathtext.fontset": "stix", "font.family": "serif"}):
        fig = plt.figure(figsize=(0.1, 0.1))
        fig.text(0, 0, f"${tex}$", fontsize=fontsize)
        fig.savefig(out, dpi=600, bbox_inches="tight", pad_inches=0.01,
                    transparent=True)
        plt.close(fig)
    from PIL import Image
    with Image.open(out) as im:
        w, h = im.size
    return out, w / 600.0, h / 600.0


SIMPLE = re.compile(
    r"^\s*(\\?[A-Za-z]+|\\(?:hat|dot|bar)\{\\?[A-Za-z]+\})"
    r"(?:_\{?([^{}$^]+)\}?)?(?:\^\{?([^{}$_]+)\}?)?\s*$")


def add_math(par, tex, size):
    """Inline maths: a simple symbol becomes italic text, else an image."""
    if "=" in tex and "\\" not in tex.replace("\\Delta", "").replace("\\tau", "").replace("\\alpha", "").replace("\\sigma", ""):
        sides = tex.split("=")
        if all(SIMPLE.match(x) or re.fullmatch(r"\s*[-+]?[\d.,]+\s*", x) for x in sides):
            for k, x in enumerate(sides):
                if k:
                    r = par.add_run(" = ")
                    r.font.size = Pt(size)
                if SIMPLE.match(x) and not re.fullmatch(r"\s*[-+]?[\d.,]+\s*", x):
                    add_math(par, x, size)
                else:
                    r = par.add_run(x.strip())
                    r.font.size = Pt(size)
            return
    m = SIMPLE.match(tex)
    if m and not m.group(1).startswith(("\\hat", "\\dot", "\\bar")):
        base = m.group(1)
        if base.startswith("\\"):
            if base[1:] not in GREEK:
                m = None
            else:
                base = GREEK[base[1:]]
        if m:
            r = par.add_run(base)
            r.italic = True
            r.font.size = Pt(size)
            for txt, attr in ((m.group(2), "subscript"), (m.group(3), "superscript")):
                if txt:
                    txt = re.sub(r"\\(?:text|mathrm)\{([^}]*)\}", r"\1", txt)
                    txt = re.sub(r"\\([A-Za-z]+)", lambda g: GREEK.get(g.group(1), g.group(1)), txt)
                    rr = par.add_run(txt)
                    rr.font.size = Pt(size)
                    setattr(rr.font, attr, True)
                    rr.italic = not re.fullmatch(r"[\d.,+\- ]+|[a-z]{2,}", txt)
            return
    path, w, h = eq_image(tex, fontsize=size)
    par.add_run().add_picture(str(path), width=Inches(w))


def add_inline(par, text, num, size=10, font=SERIF, bold=False, color=None):
    text = num.resolve(text)
    text = text.replace("**", "")
    text = text.replace("SIMULATED", "simulated").replace("MEASURED", "measured")
    text = text.replace(" +- ", " \u00b1 ")
    text = re.sub(r"(?<![\w)\]$])-(?=\d)", "\u2212", text)
    for i, chunk in enumerate(re.split(r"\$([^$]+)\$", text)):
        if i % 2:
            add_math(par, chunk, size)
            continue
        for j, piece in enumerate(re.split(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", chunk)):
            if not piece:
                continue
            r = par.add_run(piece)
            r.font.name = font
            r._element.rPr.rFonts.set(qn("w:eastAsia"), font)
            r.font.size = Pt(size)
            r.bold = bold
            r.italic = bool(j % 2)
            if color is not None:
                r.font.color.rgb = color


# ------------------------------------------------------------ docx helpers

def fmt(par, before=0, after=0, align=None, indent=None, line=None, keep=False):
    pf = par.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    if align is not None:
        pf.alignment = align
    if indent is not None:
        pf.first_line_indent = Inches(indent)
    if line is not None:
        pf.line_spacing = line
    if keep:
        pf.keep_with_next = True
    return par


def run(par, text, font=SERIF, size=10, bold=False, italic=False, color=None,
        sup=False):
    r = par.add_run(text)
    r.font.name = font
    r._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    r.font.size = Pt(size)
    r.bold = bold
    r.italic = italic
    r.font.superscript = sup
    if color is not None:
        r.font.color.rgb = color
    return r


def set_cols(section, n):
    sp = section._sectPr
    for c in sp.findall(qn("w:cols")):
        sp.remove(c)
    cols = OxmlElement("w:cols")
    cols.set(qn("w:num"), str(n))
    cols.set(qn("w:space"), str(int(GAP * 1440)))
    sp.append(cols)


class Flow:
    """Tracks the column mode so page-wide floats get their own section."""

    def __init__(self, doc):
        self.doc = doc
        self.mode = 1

    def cols(self, n):
        if self.mode != n:
            sec = self.doc.add_section(WD_SECTION.CONTINUOUS)
            set_cols(sec, n)
            self.mode = n


def cell_border(cell, **edges):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = tcPr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tcPr.append(borders)
    for edge, sz in edges.items():
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000")
        borders.append(el)


def frame(par, top=True):
    """Put a paragraph in a page-wide frame at the top or bottom margin."""
    pPr = par._p.get_or_add_pPr()
    fp = OxmlElement("w:framePr")
    fp.set(qn("w:w"), str(int(PAGE_W * 1440)))
    fp.set(qn("w:hSpace"), "0")
    fp.set(qn("w:vSpace"), "140")
    fp.set(qn("w:wrap"), "notBeside")
    fp.set(qn("w:vAnchor"), "margin")
    fp.set(qn("w:hAnchor"), "margin")
    fp.set(qn("w:xAlign"), "center")
    fp.set(qn("w:yAlign"), "top" if top else "bottom")
    pPr.insert(0, fp)


def float_table(tbl, top=False):
    tblPr = tbl._tbl.tblPr
    pp = OxmlElement("w:tblpPr")
    pp.set(qn("w:leftFromText"), "0")
    pp.set(qn("w:rightFromText"), "0")
    pp.set(qn("w:topFromText"), "140")
    pp.set(qn("w:bottomFromText"), "140")
    pp.set(qn("w:vertAnchor"), "margin")
    pp.set(qn("w:horzAnchor"), "margin")
    pp.set(qn("w:tblpXSpec"), "center")
    pp.set(qn("w:tblpYSpec"), "top" if top else "bottom")
    tblPr.insert(0, pp)
    ov = OxmlElement("w:tblOverlap")
    ov.set(qn("w:val"), "never")
    tblPr.insert(1, ov)


def page_number_field(par):
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        r = par.add_run()
        r.font.name = SANS
        r.font.size = Pt(7)
        if kind:
            fc = OxmlElement("w:fldChar")
            fc.set(qn("w:fldCharType"), kind)
            r._r.append(fc)
        else:
            it = OxmlElement("w:instrText")
            it.set(qn("xml:space"), "preserve")
            it.text = text
            r._r.append(it)


# ------------------------------------------------------------- rendering

def ref_text(r):
    a = r.get("authors", [])
    if isinstance(a, str):
        a = [a]
    if len(a) > 6:
        auth = a[0] + " et al."
    elif len(a) > 2:
        auth = ", ".join(a[:-1]) + ", and " + a[-1]
    else:
        auth = " and ".join(a)
    parts = [("" if not auth else auth + ", "), ("\u201c" + r["title"].rstrip(".") + ",\u201d ", False)]
    tail = []
    for label, key in (("vol. ", "volume"), ("no. ", "number"), ("pp. ", "pages")):
        if r.get(key):
            tail.append(label + str(r[key]).replace("--", "\u2013").replace("-", "\u2013"))
    date = " ".join(x for x in (r.get("month", ""), str(r.get("year", ""))) if x)
    if date:
        tail.append(date)
    if r.get("doi"):
        tail.append("doi: " + r["doi"])
    return parts[0], parts[1][0], r.get("venue", ""), (", " + ", ".join(tail) if tail else "") + "."


def build():
    front = json.loads((SEC / "00-front.json").read_text())
    blocks = load_blocks()
    refs = load_refs()
    num = Numbers(blocks)

    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = SERIF
    st.element.rPr.rFonts.set(qn("w:eastAsia"), SERIF)
    st.font.size = Pt(10)

    s0 = doc.sections[0]
    s0.page_width, s0.page_height = Inches(8.5), Inches(11)
    s0.left_margin = s0.right_margin = Inches((8.5 - PAGE_W) / 2)
    s0.top_margin, s0.bottom_margin = Inches(0.85), Inches(0.9)
    s0.header_distance, s0.footer_distance = Inches(0.45), Inches(0.45)
    set_cols(s0, 1)

    hp = s0.header.paragraphs[0]
    fmt(hp, align=WD_ALIGN_PARAGRAPH.LEFT)
    run(hp, front["running_head"], font=SANS, size=7)
    fp = s0.footer.paragraphs[0]
    fp.paragraph_format.tab_stops.add_tab_stop(Inches(PAGE_W), WD_TAB_ALIGNMENT.RIGHT)
    run(fp, "VOLUME XX, 2026\t", font=SANS, size=7)
    page_number_field(fp)

    # ---- title block
    p = fmt(doc.add_paragraph(), after=2)
    run(p, front["dates"], font=SANS, size=7)
    p = fmt(doc.add_paragraph(), after=10)
    run(p, "Digital Object Identifier 10.1109/ACCESS.2026.XXXXXXX", font=SANS,
        size=7, italic=True)
    p = fmt(doc.add_paragraph(), after=10, line=1.0)
    run(p, front["title"], font=SANS, size=22, bold=True)
    p = fmt(doc.add_paragraph(), after=4)
    for i, a in enumerate(front["authors"]):
        if i:
            n = len(front["authors"])
            sep = " AND " if n == 2 else (", AND " if i == n - 1 else ", ")
            run(p, sep, font=SANS, size=10.5, bold=True)
        run(p, a["name"].upper(), font=SANS, size=10.5, bold=True)
        run(p, a["mark"], font=SANS, size=10.5, bold=True, sup=True)
        if a.get("membership"):
            run(p, ", " + a["membership"], font=SANS, size=8)
    for line in front["affiliations"]:
        p = fmt(doc.add_paragraph(), after=0)
        run(p, line, font=SANS, size=7.5)
    for line in front["notes"]:
        p = fmt(doc.add_paragraph(), before=5, after=0)
        run(p, line, font=SANS, size=7.5)

    p = fmt(doc.add_paragraph(), before=14, after=6,
            align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    run(p, "ABSTRACT  ", font=SANS, size=9, bold=True, color=BLUE)
    add_inline(p, front["abstract"], num, size=9, font=SANS)
    p = fmt(doc.add_paragraph(), after=12, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    run(p, "INDEX TERMS  ", font=SANS, size=9, bold=True, color=BLUE)
    run(p, front["index_terms"], font=SANS, size=9)

    flow = Flow(doc)
    flow.cols(2)

    counters = {"h1": 0, "h2": 0, "h3": 0}

    def caption(label, n, text, above=False, par=None):
        p = par if par is not None else doc.add_paragraph()
        fmt(p, before=3 if not above else 6, after=8 if not above else 3,
            align=WD_ALIGN_PARAGRAPH.LEFT, keep=above)
        p.paragraph_format.keep_together = True
        run(p, f"{label} {n}.  ", font=SANS, size=8, bold=True)
        add_inline(p, text, num, size=8, font=SANS)
        return p

    first_para = True
    for b in blocks:
        t = b["t"]
        if t == "h":
            flow.cols(2)
            if b["level"] == 1:
                counters["h1"] += 1
                counters["h2"] = counters["h3"] = 0
                p = fmt(doc.add_paragraph(), before=10, after=4, keep=True)
                run(p, f"{ROMAN[counters['h1']]}. {b['text'].upper()}",
                    font=SANS, size=10, bold=True, color=BLUE)
            elif b["level"] == 2:
                counters["h2"] += 1
                counters["h3"] = 0
                p = fmt(doc.add_paragraph(), before=7, after=2, keep=True)
                run(p, f"{chr(64 + counters['h2'])}. {b['text'].upper()}",
                    font=SANS, size=9, italic=True)
            else:
                counters["h3"] += 1
                p = fmt(doc.add_paragraph(), before=5, after=1, keep=True)
                run(p, f"{counters['h3']}) {b['text'].upper()}", font=SANS,
                    size=8.5, italic=True)
            first_para = True
        elif t == "p":
            flow.cols(2)
            p = fmt(doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.JUSTIFY,
                    indent=0 if first_para else 0.14)
            add_inline(p, b["text"], num)
            first_para = False
        elif t == "li":
            flow.cols(2)
            p = fmt(doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.JUSTIFY, after=1)
            p.paragraph_format.left_indent = Inches(0.22)
            p.paragraph_format.first_line_indent = Inches(-0.14)
            run(p, "\u2022  ")
            add_inline(p, b["text"], num)
        elif t == "eq":
            flow.cols(2)
            path, w, h = eq_image(b["tex"])
            if w > COL_W - 0.45:
                w = COL_W - 0.45
            p = fmt(doc.add_paragraph(), before=4, after=4)
            ts = p.paragraph_format.tab_stops
            ts.add_tab_stop(Inches((COL_W - 0.3) / 2), WD_TAB_ALIGNMENT.CENTER)
            ts.add_tab_stop(Inches(COL_W), WD_TAB_ALIGNMENT.RIGHT)
            p.add_run("\t")
            p.add_run().add_picture(str(path), width=Inches(w))
            if b["id"]:
                run(p, f"\t({num.eq[b['id']]})")
            first_para = True
        elif t == "fig":
            wide = b["width"] == "page"
            flow.cols(2)
            img = ROOT / b["path"]
            p = fmt(doc.add_paragraph(), before=0 if wide else 6,
                    align=WD_ALIGN_PARAGRAPH.CENTER, keep=True)
            if img.exists():
                p.add_run().add_picture(str(img), width=Inches(PAGE_W if wide else COL_W))
            else:
                run(p, f"[missing figure: {b['path']}]", color=RGBColor(200, 0, 0))
                num.missing.add(b["path"])
            cp = caption("FIGURE", num.fig[b["id"]], b["cap"])
            if wide:
                frame(p, top=True)
                frame(cp, top=True)
        elif t == "tab":
            wide = b["width"] == "page"
            flow.cols(2)
            rows = b["rows"]
            ncol = max(len(r) for r in rows)
            off = 1 if wide else 0
            if not wide:
                caption("TABLE", num.tab[b["id"]], b["cap"], above=True)
            tbl = doc.add_table(rows=len(rows) + off, cols=ncol)
            tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
            tbl.autofit = True
            tblPr = tbl._tbl.tblPr
            for old_w in tblPr.findall(qn("w:tblW")):
                tblPr.remove(old_w)
            tw = OxmlElement("w:tblW")
            if wide:
                tw.set(qn("w:w"), str(int(PAGE_W * 1440)))
                tw.set(qn("w:type"), "dxa")
            else:
                tw.set(qn("w:w"), "5000")
                tw.set(qn("w:type"), "pct")
            tblPr.append(tw)
            if wide:
                cap_cell = tbl.cell(0, 0).merge(tbl.cell(0, ncol - 1))
                caption("TABLE", num.tab[b["id"]], b["cap"], above=True,
                        par=cap_cell.paragraphs[0])
                float_table(tbl, top=len(rows) > 10)
            for i, row in enumerate(rows):
                for j in range(ncol):
                    cell = tbl.cell(i + off, j)
                    cp = cell.paragraphs[0]
                    fmt(cp, before=1, after=1, align=WD_ALIGN_PARAGRAPH.LEFT,
                        keep=(i < len(rows) - 1))
                    add_inline(cp, row[j] if j < len(row) else "", num,
                               size=7.5, font=SANS, bold=(i == 0))
                    edges = {}
                    if i == 0:
                        edges.update(top=8, bottom=4)
                    if i == len(rows) - 1:
                        edges["bottom"] = 8
                    if edges:
                        cell_border(cell, **edges)
            fmt(doc.add_paragraph(), after=4)
            first_para = True

    # ---- back matter
    flow.cols(2)
    for title, text in front.get("back", []):
        p = fmt(doc.add_paragraph(), before=10, after=4, keep=True)
        run(p, title.upper(), font=SANS, size=10, bold=True, color=BLUE)
        p = fmt(doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.JUSTIFY)
        add_inline(p, text, num)

    p = fmt(doc.add_paragraph(), before=10, after=4, keep=True)
    run(p, "REFERENCES", font=SANS, size=10, bold=True, color=BLUE)
    for i, key in enumerate(num.cites, 1):
        p = fmt(doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.JUSTIFY, after=1)
        p.paragraph_format.left_indent = Inches(0.28)
        p.paragraph_format.first_line_indent = Inches(-0.28)
        run(p, f"[{i}]\t", size=8)
        p.paragraph_format.tab_stops.add_tab_stop(Inches(0.28))
        if key not in refs:
            run(p, f"MISSING REFERENCE: {key}", size=8, color=RGBColor(200, 0, 0))
            num.missing.add("ref:" + key)
            continue
        auth, title, venue, tail = ref_text(refs[key])
        run(p, auth + title, size=8)
        run(p, venue, size=8, italic=True)
        run(p, tail, size=8)

    for name, bio in front.get("bios", []):
        p = fmt(doc.add_paragraph(), before=10, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
        run(p, name.upper() + " ", font=SANS, size=8, bold=True)
        run(p, bio, size=8)

    doc.save(OUT)
    words = sum(len(b.get("text", "").split()) for b in blocks if b["t"] in ("p", "li"))
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"body words {words}, figures {len(num.fig)}, tables {len(num.tab)}, "
          f"equations {len(num.eq)}, references cited {len(num.cites)}")
    unused = sorted(set(refs) - set(num.cites))
    if unused:
        print("reference entries never cited:", ", ".join(unused))
    if num.missing:
        print("UNRESOLVED:", ", ".join(sorted(num.missing)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(build())
