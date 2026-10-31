"""Create an admin account from the command line (servers, recovery).

    python scripts/create_admin.py --email ops@corridor1x.com --name "Ops Lead" --role super_admin
    python scripts/create_admin.py --bootstrap-from-env

The first form prints a one-time temporary password (the admin sets their
own at first sign-in) — run it in a private terminal. ``--bootstrap-from-env``
creates the first super admin from ADMIN_EMAIL / ADMIN_PASSWORD_HASH (what
the first admin sign-in would do) and is a no-op when admins exist.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.core.security import hash_password, temporary_password  # noqa: E402
from app.models.admin_user import AdminRole, AdminUser  # noqa: E402


async def main(args: argparse.Namespace) -> int:
    async with SessionLocal() as db:
        if args.bootstrap_from_env:
            if await db.scalar(select(func.count()).select_from(AdminUser)):
                print("Admins already exist — nothing to do.")
                return 0
            if not settings.admin_password_hash:
                print("ADMIN_PASSWORD_HASH is not set.", file=sys.stderr)
                return 1
            db.add(AdminUser(
                email=settings.admin_email.strip().lower(), full_name="Super admin", role=AdminRole.super_admin,
                password_hash=settings.admin_password_hash, created_by="bootstrap",
            ))
            await db.commit()
            print(f"Super admin {settings.admin_email} created from the environment.")
            return 0

        email = args.email.strip().lower()
        if await db.scalar(select(AdminUser.id).where(AdminUser.email == email)):
            print(f"{email} already exists.", file=sys.stderr)
            return 1
        password = temporary_password()
        db.add(AdminUser(
            email=email, full_name=args.name.strip(), role=AdminRole(args.role),
            password_hash=hash_password(password), must_change_password=True, created_by="cli",
        ))
        await db.commit()
        if args.password_file:
            Path(args.password_file).write_text(password + "\n")
            print(f"{email} created ({args.role}); temporary password written to {args.password_file}.")
        else:
            print(f"{email} created ({args.role}). Temporary password (shown once): {password}")
        return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bootstrap-from-env", action="store_true")
    p.add_argument("--email")
    p.add_argument("--name", default="Admin")
    p.add_argument("--role", choices=[r.value for r in AdminRole], default="reviewer")
    p.add_argument("--password-file", help="write the temporary password here instead of printing it")
    a = p.parse_args()
    if not a.bootstrap_from_env and not a.email:
        p.error("--email is required (or use --bootstrap-from-env)")
    raise SystemExit(asyncio.run(main(a)))
