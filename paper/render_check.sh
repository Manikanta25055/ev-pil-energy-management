#!/bin/zsh
# Convert the mock paper to PDF with Microsoft Word and render pages to PNG.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/paper/EV-PIL-mock-paper-IEEE-Access.docx"
WD="$HOME/Library/Containers/com.microsoft.Word/Data/Documents"
TAG="evpil-mock-$(date +%s)"
cp "$SRC" "$WD/$TAG.docx"
osascript <<OSA
tell application "Microsoft Word"
  open file name (POSIX file "$WD/$TAG.docx" as text)
  delay 2
  save as active document file name (POSIX file "$WD/$TAG.pdf" as text) file format format PDF
  close active document saving no
end tell
OSA
cp "$WD/$TAG.pdf" "$ROOT/paper/EV-PIL-mock-paper-IEEE-Access.pdf"
rm -f "$WD/$TAG.docx" "$WD/$TAG.pdf"
mkdir -p "$ROOT/paper/_render"; rm -f "$ROOT"/paper/_render/*.png(N)
python3 - "$ROOT" <<'PY'
import sys, pymupdf
root=sys.argv[1]
d=pymupdf.open(root+"/paper/EV-PIL-mock-paper-IEEE-Access.pdf")
for i,p in enumerate(d):
    p.get_pixmap(dpi=80).save(f"{root}/paper/_render/p{i+1:02d}.png")
print("pages",len(d))
PY
