"""
Fill missing `ts` from synchronized records of the same boot.

`up` and `ts` are captured together, so `ts - up` is the boot's clock offset. It only
holds within one boot (up restarts at 0), and it shifts when NTP re-syncs; using the
offset of the nearest synced record in `up` keeps the error of such a shift local.
"""

from bisect import bisect_left
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from datenspec.dedup import RecordKey, record_key
from datenspec.models import Record

type BootKey = tuple[str, int]


@dataclass(frozen=True)
class TsResult:
    records: list[Record] = field(default_factory=list)
    reconstructed: set[RecordKey] = field(default_factory=set)
    """Keys whose ts was filled in, so analysis can tell measured from derived times."""
    unresolved: set[RecordKey] = field(default_factory=set)
    """Keys left at ts=None because their boot has no synced record at all."""


def _nearest_offset(ups: list[float], offsets: list[float], up: float) -> float:
    i = bisect_left(ups, up)
    candidates = [j for j in (i - 1, i) if 0 <= j < len(ups)]
    # Ties go to the earlier sync: min() keeps the first of equal distances.
    best = min(candidates, key=lambda j: abs(ups[j] - up))
    return offsets[best]


def fill_missing_ts(records: Iterable[Record]) -> TsResult:
    """
    Return the records in input order, with ts = round(up + offset) where it was null.
    Rounded because ts is integer seconds on the wire; keep `up` for intervals.
    """
    records = list(records)
    synced: dict[BootKey, list[tuple[float, float]]] = defaultdict(list)
    for r in records:
        if r.timestamp is not None:
            synced[(r.device_id, r.boot)].append((r.uptime, r.timestamp - r.uptime))

    tables = {
        boot: ([u for u, _ in sorted(pairs)], [o for _, o in sorted(pairs)])
        for boot, pairs in synced.items()
    }

    result = TsResult()
    for r in records:
        if r.timestamp is not None:
            result.records.append(r)
            continue
        table = tables.get((r.device_id, r.boot))
        if table is None:
            result.unresolved.add(record_key(r))
            result.records.append(r)
            continue
        ts = round(r.uptime + _nearest_offset(*table, r.uptime))
        result.records.append(r.model_copy(update={"timestamp": ts}))
        result.reconstructed.add(record_key(r))
    return result
