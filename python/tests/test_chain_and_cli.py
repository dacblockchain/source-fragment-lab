import io
import json

import pytest

from fragmentlab import chain, cli


class _Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def rpc(monkeypatch):
    """Answer JSON-RPC calls from a dict of method → result."""
    answers, calls = {}, []

    def fake_urlopen(request, timeout):
        body = json.loads(request.data)
        calls.append(body)
        return _Reply(json.dumps({"jsonrpc": "2.0", "id": 1, "result": answers[body["method"]]}).encode())

    monkeypatch.setattr(chain.urllib.request, "urlopen", fake_urlopen)
    return answers, calls


def test_root_of_encodes_the_call(rpc):
    answers, calls = rpc
    answers["eth_call"] = "0x" + "ab" * 32
    assert chain.root_of(5) == "0x" + "ab" * 32
    call = calls[0]["params"][0]
    assert call["to"] == chain.RESERVOIR_ANCHOR
    assert call["data"] == "0x9d7384d9" + "00" * 31 + "05"


def test_block_hash_waits_for_confirmations(rpc):
    answers, _ = rpc
    answers["eth_blockNumber"] = hex(105)
    answers["eth_getBlockByNumber"] = {"hash": "0x" + "cd" * 32}
    with pytest.raises(chain.ChainError, match="5 of 12"):
        chain.block_hash(100)
    assert chain.block_hash(100, confirmations=5) == "0x" + "cd" * 32


def test_block_hash_not_mined_yet(rpc):
    answers, _ = rpc
    answers["eth_blockNumber"] = hex(10**12 + 50)
    answers["eth_getBlockByNumber"] = None
    with pytest.raises(chain.ChainError):
        chain.block_hash(10**12)


def test_cli_verify_offline(demo, capsys):
    fragment, proof = demo
    assert cli.main(["verify", str(fragment), str(proof), "--offline"]) == 0
    assert "AUTHENTIC" in capsys.readouterr().out


def test_cli_verify_against_the_chain(demo, rpc, capsys):
    fragment, proof = demo
    roots = [r["root"] for r in json.loads(proof.read_text())["ranges"]]
    answers, _ = rpc
    answers["eth_call"] = roots[0]  # version 2 then mismatches: same answer for both calls
    assert cli.main(["verify", str(fragment), str(proof)]) == 1
    out = capsys.readouterr().out
    assert "rootOf(1)" in out and "OK" in out and "MISMATCH" in out


def test_cli_verify_reports_unanchored_versions(demo, rpc, capsys):
    fragment, proof = demo
    rpc[0]["eth_call"] = cli.ZERO_ROOT
    assert cli.main(["verify", str(fragment), str(proof)]) == 1
    assert "nothing anchored" in capsys.readouterr().out


def test_cli_keys_write_private_files(demo, tmp_path, capsys):
    fragment, _ = demo
    out = tmp_path / "id.key"
    assert cli.main(["keys", "ed25519", "--fragment", str(fragment), "--out", str(out)]) == 0
    assert out.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "id.key.pub").exists()
    # never overwrites an existing key
    assert cli.main(["keys", "ed25519", "--fragment", str(fragment), "--out", str(out)]) == 1


def test_cli_encrypt_decrypt(demo, tmp_path):
    fragment, _ = demo
    key, plain, sealed, back = (tmp_path / n for n in ("k", "p", "s", "b"))
    plain.write_bytes(b"secret" * 1000)
    assert cli.main(["secret-key", "--fragment", str(fragment), "--out", str(key)]) == 0
    assert cli.main(["encrypt", str(plain), str(sealed), "--key", str(key)]) == 0
    assert cli.main(["decrypt", str(sealed), str(back), "--key", str(key)]) == 0
    assert back.read_bytes() == plain.read_bytes()


def test_cli_draw_commit_then_run(demo, tmp_path, capsys, vectors):
    fragment, _ = demo
    assert cli.main(["draw-commit", "--fragment", str(fragment)]) == 0
    committed = json.loads(capsys.readouterr().out)
    entries = tmp_path / "entries.txt"
    entries.write_text("\n".join(vectors["draw"]["entries"]))
    args = [
        "draw", "--fragment", str(fragment), "--chunk", str(committed["chunk"]),
        "--entries", str(entries), "--winners", "3",
        "--block-hash", vectors["draw"]["block_hash"],
        "--commitment", committed["commitment"],
    ]
    assert cli.main(args) == 0
    transcript = json.loads(capsys.readouterr().out)
    assert len(transcript["winners"]) == 3
    assert transcript["chunk_commitment"] == committed["commitment"]


def test_cli_draw_detects_a_swapped_chunk(demo, tmp_path, vectors):
    fragment, _ = demo
    entries = tmp_path / "entries.txt"
    entries.write_text("a\nb\nc\n")
    args = [
        "draw", "--fragment", str(fragment), "--chunk", "1", "--entries", str(entries),
        "--winners", "1", "--block-hash", vectors["draw"]["block_hash"],
        "--commitment", "0x" + "00" * 32,
    ]
    assert cli.main(args) == 1


def test_cli_status_and_seed(demo, capsys):
    fragment, _ = demo
    assert cli.main(["seed", "--fragment", str(fragment), "--words", "12"]) == 0
    assert len(capsys.readouterr().out.split()) == 12
    assert cli.main(["status", str(fragment)]) == 0
    assert "32 used" in capsys.readouterr().out


def test_cli_draw_requires_a_commitment(demo, tmp_path, vectors):
    fragment, _ = demo
    entries = tmp_path / "entries.txt"
    entries.write_text("a\nb\n")
    with pytest.raises(SystemExit):
        cli.main([
            "draw", "--fragment", str(fragment), "--entries", str(entries), "--winners", "1",
            "--block-hash", vectors["draw"]["block_hash"],
        ])
