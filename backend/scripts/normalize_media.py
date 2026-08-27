"""Converts fragmented MP4 losslessly into continuously playable files."""
import argparse
import os
import sys
import tempfile
from pathlib import Path

# Make 'src.*' importable whether run from /app or via docker exec with another cwd.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from src import storage
from src.services import aia_chunker
from src.services.media_normalize import is_fragmented_mp4_reader, normalize_if_fragmented
from src.features.ai_assistant.repository import sources as source_repo


def _range_reader(file_path: str, counter: list):
    """A read(offset, length) callable that fetches byte ranges and counts the requests."""
    def read(offset: int, length: int) -> bytes:
        counter[0] += 1
        return storage.get_range(file_path, offset, length)
    return read


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Remux fragmented MP4 media to progressive faststart (lossless)."
    )
    ap.add_argument("--dry-run", action="store_true",
                    help="Only detect & report which files are fragmented; change nothing.")
    args = ap.parse_args()

    sources = [s for s in source_repo.get_all_aia_sources()
               if aia_chunker.is_media_file(s.get("file_type", ""))]
    print(f"Media sources: {len(sources)}  (dry-run={args.dry_run})")

    fragmented = fixed = total_reqs = 0
    for s in sources:
        fp = s["file_path"]
        fn = s.get("filename", fp)
        counter = [0]
        is_frag = is_fragmented_mp4_reader(_range_reader(fp, counter))
        total_reqs += counter[0]

        if not is_frag:
            print(f"  ok         {fn}  ({counter[0]} header reads)")
            continue

        fragmented += 1
        if args.dry_run:
            print(f"  FRAGMENTED {fn}  -> would remux  ({counter[0]} header reads)")
            continue

        # Only fragmented files are fully downloaded + remuxed + re-uploaded.
        suffix = os.path.splitext(fp)[1] or ".mp4"
        fd, tmp = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        try:
            with open(tmp, "wb") as fh:
                fh.write(storage.get_file(fp))
            out = normalize_if_fragmented(tmp)
            if out:
                storage.put_file(fp, out)
                os.unlink(out)
                fixed += 1
                print(f"  FIXED      {fn}  -> progressive (re-uploaded)")
            else:
                print(f"  skipped    {fn}  (range flagged it but local scan disagreed)")
        finally:
            os.unlink(tmp)

    print(f"--- scanned {len(sources)}, fragmented {fragmented}, remuxed {fixed}, "
          f"{total_reqs} range header reads total ---")
    if args.dry_run and fragmented:
        print("Re-run without --dry-run to remux the fragmented files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
