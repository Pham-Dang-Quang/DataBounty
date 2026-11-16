const evaluation = document.querySelector("[data-evaluation-progress]");

if (evaluation) {
  const progress = evaluation.querySelector("progress");
  const stage = evaluation.querySelector("[data-evaluation-stage]");
  const percent = evaluation.querySelector("[data-evaluation-percent]");

  async function refreshEvaluation() {
    try {
      const response = await fetch(evaluation.dataset.endpoint, {
        headers: {Accept: "application/json"},
      });
      if (!response.ok) throw new Error("Evaluation status is temporarily unavailable.");
      const result = await response.json();
      progress.value = result.progress;
      stage.textContent = result.stage;
      percent.textContent = `${result.progress}%`;
      if (result.status !== "evaluating") {
        window.location.reload();
        return;
      }
      window.setTimeout(refreshEvaluation, 1000);
    } catch (error) {
      stage.textContent = error.message;
      window.showErrorPopup?.(error.message);
      window.setTimeout(refreshEvaluation, 3000);
    }
  }

  window.setTimeout(refreshEvaluation, 500);
}
