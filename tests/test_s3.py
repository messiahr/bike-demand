from pathlib import Path

from src.adapters.s3 import sanitize_csv


def test_sanitize_csv_removes_null_bytes(tmp_path: Path) -> None:
    csv_file = tmp_path / "test.csv"
    csv_file.write_bytes(b"id,name\n1,foo\x00bar\n2,baz\n")

    sanitize_csv(csv_file)

    assert csv_file.read_bytes() == b"id,name\n1,foobar\n2,baz\n"


def test_sanitize_csv_multiple_null_bytes(tmp_path: Path) -> None:
    csv_file = tmp_path / "test.csv"
    csv_file.write_bytes(b"\x00id,\x00name\x00\n1,foo\n")

    sanitize_csv(csv_file)

    assert csv_file.read_bytes() == b"id,name\n1,foo\n"


def test_sanitize_csv_binary_content(tmp_path: Path) -> None:
    csv_file = tmp_path / "test.csv"
    content = b"col1,col2\nval1\x00\x00val2\nval3,val4\x00\n"
    csv_file.write_bytes(content)

    sanitize_csv(csv_file)

    assert b"\x00" not in csv_file.read_bytes()
    assert csv_file.read_bytes() == b"col1,col2\nval1val2\nval3,val4\n"
