"""
Hand-written data structures that power FloodWatch.

These are deliberately implemented from scratch (no dict-as-hash-table,
no heapq, no collections.deque) because they ARE the project:

  * HashTable  - separate chaining, used as the primary report index
  * MinHeap    - binary min-heap, the priority queue inside Dijkstra
  * FIFOQueue  - singly linked list queue, the admin verification queue

Every operation reports what it did (bucket index, probe steps, heap
pushes...) so the frontend can visualise the mechanics live.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, Iterator, Optional, TypeVar

T = TypeVar("T")


# --------------------------------------------------------------------------
# Hash table (separate chaining)
# --------------------------------------------------------------------------
@dataclass
class _Entry:
    key: str
    value: Any


class HashTable:
    """Hash table with separate chaining.

    Hash function: sum of character codes mod bucket count. Intentionally
    simple so collisions are easy to provoke and demonstrate.
    """

    ALLOWED_SIZES = (5, 8, 11, 13, 17)

    def __init__(self, size: int = 8, hash_fn: str = "sum") -> None:
        """hash_fn="sum" (default) is the original char-sum hash used for reports.
        hash_fn="poly" is a polynomial rolling hash; our benchmark showed char-sum
        clusters badly on large key sets, so the big Ghana map indexes use "poly"."""
        if size < 1:
            raise ValueError("size must be >= 1")
        if hash_fn not in ("sum", "poly"):
            raise ValueError("hash_fn must be 'sum' or 'poly'")
        self.size = size
        self.hash_fn = hash_fn
        self.buckets: list[list[_Entry]] = [[] for _ in range(size)]
        self.count = 0

    # -- hashing ----------------------------------------------------------
    @staticmethod
    def sum_key(key: str) -> int:
        return sum(ord(c) for c in key)

    @staticmethod
    def poly_key(key: str, size: int) -> int:
        h = 0
        for c in key:                       # h = h*31 + c  (Horner's rule), kept small by mod
            h = (h * 31 + ord(c)) % size
        return h

    def index(self, key: str) -> int:
        if self.hash_fn == "poly":
            return self.poly_key(key, self.size)
        return self.sum_key(key) % self.size

    # -- core operations ----------------------------------------------------
    def put(self, key: str, value: Any) -> bool:
        """Insert or update. Returns True if a new key was inserted."""
        bucket = self.buckets[self.index(key)]
        for entry in bucket:
            if entry.key == key:
                entry.value = value
                return False
        bucket.append(_Entry(key, value))
        self.count += 1
        return True

    def get(self, key: str) -> dict:
        """Lookup with a full probe trace for visualisation."""
        idx = self.index(key)
        visited: list[str] = []
        for entry in self.buckets[idx]:
            visited.append(entry.key)
            if entry.key == key:
                return {"found": True, "index": idx, "steps": len(visited),
                        "visited": visited, "value": entry.value}
        return {"found": False, "index": idx, "steps": len(visited),
                "visited": visited, "value": None}

    def remove(self, key: str) -> bool:
        """Remove key. Fixes the original bug where count was decremented
        even when the key did not exist."""
        bucket = self.buckets[self.index(key)]
        for i, entry in enumerate(bucket):
            if entry.key == key:
                del bucket[i]
                self.count -= 1
                return True
        return False

    def clear(self) -> None:
        self.buckets = [[] for _ in range(self.size)]
        self.count = 0

    def values(self) -> list[Any]:
        return [e.value for bucket in self.buckets for e in bucket]

    def get_value(self, key: str, default: Any = None) -> Any:
        """Convenience lookup without the probe trace (used by the map indexes)."""
        for entry in self.buckets[self.index(key)]:
            if entry.key == key:
                return entry.value
        return default

    def resize(self, new_size: int) -> None:
        old = [(e.key, e.value) for bucket in self.buckets for e in bucket]
        self.size = new_size
        self.clear()
        for k, v in old:
            self.put(k, v)

    # -- introspection ------------------------------------------------------
    def stats(self) -> dict:
        non_empty = sum(1 for b in self.buckets if b)
        return {
            "size": self.size,
            "count": self.count,
            "loadFactor": round(self.count / self.size, 2),
            "collisions": self.count - non_empty,
            "longestChain": max((len(b) for b in self.buckets), default=0),
            "usedBuckets": non_empty,
        }

    def layout(self, label) -> list[list[dict]]:
        """Bucket -> chain of {key, ...label(value)} for the UI."""
        return [[{"key": e.key, **label(e.value)} for e in b] for b in self.buckets]


# --------------------------------------------------------------------------
# Binary min-heap
# --------------------------------------------------------------------------
class MinHeap:
    """Array-backed binary min-heap with operation counters."""

    def __init__(self) -> None:
        self._items: list[tuple[float, Any]] = []
        self.pushes = 0
        self.pops = 0
        self.peak = 0

    def __len__(self) -> int:
        return len(self._items)

    def push(self, priority: float, value: Any) -> None:
        items = self._items
        items.append((priority, value))
        self.pushes += 1
        self.peak = max(self.peak, len(items))
        i = len(items) - 1
        while i > 0:                                  # sift up
            parent = (i - 1) // 2
            if items[parent][0] <= items[i][0]:
                break
            items[parent], items[i] = items[i], items[parent]
            i = parent

    def pop(self) -> Optional[tuple[float, Any]]:
        items = self._items
        if not items:
            return None
        self.pops += 1
        smallest = items[0]
        last = items.pop()
        if items:
            items[0] = last
            i, n = 0, len(items)
            while True:                               # sift down
                l, r, m = 2 * i + 1, 2 * i + 2, i
                if l < n and items[l][0] < items[m][0]:
                    m = l
                if r < n and items[r][0] < items[m][0]:
                    m = r
                if m == i:
                    break
                items[i], items[m] = items[m], items[i]
                i = m
        return smallest


# --------------------------------------------------------------------------
# FIFO queue (singly linked list, O(1) enqueue/dequeue)
# --------------------------------------------------------------------------
@dataclass
class _Node(Generic[T]):
    value: T
    next: Optional["_Node[T]"] = None


class FIFOQueue(Generic[T]):
    def __init__(self) -> None:
        self._head: Optional[_Node[T]] = None
        self._tail: Optional[_Node[T]] = None
        self._len = 0

    def __len__(self) -> int:
        return self._len

    def __iter__(self) -> Iterator[T]:
        node = self._head
        while node:
            yield node.value
            node = node.next

    def __contains__(self, item: T) -> bool:
        return any(v == item for v in self)

    def enqueue(self, value: T) -> None:
        node = _Node(value)
        if self._tail:
            self._tail.next = node
        else:
            self._head = node
        self._tail = node
        self._len += 1

    def dequeue(self) -> Optional[T]:
        if not self._head:
            return None
        node = self._head
        self._head = node.next
        if self._head is None:
            self._tail = None
        self._len -= 1
        return node.value

    def remove(self, value: T) -> bool:
        prev, node = None, self._head
        while node:
            if node.value == value:
                if prev:
                    prev.next = node.next
                else:
                    self._head = node.next
                if node is self._tail:
                    self._tail = prev
                self._len -= 1
                return True
            prev, node = node, node.next
        return False

    def clear(self) -> None:
        self._head = self._tail = None
        self._len = 0


# --------------------------------------------------------------------------
# Binary search (prefix lookup in a sorted list) - powers place-name search
# --------------------------------------------------------------------------
def lower_bound(items: list, target) -> int:
    """First index i with items[i] >= target in a sorted list. O(log n)."""
    lo, hi = 0, len(items)
    while lo < hi:
        mid = (lo + hi) // 2
        if items[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo


def prefix_range(sorted_keys: list[str], prefix: str) -> tuple[int, int]:
    """[start, end) slice of sorted_keys that start with prefix, via two binary searches."""
    start = lower_bound(sorted_keys, prefix)
    end = lower_bound(sorted_keys, prefix + "\uffff")
    return start, end
