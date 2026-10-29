"""Build the browser-translation edition for GitHub Pages."""
import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / "site-dist"
if target.exists():
    shutil.rmtree(target)
shutil.copytree(root / "webapp" / "static", target)
shutil.copytree(root / "pseudoc", target / "pseudoc", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
(target / "webapp").mkdir()
(target / "webapp" / "__init__.py").write_text("", encoding="utf-8")
shutil.copy2(root / "webapp" / "ast_tree.py", target / "webapp" / "ast_tree.py")
shutil.copy2(root / "site" / "bridge.py", target / "bridge.py")
shutil.copy2(root / "site" / "bridge.js", target / "bridge.js")

examples = []
for path in sorted((root / "examples").glob("*.pseudo")):
    examples.append({"id": path.stem, "name": path.stem.replace("_", " ").title(),
                     "source": path.read_text(encoding="utf-8"), "input": ""})
(target / "examples.json").write_text(json.dumps({"examples": examples}), encoding="utf-8")

html = (target / "index.html").read_text(encoding="utf-8")
html = html.replace('<script src="/app.js" defer></script>',
                    '<script src="https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.js" defer></script>\n'
                    '  <script src="./bridge.js" defer></script>\n  <script src="./app.js" defer></script>')
html = html.replace('href="/favicon.svg"', 'href="./favicon.svg"').replace('href="/styles.css"', 'href="./styles.css"')
html = html.replace('Running C requires GCC installed on this computer; it has a three-second limit.',
                    'This hosted version translates in your browser. To compile and run the generated C, use the local project with GCC.')
html = html.replace('Running C requires GCC installed on this computer', 'Running generated C requires the local project and GCC')
html = html.replace('and run the generated C locally.', 'and download generated C. Execution is available in the local edition.')
html = html.replace('<button id="run-btn" class="button outline" type="button">Translate &amp; run</button>', '')
(target / "index.html").write_text(html, encoding="utf-8")

js = (target / "app.js").read_text(encoding="utf-8")
js = js.replace('fetch("/api/examples")', 'fetch("./examples.json")')
start = js.index('    const response = await fetch("/api/compile", {')
end = js.index('    compilation = data;', start)
js = js[:start] + '''    const data = await window.compileInBrowser(source.value);
    if (data.error) {
      compilation = null;
      showDiagnostic(data.error);
      result.textContent = data.error;
      setStatus("Source error", "error");
      copyButton.disabled = true;
      downloadButton.disabled = true;
      return;
    }
''' + js[end:]
js = js.replace('runButton.disabled = true;', 'if (runButton) runButton.disabled = true;')
js = js.replace('runButton.disabled = false;', 'if (runButton) runButton.disabled = false;')
js = js.replace('runButton.addEventListener("click", () => translate(true));', '')
js = js.replace('The local compiler server could not be reached. Restart it with: python webapp/server.py',
                'The browser compiler could not load. Check your internet connection and reload the page.')
js = js.replace('fetch("/api/examples")', 'fetch("./examples.json")')
(target / "app.js").write_text(js, encoding="utf-8")
print(target)
