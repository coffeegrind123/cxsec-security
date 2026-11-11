"""Build bounded source previews and binary classifications for scan worklists."""

# Upstream deleted rank_preview.py in 0.7.0 (05cceee24, "run inventory and ranking
# helpers in Node") and moved it into its TypeScript MCP launcher
# (mcp-app/src/helpers/source-preview.ts), which this port does not vendor. This
# carried copy is the last upstream Python version brought in line with that
# implementation: one sampler classifies every byte of a file or Git blob as binary
# or text while retaining only the first 64 KiB for the preview, UTF-16 sources are
# recognised by their byte-order mark, and a read failure classifies as binary.
# Imported by the carried generate_rank_input.py and generate_in_scope_files.py.

from __future__ import annotations

import argparse
import codecs
from pathlib import Path

DEFAULT_PREVIEW_BYTES = 1024
DEFAULT_PREVIEW_READ_BYTES = 64 * 1024
PREVIEW_HEAD_LINES = 12
PREVIEW_SAMPLE_LINES = 10
_UTF16_BOMS = (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)
_READ_CHUNK = 64 * 1024


def _bom(data: bytes) -> bytes:
    return data[:2] if data.startswith(_UTF16_BOMS) else b""


def _decode_source(data: bytes) -> str:
    # Preview decoding ignores malformed or incomplete source units.
    bom = _bom(data)
    if not bom:
        return data.decode("utf-8", errors="ignore").removeprefix("﻿")
    units = data[2 : len(data) - (len(data) % 2)]
    encoding = "utf-16-le" if bom == codecs.BOM_UTF16_LE else "utf-16-be"
    return units.decode(encoding, errors="ignore")


def is_binary_sample(data: bytes) -> bool:
    if _bom(data):
        return "\0" in _decode_source(data)
    return b"\0" in data


class SourceSampler:
    """Classify a whole stream while retaining at most the preview read window."""

    def __init__(self) -> None:
        self._sample = b""
        self._binary = False
        self._bom = b""
        self._unit_tail = b""

    def consume(self, data: bytes) -> bool:
        if len(self._sample) < DEFAULT_PREVIEW_READ_BYTES:
            self._sample += data[: DEFAULT_PREVIEW_READ_BYTES - len(self._sample)]
        classified = self._unit_tail + data
        if not self._bom and len(self._sample) >= 2 and _bom(self._sample):
            self._bom = self._sample[:2]
        # Hold one byte until the encoding is known, and keep UTF-16 units aligned.
        hold = len(classified) % 2 if self._bom or len(self._sample) < 2 else 0
        length = len(classified) - hold
        if length and not self._binary:
            chunk = classified[:length]
            self._binary = is_binary_sample(self._bom + chunk) if self._bom else b"\0" in chunk
        self._unit_tail = classified[length:]
        return not self._binary

    def finish(self) -> tuple[bytes, bool]:
        if not self._bom and self._unit_tail:
            self._binary = self._binary or b"\0" in self._unit_tail
        return (b"" if self._binary else self._sample), self._binary


def sample_file(path: Path) -> tuple[bytes, bool]:
    """Return the preview window and whether any byte of the file is binary."""
    sampler = SourceSampler()
    try:
        with path.open("rb") as source:
            while chunk := source.read(_READ_CHUNK):
                if not sampler.consume(chunk):
                    break
    except OSError:
        return b"", True
    return sampler.finish()


def is_binary_file(path: Path) -> bool:
    return sample_file(path)[1]


def truncate_utf8(text: str, max_bytes: int) -> str:
    if max_bytes <= 0:
        return ""
    encoded = text.encode("utf-8", errors="surrogatepass")
    if len(encoded) <= max_bytes:
        return text
    end = max_bytes
    while end > 0 and (encoded[end] & 0xC0) == 0x80:
        end -= 1
    return encoded[:end].decode("utf-8", errors="ignore")


def _size(text: str) -> int:
    return len(text.encode("utf-8", errors="surrogatepass"))


def select_preview_lines(lines: list[str]) -> list[str]:
    nonblank = [line for line in lines if line.strip()]
    remainder = nonblank[PREVIEW_HEAD_LINES:]
    if len(remainder) <= PREVIEW_SAMPLE_LINES:
        return nonblank
    last_index = len(remainder) - 1
    sampled = [
        remainder[index * last_index // (PREVIEW_SAMPLE_LINES - 1)]
        for index in range(PREVIEW_SAMPLE_LINES)
    ]
    return [*nonblank[:PREVIEW_HEAD_LINES], "...", *sampled]


def fit_preview_lines(lines: list[str], max_bytes: int) -> str:
    if not lines or max_bytes <= 0:
        return ""
    sampled = "\n".join(lines)
    if _size(sampled) <= max_bytes:
        return sampled

    def render(line_bytes: int) -> str:
        return "\n".join(
            line if line == "..." else truncate_utf8(line, line_bytes) for line in lines
        )

    low, high, best = 0, max(_size(line) for line in lines), ""
    while low <= high:
        middle = (low + high) // 2
        candidate = render(middle)
        if _size(candidate) <= max_bytes:
            best, low = candidate, middle + 1
        else:
            high = middle - 1
    if best.strip() not in {"", "..."}:
        return best
    return truncate_utf8(sampled, max_bytes)


def preview_for_bytes(data: bytes, preview_bytes: int = DEFAULT_PREVIEW_BYTES) -> tuple[str, bool]:
    if is_binary_sample(data):
        return "", True
    if preview_bytes <= 0:
        return "", False
    lines = _decode_source(data).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    lines = lines[start:end]
    complete = "\n".join(lines)
    if _size(complete) <= preview_bytes:
        return complete, False
    return fit_preview_lines(select_preview_lines(lines), preview_bytes), False


def preview_for(
    path: Path, preview_bytes: int, *, max_read_bytes: int = DEFAULT_PREVIEW_READ_BYTES
) -> tuple[str, bool]:
    """Preview a file from its first read window, classifying every byte."""
    if max_read_bytes <= 0:
        raise ValueError("max_read_bytes must be positive")
    sample, binary = sample_file(path)
    if binary:
        return "", True
    return preview_for_bytes(sample[:max_read_bytes], preview_bytes)


if __name__ == "__main__":
    argparse.ArgumentParser(
        description="Build bounded source previews for security-scan worklists."
    ).parse_args()
