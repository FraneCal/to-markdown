// Runs Microsoft MarkItDown in the browser via Pyodide. Files never leave the device.
const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v0.29.3/full/";
importScripts(PYODIDE_URL + "pyodide.js");

// Shipped with Pyodide
const PYODIDE_PACKAGES = [
  "micropip", "beautifulsoup4", "lxml", "pandas", "xlrd", "pillow",
  "cryptography", "requests", "charset-normalizer",
];
// Pure-Python wheels from PyPI
const PYPI_PACKAGES = [
  "markdownify==1.2.3", "defusedxml==0.7.1", "mammoth==1.11.0",
  "python-pptx==1.0.2", "openpyxl==3.1.5", "olefile==0.47",
  "pdfminer.six==20260107",
];
// Installed without dependencies: magika (onnxruntime) and pypdfium2 have no
// browser builds, and MarkItDown works without them (see converter.py).
const PYPI_PACKAGES_NO_DEPS = ["pdfplumber==0.11.10", "markitdown==0.1.8"];

// Four loading steps, reported so the page can show determinate progress
const status = (step) => postMessage({ type: "status", step });

const ready = (async () => {
  status(1);
  const pyodide = await loadPyodide({ indexURL: PYODIDE_URL });
  status(2);
  await pyodide.loadPackage(PYODIDE_PACKAGES);
  const micropip = pyodide.pyimport("micropip");
  status(3);
  await micropip.install(PYPI_PACKAGES);
  await micropip.install.callKwargs(PYPI_PACKAGES_NO_DEPS, { deps: false });
  status(4);
  const source = await (await fetch("converter.py" + self.location.search)).text();
  pyodide.runPython(source);
  return pyodide;
})();

ready.then(
  () => postMessage({ type: "ready" }),
  (err) => postMessage({ type: "fatal", error: String(err) }),
);

// Each message calls one function from converter.py: { job, fn, args }
onmessage = async ({ data: { job, fn, args } }) => {
  try {
    const pyodide = await ready;
    const pyArgs = args.map((a) => (a instanceof ArrayBuffer ? new Uint8Array(a) : a));
    let result = pyodide.globals.get(fn)(...pyArgs);
    if (result && typeof result.toJs === "function") {
      const proxy = result;
      result = proxy.toJs();
      proxy.destroy();
    }
    postMessage({ type: "result", job, result });
  } catch (err) {
    // Last line of a Python traceback is the human-readable part
    const lines = String(err.message || err).trim().split("\n");
    const error = lines[lines.length - 1].replace(/^[\w.]+(Error|Exception): /, "");
    postMessage({ type: "error", job, error });
  }
};
