"""In-memory Firestore client matching google.cloud.firestore for isolated testing."""

from copy import deepcopy
from datetime import datetime, timezone
import secrets


def _normalize_for_compare(value):
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _match_filter(data, field_path, op_string, target):
    if data is None:
        return False
    actual = data.get(field_path)
    actual_cmp = _normalize_for_compare(actual)
    target_cmp = _normalize_for_compare(target)

    if op_string == "==":
        return actual_cmp == target_cmp
    if op_string == "!=":
        return actual_cmp != target_cmp
    if op_string == "in":
        return actual_cmp in [ _normalize_for_compare(item) for item in (target or []) ]
    if actual_cmp is None or target_cmp is None:
        return False
    if op_string == "<":
        return actual_cmp < target_cmp
    if op_string == "<=":
        return actual_cmp <= target_cmp
    if op_string == ">":
        return actual_cmp > target_cmp
    if op_string == ">=":
        return actual_cmp >= target_cmp
    raise ValueError(f"Unsupported Firestore filter operator: {op_string}")


class InMemoryDocumentSnapshot:
    def __init__(self, doc_id, data):
        self.id = str(doc_id)
        self._data = deepcopy(data) if data is not None else None

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return deepcopy(self._data) if self._data is not None else None


class InMemoryDocumentRef:
    def __init__(self, client, collection_name, doc_id):
        self._client = client
        self._collection_name = collection_name
        self.id = str(doc_id)

    def get(self, transaction=None):
        store = self._client._store.setdefault(self._collection_name, {})
        return InMemoryDocumentSnapshot(self.id, store.get(self.id))

    def set(self, data, merge=False):
        store = self._client._store.setdefault(self._collection_name, {})
        if merge and self.id in store:
            merged = deepcopy(store[self.id])
            merged.update(deepcopy(data))
            store[self.id] = merged
        else:
            store[self.id] = deepcopy(data)

    def update(self, updates):
        store = self._client._store.setdefault(self._collection_name, {})
        if self.id not in store:
            raise KeyError(f"Document {self._collection_name}/{self.id} does not exist.")
        store[self.id].update(deepcopy(updates))

    def delete(self):
        store = self._client._store.setdefault(self._collection_name, {})
        store.pop(self.id, None)


class InMemoryQuery:
    def __init__(self, client, collection_name, filters=None, limit_count=None):
        self._client = client
        self._collection_name = collection_name
        self._filters = list(filters or [])
        self._limit_count = limit_count

    def where(self, field_path=None, op_string=None, value=None, *, filter=None):
        if filter is not None:
            field_path = filter.field_path
            op_string = filter.op_string
            value = filter.value
        return InMemoryQuery(
            self._client,
            self._collection_name,
            self._filters + [(field_path, op_string, value)],
            self._limit_count,
        )

    def limit(self, count):
        return InMemoryQuery(
            self._client,
            self._collection_name,
            self._filters,
            count,
        )

    def stream(self):
        store = self._client._store.get(self._collection_name, {})
        results = []
        for doc_id, data in list(store.items()):
            if all(_match_filter(data, fp, op, val) for fp, op, val in self._filters):
                results.append(InMemoryDocumentSnapshot(doc_id, data))
                if self._limit_count is not None and len(results) >= self._limit_count:
                    break
        return iter(results)

    def get(self):
        return list(self.stream())


class InMemoryCollection(InMemoryQuery):
    def __init__(self, client, collection_name):
        super().__init__(client, collection_name)

    def document(self, doc_id=None):
        resolved_id = str(doc_id) if doc_id is not None else secrets.token_hex(10)
        return InMemoryDocumentRef(self._client, self._collection_name, resolved_id)


class InMemoryWriteBatch:
    def __init__(self, client):
        self._client = client
        self._ops = []

    def set(self, doc_ref, data, merge=False):
        self._ops.append(("set", doc_ref, data, merge))

    def update(self, doc_ref, updates):
        self._ops.append(("update", doc_ref, updates, False))

    def delete(self, doc_ref):
        self._ops.append(("delete", doc_ref, None, False))

    def commit(self):
        for action, doc_ref, payload, merge in self._ops:
            if action == "set":
                doc_ref.set(payload, merge=merge)
            elif action == "update":
                doc_ref.update(payload)
            elif action == "delete":
                doc_ref.delete()
        self._ops.clear()


class InMemoryTransaction(InMemoryWriteBatch):
    def get(self, doc_ref):
        return doc_ref.get()


class InMemoryFirestoreClient:
    def __init__(self):
        self._store = {}

    def collection(self, name):
        return InMemoryCollection(self, name)

    def batch(self):
        return InMemoryWriteBatch(self)

    def transaction(self):
        return InMemoryTransaction(self)
