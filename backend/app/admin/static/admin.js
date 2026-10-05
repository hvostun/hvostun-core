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
