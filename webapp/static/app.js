let examples = [];
let sourceMode = "examples";
let customDraft = "BEGIN\n\nEND";

const stageLabels = {
  tokens: "Tokens and source positions",
  ast: "Abstract syntax tree",
  symbols: "Symbol table",
  ir: "Intermediate representation",
  optimized_ir: "Optimized IR",
  c: "Generated C source",
  output: "Program output"
};

const source = document.querySelector("#source");
const programInput = document.querySelector("#program-input");
const exampleSelect = document.querySelector("#example-select");
const exampleFile = document.querySelector("#example-file");
const examplePicker = document.querySelector("#example-picker");
const customModeButton = document.querySelector("#custom-mode");
const examplesModeButton = document.querySelector("#examples-mode");
const lineNumbers = document.querySelector("#line-numbers");
const result = document.querySelector("#result");
const astTree = document.querySelector("#ast-tree");
const expandTreeButton = document.querySelector("#expand-tree");
const collapseTreeButton = document.querySelector("#collapse-tree");
const status = document.querySelector("#status");
const stageName = document.querySelector("#stage-name");
const diagnostic = document.querySelector("#diagnostic");
const translateButton = document.querySelector("#translate-btn");
const runButton = document.querySelector("#run-btn");
const copyButton = document.querySelector("#copy-btn");
const downloadButton = document.querySelector("#download-btn");
const tabs = [...document.querySelectorAll("[data-stage]")];
let compilation = null;
let activeStage = "c";
let pending = null;

function updateLines() {
  lineNumbers.textContent = Array.from({ length: source.value.split("\n").length }, (_, i) => i + 1).join("\n");
  lineNumbers.scrollTop = source.scrollTop;
}

function setSourceMode(mode) {
  sourceMode = mode;
  customModeButton.setAttribute("aria-pressed", String(mode === "custom"));
  examplesModeButton.setAttribute("aria-pressed", String(mode === "examples"));
  examplePicker.hidden = mode !== "examples";
}

function invalidateCompilation() {
  compilation = null;
  showDiagnostic("");
  setStatus("Edit ready");
  selectStage(activeStage);
}

function selectExample(key, focus = true) {
  const example = examples.find(item => item.id === key);
  if (!example) return;
  if (sourceMode === "custom") customDraft = source.value;
  setSourceMode("examples");
  exampleSelect.value = key;
  exampleFile.textContent = `examples/${key}.pseudo`;
  source.value = example.source;
  programInput.value = example.input;
  updateLines();
  source.setSelectionRange(0, 0);
  if (focus) source.focus();
  source.scrollTop = 0;
  lineNumbers.scrollTop = 0;
  invalidateCompilation();
}

async function loadExamples() {
  try {
    const response = await fetch("/api/examples");
    if (!response.ok) throw new Error("Could not load project examples.");
    examples = (await response.json()).examples;
    exampleSelect.replaceChildren();
    for (const example of examples) {
      const option = document.createElement("option");
      option.value = example.id;
      option.textContent = example.name;
      exampleSelect.append(option);
    }
    selectExample(examples.find(item => item.id === "array_sum_input")?.id || examples[0]?.id, false);
    translate(false);
  } catch {
    exampleSelect.replaceChildren(new Option("Examples unavailable — write your own", ""));
    setSourceMode("custom");
    source.value = customDraft;
    updateLines();
    showDiagnostic("Saved examples could not be loaded. You can still type a program yourself.");
  }
}

function setStatus(label, kind = "") {
  status.textContent = label;
  status.className = `status ${kind}`.trim();
}

function showDiagnostic(message) {
  diagnostic.hidden = !message;
  diagnostic.textContent = message || "";
}

function stageText(stage) {
  if (!compilation) return "Translate a program to inspect this stage.";
  if (stage !== "output") return compilation.stages[stage] || "";
  if (!compilation.execution) return "C generated. Select “Translate & run” to see program output.";
  if (compilation.execution.error) return compilation.execution.error;
  const run = compilation.execution;
  return [
    run.stdout ? `stdout:\n${run.stdout.trimEnd()}` : "stdout: (empty)",
    run.stderr ? `stderr:\n${run.stderr.trimEnd()}` : "",
    `exit status: ${run.exit_code}`
  ].filter(Boolean).join("\n\n");
}

function astNode(node, role = "") {
  const item = document.createElement("li");
  if (role) {
    const roleLabel = document.createElement("span");
    roleLabel.className = "ast-role";
    roleLabel.textContent = role;
    item.append(roleLabel);
  }
  const chip = document.createElement("span");
  chip.className = `ast-chip ast-${node.kind.toLowerCase().replace(/[^a-z]+/g, "-")}`;
  const kind = document.createElement("strong");
  kind.textContent = node.kind;
  chip.append(kind);
  if (node.detail) {
    const detail = document.createElement("span");
    detail.textContent = node.detail;
    chip.append(detail);
  }
  if (node.children.length) {
    const group = document.createElement("details");
    group.open = true;
    const heading = document.createElement("summary");
    heading.append(chip);
    group.append(heading);
    const children = document.createElement("ul");
    children.className = "ast-children";
    node.children.forEach(child => children.append(astNode(child.node, child.role)));
    group.append(children);
    item.append(group);
  } else {
    const leaf = document.createElement("div");
    leaf.className = "ast-leaf";
    leaf.append(chip);
    item.append(leaf);
  }
  return item;
}

function showAstTree(tree) {
  const root = document.createElement("ul");
  root.className = "ast-root";
  root.append(astNode(tree));
  astTree.replaceChildren(root);
}

function selectStage(stage) {
  activeStage = stage;
  tabs.forEach(tab => { tab.setAttribute("aria-selected", String(tab.dataset.stage === stage)); tab.tabIndex = tab.dataset.stage === stage ? 0 : -1; });
  stageName.textContent = stageLabels[stage];
  const visualAst = stage === "ast" && Boolean(compilation?.ast_tree);
  result.hidden = visualAst;
  astTree.hidden = !visualAst;
  expandTreeButton.hidden = !visualAst;
  collapseTreeButton.hidden = !visualAst;
  if (visualAst) showAstTree(compilation.ast_tree);
  else result.textContent = stageText(stage);
  result.scrollTop = 0;
  copyButton.disabled = !compilation;
  downloadButton.disabled = !compilation;
}

async function translate(run) {
  if (pending) pending.abort();
  pending = new AbortController();
  const controller = pending;
  setStatus(run ? "Running…" : "Translating…", "busy");
  translateButton.disabled = true;
  runButton.disabled = true;
  showDiagnostic("");
  try {
    const response = await fetch("/api/compile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: source.value, input: programInput.value, run }),
      signal: controller.signal
    });
    const data = await response.json();
    if (!response.ok) {
      compilation = null;
      showDiagnostic(data.error || "Translation failed.");
      result.textContent = data.error || "Translation failed.";
      setStatus("Source error", "error");
      copyButton.disabled = true;
      downloadButton.disabled = true;
      return;
    }
    compilation = data;
    selectStage(run ? "output" : "c");
    if (run && data.execution?.error) {
      showDiagnostic(data.execution.error);
      setStatus("Run unavailable", "error");
    } else if (run && data.execution?.exit_code !== 0) {
      setStatus("Program error", "error");
    } else {
      setStatus(run ? "Run complete" : "Translated");
    }
  } catch (error) {
    if (error.name === "AbortError") return;
    compilation = null;
    showDiagnostic("The local compiler server could not be reached. Restart it with: python webapp/server.py");
    setStatus("Disconnected", "error");
  } finally {
    if (pending === controller) {
      pending = null;
      translateButton.disabled = false;
      runButton.disabled = false;
    }
  }
}

exampleSelect.addEventListener("change", () => selectExample(exampleSelect.value));
examplesModeButton.addEventListener("click", () => {
  if (sourceMode === "custom") customDraft = source.value;
  selectExample(exampleSelect.value || examples[0]?.id);
});
customModeButton.addEventListener("click", () => {
  if (sourceMode === "custom") return;
  setSourceMode("custom");
  exampleFile.textContent = "";
  source.value = customDraft;
  programInput.value = "";
  updateLines();
  source.scrollTop = 0;
  lineNumbers.scrollTop = 0;
  invalidateCompilation();
  source.focus();
  source.setSelectionRange(6, 6);
});
source.addEventListener("input", () => {
  updateLines();
  if (sourceMode === "examples") setSourceMode("custom");
  customDraft = source.value;
  invalidateCompilation();
});
source.addEventListener("scroll", () => { lineNumbers.scrollTop = source.scrollTop; });
source.addEventListener("keydown", event => {
  if (event.key === "Tab") {
    event.preventDefault();
    const start = source.selectionStart;
    source.setRangeText("    ", start, source.selectionEnd, "end");
    updateLines();
  }
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    translate(false);
  }
});
translateButton.addEventListener("click", () => translate(false));
runButton.addEventListener("click", () => translate(true));
tabs.forEach(tab => tab.addEventListener("click", () => selectStage(tab.dataset.stage)));
expandTreeButton.addEventListener("click", () => astTree.querySelectorAll("details").forEach(item => { item.open = true; }));
collapseTreeButton.addEventListener("click", () => astTree.querySelectorAll("details").forEach((item, index) => { item.open = index === 0; }));
copyButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(stageText(activeStage));
    const previous = copyButton.textContent;
    copyButton.textContent = "Copied";
    setTimeout(() => { copyButton.textContent = previous; }, 1500);
  } catch { showDiagnostic("Clipboard access is unavailable. Select the text and copy it manually."); }
});
downloadButton.addEventListener("click", () => {
  if (!compilation) return;
  const url = URL.createObjectURL(new Blob([compilation.stages.c], { type: "text/x-csrc" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "generated.c";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

selectStage("c");
loadExamples();
