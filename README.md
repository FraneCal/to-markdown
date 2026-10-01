# Anything → Markdown

A static website that converts documents (PDF, Word, Excel, PowerPoint, HTML, CSV, JSON, XML, EPUB, ZIP, text and code files) to Markdown, so they cost fewer tokens when given to an AI.

It runs [Microsoft MarkItDown](https://github.com/microsoft/markitdown) entirely in the browser through [Pyodide](https://pyodide.org). Files are never uploaded anywhere.

## Files

- `index.html`: the page and UI
- `worker.js`: web worker that loads Pyodide and installs MarkItDown
- `converter.py`: Python glue executed inside Pyodide

## Run locally

```bash
python -m http.server 8765
```

Then open http://localhost:8765 (opening `index.html` directly from disk does not work, because web workers need http).

## Hosting on GitHub Pages

Push to GitHub, then in the repository: **Settings → Pages → Deploy from a branch → `main` / root**.

## Limitations

- Images and audio are not transcribed (MarkItDown needs external tools or an LLM for those).
- Scanned PDFs without a text layer produce no output (no OCR).
- The first visit downloads about 30 MB of Python packages; afterwards they are cached by the browser.
