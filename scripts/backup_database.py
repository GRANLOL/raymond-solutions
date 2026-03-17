from __future__ import annotations

from backup_service import create_database_backup
from config import DATABASE_PATH


def main() -> int:
    backup_path = create_database_backup()
    if backup_path is None:
        print(f"Database not found: {DATABASE_PATH}")
        return 1

    print(backup_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
