/*
 * びっくらポン ハードウェア担当ファームウェア(Seeed XIAO ESP32-C3 / USB接続版)
 *
 * XIAO ESP32-C3をUSBケーブルでノートPCに直結して使う版。WiFiは使わない。
 * 当たり用・はずれ用、それぞれ専用のホッパー(サーボ)を1個ずつ、
 * 計2個のサーボをこの1枚のESP32で制御する。
 *
 * コインセンサーの投入を検知したら、USBシリアル経由でノートPCに
 * "COIN" という1行を送る。ノートPC側(Flaskサーバー)が抽選し、
 *   - 当たり用ホッパーから排出するなら "DISPENSE:A"
 *   - はずれ用ホッパーから排出するなら "DISPENSE:B"
 *   - どちらも動かさないなら "NONE"
 * を1行返してくるので、それに応じて該当するサーボモーターでカプセルを
 * 排出する。サーボの角度自体はこのファームウェアの固定値(ホッパーごとの
 * 現物合わせ)で、サーバー側は「どちらのホッパーか」だけを指定する。
 *
 * Arduino IDE設定:
 *   - ボード: "XIAO_ESP32C3" を選択(esp32 by Espressif Systems のボードパッケージ内)
 *   - Tools > USB CDC On Boot: "Enabled" にすること
 *     (これをしないとUSB経由のシリアル通信が正しく使えません)
 * 必要なライブラリ:
 *   - ESP32Servo (by Kevin Harrington)
 *
 * 配線例:
 *   - コインセンサー信号線 -> D0(内部プルアップ、投入でLOWになる想定)
 *   - 当たり用ホッパーのサーボ信号線 -> D1
 *   - はずれ用ホッパーのサーボ信号線 -> D2
 */

#include <ESP32Servo.h>

const int COIN_SENSOR_PIN = D0;

const int SERVO_A_PIN = D1;   // 当たり用ホッパー
const int SERVO_B_PIN = D2;   // はずれ用ホッパー

// 2ポケットローターは0度と180度のどちらでも装填／排出できる。
// 角度は個体差が大きいので、実機で組み立てたあとに調整すること。
const int SERVO_A_POSITION_0   = 0;
const int SERVO_A_POSITION_180 = 180;
const int SERVO_B_POSITION_0   = 0;
const int SERVO_B_POSITION_180 = 180;

const unsigned long SERVO_SETTLE_MS = 1000;
const unsigned long DEBOUNCE_MS = 300;
const unsigned long RESPONSE_TIMEOUT_MS = 3000;

Servo servoA;
Servo servoB;
bool servoAAt180 = false;
bool servoBAt180 = false;
unsigned long lastTriggerMs = 0;
bool coinWasLow = false;

void setup() {
  Serial.begin(115200);
  pinMode(COIN_SENSOR_PIN, INPUT_PULLUP);

  servoA.attach(SERVO_A_PIN);
  servoA.write(SERVO_A_POSITION_0);
  servoB.attach(SERVO_B_PIN);
  servoB.write(SERVO_B_POSITION_0);
}

void loop() {
  bool coinIsLow = digitalRead(COIN_SENSOR_PIN) == LOW;
  if (coinIsLow && !coinWasLow) {
    unsigned long now = millis();
    if (now - lastTriggerMs > DEBOUNCE_MS) {
      lastTriggerMs = now;
      handleCoinInserted();
    }
  }
  coinWasLow = coinIsLow;
  delay(20);
}

void handleCoinInserted() {
  Serial.println("COIN");

  String response = waitForResponse(RESPONSE_TIMEOUT_MS);
  if (response.length() == 0) {
    Serial.println("[WARN] ノートPCからの応答がタイムアウトしました。");
    return;
  }

  dispenseIfWon(response);
}

String waitForResponse(unsigned long timeoutMs) {
  unsigned long startMs = millis();
  while (millis() - startMs < timeoutMs) {
    if (Serial.available()) {
      String line = Serial.readStringUntil('\n');
      line.trim();
      if (line.length() > 0) {
        return line;
      }
    }
  }
  return "";
}

void dispenseIfWon(const String &response) {
  if (response == "NONE") {
    Serial.println("はずれ扱い: どちらのホッパーも動かしません。");
    return;
  }

  if (response == "DISPENSE:A") {
    Serial.println("当たり: ホッパーAからカプセルを排出します。");
    advanceRotor(
      servoA, servoAAt180, SERVO_A_POSITION_0, SERVO_A_POSITION_180
    );
    return;
  }

  if (response == "DISPENSE:B") {
    Serial.println("はずれ景品: ホッパーBからカプセルを排出します。");
    advanceRotor(
      servoB, servoBAt180, SERVO_B_POSITION_0, SERVO_B_POSITION_180
    );
    return;
  }

  Serial.println("[WARN] 想定外の応答: " + response);
}

void advanceRotor(Servo &servo, bool &at180, int position0, int position180) {
  at180 = !at180;
  servo.write(at180 ? position180 : position0);
  delay(SERVO_SETTLE_MS);
}
