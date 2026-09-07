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

// サーボの角度は個体差が大きいので、実機で組み立てたあとに調整すること
const int SERVO_A_REST_ANGLE     = 0;
const int SERVO_A_DISPENSE_ANGLE = 90;
const int SERVO_B_REST_ANGLE     = 0;
const int SERVO_B_DISPENSE_ANGLE = 90;

const unsigned long SERVO_HOLD_MS = 1000;
const unsigned long DEBOUNCE_MS = 300;
const unsigned long RESPONSE_TIMEOUT_MS = 3000;

Servo servoA;
Servo servoB;
unsigned long lastTriggerMs = 0;

void setup() {
  Serial.begin(115200);
  pinMode(COIN_SENSOR_PIN, INPUT_PULLUP);

  servoA.attach(SERVO_A_PIN);
  servoA.write(SERVO_A_REST_ANGLE);
  servoB.attach(SERVO_B_PIN);
  servoB.write(SERVO_B_REST_ANGLE);
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
    Serial.println("はずれ扱い: どちらのホッパーも動かしません。");
    return;
  }

  if (response == "DISPENSE:A") {
    Serial.println("当たり: ホッパーAからカプセルを排出します。");
    dispenseFrom(servoA, SERVO_A_REST_ANGLE, SERVO_A_DISPENSE_ANGLE);
    return;
  }

  if (response == "DISPENSE:B") {
    Serial.println("はずれ景品: ホッパーBからカプセルを排出します。");
    dispenseFrom(servoB, SERVO_B_REST_ANGLE, SERVO_B_DISPENSE_ANGLE);
    return;
  }

  Serial.println("[WARN] 想定外の応答: " + response);
}

void dispenseFrom(Servo &servo, int restAngle, int dispenseAngle) {
  servo.write(dispenseAngle);
  delay(SERVO_HOLD_MS);
  servo.write(restAngle);
}
