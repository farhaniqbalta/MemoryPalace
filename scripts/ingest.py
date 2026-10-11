"""Ingest a UTF-8 text/Markdown file or folder: python -m scripts.ingest docs"""
import argparse
from pathlib import Path

from app.core.ingestion import ingest_text
from app.db import SessionLocal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Root for stable relative source names")
    args = parser.parse_args()
    root = args.root.resolve()
    path = args.path.resolve()
    if not path.exists():
        parser.error("Input path does not exist")
    files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in (".txt", ".md", ".markdown"))
    saved = skipped = failed = 0
    for file in files:
        try:
            source = file.relative_to(root).as_posix()
            content = file.read_text(encoding="utf-8")
            with SessionLocal() as db:
                rows = ingest_text(db, source, content, {"format": file.suffix.lower()[1:]})
            if rows:
                saved += 1
                print(f"Saved {source}: {len(rows)} chunks")
            else:
                skipped += 1
                print(f"Skipped empty source: {source}")
        except Exception as error:
            failed += 1
            # Avoid echoing provider exception bodies that may contain submitted text.
            print(f"Failed {file.name}: {type(error).__name__}")
    print(f"Files saved: {saved}; skipped: {skipped}; failed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
