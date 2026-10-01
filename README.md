# Anything → Markdown

A static website that converts documents (PDF, Word, Excel, PowerPoint, HTML, CSV, JSON, XML, EPUB, ZIP, text and code files) to Markdown, so they cost fewer tokens when given to an AI.

It runs [Microsoft MarkItDown](https://github.com/microsoft/markitdown) entirely in the browser through [Pyodide](https://pyodide.org). Files are never uploaded anywhere.

PDFs take a faster route: [pdf.js](https://mozilla.github.io/pdf.js/) reads the text and its position on the page, and MarkItDown's own table detection turns that into Markdown. If pdf.js cannot read a file, MarkItDown reads the PDF itself, which is slower.

## Files

- `index.html`: the page, UI and PDF text reading
- `worker.js`: web worker that loads Pyodide and installs MarkItDown
- `converter.py`: Python glue executed inside Pyodide

After changing `worker.js` or `converter.py`, raise `VERSION` in `index.html` so browsers load the new files.

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
