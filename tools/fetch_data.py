"""Download the English source corpora into data/raw/ (gitignored).

    uv run python tools/fetch_data.py tinystories-valid     # 22 MB, for tests/sampling
    uv run python tools/fetch_data.py tinystories-train     # 2.2 GB, for the corpus
    uv run python tools/fetch_data.py all

Downloads resume if interrupted (HTTP Range), are checked against the exact
expected size, and are recorded with their SHA-256 in data/raw/MANIFEST.json
so a corpus manifest can say exactly which input it came from.

Source: TinyStories (Eldan & Li 2023), https://huggingface.co/datasets/roneneldan/TinyStories,
license CDLA-Sharing-1.0.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
BASE = "https://huggingface.co/datasets/roneneldan/TinyStories/resolve/main/"

DATASETS = {
    "tinystories-valid": ("TinyStoriesV2-GPT4-valid.txt", 22_502_601),
    "tinystories-train": ("TinyStoriesV2-GPT4-train.txt", 2_227_753_162),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(name: str) -> Path:
    filename, size = DATASETS[name]
    dest = RAW / filename
    part = dest.with_suffix(dest.suffix + ".part")
    RAW.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size == size:
        print(f"{filename}: already present ({size:,} bytes)")
        return dest
    have = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(BASE + filename, headers={"Range": f"bytes={have}-"} if have else {})
    t0, last = time.time(), 0.0
    with urllib.request.urlopen(req) as r, part.open("ab" if have else "wb") as f:
        if have and r.status != 206:           # server ignored Range: start over
            f.seek(0)
            f.truncate()
            have = 0
        done = have
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if time.time() - last > 2:
                rate = (done - have) / max(time.time() - t0, 1e-6) / 1e6
                print(f"\r{filename}: {done / 1e6:,.0f} / {size / 1e6:,.0f} MB  ({rate:.1f} MB/s)",
                      end="", flush=True)
                last = time.time()
    print()
    if part.stat().st_size != size:
        raise SystemExit(f"{filename}: got {part.stat().st_size:,} bytes, expected {size:,}; "
                         "re-run to resume")
    part.replace(dest)
    return dest


def record(path: Path) -> None:
    manifest_path = RAW / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    print(f"{path.name}: hashing...")
    manifest[path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path),
                           "source": BASE + path.name}
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"{path.name}: sha256 {manifest[path.name]['sha256']}")


def main() -> None:
    names = sys.argv[1:] or ["tinystories-valid"]
    if names == ["all"]:
        names = list(DATASETS)
    for n in names:
        if n not in DATASETS:
            raise SystemExit(f"unknown dataset {n!r}; choose from {list(DATASETS)} or 'all'")
        record(fetch(n))


if __name__ == "__main__":
    main()
