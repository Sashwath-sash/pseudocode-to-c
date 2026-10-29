let pyodidePromise;

async function pythonRuntime() {
  if (!pyodidePromise) {
    pyodidePromise = (async () => {
      const runtime = await loadPyodide({ indexURL: "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/" });
      runtime.FS.mkdir("/home/pyodide/pseudoc");
      runtime.FS.mkdir("/home/pyodide/webapp");
      const files = [
        "pseudoc/__init__.py", "pseudoc/lexer.py", "pseudoc/parser.py",
        "pseudoc/semantic.py", "pseudoc/nodes.py", "pseudoc/errors.py",
        "pseudoc/ir.py", "pseudoc/optimizer.py", "pseudoc/cgen.py",
        "pseudoc/compiler.py", "pseudoc/astview.py", "webapp/__init__.py",
        "webapp/ast_tree.py", "bridge.py"
      ];
      await Promise.all(files.map(async path => {
        const response = await fetch(`./${path}`);
        if (!response.ok) throw new Error(`Could not load compiler module ${path}`);
        runtime.FS.writeFile(`/home/pyodide/${path}`, await response.text());
      }));
      runtime.runPython("from bridge import compile_json");
      return runtime;
    })();
  }
  return pyodidePromise;
}

window.compileInBrowser = async source => {
  const runtime = await pythonRuntime();
  runtime.globals.set("_source_for_compile", source);
  return JSON.parse(runtime.runPython("compile_json(_source_for_compile)"));
};
