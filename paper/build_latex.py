"""Assemble the section drafts in paper/sections into the official IEEE Access
LaTeX template (ACCESS_latex_template_20260513). Run from the repository root:

    python3 paper/build_latex.py

Reads the same inputs as build_paper.py (00-front.json, every NN-*.md that is
not a claims file, every NN-refs.json) and writes
paper/ieee-access-tex/access.tex plus a copy of every figure it uses. The
template's class, style, font and logo files live in paper/ieee-access-tex/
and are not touched. Compile there with:  pdflatex access && pdflatex access
"""
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "paper"
SEC = PAPER / "sections"
OUT_DIR = PAPER / "ieee-access-tex"
OUT = OUT_DIR / "access.tex"

UNICODE = {
    "µ": r"\textmu{}", "°": r"\textdegree{}", "²": r"\textsuperscript{2}",
    "±": r"$\pm$", "é": r"\'{e}", "–": "--", "—": "---", "’": "'",
    "×": r"$\times$", "≤": r"$\le$", "≥": r"$\ge$", "→": r"$\to$",
}


# ------------------------------------------------------------------ parsing
# Same grammar as build_paper.load_blocks (see paper/BRIEF.md section 7).

def load_blocks():
    blocks = []
    files = sorted(p for p in SEC.glob("[0-9][0-9]-*.md")
                   if not p.name.endswith("-claims.md"))
    for path in files:
        lines = path.read_text().splitlines()
        i, para = 0, []

        def flush():
            if para:
                blocks.append({"t": "p", "text": " ".join(s.strip() for s in para)})
                para.clear()

        while i < len(lines):
            s = lines[i].strip()
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
                cap = ""
                if i + 1 < len(lines) and lines[i + 1].strip().startswith("Caption:"):
                    cap = lines[i + 1].strip()[len("Caption:"):].strip()
                    i += 1
                blocks.append({"t": "fig", "id": m.group(1), "path": m.group(2),
                               "width": m.group(4) or "col", "cap": cap})
            elif s.startswith("Table:"):
                flush()
                parts = [x.strip() for x in s[len("Table:"):].split("|")]
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
                blocks.append({"t": "tab", "id": parts[0], "cap": parts[1],
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


# ------------------------------------------------------------- inline text

def esc_plain(t):
    t = t.replace("\\", r"\textbackslash{}")
    for a, b in (("&", r"\&"), ("%", r"\%"), ("#", r"\#"), ("_", r"\_"),
                 ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}"),
                 ("<", r"\textless{}"), (">", r"\textgreater{}")):
        t = t.replace(a, b)
    t = re.sub(r'"([^"]*)"', r"``\1''", t)
    for a, b in UNICODE.items():
        t = t.replace(a, b)
    return t


def inline(text):
    """Markdown-ish paragraph text to LaTeX: maths kept, the rest escaped,
    citations and cross-references turned into \\cite and \\ref."""
    out = []
    # split on inline maths
    for k, piece in enumerate(re.split(r"(\$[^$]+\$)", text)):
        if k % 2:
            out.append(piece.replace("µ", r"\mu "))
            continue
        cites = []

        def keep_cite(m):
            cites.append(",".join(re.findall(r"@([\w-]+)", m.group(1))))
            return f"\x00C{len(cites)-1}\x00"
        piece = re.sub(r"\[(@[^\]]+)\]", keep_cite, piece)
        refs = []

        def keep_ref(m):
            refs.append(m.group(1))
            return f"\x00R{len(refs)-1}\x00"
        piece = re.sub(r"\(@(eq:[\w-]+)\)", lambda m: f"\x00E{m.group(1)}\x00", piece)
        piece = re.sub(r"@((?:fig|tab|eq|sec):[\w-]+)", keep_ref, piece)
        urls = []

        def keep_url(m):
            urls.append(m.group(1))
            return f"\x00U{len(urls)-1}\x00" + m.group(2)
        piece = re.sub(r"(https?://\S+?)([.,;)]?(?:\s|$))", keep_url, piece)
        piece = re.sub(r"\*\*([^*]+)\*\*", "\x00B\\1\x00b", piece)
        piece = esc_plain(piece)
        piece = re.sub("\x00B(.*?)\x00b", r"\\textbf{\1}", piece)
        piece = re.sub("\x00C(\\d+)\x00", lambda m: r"~\cite{" + cites[int(m.group(1))] + "}", piece)
        piece = re.sub("\x00E(eq:[\\w-]+)\x00", lambda m: r"\eqref{" + m.group(1).replace(r"\_", "_") + "}", piece)
        piece = re.sub("\x00U(\\d+)\x00", lambda m: r"\url{" + urls[int(m.group(1))] + "}", piece)
        piece = re.sub("\x00R(\\d+)\x00", lambda m: r"\ref{" + refs[int(m.group(1))] + "}", piece)
        # tie Fig./Table/Section to their number
        piece = re.sub(r"(Fig\.|Figs\.|Table|Tables|Section|Sections) \\ref",
                       r"\1~\\ref", piece)
        piece = piece.replace(" ~\\cite", "~\\cite")
        out.append(piece)
    return "".join(out)


def heading(text, level):
    t = inline(text)
    if level == 1:
        return t.upper()
    return t


# ------------------------------------------------------------------ blocks

def table(b):
    rows = b["rows"]
    ncol = len(rows[0])
    star = "*" if b["width"] == "page" else ""
    width = r"\textwidth" if star else r"\columnwidth"
    spec = "@{}" + "X" * ncol + "@{}"
    lines = [rf"\begin{{table{star}}}[!t]",
             r"\centering",
             rf"\caption{{{inline(b['cap'])}}}",
             rf"\label{{{b['id']}}}",
             r"\footnotesize",
             r"\setlength{\tabcolsep}{3pt}",
             r"\renewcommand{\arraystretch}{1.15}",
             rf"\begin{{tabularx}}{{{width}}}{{{spec}}}",
             r"\hline"]
    for k, r in enumerate(rows):
        r = r + [""] * (ncol - len(r))
        cells = [inline(c) for c in r]
        if k == 0:
            cells = [rf"\textbf{{{c}}}" for c in cells]
        lines.append(" & ".join(cells) + r" \\")
        if k == 0:
            lines.append(r"\hline")
    lines += [r"\hline", r"\end{tabularx}", rf"\end{{table{star}}}", ""]
    return "\n".join(lines)


def figure(b, used):
    src = ROOT / b["path"]
    name = src.name
    used.append(src)
    star = "*" if b["width"] == "page" else ""
    width = r"\textwidth" if star else r"\columnwidth"
    return "\n".join([rf"\begin{{figure{star}}}[!t]",
                      r"\centering",
                      rf"\includegraphics[width={width}]{{figures/{name}}}",
                      rf"\caption{{{inline(b['cap'])}}}",
                      rf"\label{{{b['id']}}}",
                      rf"\end{{figure{star}}}", ""])


def body(blocks, used):
    out, in_list, first_par = [], False, True
    for b in blocks:
        if b["t"] != "li" and in_list:
            out.append(r"\end{itemize}" + "\n")
            in_list = False
        t = b["t"]
        if t == "h":
            cmd = {1: "section", 2: "subsection", 3: "subsubsection"}[b["level"]]
            out.append(rf"\{cmd}{{{heading(b['text'], b['level'])}}}")
            if b["id"]:
                out.append(rf"\label{{{b['id']}}}")
            out.append("")
        elif t == "p":
            txt = inline(b["text"])
            if first_par:
                m = re.match(r"^(\w)(\w*)(.*)$", txt, re.S)
                txt = rf"\PARstart{{{m.group(1)}}}{{{m.group(2)}}}{m.group(3)}"
                first_par = False
            out.append(txt + "\n")
        elif t == "li":
            if not in_list:
                out.append(r"\begin{itemize}")
                in_list = True
            out.append(r"\item " + inline(b["text"]))
        elif t == "eq":
            out.append(r"\begin{equation}")
            if b["id"]:
                out.append(rf"\label{{{b['id']}}}")
            tex = b["tex"]
            # long one-line equations are split at \qquad into aligned rows
            if len(tex) > 90 and r"\qquad" in tex:
                parts = [p.strip().rstrip(",") for p in tex.split(r"\qquad")]
                tex = r"\begin{gathered}" + r" \\ ".join(parts) + r"\end{gathered}"
            elif len(tex) > 90 and r"\quad" in tex:
                parts = [p.strip().rstrip(",") for p in tex.split(r"\quad")]
                tex = r"\begin{gathered}" + r" \\ ".join(parts) + r"\end{gathered}"
            out.append(tex)
            out.append(r"\end{equation}" + "\n")
        elif t == "fig":
            out.append(figure(b, used))
        elif t == "tab":
            out.append(table(b))
    if in_list:
        out.append(r"\end{itemize}")
    return "\n".join(out)


# -------------------------------------------------------------- references

def bibitem(r):
    a = r["authors"]
    if len(a) > 6:
        auth = a[0] + " \\emph{et al.}"
    elif len(a) > 2:
        auth = ", ".join(a[:-1]) + ", and " + a[-1]
    else:
        auth = " and ".join(a)
    auth = esc_plain(auth).replace(r"\textbackslash{}emph\{et al.\}", r"\emph{et al.}")
    if len(a) > 6:
        auth = esc_plain(a[0]) + r" \emph{et al.}"
    venue = esc_plain(r["venue"])
    parts = []
    if auth:
        parts.append(auth)
    title = esc_plain(r["title"])
    is_book = r["key"] == "bellman1957"
    if is_book:
        parts.append(rf"\emph{{{title}}}")
        parts.append(venue)
    else:
        parts.append(f"``{title},''")
        if venue.startswith(("Proc", "Advances")):
            parts.append(rf"in \emph{{{venue}}}")
        else:
            parts.append(rf"\emph{{{venue}}}")
    if r["volume"]:
        parts.append(f"vol. {r['volume']}")
    if r["number"]:
        parts.append(f"no. {r['number']}")
    if r["pages"]:
        pg = r["pages"].replace("-", "--")
        parts.append(("pp. " if "--" in pg else "Art. no. ") + pg)
    date = " ".join(x for x in (abbr_month(r["month"]), r["year"]) if x)
    if date:
        parts.append(date)
    s = ", ".join(p for p in parts if p)
    s = s.replace(",'', ", ",'' ")
    if r["doi"]:
        s += rf", doi: {esc_plain(r['doi'])}."
    elif r.get("verified_url"):
        s += rf". [Online]. Available: \url{{{r['verified_url']}}}"
    else:
        s += "."
    return rf"\bibitem{{{r['key']}}} {s}"


def abbr_month(m):
    if not m:
        return ""
    m = m.rstrip(".")
    full = {"January": "Jan.", "February": "Feb.", "March": "Mar.",
            "April": "Apr.", "May": "May", "June": "Jun.", "July": "Jul.",
            "August": "Aug.", "September": "Sep.", "October": "Oct.",
            "November": "Nov.", "December": "Dec."}
    for k, v in full.items():
        if k.startswith(m):
            return v
    return m


def cite_order(blocks, back):
    order = []
    texts = []
    for b in blocks:
        texts += [b.get("text", ""), b.get("cap", "")]
        for row in b.get("rows", []):
            texts += row
    texts += [t for _, t in back]
    for t in texts:
        for grp in re.findall(r"\[(@[^\]]+)\]", t):
            for k in re.findall(r"@([\w-]+)", grp):
                if k not in order:
                    order.append(k)
    return order


# ------------------------------------------------------------------- main

def main():
    front = json.loads((SEC / "00-front.json").read_text())
    blocks = load_blocks()
    refs = load_refs()
    used = []
    text = body(blocks, used)

    back = [(h, t) for h, t in front.get("back", [])]
    order = cite_order(blocks, back)
    missing = [k for k in order if k not in refs]
    if missing:
        raise SystemExit(f"missing reference entries: {missing}")
    unused = [k for k in refs if k not in order]

    # authors
    auths = []
    for k, a in enumerate(front["authors"]):
        s = r"\uppercase{" + esc_plain(a["name"]) + r"}\authorrefmark{" + a["mark"] + "}"
        if a.get("membership"):
            s += r", \IEEEmembership{" + a["membership"] + "}"
        auths.append(s)
    if len(auths) > 2:
        author = ", ".join(auths[:-1]) + ", AND " + auths[-1]
    else:
        author = " AND ".join(auths)
    addr = []
    for aff in front["affiliations"]:
        m = re.match(r"^(\d+)(.*)$", aff)
        addr.append(rf"\address[{m.group(1)}]{{{esc_plain(m.group(2).strip())}}}")
    corresp = esc_plain(front["notes"][0]) if front.get("notes") else ""
    title = esc_plain(front["title"])
    head = esc_plain(front["running_head"])
    # running head: "M. Gonugondla et al.: Title" -> template's \headeretal form
    head = head.replace(" et al.:", r" \headeretal:")

    backtex = []
    for h, t in back:
        backtex.append(rf"\section*{{{h.title() if h.isupper() else h}}}")
        backtex.append(inline(t) + "\n")

    bib = [r"\begin{thebibliography}{00}"]
    for k in order:
        bib.append(bibitem(refs[k]) + "\n")
    bib.append(r"\end{thebibliography}")

    bios = []
    for a in front["authors"]:
        bios.append(rf"\begin{{IEEEbiographynophoto}}{{{esc_plain(a['name'])}}}")
        bios.append("Biography to be written.")
        bios.append(r"\end{IEEEbiographynophoto}" + "\n")

    preamble = r"""\documentclass{ieeeaccess}
%Adjusted 05/13/2026 at the byline author names
% Official IEEE Access LaTeX template (ACCESS_latex_template_20260513).
% GENERATED by paper/build_latex.py from paper/sections; edit the sections,
% not this file, or your edits are lost on the next build.
\usepackage{cite}
\usepackage{amsmath,amssymb,amsfonts}
% \usepackage{algorithmic}  % not used; not in every TeX install
\usepackage{graphicx}
\usepackage{textcomp}
\usepackage{tabularx}
\usepackage{url}
\makeatletter\g@addto@macro{\UrlBreaks}{\UrlOrds}\makeatother % let long URLs break
\renewcommand{\tabularxcolumn}[1]{>{\raggedright\arraybackslash}p{#1}}

\usepackage{bm}
\makeatletter
\AtBeginDocument{\DeclareMathVersion{bold}
\SetSymbolFont{operators}{bold}{T1}{times}{b}{n}
\SetSymbolFont{NewLetters}{bold}{T1}{times}{b}{it}
\SetMathAlphabet{\mathrm}{bold}{T1}{times}{b}{n}
\SetMathAlphabet{\mathit}{bold}{T1}{times}{b}{it}
\SetMathAlphabet{\mathbf}{bold}{T1}{times}{b}{n}
\SetMathAlphabet{\mathtt}{bold}{OT1}{pcr}{b}{n}
\SetSymbolFont{symbols}{bold}{OMS}{cmsy}{b}{n}
\renewcommand\boldmath{\@nomath\boldmath\mathversion{bold}}}
\makeatother

%Your document starts from here ___________________________________________________
\begin{document}
\history{Date of publication xxxx 00, 0000, date of current version xxxx 00, 0000.}
\doi{10.1109/ACCESS.2024.0429000}
"""
    doc = [preamble,
           rf"\title{{{title}}}",
           rf"\author{{{author}}}",
           "\n".join(addr),
           r"\tfootnote{Funding information to be added by the authors.}",
           "",
           r"\markboth",
           "{" + head + "}",
           "{" + head + "}",
           "",
           rf"\corresp{{{corresp} (e-mail: to be added).}}",
           "",
           r"\begin{abstract}",
           esc_plain(front["abstract"]),
           r"\end{abstract}",
           "",
           r"\begin{keywords}",
           esc_plain(front["index_terms"].rstrip(".")),
           r"\end{keywords}",
           "",
           r"\titlepgskip=-21pt",
           "",
           r"\maketitle",
           "",
           text,
           "\n".join(backtex),
           "\n".join(bib),
           "",
           "\n".join(bios),
           r"\EOD",
           "",
           r"\end{document}",
           ""]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "figures").mkdir(exist_ok=True)
    for src in used:
        shutil.copy2(src, OUT_DIR / "figures" / src.name)
    OUT.write_text("\n".join(doc))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(order)} references cited, "
          f"{len(used)} figures, {sum(b['t'] == 'tab' for b in blocks)} tables")
    if unused:
        print("reference entries never cited:", ", ".join(unused))


if __name__ == "__main__":
    main()
