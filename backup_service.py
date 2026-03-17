from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from config import DATABASE_PATH, salon_config
from runtime_state import get_runtime_value, set_runtime_value
from time_utils import get_salon_now


def create_database_backup() -> Path | None:
    source = DATABASE_PATH
    if not source.exists():
        return None

    backup_dir = source.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = backup_dir / f"bookings_{timestamp}.db"
    shutil.copy2(source, destination)
    return destination


def prune_old_backups(keep_last: int = 14) -> None:
    backup_dir = DATABASE_PATH.parent / "backups"
    if not backup_dir.exists():
        return

    backups = sorted(backup_dir.glob("bookings_*.db"), key=lambda item: item.stat().st_mtime, reverse=True)
    for stale_backup in backups[keep_last:]:
        stale_backup.unlink(missing_ok=True)


def run_scheduled_backup_if_due() -> Path | None:
    salon_now = get_salon_now()
    target_hour = int(salon_config.get("backup_hour", 3) or 3)
    today_key = salon_now.date().isoformat()

    if salon_now.hour < target_hour:
        return None

    if get_runtime_value("last_backup_date") == today_key:
        return None

    backup_path = create_database_backup()
    if backup_path is None:
        return None

    prune_old_backups(int(salon_config.get("backup_keep_days", 14) or 14))
    set_runtime_value("last_backup_date", today_key)
    return backup_path
