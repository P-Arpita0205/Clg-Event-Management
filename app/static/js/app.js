document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelector("#sidebar")?.classList.toggle("open");
  });
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy-key]");
  if (!button) return;
  const key = button.dataset.copyKey;
  if (!key) return;
  const original = button.dataset.originalLabel || button.textContent.trim();
  button.dataset.originalLabel = original;
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(key);
    } else {
      const input = document.createElement("input");
      input.value = key;
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      input.remove();
    }
    button.textContent = "Copied";
    setTimeout(() => {
      button.textContent = original;
    }, 1500);
  } catch (_) {}
});

function buildBarOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    layout: { padding: { top: 8, right: 8, left: 0, bottom: 0 } },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#0f172a",
        padding: 10,
        cornerRadius: 8,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        ticks: { precision: 0, color: "#64748b", font: { size: 12 } },
        grid: { color: "#eef2f7" },
        border: { display: false },
      },
      x: {
        ticks: { color: "#475569", font: { size: 12 } },
        grid: { display: false },
        border: { display: false },
      },
    },
  };
}

const PALETTE = ["#155eef", "#087f8c", "#22a699", "#7c3aed", "#f59e0b", "#ef4444"];

const departmentCanvas = document.querySelector("#departmentChart");
if (departmentCanvas && window.Chart) {
  const labels = JSON.parse(departmentCanvas.dataset.labels || "[]");
  const values = JSON.parse(departmentCanvas.dataset.values || "[]");
  new Chart(departmentCanvas, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Users",
        data: values,
        backgroundColor: "#155eef",
        borderRadius: 8,
        borderSkipped: false,
        maxBarThickness: 44,
      }],
    },
    options: buildBarOptions(),
  });
}

const categoryCanvas = document.querySelector("#categoryChart");
if (categoryCanvas && window.Chart) {
  const labels = JSON.parse(categoryCanvas.dataset.labels || "[]");
  const values = JSON.parse(categoryCanvas.dataset.values || "[]");
  new Chart(categoryCanvas, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Events",
        data: values,
        backgroundColor: PALETTE,
        borderRadius: 8,
        borderSkipped: false,
        maxBarThickness: 44,
      }],
    },
    options: buildBarOptions(),
  });
}

const statusCanvas = document.querySelector("#statusChart");
if (statusCanvas && window.Chart) {
  const labels = JSON.parse(statusCanvas.dataset.labels || "[]");
  const values = JSON.parse(statusCanvas.dataset.values || "[]");
  new Chart(statusCanvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        label: "Events",
        data: values,
        backgroundColor: PALETTE,
        borderColor: "#ffffff",
        borderWidth: 3,
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "66%",
      plugins: {
        legend: {
          display: true,
          position: "bottom",
          labels: {
            usePointStyle: true,
            pointStyle: "circle",
            padding: 16,
            color: "#334155",
            font: { size: 12 },
          },
        },
        tooltip: {
          backgroundColor: "#0f172a",
          padding: 10,
          cornerRadius: 8,
        },
      },
    },
  });
}
