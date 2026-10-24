document.addEventListener("input", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement)) {
    return;
  }
  const outputId = target.dataset.weightOutput;
  if (!outputId) {
    return;
  }
  const output = document.getElementById(outputId);
  if (output) {
    output.textContent = target.value;
  }
});

document.addEventListener("change", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLSelectElement) || target.id !== "recomendation_id") {
    return;
  }
  const form = document.getElementById("new-recommendation-form");
  if (!(form instanceof HTMLElement)) {
    return;
  }
  const creating = target.value === "new";
  form.hidden = !creating;
  for (const field of form.querySelectorAll("input, textarea")) {
    if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement) {
      field.required = creating;
    }
  }
});

document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) {
    return;
  }
  const message = target.dataset.confirm;
  if (message && !window.confirm(message)) {
    event.preventDefault();
  }
});
