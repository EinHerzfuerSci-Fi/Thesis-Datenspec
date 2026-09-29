"""
Remove duplicate records.

Duplicates are expected: QoS 1 may deliver a message twice, and SD replay resends
records that already went out over MQTT. seq counts per kind: per run for data, per boot
for everything else, so a record is identified by (dev, run, seq) for data and by
(dev, boot, k, seq) otherwise.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from datenspec.models import Record

type RecordKey = tuple[str, str, int, int]
"""(dev, k, scope, seq), scope being run for data and boot for all other kinds."""


def record_key(record: Record) -> RecordKey:
    scope = record.run if record.kind == "data" else record.boot
    return (record.device_id, record.kind, scope, record.seq)


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
