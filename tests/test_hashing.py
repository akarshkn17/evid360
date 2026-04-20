from pathlib import Path

from evidence_engine.artifacts.hashing import sha256_file


def test_sha256_file(tmp_path: Path) -> None:
    target = tmp_path / "example.txt"
    target.write_text("trace360", encoding="utf-8")

    assert sha256_file(target) == "12889b6c4739200bbccb30a146442869a3d48a51e1abdd4915ba3d903c94b138"
