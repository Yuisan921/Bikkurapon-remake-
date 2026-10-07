const socket = io();

const screens = {
  idle: document.getElementById("idle-screen"),
  playing: document.getElementById("playing-screen"),
  result: document.getElementById("result-screen"),
  soldout: document.getElementById("soldout-screen"),
};
const stage = document.getElementById("stage");
const resultTitle = document.getElementById("result-title");
const resultMessage = document.getElementById("result-message");

const RESULT_DISPLAY_MS = 4000;
const PLAYING_DURATION_MS = 2500;

let playingTimer = null;
let resetTimer = null;
// 抽選演出(抽選中〜結果表示)の最中かどうか。演出中は在庫更新の通知で
// 画面を切り替えず、演出が終わって待機画面に戻るときにまとめて反映する。
let busy = false;
// 抽選できる景品が1つでも残っているか。false の間は待機画面の代わりに
// 「巫女さんを呼んでください」画面を出す。
let hasStock = true;

function showScreen(name) {
  Object.values(screens).forEach((el) => el.classList.add("hidden"));
  screens[name].classList.remove("hidden");
}

function clearTimers() {
  if (playingTimer) {
    clearTimeout(playingTimer);
    playingTimer = null;
  }
  if (resetTimer) {
    clearTimeout(resetTimer);
    resetTimer = null;
  }
}

function showSoldout() {
  clearTimers();
  busy = false;
  stage.className = "state-soldout";
  showScreen("soldout");
}

function goIdle() {
  busy = false;
  if (!hasStock) {
    showSoldout();
    return;
  }
  stage.className = "state-idle";
  showScreen("idle");
}

function hasAnyStock(prizes) {
  // サーバー側の抽選と同じ判定: 在庫無制限(null)か、残数が1以上の景品があるか
  return prizes.some((p) => p.remaining === null || p.remaining > 0);
}

function applyStock(prizes) {
  hasStock = hasAnyStock(prizes);
  if (!busy) {
    goIdle();
  }
}

socket.on("connect", () => {
  // 画面を開いた直後・再接続時に、現在の在庫状況を見て待機画面か在庫切れ画面を決める
  fetch("/api/status")
    .then((res) => res.json())
    .then((data) => applyStock(data.prizes))
    .catch(goIdle);
});

socket.on("stock_updated", applyStock);

socket.on("out_of_stock", () => {
  hasStock = false;
  showSoldout();
});

socket.on("draw_result", (result) => {
  clearTimers();
  busy = true;

  stage.className = "state-playing";
  showScreen("playing");

  playingTimer = setTimeout(() => {
    playingTimer = null;
    stage.className = `state-result state-${result.id}`;
    resultTitle.textContent = result.name;
    if (result.remaining === 0) {
      resultMessage.textContent = `${result.name}!(この景品は在庫終了です)`;
    } else {
      resultMessage.textContent = "カプセルが出てくるよ!";
    }
    showScreen("result");

    resetTimer = setTimeout(goIdle, RESULT_DISPLAY_MS);
  }, PLAYING_DURATION_MS);
});

const debugButton = document.getElementById("debug-insert-coin");
if (debugButton) {
  debugButton.addEventListener("click", () => {
    fetch("/api/insert_coin", { method: "POST" });
  });
}
