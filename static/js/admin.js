const socket = io();
const tbody = document.querySelector("#stock-table tbody");

function render(prizes) {
  tbody.innerHTML = "";
  prizes.forEach((p) => {
    const tr = document.createElement("tr");
    const remainingText = p.remaining === null ? "無制限" : p.remaining;
    const controlsHtml =
      p.remaining === null
        ? "-"
        : `<input type="number" class="stock-input" data-id="${p.id}" value="${p.remaining}" min="0">
           <button data-id="${p.id}" class="set-stock-btn">更新</button>`;

    tr.innerHTML = `
      <td>${p.name}</td>
      <td>${Math.round(p.probability * 100)}%</td>
      <td>${remainingText}</td>
      <td>${controlsHtml}</td>
    `;
    tbody.appendChild(tr);
  });

  document.querySelectorAll(".set-stock-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      const input = document.querySelector(`.stock-input[data-id="${id}"]`);
      fetch("/api/set_stock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prize_id: id, amount: Number(input.value) }),
      });
    });
  });
}

fetch("/api/status")
  .then((res) => res.json())
  .then((data) => render(data.prizes));

socket.on("stock_updated", (prizes) => render(prizes));
