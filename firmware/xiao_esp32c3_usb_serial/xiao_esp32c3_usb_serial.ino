/*
 * びっくらポン ハードウェア担当ファームウェア(Seeed XIAO ESP32-C3 / USB接続版)
 *
 * XIAO ESP32-C3をUSBケーブルでノートPCに直結して使う版。WiFiは使わない。
 *
 * コインセンサーの投入を検知したら、USBシリアル経由でノートPCに
 * "COIN" という1行を送る。ノートPC側(Flaskサーバー)が抽選し、
 *   - 当選なら "DISPENSE:<角度>"
 *   - はずれなら "NONE"
 * を1行返してくるので、それに応じてサーボモーターでカプセルを排出する。
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
 *   - サーボモーター信号線 -> D1
 */

#include <ESP32Servo.h>

const int COIN_SENSOR_PIN = D0;
const int SERVO_PIN = D1;
const int SERVO_REST_ANGLE = 0;
const unsigned long SERVO_HOLD_MS = 1000;
const unsigned long DEBOUNCE_MS = 300;
const unsigned long RESPONSE_TIMEOUT_MS = 3000;

Servo capsuleServo;
unsigned long lastTriggerMs = 0;

void setup() {
  Serial.begin(115200);
  pinMode(COIN_SENSOR_PIN, INPUT_PULLUP);

  capsuleServo.attach(SERVO_PIN);
  capsuleServo.write(SERVO_REST_ANGLE);
}

void loop() {
  if (digitalRead(COIN_SENSOR_PIN) == LOW) {
    unsigned long now = millis();
    if (now - lastTriggerMs > DEBOUNCE_MS) {
      lastTriggerMs = now;
      handleCoinInserted();
    }
  }
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
    Serial.println("はずれ: カプセルは排出しません。");
    return;
  }

  if (response.startsWith("DISPENSE:")) {
    int angle = response.substring(strlen("DISPENSE:")).toInt();
    Serial.printf("当選: サーボを%d度に動かしてカプセルを排出します。\n", angle);
    capsuleServo.write(angle);
    delay(SERVO_HOLD_MS);
    capsuleServo.write(SERVO_REST_ANGLE);
    return;
  }

  Serial.println("[WARN] 想定外の応答: " + response);
}
