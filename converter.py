"""Runs inside Pyodide (see worker.js). Exposes convert(data, filename) -> markdown."""

import io
import os
import sys
import types

# MarkItDown uses magika (needs onnxruntime, unavailable in the browser) only to
# sniff file types. Stub it out; we rely on the file extension instead.
_magika = types.ModuleType("magika")


class _Magika:
    def identify_stream(self, stream):
        return types.SimpleNamespace(status="unknown")


_magika.Magika = _Magika
sys.modules["magika"] = _magika

from charset_normalizer import from_bytes  # noqa: E402
from markitdown import MarkItDown, StreamInfo  # noqa: E402
from markitdown import UnsupportedFormatException  # noqa: E402

_md = MarkItDown(enable_plugins=False)


def _as_text(raw):
    """Decode raw bytes as plain text, or return None if they look binary."""
    if b"\x00" in raw[:8192]:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        best = from_bytes(raw).best()
        return str(best) if best is not None else None


def convert(data, filename):
    raw = data.to_bytes() if hasattr(data, "to_bytes") else bytes(data)
    ext = os.path.splitext(filename)[1].lower()
    try:
        result = _md.convert_stream(
            io.BytesIO(raw),
            stream_info=StreamInfo(extension=ext or None, filename=filename),
        )
        text = result.markdown
    except UnsupportedFormatException:
        # Unknown extension (source code, logs, ...): fall back to plain text.
        text = _as_text(raw)
        if text is None:
            raise ValueError(
                "This file type can't be read. Try a PDF, Office document, web page or text file."
            ) from None
    except Exception:
        raise ValueError(
            "This file can't be opened. It may be damaged or password protected."
        ) from None
    if not text.strip():
        raise ValueError(
            "No text was found. Images, audio and scanned pages can't be converted."
        )
    return text.strip() + "\n"
