const socket = io();

const screens = {
  idle: document.getElementById("idle-screen"),
  playing: document.getElementById("playing-screen"),
  video: document.getElementById("video-screen"),
  result: document.getElementById("result-screen"),
  error: document.getElementById("error-screen"),
  soldout: document.getElementById("soldout-screen"),
};

const stage = document.getElementById("stage");
const connectionState = document.getElementById("connection-state");
const connectionLabel = connectionState.querySelector(".connection-label");
const rouletteSymbol = document.getElementById("roulette-symbol");
const playingCaption = document.getElementById("playing-caption");
const resultTitle = document.getElementById("result-title");
const resultMessage = document.getElementById("result-message");
const resultSymbol = document.getElementById("result-symbol");
const resultVideo = document.getElementById("result-video");
const confetti = document.getElementById("confetti");
const navAdmin = document.getElementById("nav-admin");
const navFullscreen = document.getElementById("nav-fullscreen");
const navHideGame = document.getElementById("nav-hide-game");
const navCloseApp = document.getElementById("nav-close-app");

const MIN_PLAYING_MS = 3200;
const RESULT_DISPLAY_MS = 5200;
const ERROR_DISPLAY_MS = 5000;
const rouletteSymbols = ["火", "水", "風", "雷", "福", "縁", "祭"];
const captions = [
  "木霊たちが運を選んでいます…",
  "御神木の力を集めています…",
  "古いガチャが動きはじめた！",
  "もうすぐカプセルが決まるよ！",
];

let hasStock = true;
let busy = false;
let playingStartedAt = 0;
let rouletteTimer = null;
let captionTimer = null;
let revealTimer = null;
let resetTimer = null;
let queuedResult = null;

function setFullscreenLabel(isFullscreen) {
  navFullscreen.textContent = isFullscreen ? "全画面をやめる" : "全画面にする";
}

async function showAdminWindow() {
  if (window.pywebview?.api) {
    await window.pywebview.api.show_admin();
    setFullscreenLabel(false);
  } else {
    window.open("/admin", "bikkurapon-admin");
  }
}

async function toggleFullscreen() {
  if (window.pywebview?.api) {
    const state = await window.pywebview.api.toggle_game_fullscreen();
    setFullscreenLabel(Boolean(state?.fullscreen));
    return;
  }

  if (document.fullscreenElement) {
    await document.exitFullscreen();
  } else {
    await document.documentElement.requestFullscreen();
  }
  setFullscreenLabel(Boolean(document.fullscreenElement));
}

async function hideGameWindow() {
  if (window.pywebview?.api) {
    await window.pywebview.api.hide_game();
    setFullscreenLabel(false);
  } else {
    window.location.href = "/admin";
  }
}

async function closeApplication() {
  if (!window.confirm("ゲーム画面を閉じますか？\n管理画面からもう一度開けます。")) return;
  if (window.pywebview?.api) {
    await window.pywebview.api.close_app();
  } else {
    window.close();
  }
}

function showScreen(name) {
  Object.values(screens).forEach((screen) => screen.classList.add("hidden"));
  screens[name].classList.remove("hidden");
}

function clearAnimationTimers() {
  [rouletteTimer, captionTimer, revealTimer, resetTimer].forEach((timer) => {
    if (timer) window.clearInterval(timer);
  });
  rouletteTimer = null;
  captionTimer = null;
  revealTimer = null;
  resetTimer = null;
}

function resetResultVideo() {
  resultVideo.onerror = null;
  resultVideo.onended = null;
  resultVideo.pause();
  resultVideo.removeAttribute("src");
  resultVideo.load();
  screens.video.classList.remove("is-preview");
}

function setConnection(connected) {
  connectionState.classList.toggle("is-online", connected);
  connectionState.classList.toggle("is-offline", !connected);
  connectionLabel.textContent = connected ? "ゲーム接続中" : "接続を待っています";
}

function showIdle() {
  clearAnimationTimers();
  resetResultVideo();
  busy = false;
  queuedResult = null;
  confetti.replaceChildren();
  if (!hasStock) {
    showSoldout();
    return;
  }
  stage.className = "state-idle";
  showScreen("idle");
}

function showSoldout() {
  clearAnimationTimers();
  busy = false;
  stage.className = "state-soldout";
  showScreen("soldout");
}

function startPlaying() {
  clearAnimationTimers();
  busy = true;
  queuedResult = null;
  playingStartedAt = Date.now();
  stage.className = "state-playing";
  showScreen("playing");

  let symbolIndex = 0;
  rouletteTimer = window.setInterval(() => {
    symbolIndex = (symbolIndex + 1) % rouletteSymbols.length;
    rouletteSymbol.textContent = rouletteSymbols[symbolIndex];
  }, 110);

  let captionIndex = 0;
  playingCaption.textContent = captions[captionIndex];
  captionTimer = window.setInterval(() => {
    captionIndex = (captionIndex + 1) % captions.length;
    playingCaption.textContent = captions[captionIndex];
  }, 850);
}

function makeConfetti() {
  confetti.replaceChildren();
  const colors = ["#ffcb3c", "#ef4b45", "#50c9b5", "#ffffff", "#f18bb7"];
  for (let index = 0; index < 36; index += 1) {
    const piece = document.createElement("i");
    piece.style.setProperty("--x", `${Math.random() * 100}vw`);
    piece.style.setProperty("--delay", `${Math.random() * 0.8}s`);
    piece.style.setProperty("--duration", `${2.2 + Math.random() * 1.8}s`);
    piece.style.setProperty("--rotation", `${Math.random() * 720 - 360}deg`);
    piece.style.background = colors[index % colors.length];
    confetti.appendChild(piece);
  }
}

function showFallbackResult(result) {
  resetResultVideo();
  const isWinner = result.id === "atari" || String(result.hopper).toLowerCase() === "a";
  stage.className = `state-result ${isWinner ? "state-atari" : "state-hazure"}`;
  resultSymbol.textContent = isWinner ? "福" : "縁";
  resultTitle.textContent = result.name;
  resultMessage.textContent = result.preview
    ? "これは画面だけのテストです"
    : isWinner
      ? "大当たりのカプセルを受け取ってね！"
      : "参加賞のカプセルを受け取ってね！";
  showScreen("result");
  makeConfetti();
  resetTimer = window.setTimeout(showIdle, RESULT_DISPLAY_MS);
}

function revealResult(result) {
  window.clearInterval(rouletteTimer);
  window.clearInterval(captionTimer);
  rouletteTimer = null;
  captionTimer = null;

  if (!result.video) {
    showFallbackResult(result);
    return;
  }

  stage.className = "state-video";
  screens.video.classList.toggle("is-preview", Boolean(result.preview));
  showScreen("video");
  let fellBack = false;
  const fallback = () => {
    if (fellBack) return;
    fellBack = true;
    showFallbackResult(result);
  };
  resultVideo.onerror = fallback;
  resultVideo.onended = () => {
    resetTimer = window.setTimeout(showIdle, 500);
  };
  resultVideo.src = result.video;
  resultVideo.load();
  const playback = resultVideo.play();
  if (playback) playback.catch(fallback);
}

function queueResult(result) {
  if (!busy) startPlaying();
  queuedResult = result;
  const elapsed = Date.now() - playingStartedAt;
  revealTimer = window.setTimeout(() => {
    if (queuedResult) revealResult(queuedResult);
    queuedResult = null;
  }, Math.max(0, MIN_PLAYING_MS - elapsed));
}

function showDispenseError() {
  clearAnimationTimers();
  busy = true;
  stage.className = "state-error";
  showScreen("error");
  resetTimer = window.setTimeout(showIdle, ERROR_DISPLAY_MS);
}

function hasAnyStock(prizes) {
  return prizes.some((prize) => prize.remaining === null || prize.remaining > 0);
}

function applyStock(prizes) {
  hasStock = hasAnyStock(prizes);
  if (!busy) showIdle();
}

socket.on("connect", () => {
  setConnection(true);
  fetch("/api/status")
    .then((response) => response.json())
    .then((data) => applyStock(data.prizes))
    .catch(() => setConnection(false));
});

socket.on("disconnect", () => setConnection(false));
socket.on("stock_updated", applyStock);
socket.on("draw_started", startPlaying);
socket.on("draw_result", queueResult);
socket.on("draw_cancelled", showDispenseError);
socket.on("out_of_stock", () => {
  hasStock = false;
  showSoldout();
});

navAdmin.addEventListener("click", showAdminWindow);
navFullscreen.addEventListener("click", toggleFullscreen);
navHideGame.addEventListener("click", hideGameWindow);
navCloseApp.addEventListener("click", closeApplication);
document.addEventListener("fullscreenchange", () => {
  if (!window.pywebview?.api) setFullscreenLabel(Boolean(document.fullscreenElement));
});
window.addEventListener("pywebviewready", async () => {
  const state = await window.pywebview.api.get_window_state();
  setFullscreenLabel(Boolean(state?.fullscreen));
});
