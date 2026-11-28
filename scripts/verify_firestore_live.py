"""Verify live Google Cloud Firestore connectivity, CRUD operations, and collection counts."""

from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app  # noqa: E402
from app.firebase_config import get_firestore_client  # noqa: E402


COLLECTIONS = [
    "roles",
    "departments",
    "clubs",
    "event_categories",
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
    "resources",
    "resource_bookings",
    "student_interests",
]


def main():
    app = create_app()
    if app.config.get("FIRESTORE_BACKEND") == "memory":
        print("ERROR: FIRESTORE_BACKEND is set to 'memory'. Set FIRESTORE_BACKEND=firestore in .env.")
        raise SystemExit(1)

    with app.app_context():
        client = get_firestore_client()
        probe_ref = client.collection("_verification").document("health_probe")
        probe_ref.set({"checked_at": datetime.now(timezone.utc), "status": "ok"})
        snap = probe_ref.get()
        assert snap.exists and snap.to_dict().get("status") == "ok"
        probe_ref.update({"status": "updated"})
        assert probe_ref.get().to_dict().get("status") == "updated"
        probe_ref.delete()
        assert not probe_ref.get().exists

        print(f"Live Firestore write/read/update/delete check PASSED for project: {app.config.get('FIREBASE_PROJECT_ID')}")
        print("\n=== Firestore Collection Counts ===")
        for col in COLLECTIONS:
            count = len(list(client.collection(col).stream()))
            print(f"{col:24s}: {count}")


if __name__ == "__main__":
    main()
