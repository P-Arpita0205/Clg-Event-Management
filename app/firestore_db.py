"""Cloud Firestore data access helpers, transactions, batch writes, and serialization."""

from datetime import date, datetime, time, timezone
from decimal import Decimal

from flask import has_request_context, request

from app.firebase_config import get_firestore_client
from app.firestore_memory import InMemoryFirestoreClient


COUNTERS_COLLECTION = "_counters"


def _invalidate_request_cache():
    if not has_request_context():
        return
    if hasattr(request, "_fs_doc_cache"):
        delattr(request, "_fs_doc_cache")
    if hasattr(request, "_fs_all_cache"):
        delattr(request, "_fs_all_cache")


def _doc_cache():
    if not has_request_context():
        return None
    cache = getattr(request, "_fs_doc_cache", None)
    if cache is None:
        cache = {}
        request._fs_doc_cache = cache
    return cache


def _all_cache():
    if not has_request_context():
        return None
    cache = getattr(request, "_fs_all_cache", None)
    if cache is None:
        cache = {}
        request._fs_all_cache = cache
    return cache


def to_firestore_value(value):
    """Convert Python domain types to Firestore-native serializable values."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.strftime("%H:%M:%S")
    if isinstance(value, list):
        return [to_firestore_value(item) for item in value]
    if isinstance(value, dict):
        return {k: to_firestore_value(v) for k, v in value.items()}
    return value


def serialize_dict(data):
    """Serialize a dictionary of fields for Firestore storage."""
    return {key: to_firestore_value(val) for key, val in data.items()}


def parse_date(value):
    if value is None or (isinstance(value, date) and not isinstance(value, datetime)):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value)[:10])


def parse_time(value):
    if value is None or isinstance(value, time):
        return value
    raw = str(value).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    return time.fromisoformat(raw)


def parse_datetime(value, naive=False):
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if naive:
        return dt.replace(tzinfo=None)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_decimal(value, default="0"):
    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def run_transaction(callback):
    """Execute callback(transaction) inside a real Firestore or in-memory transaction."""
    client = get_firestore_client()
    if isinstance(client, InMemoryFirestoreClient):
        tx = client.transaction()
        result = callback(tx)
        tx.commit()
        _invalidate_request_cache()
        return result

    from google.cloud import firestore as gcf

    @gcf.transactional
    def _runner(transaction):
        return callback(transaction)

    result = _runner(client.transaction())
    _invalidate_request_cache()
    return result


def next_id(collection_name, client=None):
    """Atomically allocate the next integer ID for a Firestore collection."""
    target_client = client or get_firestore_client()

    def _allocate(transaction):
        counter_ref = target_client.collection(COUNTERS_COLLECTION).document(collection_name)
        snapshot = counter_ref.get(transaction=transaction)
        current = int(snapshot.to_dict().get("seq", 0)) if snapshot.exists else 0
        new_seq = current + 1
        transaction.set(counter_ref, {"seq": new_seq})
        return new_seq

    if isinstance(target_client, InMemoryFirestoreClient):
        tx = target_client.transaction()
        seq = _allocate(tx)
        tx.commit()
        return seq

    from google.cloud import firestore as gcf

    @gcf.transactional
    def _runner(transaction):
        return _allocate(transaction)

    return _runner(target_client.transaction())


def sync_counter(collection_name, min_seq, client=None):
    """Ensure _counters/<collection_name>.seq is at least min_seq."""
    target_client = client or get_firestore_client()

    def _sync(transaction):
        counter_ref = target_client.collection(COUNTERS_COLLECTION).document(collection_name)
        snapshot = counter_ref.get(transaction=transaction)
        current = int(snapshot.to_dict().get("seq", 0)) if snapshot.exists else 0
        if min_seq > current:
            transaction.set(counter_ref, {"seq": int(min_seq)})
            return int(min_seq)
        return current

    if isinstance(target_client, InMemoryFirestoreClient):
        tx = target_client.transaction()
        res = _sync(tx)
        tx.commit()
        return res

    from google.cloud import firestore as gcf

    @gcf.transactional
    def _runner(transaction):
        return _sync(transaction)

    return _runner(target_client.transaction())


def _snapshot_to_dict(snapshot):
    if not snapshot.exists:
        return None
    data = snapshot.to_dict() or {}
    if "id" not in data:
        try:
            data["id"] = int(snapshot.id)
        except ValueError:
            data["id"] = snapshot.id
    return data


def get_doc(collection_name, doc_id):
    if doc_id is None:
        return None
    key = (collection_name, str(doc_id))
    cache = _doc_cache()
    if cache is not None and key in cache:
        return dict(cache[key]) if cache[key] is not None else None

    client = get_firestore_client()
    snapshot = client.collection(collection_name).document(str(doc_id)).get()
    data = _snapshot_to_dict(snapshot)
    if cache is not None:
        cache[key] = dict(data) if data is not None else None
    return data


def _where_eq(query, field, value, client):
    normalized = to_firestore_value(value)
    if isinstance(client, InMemoryFirestoreClient):
        return query.where(field, "==", normalized)
    from google.cloud.firestore_v1.base_query import FieldFilter

    return query.where(filter=FieldFilter(field, "==", normalized))


def list_docs(collection_name, filters=None):
    """Fetch documents from a collection matching equality filters."""
    filters = filters or {}
    all_cache = _all_cache()
    if not filters and all_cache is not None and collection_name in all_cache:
        return [dict(item) for item in all_cache[collection_name]]

    client = get_firestore_client()
    query = client.collection(collection_name)

    remaining_filters = {}
    if filters:
        # Use a single server-side equality filter to avoid requiring composite indexes.
        first_key = next(iter(filters))
        first_val = filters[first_key]
        if first_val is not None:
            query = _where_eq(query, first_key, first_val, client)
            remaining_filters = {k: v for k, v in filters.items() if k != first_key}
        else:
            remaining_filters = dict(filters)

    docs = []
    doc_cache = _doc_cache()
    for snapshot in query.stream():
        data = _snapshot_to_dict(snapshot)
        if data is None:
            continue
        if doc_cache is not None:
            doc_cache[(collection_name, str(data["id"]))] = dict(data)
        if all(data.get(k) == to_firestore_value(v) for k, v in remaining_filters.items()):
            docs.append(data)

    if not filters and all_cache is not None:
        all_cache[collection_name] = [dict(item) for item in docs]
    return docs


def find_one(collection_name, **filters):
    results = list_docs(collection_name, filters=filters)
    return results[0] if results else None


def count_docs(collection_name, **filters):
    return len(list_docs(collection_name, filters=filters))


def create_doc(collection_name, data, doc_id=None):
    client = get_firestore_client()
    assigned_id = int(doc_id) if doc_id is not None else next_id(collection_name, client=client)
    payload = serialize_dict(data)
    payload["id"] = assigned_id
    client.collection(collection_name).document(str(assigned_id)).set(payload)
    _invalidate_request_cache()
    return payload


def update_doc(collection_name, doc_id, updates):
    client = get_firestore_client()
    payload = serialize_dict(updates)
    payload["id"] = int(doc_id)
    client.collection(collection_name).document(str(doc_id)).set(payload, merge=True)
    _invalidate_request_cache()
    return payload


def delete_doc(collection_name, doc_id):
    client = get_firestore_client()
    client.collection(collection_name).document(str(doc_id)).delete()
    _invalidate_request_cache()


def batch_write(operations):
    """Execute ('set'|'update'|'delete', collection, doc_id, payload) in 450-op chunks."""
    if not operations:
        return
    client = get_firestore_client()
    chunk_size = 450
    for start in range(0, len(operations), chunk_size):
        batch = client.batch()
        for op in operations[start : start + chunk_size]:
            action = op[0]
            collection_name = op[1]
            doc_id = str(op[2])
            doc_ref = client.collection(collection_name).document(doc_id)
            if action == "set":
                payload = serialize_dict(op[3])
                payload["id"] = int(op[2]) if str(op[2]).isdigit() else op[2]
                batch.set(doc_ref, payload)
            elif action == "update":
                payload = serialize_dict(op[3])
                batch.update(doc_ref, payload)
            elif action == "delete":
                batch.delete(doc_ref)
            else:
                raise ValueError(f"Unknown batch action: {action}")
        batch.commit()
    _invalidate_request_cache()


def check_connection():
    """Verify Firestore connectivity by performing a lightweight collection read."""
    client = get_firestore_client()
    list(client.collection("roles").limit(1).stream())
    return True
