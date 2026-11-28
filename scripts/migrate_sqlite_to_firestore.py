"""Migrate existing SQLite data into Google Firebase Cloud Firestore (idempotent & non-destructive).

Usage:
    python scripts/migrate_sqlite_to_firestore.py --source instance/college_events.db --dry-run
    python scripts/migrate_sqlite_to_firestore.py --source instance/college_events.db
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import secrets
import sqlite3
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.firestore_db import COUNTERS_COLLECTION, serialize_dict, sync_counter  # noqa: E402


COLLECTIONS_ORDER = [
    "roles",
    "departments",
    "clubs",
    "event_categories",
    "resources",
    "users",
    "events",
    "event_registrations",
    "volunteer_applications",
    "volunteer_assignments",
    "volunteer_tasks",
    "attendance",
    "certificates",
    "notifications",
    "feedback",
    "event_galleries",
    "volunteer_hours",
    "event_budgets",
    "event_expenses",
    "resource_bookings",
    "student_interests",
]

BOOL_FIELDS = {
    "clubs": {"is_active"},
    "users": {"is_active"},
    "events": {"registration_compulsory"},
    "certificates": {"is_valid"},
    "notifications": {"is_read"},
    "feedback": {"is_anonymous"},
    "resources": {"is_active"},
}

DATETIME_FIELDS = {
    "users": {"created_at", "updated_at"},
    "events": {"registration_deadline", "created_at", "updated_at"},
    "event_registrations": {"registered_at"},
    "volunteer_applications": {"reviewed_at", "created_at"},
    "volunteer_assignments": {"assigned_at"},
    "volunteer_tasks": {"deadline", "created_at", "updated_at"},
    "attendance": {"checked_in_at"},
    "certificates": {"created_at"},
    "notifications": {"created_at"},
    "feedback": {"created_at"},
    "event_galleries": {"created_at"},
    "volunteer_hours": {"recorded_at"},
    "event_budgets": {"created_at"},
    "event_expenses": {"created_at"},
    "resource_bookings": {"created_at"},
    "student_interests": {"created_at"},
}

NUMERIC_FIELDS = {
    "volunteer_hours": {"hours"},
    "event_budgets": {"allocated_amount"},
    "event_expenses": {"amount"},
}


def _parse_dt(val):
    if val is None or isinstance(val, datetime):
        return val
    dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _convert_row(table_name, row_dict):
    converted = dict(row_dict)
    for field in BOOL_FIELDS.get(table_name, ()):
        if field in converted and converted[field] is not None:
            converted[field] = bool(converted[field])
    for field in DATETIME_FIELDS.get(table_name, ()):
        if field in converted and converted[field] is not None:
            converted[field] = _parse_dt(converted[field])
    for field in NUMERIC_FIELDS.get(table_name, ()):
        if field in converted and converted[field] is not None:
            converted[field] = float(converted[field])

    if table_name == "event_registrations" and not converted.get("qr_token"):
        converted["qr_token"] = secrets.token_urlsafe(32)
    if table_name == "volunteer_applications" and not converted.get("qr_token"):
        converted["qr_token"] = secrets.token_urlsafe(32)
    if table_name == "events" and "registration_compulsory" not in converted:
        converted["registration_compulsory"] = False
    return serialize_dict(converted)


def migrate_sqlite_to_firestore(sqlite_path, client, dry_run=False, overwrite=False):
    """Export all tables from SQLite into Cloud Firestore, preserving IDs and syncing counters."""
    source = Path(sqlite_path)
    if not source.exists():
        raise FileNotFoundError(f"SQLite source database not found: {source}")

    conn = sqlite3.connect(str(source))
    conn.row_factory = sqlite3.Row
    try:
        existing_tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        summary = {}
        for collection_name in COLLECTIONS_ORDER:
            if collection_name not in existing_tables:
                summary[collection_name] = {
                    "sqlite_rows": 0,
                    "written": 0,
                    "skipped": 0,
                    "firestore_total": 0,
                }
                continue

            rows = conn.execute(f'SELECT * FROM "{collection_name}"').fetchall()
            sqlite_count = len(rows)

            existing_ids = set()
            if not overwrite:
                for snap in client.collection(collection_name).stream():
                    existing_ids.add(snap.id)

            to_write = []
            max_id = 0
            skipped = 0
            for row in rows:
                row_dict = _convert_row(collection_name, dict(row))
                doc_id = row_dict["id"]
                if isinstance(doc_id, int) and doc_id > max_id:
                    max_id = doc_id
                if not overwrite and str(doc_id) in existing_ids:
                    skipped += 1
                    continue
                to_write.append((str(doc_id), row_dict))

            if not dry_run:
                for start in range(0, len(to_write), 450):
                    batch = client.batch()
                    for doc_id_str, payload in to_write[start : start + 450]:
                        doc_ref = client.collection(collection_name).document(doc_id_str)
                        batch.set(doc_ref, payload)
                    batch.commit()

                if max_id > 0:
                    sync_counter(collection_name, max_id, client=client)

                firestore_total = len(list(client.collection(collection_name).stream()))
            else:
                firestore_total = len(existing_ids) + len(to_write)

            summary[collection_name] = {
                "sqlite_rows": sqlite_count,
                "written": len(to_write),
                "skipped": skipped,
                "firestore_total": firestore_total,
            }
        return summary
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Migrate existing SQLite data to Google Cloud Firestore."
    )
    parser.add_argument(
        "--source",
        default="instance/college_events.db",
        help="Path to source SQLite .db file (default: instance/college_events.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview record counts without writing to Firestore.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing Firestore documents with matching IDs.",
    )
    args = parser.parse_args()

    from app import create_app
    from app.firebase_config import get_firestore_client

    app = create_app()
    with app.app_context():
        client = get_firestore_client()
        summary = migrate_sqlite_to_firestore(
            args.source,
            client,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        )

    mode = "DRY-RUN" if args.dry_run else "MIGRATED"
    print(f"=== SQLite -> Firestore ({mode}) from {args.source} ===")
    all_valid = True
    for name, stats in summary.items():
        status = "OK" if stats["firestore_total"] >= stats["sqlite_rows"] else "MISMATCH"
        if status != "OK":
            all_valid = False
        print(
            f"{name:24s} sqlite={stats['sqlite_rows']:4d}  "
            f"written={stats['written']:4d}  skipped={stats['skipped']:4d}  "
            f"firestore={stats['firestore_total']:4d}  [{status}]"
        )
    if not all_valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
