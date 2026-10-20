const examples = {
  arithmetic: {
    source: `BEGIN
DECLARE x AS INTEGER
SET x = 2 + 3
PRINT x
END`, input: ""
  },
  branch: {
    source: `BEGIN
DECLARE mark AS INTEGER
SET mark = 72
IF mark >= 50 THEN
    PRINT "Pass"
ELSE
    PRINT "Fail"
ENDIF
END`, input: ""
  },
  loop: {
    source: `BEGIN
DECLARE total AS INTEGER
DECLARE i AS INTEGER
SET total = 0
FOR i = 1 TO 4 DO
    IF i == 2 THEN
        CONTINUE
    ENDIF
    SET total = total + i
ENDFOR
PRINT total
END`, input: ""
  },
  stringBits: {
    source: `BEGIN
DECLARE name AS STRING
DECLARE bits AS INTEGER
SET name = "Mira"
SET bits = 5 & 3
PRINT name
PRINT bits
END`, input: ""
  },
  division: {
    source: `BEGIN
DECLARE dividend AS INTEGER
DECLARE divisor AS INTEGER
READ dividend
READ divisor
PRINT dividend / divisor
END`, input: "20 0"
  },
  array: {
    source: `BEGIN
DECLARE values[3] AS INTEGER
DECLARE index AS INTEGER
DECLARE value AS INTEGER
READ index
READ value
SET values[index] = value
PRINT values[index]
END`, input: "3 42"
  }
};

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
const lineNumbers = document.querySelector("#line-numbers");
const result = document.querySelector("#result");
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

function selectExample(key, focus = true) {
  const example = examples[key];
  source.value = example.source;
  programInput.value = example.input;
  updateLines();
  if (focus) source.focus();
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

function selectStage(stage) {
  activeStage = stage;
  tabs.forEach(tab => { tab.setAttribute("aria-selected", String(tab.dataset.stage === stage)); tab.tabIndex = tab.dataset.stage === stage ? 0 : -1; });
  stageName.textContent = stageLabels[stage];
  result.textContent = stageText(stage);
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
source.addEventListener("input", updateLines);
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

selectExample("arithmetic", false);
selectStage("c");
translate(false);
