#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
01_inventory.py - censimento del disco del Victus. Fase 1: nessun modello.

Cammina sui path indicati, salta sistema/applicazioni/cache, classifica i file
per estensione e individua i duplicati per contenuto (hash parziale, poi hash
completo solo sui gruppi ancora in collisione).

NON sposta e NON cancella niente: produce inventory.csv e un riepilogo a schermo.

Uso, dal Victus:
    python 01_inventory.py C:\\Users\\paolo
    python 01_inventory.py C:\\Users\\paolo D:\\ -o inventory.csv

Solo stdlib, Python 3.9+.
"""

import argparse
import csv
import hashlib
import os
import sys
from collections import defaultdict
from datetime import datetime

# --- cosa non guardare -----------------------------------------------------
# Frammenti di percorso delimitati da backslash su entrambi i lati: cosi'
# "\temp\" non becca "\tempo-libero\".

_EXCLUDE_NAMES = (
    "windows", "program files", "program files (x86)", "programdata",
    "$recycle.bin", "system volume information", "recovery", "boot",
    "perflogs", "intel", "nvidia",
    "node_modules", ".git", ".svn", ".hg", "venv", ".venv", "__pycache__",
    ".cache", "cache", "caches", ".gradle", ".nuget", ".m2", ".npm", ".conda",
    "anaconda3", "miniconda3", ".ollama", ".docker", "steamapps",
    "temp", "tmp", ".tmp", "logs",
)
EXCLUDE = tuple("\\" + n + "\\" for n in _EXCLUDE_NAMES)

# AppData e' quasi tutto spazzatura applicativa, ma gli archivi di posta stanno
# li' dentro e sono la miniera piu' facile da dimenticare. Quindi: non ci si
# scende dentro, tranne in questi rami.
APPDATA_KEEP = (
    r"Local\Microsoft\Outlook",
    r"Roaming\Microsoft\Outlook",
    r"Roaming\Microsoft\Templates",
    r"Roaming\Microsoft\Signatures",
    r"Roaming\Thunderbird",
)

# --- classificazione per estensione -----------------------------------------

KINDS = {
    "foto": {
        "jpg", "jpeg", "jpe", "png", "heic", "heif", "webp", "tif", "tiff",
        "bmp", "gif", "dng", "cr2", "cr3", "nef", "arw", "raf", "orf", "rw2",
    },
    "video": {"mp4", "mov", "avi", "mkv", "m4v", "3gp", "mts", "mpg", "mpeg", "wmv"},
    "documento": {
        "pdf", "doc", "docx", "odt", "rtf", "txt", "md", "xls", "xlsx", "xlsm",
        "ods", "csv", "ppt", "pptx", "odp", "epub", "pages", "numbers", "key",
        "tex", "djvu",
    },
    "posta": {"pst", "ost", "mbox", "eml", "msg", "olm"},
    "archivio": {"zip", "rar", "7z", "tar", "gz", "bz2", "xz", "tgz"},
    "audio": {"mp3", "m4a", "wav", "ogg", "flac", "amr", "opus", "aac", "wma"},
    "progetto": {"psd", "ai", "indd", "svg", "dwg", "skp", "blend", "afphoto", "afdesign"},
}
EXT2KIND = {e: k for k, exts in KINDS.items() for e in exts}

# Solo su questi ha senso spendere I/O per il dedup.
HASHABLE = {"foto", "video", "documento", "posta", "archivio", "audio", "progetto"}


def lp(path):
    """Prefisso \\?\\ per i percorsi lunghi di Windows."""
    if os.name == "nt" and len(path) > 240 and not path.startswith("\\\\?\\"):
        return "\\\\?\\" + os.path.abspath(path)
    return path


def excluded(path):
    p = path.replace("/", "\\").lower()
    if not p.endswith("\\"):
        p += "\\"
    return any(frag in p for frag in EXCLUDE)


def walk(roots):
    """Ritorna (records, statistiche). record = [path, kind, ext, size, mtime]."""
    out, stats = [], {"visti": 0, "dir_saltate": 0, "errori": 0}
    stack = [os.path.abspath(r) for r in roots]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(lp(d)) as it:
                entries = list(it)
        except OSError:
            stats["errori"] += 1
            continue
        for e in entries:
            try:
                if e.is_symlink():
                    continue
                if e.is_dir(follow_symlinks=False):
                    if e.name.lower() == "appdata":
                        for sub in APPDATA_KEEP:
                            p = os.path.join(e.path, sub)
                            if os.path.isdir(lp(p)):
                                stack.append(p)
                        stats["dir_saltate"] += 1
                        continue
                    if excluded(e.path):
                        stats["dir_saltate"] += 1
                        continue
                    stack.append(e.path)
                    continue
                if not e.is_file(follow_symlinks=False):
                    continue
                st = e.stat(follow_symlinks=False)
            except OSError:
                stats["errori"] += 1
                continue

            stats["visti"] += 1
            if stats["visti"] % 25000 == 0:
                print("  ... %d file" % stats["visti"], file=sys.stderr)
            ext = os.path.splitext(e.name)[1].lstrip(".").lower()
            out.append([e.path, EXT2KIND.get(ext, "altro"), ext, st.st_size, st.st_mtime])
    return out, stats


def partial_hash(path, size):
    h = hashlib.blake2b(digest_size=16)
    h.update(str(size).encode())
    with open(lp(path), "rb") as f:
        h.update(f.read(65536))
        if size > 131072:
            f.seek(-65536, os.SEEK_END)
            h.update(f.read(65536))
    return h.hexdigest()


def full_hash(path):
    h = hashlib.blake2b(digest_size=16)
    with open(lp(path), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_dups(records):
    """Assegna dup_group/dup_rank. rank 1 = copia piu' vecchia = l'originale."""
    by_size = defaultdict(list)
    for i, r in enumerate(records):
        if r[1] in HASHABLE and r[3] > 0:
            by_size[r[3]].append(i)

    candidates = [i for idxs in by_size.values() if len(idxs) > 1 for i in idxs]
    print("  %d file con dimensione condivisa -> hash parziale" % len(candidates),
          file=sys.stderr)

    pgroups = defaultdict(list)
    for i in candidates:
        try:
            pgroups[partial_hash(records[i][0], records[i][3])].append(i)
        except OSError:
            pass

    todo = [idxs for idxs in pgroups.values() if len(idxs) > 1]
    print("  %d file ancora in collisione -> hash completo" % sum(len(x) for x in todo),
          file=sys.stderr)

    fgroups = defaultdict(list)
    for idxs in todo:
        for i in idxs:
            try:
                fgroups[full_hash(records[i][0])].append(i)
            except OSError:
                pass

    dup = {}
    for digest, idxs in fgroups.items():
        if len(idxs) < 2:
            continue
        ordered = sorted(idxs, key=lambda i: (records[i][4], records[i][0]))
        for rank, i in enumerate(ordered, 1):
            dup[i] = (digest[:12], rank)
    return dup


def human(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return "%d B" % n if unit == "B" else "%.1f %s" % (n, unit)
        n /= 1024


def main():
    ap = argparse.ArgumentParser(description="Censimento disco, fase 1.")
    ap.add_argument("roots", nargs="+", help="cartelle da cui partire")
    ap.add_argument("-o", "--out", default="inventory.csv")
    args = ap.parse_args()

    print("Fase 1/2 - cammino sul disco...", file=sys.stderr)
    records, stats = walk(args.roots)
    print("Fase 2/2 - duplicati su %d file..." % len(records), file=sys.stderr)
    dup = find_dups(records)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["path", "kind", "ext", "size", "mtime", "dup_group", "dup_rank"])
        for i, (path, kind, ext, size, mtime) in enumerate(records):
            g, rank = dup.get(i, ("", ""))
            w.writerow([path, kind, ext, size,
                        datetime.fromtimestamp(mtime).isoformat(timespec="seconds"),
                        g, rank])

    per_kind = defaultdict(lambda: [0, 0])
    folders = defaultdict(int)
    for i, (path, kind, ext, size, _m) in enumerate(records):
        per_kind[kind][0] += 1
        per_kind[kind][1] += size
        if kind in HASHABLE and dup.get(i, ("", 1))[1] == 1:
            folders[os.path.dirname(path)] += size

    redundant = [i for i, (_g, r) in dup.items() if r > 1]
    print("\n=== %s ===" % args.out)
    print("file censiti : %d   cartelle saltate: %d   errori: %d"
          % (stats["visti"], stats["dir_saltate"], stats["errori"]))
    print("\n  tipo          file        spazio")
    for kind, (n, sz) in sorted(per_kind.items(), key=lambda kv: -kv[1][1]):
        print("  %-12s %8d   %10s" % (kind, n, human(sz)))
    print("\n  duplicati: %d file ridondanti, %s recuperabili"
          % (len(redundant), human(sum(records[i][3] for i in redundant))))
    print("\n  cartelle piu' pesanti (al netto dei duplicati):")
    for d, sz in sorted(folders.items(), key=lambda kv: -kv[1])[:20]:
        print("    %10s  %s" % (human(sz), d))
    print("\nProssimo passo: python 02_triage.py %s" % args.out)


if __name__ == "__main__":
    main()
