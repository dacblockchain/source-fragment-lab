import json

import pytest

from fragmentlab.pool import FragmentExhausted, FragmentPool


def test_bytes_are_never_handed_out_twice(demo):
    fragment, _ = demo
    raw = fragment.read_bytes()
    first, second = FragmentPool(fragment).take(10), FragmentPool(fragment).take(10)
    assert first == raw[:10] and second == raw[10:20]
    assert FragmentPool(fragment).consumed == 20


def test_mixed_consumes_32_bytes(demo):
    fragment, _ = demo
    pool = FragmentPool(fragment)
    pool.mixed("test", 64)
    assert pool.consumed == 32 and pool.remaining == pool.size - 32


def test_exhaustion_does_not_move_the_cursor(demo):
    fragment, _ = demo
    pool = FragmentPool(fragment)
    pool.take(pool.size - 5)
    with pytest.raises(FragmentExhausted):
        pool.take(6)
    assert pool.remaining == 5


def test_take_chunk_skips_to_the_next_boundary(demo):
    fragment, _ = demo
    pool = FragmentPool(fragment)
    pool.take(1)
    index, chunk = pool.take_chunk()
    assert index == 1 and chunk == fragment.read_bytes()[2048:4096]
    assert pool.consumed == 4096


def test_a_corrupt_cursor_is_refused(demo):
    fragment, _ = demo
    pool = FragmentPool(fragment)
    pool.cursor_path.write_text(json.dumps({"format": "x", "consumed": 1}))
    with pytest.raises(ValueError):
        pool.take(1)


def test_a_missing_fragment_is_refused(tmp_path):
    with pytest.raises(FileNotFoundError):
        FragmentPool(tmp_path / "nope.bin")


def _drain(path: str, draws: int) -> list[bytes]:
    pool = FragmentPool(path)
    return [pool.take(32) for _ in range(draws)]


def test_concurrent_processes_never_share_bytes(demo):
    import multiprocessing

    fragment, _ = demo
    workers, draws = 6, 20
    with multiprocessing.get_context("spawn").Pool(workers) as procs:
        results = procs.starmap(_drain, [(str(fragment), draws)] * workers)
    handed_out = [chunk for batch in results for chunk in batch]
    raw = fragment.read_bytes()
    expected = {raw[i : i + 32] for i in range(0, workers * draws * 32, 32)}
    assert len(handed_out) == workers * draws
    assert set(handed_out) == expected  # every window exactly once, none skipped
    assert FragmentPool(fragment).consumed == workers * draws * 32
