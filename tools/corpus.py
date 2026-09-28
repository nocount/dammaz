"""Build the Dammaz training corpus for dwarfgpt (PLAN.md Phase 5).

Three steps, each safe to re-run:

    # 1. translate English stories -> sharded parallel JSONL (resumable, parallel)
    uv run --group nlp python tools/corpus.py translate data/raw/TinyStoriesV2-GPT4-train.txt \\
        --out data/corpus/tinystories --workers 8

    # 2. progress / quality so far
    uv run python tools/corpus.py report data/corpus/tinystories

    # 3. filter + dedupe + split -> Parquet (nanochat-style "text" column) + parallel JSONL
    uv run --group corpus python tools/corpus.py pack data/corpus/tinystories

**translate** cuts the input into fixed shards of ``--shard-size`` stories
(shard k = stories k*S .. k*S+S-1, so shard contents never depend on worker
count). Each shard is written atomically (``.tmp`` then rename), so an
interrupted run just continues with ``translate`` again. The manifest records
the lexicon/code fingerprint (``dammaz.lexicon.fingerprint``); shards made with
a different fingerprint are refused unless ``--allow-mixed``.

**pack** keeps stories with no unknown tokens, at most ``--max-loan-rate`` loans,
and at least ``--min-words`` words, drops exact duplicates (normalized English), and
assigns ~``--val-frac`` of stories to validation by a hash of their English
text. It writes:

    <out>/packed/dz/train/shard_00000.parquet ...   {"text": Dammaz story}
    <out>/packed/dz/val/shard_00000.parquet
    <out>/packed/parallel/train.jsonl, val.jsonl    {"id", "en", "dz"}
    <out>/packed/pack_manifest.json, REPORT.md      counts, loan rate, top loans
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from dammaz import __version__  # noqa: E402
from dammaz.lexicon import fingerprint  # noqa: E402

MANIFEST = "translate_manifest.json"


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------

def iter_stories(path: Path):
    """Stories separated by <|endoftext|> lines (TinyStories format)."""
    buf: list[str] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if "<|endoftext|>" in line:
                if buf and "".join(buf).strip():
                    yield "".join(buf).strip()
                buf = []
            else:
                buf.append(line)
    if buf and "".join(buf).strip():
        yield "".join(buf).strip()


def git_info() -> dict:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "src", "lexicon"],
                                    cwd=ROOT, capture_output=True, text=True).stdout.strip())
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def input_info(path: Path) -> dict:
    info = {"file": path.name, "bytes": path.stat().st_size}
    raw_manifest = path.parent / "MANIFEST.json"
    if raw_manifest.exists():
        info["sha256"] = json.loads(raw_manifest.read_text()).get(path.name, {}).get("sha256")
    return info


def shard_path(out: Path, k: int) -> Path:
    return out / "shards" / f"shard_{k:05d}.jsonl"


# ---------------------------------------------------------------------------
# translate (runs in worker processes)
# ---------------------------------------------------------------------------

_translator = None


def _init_worker() -> None:
    global _translator
    from dammaz.translate import Translator
    _translator = Translator()
    _translator.translate("Warm up.")          # load spaCy + lexicon once per worker


def _translate_shard(k: int, start: int, stories: list[str], out: str, source: str) -> dict:
    t0 = time.time()
    path = shard_path(Path(out), k)
    tmp = path.with_suffix(".jsonl.tmp")
    words = loans = unknown = 0
    with tmp.open("w", encoding="utf-8") as f:
        for j, (en, (dz, st)) in enumerate(zip(stories, _translator.translate_many(stories))):
            words += st.tokens
            loans += st.loans
            unknown += st.unknown
            f.write(json.dumps({
                "id": f"{source}-{start + j}", "en": en, "dz": dz,
                "words": st.tokens, "loans": st.loans, "loan_rate": round(st.loan_rate, 4),
                "unknown": st.unknown, "names": st.names,
                "loan_words": sorted(st.loan_words.elements()),
            }, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return {"k": k, "stories": len(stories), "en_words": sum(len(s.split()) for s in stories),
            "words": words, "loans": loans, "unknown": unknown,
            "seconds": round(time.time() - t0, 1)}


def cmd_translate(args) -> None:
    out: Path = args.out
    (out / "shards").mkdir(parents=True, exist_ok=True)
    fp = fingerprint()
    mpath = out / MANIFEST
    manifest = json.loads(mpath.read_text()) if mpath.exists() else None
    if manifest:
        if manifest["fingerprint"] != fp and not args.allow_mixed:
            raise SystemExit(
                f"existing shards were made with fingerprint {manifest['fingerprint']}, the "
                f"lexicon/translator is now {fp}. Use a new --out, delete {out}, or pass "
                "--allow-mixed if you really want to mix versions.")
        if manifest["shard_size"] != args.shard_size:
            raise SystemExit(f"shard size must stay {manifest['shard_size']} for this output dir")
    else:
        manifest = {"source": args.source, "input": input_info(args.input),
                    "fingerprint": fp, "dammaz_version": __version__, "git": git_info(),
                    "shard_size": args.shard_size, "host": platform.node(),
                    "started": datetime.now(timezone.utc).isoformat(), "shards": {}}

    def save() -> None:
        manifest["updated"] = datetime.now(timezone.utc).isoformat()
        tmp = mpath.with_suffix(".tmp")
        tmp.write_text(json.dumps(manifest, indent=1))
        tmp.replace(mpath)

    save()
    workers = args.workers or max(1, (os.cpu_count() or 2) - 1)
    print(f"translating {args.input.name} -> {out}  (fingerprint {fp}, {workers} workers, "
          f"{args.shard_size} stories/shard)")
    t0 = time.time()
    done_words = 0

    def shards():
        buf, k, start = [], 0, 0
        for i, story in enumerate(iter_stories(args.input)):
            if args.max_stories and i >= args.max_stories:
                break
            buf.append(story)
            if len(buf) == args.shard_size:
                yield k, start, buf
                k, start, buf = k + 1, i + 1, []
        if buf:
            yield k, start, buf

    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as pool:
        pending = set()
        for k, start, stories in shards():
            if shard_path(out, k).exists():
                continue                                   # finished in an earlier run
            pending.add(pool.submit(_translate_shard, k, start, stories, str(out), args.source))
            while len(pending) >= workers * 2:             # bound memory: don't read ahead too far
                finished, pending = wait(pending, return_when=FIRST_COMPLETED)
                for fut in finished:
                    done_words = _record(fut.result(), manifest, save, t0, done_words)
        for fut in pending:
            done_words = _record(fut.result(), manifest, save, t0, done_words)
    manifest["finished"] = datetime.now(timezone.utc).isoformat()
    save()
    print(summary(out))


def _record(res: dict, manifest: dict, save, t0: float, done_words: int) -> int:
    manifest["shards"][str(res["k"])] = res
    save()
    done_words += res["en_words"]
    rate = done_words / max(time.time() - t0, 1e-6)
    lr = res["loans"] / max(res["words"], 1)
    print(f"  shard {res['k']:5d}: {res['stories']:,} stories, loans {lr:.2%}, "
          f"unknown {res['unknown']}, {res['seconds']:.0f}s   | this run {done_words:,} "
          f"words at {rate:,.0f} words/s", flush=True)
    return done_words


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def summary(out: Path) -> str:
    m = json.loads((out / MANIFEST).read_text())
    shards = m["shards"].values()
    stories = sum(s["stories"] for s in shards)
    words = sum(s["words"] for s in shards)
    loans = sum(s["loans"] for s in shards)
    unknown = sum(s["unknown"] for s in shards)
    secs = sum(s["seconds"] for s in shards)
    return (f"{out}: {len(m['shards'])} shards, {stories:,} stories, {words:,} Dammaz words, "
            f"loans {loans / max(words, 1):.2%}, unknown {unknown:,}, "
            f"{secs / 3600:.2f} worker-hours; fingerprint {m['fingerprint']}")


def cmd_report(args) -> None:
    print(summary(args.dir))


# ---------------------------------------------------------------------------
# pack
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _is_val(en: str, frac: float) -> bool:
    h = int(hashlib.sha1(_norm(en).encode()).hexdigest()[:8], 16)
    return (h % 10_000) < frac * 10_000


def pack_records(records, max_loan_rate: float, min_words: int, val_frac: float):
    """Yield (split, record) for kept records; returns drop counts via .drops."""
    seen: set[bytes] = set()
    drops: Counter = Counter()
    for r in records:
        if r["unknown"]:
            drops["unknown tokens"] += 1
            continue
        if r["loan_rate"] > max_loan_rate:
            drops[f"loan rate > {max_loan_rate:.0%}"] += 1
            continue
        if r["words"] < min_words:
            drops[f"< {min_words} words"] += 1
            continue
        key = hashlib.sha1(_norm(r["en"]).encode()).digest()
        if key in seen:
            drops["duplicate"] += 1
            continue
        seen.add(key)
        yield ("val" if _is_val(r["en"], val_frac) else "train"), r
    pack_records.drops = drops


class ParquetShards:
    """Writes {"text"} rows into numbered Parquet files, row groups of 1024."""

    def __init__(self, directory: Path, rows_per_file: int):
        self.dir, self.rows_per_file = directory, rows_per_file
        self.dir.mkdir(parents=True, exist_ok=True)
        self.buf: list[str] = []
        self.n = 0

    def add(self, text: str) -> None:
        self.buf.append(text)
        if len(self.buf) >= self.rows_per_file:
            self.flush()

    def flush(self) -> None:
        if not self.buf:
            return
        import pyarrow as pa
        import pyarrow.parquet as pq
        pq.write_table(pa.table({"text": self.buf}), self.dir / f"shard_{self.n:05d}.parquet",
                       row_group_size=1024, compression="zstd")
        self.n += 1
        self.buf = []


def cmd_pack(args) -> None:
    src: Path = args.dir
    m = json.loads((src / MANIFEST).read_text())
    dst = args.out or (src / "packed")
    if dst.exists() and any(dst.iterdir()) and not args.overwrite:
        raise SystemExit(f"{dst} exists; pass --overwrite to rebuild it")
    import shutil
    if dst.exists():
        shutil.rmtree(dst)

    def records():
        for k in sorted(int(x) for x in m["shards"]):
            with shard_path(src, k).open(encoding="utf-8") as f:
                for line in f:
                    yield json.loads(line)

    pq_out = {s: ParquetShards(dst / "dz" / s, args.rows_per_file) for s in ("train", "val")}
    (dst / "parallel").mkdir(parents=True, exist_ok=True)
    par = {s: (dst / "parallel" / f"{s}.jsonl").open("w", encoding="utf-8") for s in ("train", "val")}
    counts: Counter = Counter()
    words: Counter = Counter()
    chars: Counter = Counter()
    loans: Counter = Counter()
    loan_words: Counter = Counter()
    for split, r in pack_records(records(), args.max_loan_rate, args.min_words, args.val_frac):
        pq_out[split].add(r["dz"])
        par[split].write(json.dumps({"id": r["id"], "en": r["en"], "dz": r["dz"]},
                                    ensure_ascii=False) + "\n")
        counts[split] += 1
        words[split] += r["words"]
        chars[split] += len(r["dz"])
        loans[split] += r["loans"]
        loan_words.update(r.get("loan_words", []))
    for w in pq_out.values():
        w.flush()
    for f in par.values():
        f.close()
    drops = pack_records.drops
    total_words = sum(words.values())
    pack = {"source_manifest": {k: m[k] for k in ("source", "input", "fingerprint", "git",
                                                   "shard_size", "host")},
            "packed": datetime.now(timezone.utc).isoformat(),
            "filters": {"max_loan_rate": args.max_loan_rate, "min_words": args.min_words,
                        "val_frac": args.val_frac, "dedupe": "exact, normalized English"},
            "stories": dict(counts), "dz_words": dict(words), "dz_chars": dict(chars),
            "loan_rate": round(sum(loans.values()) / max(total_words, 1), 4),
            "dropped": dict(drops), "parquet_files": {s: w.n for s, w in pq_out.items()}}
    (dst / "pack_manifest.json").write_text(json.dumps(pack, indent=1))
    kept = sum(counts.values())
    lines = [f"# Packed Dammaz corpus: {m['source']}", "",
             f"- fingerprint: `{m['fingerprint']}`, git `{(m['git'] or {}).get('commit')}`",
             f"- kept {kept:,} stories ({counts['train']:,} train / {counts['val']:,} val); "
             f"dropped {sum(drops.values()):,}: " + ", ".join(f"{k} {v:,}" for k, v in drops.items()),
             f"- Dammaz words: {total_words:,} ({words['train']:,} train / {words['val']:,} val); "
             f"characters {sum(chars.values()):,}",
             f"- loan rate after filtering: {pack['loan_rate']:.2%}", "",
             "## Most frequent loans (the next lexicon batch)", "",
             "| loan | count |", "|---|---:|"]
    lines += [f"| {w} | {n:,} |" for w, n in loan_words.most_common(100)]
    (dst / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:7]))
    print(f"wrote {dst}")


# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("translate", help="English stories -> sharded parallel JSONL")
    t.add_argument("input", type=Path)
    t.add_argument("--out", type=Path, required=True)
    t.add_argument("--source", default="tinystories")
    t.add_argument("--workers", type=int, default=None, help="default: CPU count - 1")
    t.add_argument("--shard-size", type=int, default=5000)
    t.add_argument("--max-stories", type=int, default=None)
    t.add_argument("--allow-mixed", action="store_true")
    r = sub.add_parser("report", help="progress / quality of a translate run")
    r.add_argument("dir", type=Path)
    p = sub.add_parser("pack", help="filter, dedupe, split -> Parquet + parallel JSONL")
    p.add_argument("dir", type=Path)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--max-loan-rate", type=float, default=0.05)
    p.add_argument("--min-words", type=int, default=20)
    p.add_argument("--val-frac", type=float, default=0.05)
    p.add_argument("--rows-per-file", type=int, default=100_000)
    p.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    {"translate": cmd_translate, "report": cmd_report, "pack": cmd_pack}[args.cmd](args)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
