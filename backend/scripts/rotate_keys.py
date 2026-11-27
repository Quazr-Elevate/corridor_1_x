"""Move stored KYB numbers and their hashes to the newest keys (CX-035, A-080).

    python scripts/rotate_keys.py           # dry run: what would change
    python scripts/rotate_keys.py --apply   # do it

Run it after a new key is deployed (docs/07_development_flow.md, "Rotating
keys"). Safe to run again; it resumes where a stopped run left off. It
prints counts only, never a number.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import crypto  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.modules.verification.key_rotation import rotate  # noqa: E402


async def main(apply: bool) -> None:
    async with SessionLocal() as db:
        report = await rotate(db, apply=apply)
    verb = "Re-encrypted" if apply else "Would re-encrypt"
    print(f"{verb} {report.reencrypted} value(s); {'rehashed' if apply else 'would rehash'} {report.rehashed}; "
          f"{'moved' if apply else 'would move'} {report.quotas_moved} free-quota row(s).")
    if report.quota_clashes:
        print(f"{report.quota_clashes} free-quota row(s) already exist under the new key; the old rows were left as they are.")
    current = crypto.current_version()
    for version in sorted(crypto.configured_versions()):
        count = report.by_version.get(version, 0)
        note = "newest" if version == current else ("can be removed from KYB_ENC_KEYS" if count == 0 else "still in use")
        print(f"  key version {version}: {count} value(s) ({note})")
    if report.totp_secrets:
        print(f"{report.totp_secrets} authenticator secret(s) on file are not rotated by this script yet.")
    if not apply:
        print("Dry run: nothing was written. Add --apply to rotate.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    asyncio.run(main(parser.parse_args().apply))
