"""FFmpeg filter-graph character escaping."""

from __future__ import annotations


def escape_chars(text: object, chars: str) -> str:
    """Escape each character in ``chars`` with a backslash.

    Backslash is escaped first when present, matching ffmpeg-python.
    """
    result = str(text)
    unique = list(dict.fromkeys(chars))
    if "\\" in unique:
        unique.remove("\\")
        unique.insert(0, "\\")
    for ch in unique:
        result = result.replace(ch, "\\" + ch)
    return result


def escape_filter_token(value: object) -> str:
    return escape_chars(value, "\\'=:")
