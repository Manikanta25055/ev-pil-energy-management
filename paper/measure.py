"""Sentence-length statistics per section and overall. Run from the repo root."""
import glob, re, statistics, json
tot=[]
def sents(text):
    return [x for x in re.split(r"(?<=[.!?])\s+", text) if len(x.split()) > 2]
for f in sorted(glob.glob("paper/sections/0[1-7]-*.md")):
    if "claims" in f: continue
    t=[l for l in open(f).read().split("\n") if l and not l.startswith(("#","|","!","Table:","Caption:","$$","-"))]
    L=[len(x.split()) for x in sents(" ".join(t))]; tot+=L
    print(f"{f[15:38]:24s} n={len(L):3d} mean={statistics.mean(L):5.1f} SD={statistics.pstdev(L):5.1f} short(<=8)={sum(l<=8 for l in L):2d} long(>=30)={sum(l>=30 for l in L):2d}")
print(f"{'ALL':24s} n={len(tot):3d} mean={statistics.mean(tot):5.1f} SD={statistics.pstdev(tot):5.1f}")
