"""Runs inside Pyodide (see worker.js). Exposes convert(data, filename) -> markdown."""

import io
import os
import re
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

# --- PDF speed-ups -----------------------------------------------------------
# MarkItDown only uses the text of a PDF, but pdfminer also parses every vector
# drawing command in pure Python, which takes minutes on drawing-heavy files.
# Drop path-construction operators from page content before it is parsed.
_NUM = rb"[-+]?(?:\d+\.?\d*|\.\d+)\s+"
_PATH_OPS = re.compile(
    # Strings, hex strings and comments are matched first and kept as they are,
    # so nothing inside them can be mistaken for a drawing command.
    rb"(\((?:\\.|[^\\()]|\((?:\\.|[^\\()])*\))*\)|<[0-9A-Fa-f\s]*>|%[^\r\n]*)"
    rb"|(?<![^\s])(?:(?:" + _NUM + rb"){2}[ml]|(?:" + _NUM + rb"){6}c|(?:"
    + _NUM + rb"){4}(?:re|v|y)|h)(?![^\s])\s*",
    re.DOTALL,
)
_INLINE_IMAGE = re.compile(rb"(?<![^\s])BI(?![^\s])")


def _strip_paths(data):
    if _INLINE_IMAGE.search(data):  # raw image bytes follow; leave untouched
        return data
    return _PATH_OPS.sub(rb"\1", data)


try:
    from pdfminer.pdfinterp import PDFContentParser

    _fillfp = PDFContentParser.fillfp

    def _fast_fillfp(self):
        had_stream = bool(self.fp)
        _fillfp(self)
        if not had_stream and self.fp:
            self.fp = io.BytesIO(_strip_paths(self.fp.getvalue()))

    PDFContentParser.fillfp = _fast_fillfp
except Exception:  # pdfminer internals changed: PDFs still work, just slower
    pass

# PDFs are also converted in page ranges, so the page can spread one document
# over several workers. These functions mirror the page loop in MarkItDown's
# PdfConverter.convert (markitdown 0.1.8); the page calls pdf_open, then
# pdf_pages (or pdf_text) for each range, then pdf_finish on the joined text.
_open_pdfs = {}


def pdf_open(key, data):
    """Open a PDF and return its page count."""
    import pdfplumber

    raw = data.to_bytes() if hasattr(data, "to_bytes") else bytes(data)
    _open_pdfs[key] = (pdfplumber.open(io.BytesIO(raw)), raw)
    return len(_open_pdfs[key][0].pages)


def pdf_pages(key, start, end):
    """Convert pages [start, end). Returns [is_table_page, markdown] per page."""
    from markitdown.converters._pdf_converter import _extract_form_content_from_words

    pdf, _ = _open_pdfs[key]
    out = []
    for page in pdf.pages[start:end]:
        content = _extract_form_content_from_words(page)
        if content is not None:
            out.append([True, content if content.strip() else ""])
        else:
            out.append([False, (page.extract_text() or "").strip()])
        page.close()  # free cached page data
    return out


def pdf_text(key, start, end):
    """Plain text of pages [start, end), for documents without table pages."""
    import pdfminer.high_level

    _, raw = _open_pdfs[key]
    return pdfminer.high_level.extract_text(
        io.BytesIO(raw), page_numbers=list(range(start, end))
    )


def pdf_finish(text):
    from markitdown.converters._pdf_converter import _merge_partial_numbering_lines

    text = _merge_partial_numbering_lines(text.strip())
    # Same clean-up MarkItDown applies to every converter's output
    text = "\n".join(line.rstrip() for line in re.split(r"\r?\n", text))
    return _finish(re.sub(r"\n{3,}", "\n\n", text))


def pdf_close(key):
    pdf, _ = _open_pdfs.pop(key, (None, None))
    if pdf is not None:
        pdf.close()
# -----------------------------------------------------------------------------


def _as_text(raw):
    """Decode raw bytes as plain text, or return None if they look binary."""
    if b"\x00" in raw[:8192]:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        best = from_bytes(raw).best()
        return str(best) if best is not None else None


def _finish(text):
    if not text.strip():
        raise ValueError(
            "No text was found. Images, audio and scanned pages can't be converted."
        )
    return text.strip() + "\n"


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
    return _finish(text)
