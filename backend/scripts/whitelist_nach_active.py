"""Once: whoever is not on the whitelist loses active, after that nobody reads the table."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import database  # noqa: E402


def main() -> int:
    with database.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users SET active = 0
                WHERE active = 1
                  AND email IS NOT NULL
                  AND email <> ''
                  AND LOWER(email) NOT IN (SELECT LOWER(email) FROM whitelist)
            """)
            gesperrt = cur.rowcount
        conn.commit()
    print(f"Gesperrt, weil nicht auf der Liste: {gesperrt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
