"""Slične reference: za objave s AI ocjenom 2 ili 3 traži najsličnije poslove iz liste referenci.

Lista referenci je u fajlu reference.enc.json u korijenu repozitorija, šifrirana istom šifrom kao
interni izvori (TR_PASSPHRASE); piše je stranica (tab Reference). Rezultat se piše šifriran u
data/refmatch.json, pa ga stranica prikazuje tek nakon unosa šifre.

Sličnost: TF-IDF nad riječima naziva (bosanski i engleski), oblasti, vrste usluge, naručioca i
opisa; riječi se skraćuju na prvih pet slova, pa se „energetska“ i „energijska“ poklapaju.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

CYR = dict(zip("абвгдђежзијклљмнњопрстћуфхцчџшѓѕќ",
               ["a", "b", "v", "g", "d", "dj", "e", "z", "z", "i", "j", "k", "l", "lj", "m", "n", "nj", "o",
                "p", "r", "s", "t", "c", "u", "f", "h", "c", "c", "dz", "s", "g", "dz", "k"]))
STOP = set("""
i u na za od do sa se je su o po iz ili kao te koji koja koje kojih kojima ova ovaj ove taj to sve svih
nakon prema kroz izmedju radi biti bila bilo bio the of and for to in on at by with from an or as is are be
this that these those its into within other new all
usluge usluga usluzi izrada izradu nabavka nabavke nabava postupak javna javni javne poziv
services service provision support project projekt projekta projekat contract ugovor ugovora
""".split())
FIELDS_REF = (("t", 2.0), ("e", 2.0), ("o", 1.0), ("v", 1.0), ("vd", 1.0), ("k", 1.0), ("d", 0.5), ("f", 0.5))
TOP, MIN_SCORE = 5, 0.18


def _norm(text: str) -> str:
    text = str(text or "").lower()
    text = "".join(CYR.get(ch, ch) for ch in text).replace("đ", "dj")
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _text(value) -> str:
    """Polje reference kao tekst; oblast, vrsta posla i države mogu biti liste."""
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value if v)
    return str(value or "")


def _tokens(text) -> list[str]:
    text = _text(text)
    out = []
    for w in re.findall(r"[a-z0-9]+", _norm(text)):
        if len(w) < 3 or w in STOP or w.isdigit():
            continue
        out.append(w[:5])
    return out


def _vector(parts, idf: dict) -> dict:
    tf: Counter = Counter()
    for text, weight in parts:
        for tok in _tokens(text):
            tf[tok] += weight
    vec = {t: c * idf.get(t, 0.0) for t, c in tf.items() if idf.get(t)}
    norm = math.sqrt(sum(x * x for x in vec.values())) or 1.0
    return {t: x / norm for t, x in vec.items()}


def match(recs: list, refs: list) -> dict:
    """{"refs": [kratki opis korištenih referenci], "m": {id objave: [[indeks, sličnost], ...]}}."""
    docs = [{tok for f, _ in FIELDS_REF for tok in _tokens(r.get(f, ""))} for r in refs]
    n = len(docs)
    df: Counter = Counter(t for d in docs for t in d)
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
    ref_vecs = [_vector([(r.get(f, ""), w) for f, w in FIELDS_REF], idf) for r in refs]
    index: dict[str, list[tuple[int, float]]] = {}
    for i, v in enumerate(ref_vecs):
        for t, x in v.items():
            index.setdefault(t, []).append((i, x))

    used: dict[int, int] = {}
    out: dict[str, list] = {}
    for r in recs:
        if r.get("dup") or (r.get("ai") or 0) < 2:
            continue
        q = _vector([(r.get("t", ""), 2.0), (r.get("en", ""), 2.0), (r.get("b", ""), 0.5),
                     (r.get("sm", ""), 1.0), ((r.get("_desc") or "")[:800], 0.5)], idf)
        score: Counter = Counter()
        for t, x in q.items():
            for i, y in index.get(t, ()):
                score[i] += x * y
        best = [(i, s) for i, s in score.most_common(TOP) if s >= MIN_SCORE]
        if best:
            out[r["id"]] = [[used.setdefault(i, len(used)), round(s, 2)] for i, s in best]
    short = [None] * len(used)
    for i, k in used.items():
        ref = refs[i]
        short[k] = {x: ref[x] for x in ("id", "i", "t", "e", "k", "y", "z", "v", "s") if ref.get(x)}
    return {"refs": short, "m": out}
