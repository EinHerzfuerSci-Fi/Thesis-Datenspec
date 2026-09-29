from datenspec.dedup import record_key
from datenspec.timestamps import fill_missing_ts


def test_fills_from_later_synced_record(make_record) -> None:
    early = make_record(seq=0, up=5.0, ts=None)
    synced = make_record(seq=1, up=65.0, ts=1_700_000_065)
    result = fill_missing_ts([early, synced])
    assert result.records[0].timestamp == 1_700_000_005
    assert result.records[1] is synced
    assert result.reconstructed == {record_key(early)}
    assert result.unresolved == set()


def test_uses_nearest_sync_after_clock_jump(make_record) -> None:
    # Second sync corrected the clock by +10 s; each gap uses the closer offset.
    first = make_record(seq=0, up=100.0, ts=1_000_100)
    second = make_record(seq=1, up=200.0, ts=1_000_210)
    near_first = make_record(seq=2, up=120.0, ts=None)
    near_second = make_record(seq=3, up=190.0, ts=None)
    result = fill_missing_ts([first, second, near_first, near_second])
    assert result.records[2].timestamp == 1_000_120
    assert result.records[3].timestamp == 1_000_200


def test_tie_goes_to_earlier_sync(make_record) -> None:
    a = make_record(seq=0, up=100.0, ts=1_000_100)
    b = make_record(seq=1, up=200.0, ts=1_000_210)
    middle = make_record(seq=2, up=150.0, ts=None)
    assert fill_missing_ts([a, b, middle]).records[2].timestamp == 1_000_150


def test_offset_does_not_cross_boots(make_record) -> None:
    synced = make_record(boot=1, seq=0, up=10.0, ts=1_000_010)
    other_boot = make_record(boot=2, seq=0, up=10.0, ts=None)
    result = fill_missing_ts([synced, other_boot])
    assert result.records[1].timestamp is None
    assert result.unresolved == {record_key(other_boot)}
    assert result.reconstructed == set()


def test_rounds_to_integer_seconds(make_record) -> None:
    synced = make_record(seq=0, up=10.0, ts=1_000_010)
    gap = make_record(seq=1, up=12.6, ts=None)
    ts = fill_missing_ts([synced, gap]).records[1].timestamp
    assert ts == 1_000_013
    assert isinstance(ts, int)


def test_input_order_is_kept(make_record) -> None:
    records = [
        make_record(seq=2, up=30.0, ts=None),
        make_record(seq=0, up=10.0, ts=1_000_010),
        make_record(seq=1, up=20.0, ts=None),
    ]
    out = fill_missing_ts(records).records
    assert [r.seq for r in out] == [2, 0, 1]
