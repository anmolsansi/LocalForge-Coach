const form = document.getElementById("run-form");
const modelsList = document.getElementById("models");
const modelsStatus = document.getElementById("models-status");
const refreshBtn = document.getElementById("refresh-models");

const strictnessInput = document.getElementById("strictness");
const strictnessValue = document.getElementById("strictness-value");
const retriesInput = document.getElementById("retries");
const retriesValue = document.getElementById("retries-value");

const runStatus = document.getElementById("run-status");
const runId = document.getElementById("run-id");
const runState = document.getElementById("run-state");
const runAttempt = document.getElementById("run-attempt");
const stepsEl = document.getElementById("steps");
const finalOutput = document.getElementById("final-output");
const judgeReport = document.getElementById("judge-report");

let pollingHandle = null;

function setSliderValue(input, output) {
  output.textContent = input.value;
}

setSliderValue(strictnessInput, strictnessValue);
setSliderValue(retriesInput, retriesValue);

strictnessInput.addEventListener("input", () =>
  setSliderValue(strictnessInput, strictnessValue)
);
retriesInput.addEventListener("input", () =>
  setSliderValue(retriesInput, retriesValue)
);

async function loadModels() {
  modelsStatus.textContent = "Loading models...";
  modelsStatus.dataset.state = "loading";
  modelsList.innerHTML = "";
  try {
    const res = await fetch("/api/models");
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || "Failed to load models");
    }
    if (data.error) {
      throw new Error(data.error);
    }
    const models = Array.isArray(data.models) ? data.models : [];
    if (models.length) {
      models.forEach((model) => {
        const option = document.createElement("option");
        option.value = model;
        modelsList.appendChild(option);
      });
    }
    modelsStatus.textContent = models.length
      ? `${models.length} model(s) available`
      : "No models returned. Check Ollama.";
  } catch (err) {
    modelsStatus.textContent = `Model list error: ${err.message}`;
  }
}

refreshBtn.addEventListener("click", loadModels);
window.addEventListener("load", loadModels);

function clearPolling() {
  if (pollingHandle) {
    clearTimeout(pollingHandle);
    pollingHandle = null;
  }
}

function updateRunMeta(run) {
  runId.textContent = run.run_id || "--";
  runState.textContent = run.status || "--";
  runAttempt.textContent = run.attempt ?? "--";
  runStatus.textContent = run.error
    ? `Run failed: ${run.error}`
    : run.status
    ? `Run status: ${run.status}`
    : "Waiting for a run.";
}

function renderSteps(run) {
  const order = ["step1", "step2", "step3", "step4", "step5", "step6"];
  stepsEl.innerHTML = "";
  order.forEach((key) => {
    const step = run.steps?.[key];
    const status = step?.status || "pending";

    const wrapper = document.createElement("div");
    wrapper.className = `step step--${status}`;

    const header = document.createElement("div");
    header.className = "step__header";

    const name = document.createElement("div");
    name.className = "step__name";
    name.textContent = key.toUpperCase();

    const pill = document.createElement("div");
    pill.className = "pill";
    pill.textContent = status;

    header.appendChild(name);
    header.appendChild(pill);

    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = "Details";
    details.appendChild(summary);

    const body = document.createElement("pre");
    body.className = "output";

    if (step?.error) {
      body.textContent = step.error;
    } else if (step?.output_text) {
      body.textContent = step.output_text;
    } else if (step?.output_json) {
      body.textContent = JSON.stringify(step.output_json, null, 2);
    } else {
      body.textContent = "No output yet.";
    }

    details.appendChild(body);

    wrapper.appendChild(header);
    wrapper.appendChild(details);
    stepsEl.appendChild(wrapper);
  });
}

function renderJudgeReport(report) {
  if (!report) {
    judgeReport.textContent = "--";
    return;
  }

  judgeReport.innerHTML = "";

  const score = document.createElement("div");
  score.innerHTML = `<h4>Score</h4><p>${report.score ?? "--"}</p>`;
  judgeReport.appendChild(score);

  const reasons = document.createElement("div");
  reasons.innerHTML = "<h4>Reasons</h4>";
  const reasonsList = document.createElement("ul");
  (report.reasons || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    reasonsList.appendChild(li);
  });
  if (reasonsList.childElementCount === 0) {
    const empty = document.createElement("p");
    empty.textContent = "No reasons returned.";
    reasons.appendChild(empty);
  } else {
    reasons.appendChild(reasonsList);
  }
  judgeReport.appendChild(reasons);

  const fixes = document.createElement("div");
  fixes.innerHTML = "<h4>Fixes</h4>";
  const fixesList = document.createElement("ul");
  (report.fixes || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    fixesList.appendChild(li);
  });
  if (fixesList.childElementCount === 0) {
    const empty = document.createElement("p");
    empty.textContent = "No fixes returned.";
    fixes.appendChild(empty);
  } else {
    fixes.appendChild(fixesList);
  }
  judgeReport.appendChild(fixes);

  if (report.raw_text) {
    const raw = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = "Raw judge output";
    raw.appendChild(summary);
    const pre = document.createElement("pre");
    pre.className = "output";
    pre.textContent = report.raw_text;
    raw.appendChild(pre);
    judgeReport.appendChild(raw);
  }
}

function renderRun(run) {
  updateRunMeta(run);
  renderSteps(run);
  finalOutput.textContent = run.final_output || "--";
  renderJudgeReport(run.judge_report);
}

async function pollRun(runIdValue) {
  try {
    const res = await fetch(`/api/run/${runIdValue}`);
    const data = await res.json();
    renderRun(data);

    if (["queued", "running"].includes(data.status)) {
      pollingHandle = setTimeout(() => pollRun(runIdValue), 1200);
    } else {
      clearPolling();
    }
  } catch (err) {
    runStatus.textContent = `Polling error: ${err.message}`;
    pollingHandle = setTimeout(() => pollRun(runIdValue), 2000);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearPolling();

  const question = document.getElementById("question").value.trim();
  const jdText = document.getElementById("jd").value.trim();
  const resumeText = document.getElementById("resume").value.trim();
  const customPromptText = document.getElementById("custom").value.trim();
  const model = document.getElementById("model").value.trim();

  if (!question || !jdText || !resumeText || !model) {
    runStatus.textContent = "Please fill in question, job description, resume, and model.";
    return;
  }

  const payload = {
    question,
    jd_text: jdText,
    resume_text: resumeText,
    model,
    judge_strictness: Number(strictnessInput.value),
    max_retries: Number(retriesInput.value),
  };

  if (customPromptText) {
    payload.custom_prompt_text = customPromptText;
  }

  runStatus.textContent = "Starting run...";
  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      const message = data?.detail
        ? JSON.stringify(data.detail)
        : data?.error || "Failed to start run";
      throw new Error(message);
    }
    runStatus.textContent = "Run created. Polling status...";
    runId.textContent = data.run_id || "--";
    pollRun(data.run_id);
  } catch (err) {
    runStatus.textContent = `Run failed: ${err.message}`;
  }
});
