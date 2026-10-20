const socket = io();

const prizeList = document.getElementById("prize-list");
const previewButtons = document.getElementById("preview-buttons");
const probabilityTotal = document.getElementById("probability-total");
const hardwareCard = document.getElementById("hardware-card");
const hardwareTitle = document.getElementById("hardware-title");
const hardwareDetail = document.getElementById("hardware-detail");
const hardwareHelp = document.getElementById("hardware-help");
const adminError = document.getElementById("admin-error");
const adminErrorTitle = document.getElementById("admin-error-title");
const adminErrorDetail = document.getElementById("admin-error-detail");
const adminErrorTime = document.getElementById("admin-error-time");
const clearAdminErrorButton = document.getElementById("clear-admin-error");
const stockCard = document.getElementById("stock-card");
const stockTitle = document.getElementById("stock-title");
const stockDetail = document.getElementById("stock-detail");
const chanceCard = document.getElementById("chance-card");
const chanceTitle = document.getElementById("chance-title");
const chanceDetail = document.getElementById("chance-detail");
const headerStatus = document.getElementById("header-status");
const toast = document.getElementById("toast");
const showGameButton = document.getElementById("show-game-button");
const fullscreenButton = document.getElementById("fullscreen-button");
const demoDrawButton = document.getElementById("demo-draw-button");
const hardwareTestButton = document.getElementById("hardware-test-button");
const hardwareTestDetail = document.getElementById("hardware-test-detail");
const autoProbabilityToggle = document.getElementById("auto-probability-toggle");
const servoTimingForm = document.getElementById("servo-timing-form");
const servoTimeA = document.getElementById("servo-time-a");
const servoTimeB = document.getElementById("servo-time-b");
let servoTimingLoaded = false;

servoTimingForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = servoTimingForm.querySelector("button");
  button.disabled = true;
  try {
    await requestJson("/api/set_servo_timing", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ a: Number(servoTimeA.value), b: Number(servoTimeB.value) }),
    });
    notify("回転時間を保存しました。次の抽選から反映します");
  } catch (error) {
    notify(error.message, true);
  } finally {
    button.disabled = false;
  }
});

let prizes = [];
let toastTimer = null;
let autoProbabilityByStock = false;
let displayedAdminErrorAt = null;

function renderAdminError(error) {
  if (!error) {
    adminError.hidden = true;
    displayedAdminErrorAt = null;
    return;
  }
  adminErrorTitle.textContent = error.title || "実機の動作でエラーが発生しました";
  adminErrorDetail.textContent = error.detail || "Arduinoとサーボを確認してください。";
  const occurredAt = new Date(Number(error.occurred_at) * 1000);
  adminErrorTime.textContent = Number.isNaN(occurredAt.getTime())
    ? ""
    : `発生時刻：${occurredAt.toLocaleString("ja-JP")}`;
  adminError.hidden = false;
  if (displayedAdminErrorAt !== error.occurred_at) {
    displayedAdminErrorAt = error.occurred_at;
    adminError.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

clearAdminErrorButton.addEventListener("click", async () => {
  clearAdminErrorButton.disabled = true;
  try {
    await requestJson("/api/clear_admin_error", { method: "POST" });
    renderAdminError(null);
  } catch (error) {
    notify(error.message, true);
  } finally {
    clearAdminErrorButton.disabled = false;
  }
});

demoDrawButton.addEventListener("click", async () => {
  demoDrawButton.disabled = true;
  try {
    const result = await requestJson("/api/demo_draw", { method: "POST" });
    notify(`${result.name}：ゲーム画面でテスト中です`);
  } catch (error) {
    notify(error.message, true);
  } finally {
    window.setTimeout(() => { demoDrawButton.disabled = false; }, 1200);
  }
});

hardwareTestButton.addEventListener("click", async () => {
  if (!window.confirm("実機を1回動かします。\n排出に成功すると在庫が1個減ります。よろしいですか？")) return;
  hardwareTestButton.disabled = true;
  try {
    await requestJson("/api/hardware_test", { method: "POST" });
    notify("実機テストを開始しました。ゲーム画面と排出口を確認してください");
  } catch (error) {
    notify(error.message, true);
  } finally {
    window.setTimeout(loadSystemStatus, 1300);
  }
});

autoProbabilityToggle.addEventListener("change", async () => {
  const enabled = autoProbabilityToggle.checked;
  autoProbabilityToggle.disabled = true;
  try {
    const data = await requestJson("/api/set_auto_probability", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    autoProbabilityByStock = data.enabled;
    renderPrizes(data.prizes);
    notify(enabled ? "在庫に合わせる自動調整をオンにしました" : "自動調整をオフにしました。確率を手動で変更できます");
  } catch (error) {
    autoProbabilityToggle.checked = !enabled;
    notify(error.message, true);
  } finally {
    autoProbabilityToggle.disabled = false;
  }
});

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "操作に失敗しました");
  return data;
}

function notify(message, isError = false) {
  window.clearTimeout(toastTimer);
  toast.textContent = message;
  toast.className = `toast is-visible${isError ? " is-error" : ""}`;
  toastTimer = window.setTimeout(() => {
    toast.className = "toast";
  }, 2800);
}

function setCardState(card, state) {
  card.classList.remove("is-loading", "is-good", "is-warning", "is-danger");
  card.classList.add(`is-${state}`);
}

function renderSummary() {
  const finitePrizes = prizes.filter((prize) => prize.remaining !== null);
  const remaining = finitePrizes.reduce((sum, prize) => sum + prize.remaining, 0);
  const initial = finitePrizes.reduce((sum, prize) => sum + Number(prize.stock || 0), 0);
  const hasStock = prizes.some((prize) => prize.remaining === null || prize.remaining > 0);

  stockTitle.textContent = hasStock ? `残り ${remaining} 個` : "在庫切れ";
  stockDetail.textContent = initial > 0 ? `開始時 ${initial} 個` : "無制限の景品があります";
  setCardState(stockCard, hasStock ? (remaining < 10 ? "warning" : "good") : "danger");

  const winner = prizes.find((prize) => prize.id === "atari") || prizes[0];
  const winnerPercent = winner ? Math.round(winner.probability * 100) : 0;
  chanceTitle.textContent = `${winnerPercent}%`;
  chanceDetail.textContent = winner ? `${winner.name}の現在値` : "景品未設定";
  setCardState(chanceCard, "good");

  const total = Math.round(prizes.reduce((sum, prize) => sum + prize.probability, 0) * 100);
  probabilityTotal.textContent = `合計 ${total}%`;
  probabilityTotal.classList.toggle("is-warning", total !== 100);
}

async function setStock(prizeId, amount) {
  try {
    await requestJson("/api/set_stock", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prize_id: prizeId, amount: Math.max(0, Number(amount)) }),
    });
    notify("在庫数を更新しました");
  } catch (error) {
    notify(error.message, true);
  }
}

async function saveProbability(prizeId, percent) {
  const value = Math.min(100, Math.max(0, Number(percent)));
  const updates = [{ prize_id: prizeId, probability: value / 100 }];
  if (prizes.length === 2) {
    const other = prizes.find((prize) => prize.id !== prizeId);
    updates.push({ prize_id: other.id, probability: (100 - value) / 100 });
  }

  try {
    await Promise.all(updates.map((payload) => requestJson("/api/set_probability", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })));
    notify("当たりやすさを保存しました");
    await loadPrizes();
  } catch (error) {
    notify(error.message, true);
  }
}

function createPrizeCard(prize, index) {
  const card = document.createElement("article");
  card.className = `prize-card prize-${index % 2 === 0 ? "winner" : "standard"}`;

  const top = document.createElement("div");
  top.className = "prize-top";

  const badge = document.createElement("span");
  badge.className = "prize-badge";
  badge.textContent = index === 0 ? "福" : "縁";

  const title = document.createElement("div");
  title.className = "prize-title";
  const name = document.createElement("h3");
  name.textContent = prize.name;
  const route = document.createElement("small");
  route.textContent = `ホッパー ${String(prize.hopper || "-").toUpperCase()}`;
  title.append(name, route);
  top.append(badge, title);

  const stockSection = document.createElement("div");
  stockSection.className = "control-block";
  stockSection.innerHTML = "<label>カプセル残数</label>";
  if (prize.remaining === null) {
    const unlimited = document.createElement("strong");
    unlimited.className = "unlimited";
    unlimited.textContent = "無制限";
    stockSection.appendChild(unlimited);
  } else {
    const stepper = document.createElement("div");
    stepper.className = "number-stepper";
    const minus = document.createElement("button");
    minus.type = "button";
    minus.textContent = "−";
    minus.setAttribute("aria-label", `${prize.name}を1個減らす`);
    const input = document.createElement("input");
    input.type = "number";
    input.min = "0";
    input.value = prize.remaining;
    input.setAttribute("aria-label", `${prize.name}の在庫`);
    const plus = document.createElement("button");
    plus.type = "button";
    plus.textContent = "+";
    plus.setAttribute("aria-label", `${prize.name}を1個増やす`);
    const save = document.createElement("button");
    save.type = "button";
    save.className = "mini-button";
    save.textContent = "在庫を保存";
    minus.addEventListener("click", () => setStock(prize.id, prize.remaining - 1));
    plus.addEventListener("click", () => setStock(prize.id, prize.remaining + 1));
    save.addEventListener("click", () => setStock(prize.id, input.value));
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") setStock(prize.id, input.value);
    });
    stepper.append(minus, input, plus);
    stockSection.append(stepper, save);
  }

  const probabilitySection = document.createElement("div");
  probabilitySection.className = `control-block probability-block${autoProbabilityByStock ? " is-automatic" : ""}`;
  probabilitySection.innerHTML = "<label>出やすさ</label>";
  const probabilityControls = document.createElement("div");
  probabilityControls.className = "probability-controls";
  const range = document.createElement("input");
  range.type = "range";
  range.min = "0";
  range.max = "100";
  range.step = "1";
  range.value = Math.round(prize.probability * 100);
  range.disabled = autoProbabilityByStock;
  const percentWrap = document.createElement("div");
  percentWrap.className = "percent-input";
  const number = document.createElement("input");
  number.type = "number";
  number.min = "0";
  number.max = "100";
  number.value = range.value;
  number.disabled = autoProbabilityByStock;
  const percentSign = document.createElement("span");
  percentSign.textContent = "%";
  const saveProbabilityButton = document.createElement("button");
  saveProbabilityButton.type = "button";
  saveProbabilityButton.className = "mini-button";
  saveProbabilityButton.textContent = "確率を保存";
  saveProbabilityButton.disabled = autoProbabilityByStock;
  range.addEventListener("input", () => { number.value = range.value; });
  number.addEventListener("input", () => { range.value = number.value; });
  saveProbabilityButton.addEventListener("click", () => saveProbability(prize.id, number.value));
  percentWrap.append(number, percentSign);
  probabilityControls.append(range, percentWrap);
  probabilitySection.append(probabilityControls, saveProbabilityButton);

  card.append(top, stockSection, probabilitySection);
  return card;
}

function renderPrizes(nextPrizes) {
  prizes = nextPrizes;
  prizeList.replaceChildren(...prizes.map(createPrizeCard));
  previewButtons.replaceChildren(...prizes.map((prize, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `button preview-button ${index === 0 ? "winner" : "standard"}`;
    button.innerHTML = `<span>${index === 0 ? "福" : "縁"}</span><b></b><small>演出を見る</small>`;
    button.querySelector("b").textContent = prize.name;
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await requestJson("/api/preview_result", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prize_id: prize.id }),
        });
        notify(`${prize.name}の演出をゲーム画面に表示します`);
      } catch (error) {
        notify(error.message, true);
      } finally {
        button.disabled = false;
      }
    });
    return button;
  }));
  renderSummary();
}

async function loadPrizes() {
  try {
    const data = await requestJson("/api/status");
    renderPrizes(data.prizes);
  } catch (error) {
    notify("在庫情報を読み込めませんでした", true);
  }
}

async function loadSystemStatus() {
  try {
    const data = await requestJson("/api/system_status");
    if (!servoTimingLoaded && data.servo_run_ms) {
      servoTimeA.value = data.servo_run_ms.a;
      servoTimeB.value = data.servo_run_ms.b;
      servoTimingLoaded = true;
    }
    renderAdminError(data.last_error);
    const hardware = data.hardware;
    if (hardware.connected) {
      hardwareTitle.textContent = "接続済み";
      hardwareDetail.textContent = hardware.port ? `${hardware.port} を自動認識` : "USBで通信中";
      setCardState(hardwareCard, "good");
      hardwareHelp.hidden = true;
      headerStatus.className = "header-status is-good";
      headerStatus.querySelector("b").textContent = data.ready ? "本番OK" : "在庫を確認";
      hardwareTestButton.disabled = Boolean(hardware.busy);
      hardwareTestDetail.textContent = hardware.busy
        ? "抽選・排出を確認中です"
        : "本番と同じ抽選・排出・在庫更新を確認";
    } else {
      hardwareTitle.textContent = hardware.enabled ? "未接続" : "USB連携オフ";
      hardwareDetail.textContent = hardware.enabled ? "USBケーブルを確認" : "設定で無効になっています";
      setCardState(hardwareCard, "warning");
      hardwareHelp.hidden = !hardware.enabled;
      headerStatus.className = "header-status is-warning";
      headerStatus.querySelector("b").textContent = "要確認";
      hardwareTestButton.disabled = true;
      hardwareTestDetail.textContent = "Arduinoの接続を待っています";
    }
    if (autoProbabilityByStock !== Boolean(data.auto_probability_by_stock)) {
      autoProbabilityByStock = Boolean(data.auto_probability_by_stock);
      autoProbabilityToggle.checked = autoProbabilityByStock;
      if (prizes.length) renderPrizes(prizes);
    } else {
      autoProbabilityToggle.checked = autoProbabilityByStock;
    }
  } catch (_error) {
    hardwareTitle.textContent = "状態を取得できません";
    setCardState(hardwareCard, "danger");
    hardwareTestButton.disabled = true;
  }
}

showGameButton.addEventListener("click", async () => {
  if (window.pywebview?.api) {
    await window.pywebview.api.show_game();
  } else {
    window.open("/", "bikkurapon-game");
  }
});

fullscreenButton.addEventListener("click", async () => {
  if (window.pywebview?.api) {
    const state = await window.pywebview.api.toggle_game_fullscreen();
    fullscreenButton.textContent = state?.fullscreen
      ? "ゲーム画面の全画面をやめる"
      : "ゲーム画面を全画面にする";
  }
});

window.addEventListener("pywebviewready", async () => {
  document.querySelectorAll(".desktop-only").forEach((element) => { element.hidden = false; });
  const state = await window.pywebview.api.get_window_state();
  fullscreenButton.textContent = state?.fullscreen
    ? "ゲーム画面の全画面をやめる"
    : "ゲーム画面を全画面にする";
});

socket.on("stock_updated", renderPrizes);
socket.on("admin_error", renderAdminError);
socket.on("admin_error_cleared", () => renderAdminError(null));
socket.on("connect", () => {
  loadPrizes();
  loadSystemStatus();
});
socket.on("disconnect", () => {
  headerStatus.className = "header-status is-warning";
  headerStatus.querySelector("b").textContent = "再接続中";
});

loadPrizes();
loadSystemStatus();
window.setInterval(loadSystemStatus, 2000);
