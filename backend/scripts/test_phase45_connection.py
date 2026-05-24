"""Quick Phase 4.5 connectivity check (run from repo root).

  py backend/scripts/test_phase45_connection.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings
from backend.app.db.session import database_configured, session_scope
from sqlalchemy import text


def main() -> int:
    print("SUPABASE_URL:", "set" if settings.supabase_url else "MISSING")
    print("SUPABASE_JWT_SECRET:", "set" if settings.resolved_supabase_jwt_secret() else "MISSING")
    print("DATABASE_URL:", "set" if settings.resolved_database_url() else "MISSING")

    if not database_configured():
        print("\nFAIL: DATABASE_URL is not configured.")
        return 1

    url = settings.resolved_database_url()
    if url.startswith("postgresql://") and "+psycopg" not in url:
        print("\nWARN: Use postgresql+psycopg:// for SQLAlchemy (not postgresql:// only).")

    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
        print("\nOK: Database connection succeeded.")
    except Exception as exc:
        print(f"\nFAIL: Database connection failed: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
