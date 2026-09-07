const socket = io();
const tbody = document.querySelector("#stock-table tbody");

// 抽選結果のたびに stock_updated が飛んでくるが、その都度テーブルを
// 作り直すと入力中の値やフォーカス、Tabでの移動先が毎回リセットされて
// 操作しづらくなる。そのため行(input要素)は一度作ったら使い回し、
// 今フォーカスしていない値だけをサーバーの最新値で上書きする。
const rows = new Map(); // prize_id -> { tr, stockInput, probInput }

function upsertRow(p) {
  let row = rows.get(p.id);

  if (!row) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="name-cell"></td>
      <td class="prob-cell"></td>
      <td class="remaining-cell"></td>
      <td class="stock-controls-cell"></td>
    `;
    tbody.appendChild(tr);
    row = { tr };
    rows.set(p.id, row);

    const probCell = tr.querySelector(".prob-cell");
    probCell.innerHTML = `<input type="number" class="prob-input" min="0" max="100" step="1">%`;
    row.probInput = probCell.querySelector(".prob-input");
    const commitProbability = () => {
      const value = Number(row.probInput.value);
      if (Number.isNaN(value) || value < 0) return;
      fetch("/api/set_probability", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prize_id: p.id, probability: value / 100 }),
      });
    };
    row.probInput.addEventListener("blur", commitProbability);
    row.probInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        commitProbability();
        row.probInput.blur();
      }
    });
  }

  row.tr.querySelector(".name-cell").textContent = p.name;
  row.tr.querySelector(".remaining-cell").textContent =
    p.remaining === null ? "無制限" : p.remaining;

  if (document.activeElement !== row.probInput) {
    row.probInput.value = Math.round(p.probability * 100);
  }

  const controlsCell = row.tr.querySelector(".stock-controls-cell");
  if (p.remaining === null) {
    controlsCell.textContent = "-";
    row.stockInput = null;
    return;
  }

  if (!row.stockInput) {
    controlsCell.innerHTML = `
      <input type="number" class="stock-input" min="0">
      <button type="button" class="set-stock-btn">更新</button>
    `;
    row.stockInput = controlsCell.querySelector(".stock-input");
    const commitStock = () => {
      const value = Number(row.stockInput.value);
      if (Number.isNaN(value)) return;
      fetch("/api/set_stock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prize_id: p.id, amount: value }),
      });
    };
    row.stockInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") commitStock();
    });
    controlsCell.querySelector(".set-stock-btn").addEventListener("click", commitStock);
  }

  if (document.activeElement !== row.stockInput) {
    row.stockInput.value = p.remaining;
  }
}

function render(prizes) {
  const seenIds = new Set(prizes.map((p) => p.id));
  prizes.forEach(upsertRow);

  // 設定から削除された景品があれば行も消す
  for (const [id, row] of rows) {
    if (!seenIds.has(id)) {
      row.tr.remove();
      rows.delete(id);
    }
  }
}

fetch("/api/status")
  .then((res) => res.json())
  .then((data) => render(data.prizes));

socket.on("stock_updated", (prizes) => render(prizes));
