const socket = io();

const screens = {
  idle: document.getElementById("idle-screen"),
  playing: document.getElementById("playing-screen"),
  result: document.getElementById("result-screen"),
};
const stage = document.getElementById("stage");
const resultTitle = document.getElementById("result-title");
const resultMessage = document.getElementById("result-message");

const RESULT_DISPLAY_MS = 4000;
const PLAYING_DURATION_MS = 2500;

let resetTimer = null;

function showScreen(name) {
  Object.values(screens).forEach((el) => el.classList.add("hidden"));
  screens[name].classList.remove("hidden");
}

function goIdle() {
  stage.className = "state-idle";
  showScreen("idle");
}

socket.on("connect", goIdle);

socket.on("draw_result", (result) => {
  if (resetTimer) {
    clearTimeout(resetTimer);
  }

  stage.className = "state-playing";
  showScreen("playing");

  setTimeout(() => {
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
