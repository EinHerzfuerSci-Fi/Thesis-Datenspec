"""
Remove duplicate records.

Duplicates are expected: QoS 1 may deliver a message twice, and SD replay resends
records that already went out over MQTT. (dev, boot, seq) identifies a record.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from datenspec.models import Record

type RecordKey = tuple[str, int, int]


def record_key(record: Record) -> RecordKey:
    return (record.device_id, record.boot, record.seq)


@dataclass(frozen=True)
class Conflict:
    """Same key, different content: a firmware bug (e.g. seq reuse), not a resend."""

    key: RecordKey
    kept: Record
    dropped: Record


@dataclass(frozen=True)
class DedupResult:
    records: list[Record] = field(default_factory=list)
    dropped: int = 0
    conflicts: list[Conflict] = field(default_factory=list)


def deduplicate(records: Iterable[Record]) -> DedupResult:
    """Keep the first record per key, in input order."""
    first: dict[RecordKey, Record] = {}
    conflicts: list[Conflict] = []
    dropped = 0
    for record in records:
        key = record_key(record)
        kept = first.setdefault(key, record)
        if kept is record:
            continue
        dropped += 1
        if record != kept:
            conflicts.append(Conflict(key, kept, record))
    return DedupResult(list(first.values()), dropped, conflicts)
