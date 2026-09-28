import pytest

from fragmentlab import draw


def _vector_chunk(vectors, demo):
    fragment, _ = demo
    return draw.read_chunk(fragment, vectors["draw"]["chunk_index"])


def test_the_draw_matches_the_shared_vector(vectors, demo):
    v = vectors["draw"]
    result = draw.run(_vector_chunk(vectors, demo), v["block_hash"], v["entries"], v["winners"])
    assert result.winners == v["picked"]
    assert result.entries_hash == v["entries_hash"]
    assert result.chunk_commitment == v["chunk_commitment"]


def test_a_different_block_changes_the_winners(vectors, demo):
    v = vectors["draw"]
    other = "0x" + "11" * 32
    assert draw.run(_vector_chunk(vectors, demo), other, v["entries"], 5).winners != v["picked"]


def test_every_entry_can_win_exactly_once(vectors, demo):
    entries = ["a", "b", "c"]
    result = draw.run(_vector_chunk(vectors, demo), "0x" + "22" * 32, entries, 3)
    assert sorted(result.winners) == entries


def test_entries_are_normalised_and_duplicates_refused():
    assert draw.normalise_entries("  alice \n\nbob\n") == ["alice", "bob"]
    with pytest.raises(ValueError):
        draw.normalise_entries("alice\nalice\n")


@pytest.mark.parametrize("winners", [0, 4])
def test_winner_count_is_bounded(vectors, demo, winners):
    with pytest.raises(ValueError):
        draw.run(_vector_chunk(vectors, demo), "0x" + "33" * 32, ["a", "b", "c"], winners)


def test_a_partial_chunk_is_refused():
    with pytest.raises(ValueError):
        draw.run(b"\x00" * 100, "0x" + "44" * 32, ["a"], 1)


def test_read_chunk_refuses_out_of_range(demo):
    fragment, _ = demo
    with pytest.raises(ValueError):
        draw.read_chunk(fragment, 12)
