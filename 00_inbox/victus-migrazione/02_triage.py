#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02_triage.py - smistamento deterministico. Fase 2: ancora nessun modello.

Legge inventory.csv e separa:
  - foto vere (EXIF di fotocamera) da screenshot, immagini scaricate e asset
  - documenti deduplicati, con la zona di provenienza

Il criterio forte sulle foto e' l'EXIF: se c'e' Make/Model la foto l'ha scattata
un telefono o una macchina, quindi e' roba tua. Screenshot e immagini scaricate
dal web non ce l'hanno. Parser EXIF minimale incluso: zero dipendenze.

NON sposta e NON cancella niente. Produce foto.csv, documenti.csv, report.md.

Uso:
    python 02_triage.py inventory.csv

Solo stdlib, Python 3.9+.
"""

import argparse
import csv
import os
import re
import struct
import sys
from collections import defaultdict

csv.field_size_limit(1 << 24)

TAG_MAKE, TAG_MODEL, TAG_DATETIME = 0x010F, 0x0110, 0x0132
TAG_EXIF_IFD, TAG_DT_ORIG = 0x8769, 0x9003
WANT = {TAG_MAKE, TAG_MODEL, TAG_DATETIME, TAG_DT_ORIG}

CAM_NAME = re.compile(
    r"^(img|dsc|dscn|dscf|pict|pxl|gopr|vid|foto|photo|"
    r"\d{8}[_-]\d{6}|\d{4}-\d{2}-\d{2})", re.I)
SHOT_NAME = re.compile(
    r"screen.?shot|schermata|cattura|snip|annotazione|immagine \d|"
    r"senza titolo|untitled|download|scaricat", re.I)
JPEGISH = {"jpg", "jpeg", "jpe", "tif", "tiff", "heic", "heif", "dng",
           "cr2", "cr3", "nef", "arw", "raf", "orf", "rw2"}
RAW = {"dng", "cr2", "cr3", "nef", "arw", "raf", "orf", "rw2"}


def lp(path):
    if os.name == "nt" and len(path) > 240 and not path.startswith("\\\\?\\"):
        return "\\\\?\\" + os.path.abspath(path)
    return path


# --- EXIF minimale (solo Make / Model / date) -------------------------------

def _read_ifd(buf, base, offset, endian, out, follow=True):
    try:
        (count,) = struct.unpack_from(endian + "H", buf, base + offset)
    except struct.error:
        return
    pos = base + offset + 2
    for _ in range(min(count, 512)):
        if pos + 12 > len(buf):
            return
        tag, typ, cnt = struct.unpack_from(endian + "HHI", buf, pos)
        valoff = pos + 8
        if tag == TAG_EXIF_IFD and follow:
            try:
                (sub,) = struct.unpack_from(endian + "I", buf, valoff)
                _read_ifd(buf, base, sub, endian, out, follow=False)
            except struct.error:
                pass
        elif tag in WANT and typ == 2 and 0 < cnt < 256:
            if cnt <= 4:
                raw = buf[valoff:valoff + cnt]
            else:
                try:
                    (o,) = struct.unpack_from(endian + "I", buf, valoff)
                except struct.error:
                    pos += 12
                    continue
                raw = buf[base + o:base + o + cnt]
            val = raw.split(b"\x00")[0].decode("ascii", "replace").strip()
            if val:
                out[tag] = val
        pos += 12


def exif(path, head=262144):
    """Make/Model/date da un JPEG (o TIFF/RAW basato su TIFF). {} se assenti."""
    try:
        with open(lp(path), "rb") as f:
            buf = f.read(head)
    except OSError:
        return {}

    if buf[:2] in (b"II", b"MM"):          # TIFF e molti RAW
        return _tiff(buf, 0)
    if not buf.startswith(b"\xff\xd8"):    # non e' un JPEG
        return {}

    i = 2
    while i + 4 <= len(buf):
        if buf[i] != 0xFF:
            return {}
        marker = buf[i + 1]
        if marker == 0xDA:                 # inizio dati immagine: oltre non serve
            return {}
        if marker in (0x01, 0xD8) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        (seglen,) = struct.unpack_from(">H", buf, i + 2)
        if seglen < 2:
            return {}
        if marker == 0xE1 and buf[i + 4:i + 10] == b"Exif\x00\x00":
            return _tiff(buf, i + 10)
        i += 2 + seglen
    return {}


def _tiff(buf, tiff):
    bo = buf[tiff:tiff + 2]
    endian = "<" if bo == b"II" else ">" if bo == b"MM" else None
    if endian is None:
        return {}
    try:
        (ifd0,) = struct.unpack_from(endian + "I", buf, tiff + 4)
    except struct.error:
        return {}
    out = {}
    _read_ifd(buf, tiff, ifd0, endian, out)
    return out


# --- decisioni --------------------------------------------------------------

def zona(path):
    p = path.replace("/", "\\").lower()
    for frag, label in (
        ("\\desktop\\", "desktop"), ("\\documents\\", "documenti"),
        ("\\documenti\\", "documenti"), ("\\downloads\\", "download"),
        ("\\download\\", "download"), ("\\onedrive", "onedrive"),
        ("\\dropbox", "dropbox"), ("\\google drive", "gdrive"),
        ("\\pictures\\", "immagini"), ("\\immagini\\", "immagini"),
        ("\\videos\\", "video"), ("\\outlook\\", "posta"),
        ("\\thunderbird\\", "posta"), ("\\music\\", "musica"),
    ):
        if frag in p:
            return label
    return "altro"


def classifica_foto(path, ext, size, meta):
    """-> (origine, azione). azione: porta | rivedi | scarta"""
    name = os.path.basename(path)
    z = zona(path)
    if meta.get(TAG_MAKE) or meta.get(TAG_MODEL):
        return "fotocamera", "porta"
    if ext in RAW:
        return "raw", "porta"
    if SHOT_NAME.search(name) or "\\screenshot" in path.lower():
        return "screenshot", "scarta"
    if size < 51200:
        return "miniatura/icona", "scarta"
    if CAM_NAME.match(name):
        return "nome-da-fotocamera", "porta"
    if z in ("immagini", "onedrive", "dropbox", "gdrive", "desktop") and size >= 307200:
        return "immagine-grande-in-%s" % z, "rivedi"
    if z == "download":
        return "scaricata", "scarta"
    return "senza-indizi", "rivedi"


def classifica_doc(path, ext, size):
    z = zona(path)
    if z in ("documenti", "desktop", "onedrive", "dropbox", "gdrive", "posta"):
        return z, "porta"
    if ext in ("txt", "md", "csv") and size < 2048:
        return z, "rivedi"
    return z, "rivedi"


def human(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return "%d B" % n if unit == "B" else "%.1f %s" % (n, unit)
        n /= 1024


def main():
    ap = argparse.ArgumentParser(description="Smistamento deterministico, fase 2.")
    ap.add_argument("inventory", nargs="?", default="inventory.csv")
    ap.add_argument("-d", "--outdir", default=".")
    args = ap.parse_args()

    with open(args.inventory, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f)]

    foto, docs, altri = [], [], defaultdict(lambda: [0, 0])
    letti = 0
    for r in rows:
        if r["dup_rank"] not in ("", "1"):     # copia ridondante: fuori
            continue
        size = int(r["size"])
        kind, ext, path = r["kind"], r["ext"], r["path"]

        if kind == "foto":
            meta = exif(path) if ext in JPEGISH else {}
            letti += 1
            if letti % 5000 == 0:
                print("  ... %d immagini lette" % letti, file=sys.stderr)
            origine, azione = classifica_foto(path, ext, size, meta)
            foto.append([path, ext, size, r["mtime"], meta.get(TAG_MAKE, ""),
                         meta.get(TAG_MODEL, ""),
                         meta.get(TAG_DT_ORIG, "") or meta.get(TAG_DATETIME, ""),
                         origine, azione])
        elif kind in ("documento", "posta", "progetto"):
            z, azione = classifica_doc(path, ext, size)
            docs.append([path, kind, ext, size, r["mtime"], z, azione])
        else:
            altri[kind][0] += 1
            altri[kind][1] += size

    out = args.outdir
    with open(os.path.join(out, "foto.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["path", "ext", "size", "mtime", "exif_make", "exif_model",
                    "exif_date", "origine", "azione"])
        w.writerows(sorted(foto, key=lambda r: (r[8], r[7], r[0])))

    with open(os.path.join(out, "documenti.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["path", "kind", "ext", "size", "mtime", "zona", "azione"])
        w.writerows(sorted(docs, key=lambda r: (r[5], -r[3])))

    def tally(rows_, idx, size_idx):
        agg = defaultdict(lambda: [0, 0])
        for r in rows_:
            agg[r[idx]][0] += 1
            agg[r[idx]][1] += r[size_idx]
        return sorted(agg.items(), key=lambda kv: -kv[1][1])

    lines = ["# Triage del Victus - fase 2 (deterministica)", ""]
    lines.append("Sorgente: `%s`. Duplicati esclusi: solo la copia piu' vecchia "
                 "di ogni gruppo sopravvive.\n" % args.inventory)

    lines.append("## Foto (`foto.csv`)\n")
    lines.append("| azione | file | spazio |")
    lines.append("|---|---:|---:|")
    for k, (n, sz) in tally(foto, 8, 2):
        lines.append("| %s | %d | %s |" % (k, n, human(sz)))
    lines.append("\nDettaglio per origine:\n")
    lines.append("| origine | file | spazio |")
    lines.append("|---|---:|---:|")
    for k, (n, sz) in tally(foto, 7, 2):
        lines.append("| %s | %d | %s |" % (k, n, human(sz)))

    lines.append("\n## Documenti (`documenti.csv`)\n")
    lines.append("| zona | file | spazio |")
    lines.append("|---|---:|---:|")
    for k, (n, sz) in tally(docs, 5, 3):
        lines.append("| %s | %d | %s |" % (k, n, human(sz)))

    lines.append("\n## Resto (non toccato da questa fase)\n")
    lines.append("| tipo | file | spazio |")
    lines.append("|---|---:|---:|")
    for k, (n, sz) in sorted(altri.items(), key=lambda kv: -kv[1][1]):
        lines.append("| %s | %d | %s |" % (k, n, human(sz)))

    n_rivedi = sum(1 for r in docs if r[6] == "rivedi")
    lines += [
        "", "## Prossimo passo", "",
        "I %d documenti in `rivedi` sono il residuo ambiguo: e' su quelli che "
        "ha senso accendere il modello sulla 3060, non sull'intero disco." % n_rivedi,
        "Le foto marcate `porta` vanno direttamente all'import Immich, che "
        "rifa' il dedup e la datazione per conto suo.",
    ]
    report = "\n".join(lines) + "\n"
    with open(os.path.join(out, "report.md"), "w", encoding="utf-8") as f:
        f.write(report)

    print(report)


if __name__ == "__main__":
    main()
