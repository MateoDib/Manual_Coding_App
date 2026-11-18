"""Exact response evidence; offsets are Unicode code points, not UTF-16 units."""

from __future__ import annotations

import hashlib


def text_digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def quote_valid(record, response):
    quote = record["quote"]
    start, end = quote["start"], quote["end"]
    return bool(
        quote["text"]
        and type(start) is int
        and type(end) is int
        and 0 <= start < end <= len(response)
        and response[start:end] == quote["text"]
    )


def source_token(ref):
    import json

    return (
        "r_"
        + hashlib.sha256(
            json.dumps(ref, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
