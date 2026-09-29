from datenspec.dedup import deduplicate, record_key


def test_data_key_is_dev_run_seq(make_record) -> None:
    r = make_record("data", run=4, seq=7, boot=2)
    assert record_key(r) == ("e6614104032b5a2c", "data", 4, 7)


def test_other_kinds_key_is_dev_boot_kind_seq(make_record) -> None:
    r = make_record("tele", run=4, seq=7, boot=2)
    assert record_key(r) == ("e6614104032b5a2c", "tele", 2, 7)


def test_identical_resend_is_dropped_silently(make_record) -> None:
    a, b = make_record(seq=1), make_record(seq=2)
    result = deduplicate([a, b, make_record(seq=1)])
    assert result.records == [a, b]
    assert result.dropped == 1
    assert result.conflicts == []


def test_first_occurrence_wins_and_conflict_is_reported(make_record) -> None:
    first = make_record(seq=1, up=10.0)
    other = make_record(seq=1, up=99.0)
    result = deduplicate([first, other])
    assert result.records == [first]
    assert len(result.conflicts) == 1
    assert result.conflicts[0].kept is first
    assert result.conflicts[0].dropped is other


def test_same_seq_in_other_boot_or_device_is_kept(make_record) -> None:
    records = [
        make_record("tele", seq=1),
        make_record("tele", seq=1, boot=4),
        make_record("tele", seq=1, dev="0000000000000001"),
    ]
    assert deduplicate(records).records == records


def test_data_seq_restarts_per_run(make_record) -> None:
    records = [make_record("data", run=7, seq=0), make_record("data", run=8, seq=0)]
    assert deduplicate(records).records == records


def test_same_seq_in_other_kind_is_kept(make_record) -> None:
    # seq counts per kind, so equal numbers across kinds are distinct records.
    records = [make_record("data", seq=5), make_record("tele", seq=5)]
    result = deduplicate(records)
    assert result.records == records
    assert result.conflicts == []
