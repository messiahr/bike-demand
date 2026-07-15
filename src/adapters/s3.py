"""Repository for downloading from S3."""

import xml.etree.ElementTree as ET
from pathlib import Path

import requests

CHUNK_SIZE = 8192


def list_bucket_files(bucket_url: str, prefix: str = "") -> list[str]:
    """List all object keys in the hubway-data S3 bucket.

    Uses the S3 REST API (ListObjectsV2), which returns XML for
    public buckets. No AWS credentials required.

    Args:
        prefix: Optional prefix to filter keys (e.g. 'hubway_Trips').

    Returns:
        List of object keys (filenames) in the bucket.
    """
    keys: list[str] = []
    continuation_token: str | None = None

    while True:
        params: dict[str, str] = {"list-type": "2"}
        if prefix:
            params["prefix"] = prefix
        if continuation_token:
            params["continuation-token"] = continuation_token

        response = requests.get(bucket_url, params=params, timeout=30)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        # S3 XML uses namespace — extract it dynamically
        ns = {"s3": root.tag.split("}")[0].strip("{")} if "}" in root.tag else None

        contents = root.findall("s3:Contents", ns) if ns else root.findall("Contents")
        for content in contents:
            key_el = content.find("s3:Key", ns) if ns else content.find("Key")
            if key_el is not None and key_el.text and not key_el.text.endswith("/"):
                keys.append(key_el.text)

        # Check if there are more results (S3 returns max 1000 per page)
        is_truncated = root.find("s3:IsTruncated", ns) if ns else root.find("IsTruncated")
        if is_truncated is not None and is_truncated.text == "true":
            token_el = (
                root.find("s3:NextContinuationToken", ns)
                if ns
                else root.find("NextContinuationToken")
            )
            continuation_token = token_el.text if token_el is not None else None
        else:
            break

    return keys


def sanitize_csv(path: Path) -> None:
    """Remove null bytes from a CSV file in-place.

    Some Hubway CSVs contain macOS extended attribute binary data
    (com.apple.macl, com.apple.lastuseddate#PS, etc.) that leaked
    into the CSV content during the original zip creation on macOS.
    These null bytes crash Polars' Arrow FFI layer and will also
    cause errors in PostgreSQL text columns.
    """
    content = path.read_bytes()
    if b"\x00" in content:
        path.write_bytes(content.replace(b"\x00", b""))


def download(url: str, dest: Path) -> Path:
    """Download a file from URL to dest, return the local path."""

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest

    response = requests.get(url, timeout=60, stream=True)
    response.raise_for_status()
    with dest.open("wb") as f:
        for chunk in response.iter_content(CHUNK_SIZE):
            f.write(chunk)
    return dest
