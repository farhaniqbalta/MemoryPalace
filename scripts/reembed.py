"""Re-embed stored chunks using the configured provider: python -m scripts.reembed"""
import argparse

from app.core.reembedding import reembed_chunks
from app.db import SessionLocal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force', action='store_true', help='Also regenerate chunks already marked with the target model')
    args = parser.parse_args()
    try:
        with SessionLocal() as db:
            result = reembed_chunks(db, force=args.force)
    except KeyboardInterrupt:
        print('Interrupted. Completed chunks remain saved; rerun to resume.')
        return 130
    return 1 if result.failed or result.remaining else 0


if __name__ == '__main__':
    raise SystemExit(main())
