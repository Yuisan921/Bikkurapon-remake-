/*
 * びっくらポン ハードウェア担当ファームウェア(Seeed XIAO ESP32-C3 / USB接続版)
 *
 * XIAO ESP32-C3をUSBケーブルでノートPCに直結して使う版。WiFiは使わない。
 * 当たり用・はずれ用、それぞれ専用のホッパー(サーボ)を1個ずつ、
 * 計2個のサーボをこの1枚のESP32で制御する。
 *
 * コインセンサーの投入を検知したら、USBシリアル経由でノートPCに
 * "COIN:<連番>" を送る。ノートPC側が予約番号付きのDISPENSE命令を返し、
 * サーボ動作後に "DONE:<予約番号>" を返して初めて在庫と当選表示を確定する。
 * タイムアウトやUSB切断時は予約が取り消され、在庫だけ減ることを防ぐ。
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
<<<<<<< HEAD
bool coinWasLow = false;
=======
unsigned long coinSequence = 0;
bool coinArmed = true;
>>>>>>> 251ce8c766819690cefd0f56fca9b64794677e31

void setup() {
  Serial.begin(115200);
  pinMode(COIN_SENSOR_PIN, INPUT_PULLUP);

  servoA.attach(SERVO_A_PIN);
  servoA.write(SERVO_A_POSITION_0);
  servoB.attach(SERVO_B_PIN);
  servoB.write(SERVO_B_POSITION_0);
}

void loop() {
<<<<<<< HEAD
  bool coinIsLow = digitalRead(COIN_SENSOR_PIN) == LOW;
  if (coinIsLow && !coinWasLow) {
=======
  bool coinLow = digitalRead(COIN_SENSOR_PIN) == LOW;
  if (coinLow && coinArmed) {
>>>>>>> 251ce8c766819690cefd0f56fca9b64794677e31
    unsigned long now = millis();
    if (now - lastTriggerMs > DEBOUNCE_MS) {
      lastTriggerMs = now;
      coinArmed = false;
      handleCoinInserted();
    }
  } else if (!coinLow) {
    // 一度投入を処理したら、信号がHIGHへ戻るまで次の投入を受け付けない。
    coinArmed = true;
  }
  coinWasLow = coinIsLow;
  delay(20);
}

void handleCoinInserted() {
  String coinId = String(++coinSequence);
  Serial.println("COIN:" + coinId);

  String response = waitForResponse(coinId, RESPONSE_TIMEOUT_MS);
  if (response.length() == 0) {
    Serial.println("[WARN] ノートPCからの応答がタイムアウトしました。");
    return;
  }

  dispenseIfWon(response);
}

String waitForResponse(const String &coinId, unsigned long timeoutMs) {
  unsigned long startMs = millis();
  String noneResponse = "NONE:" + coinId;
  String dispensePrefix = "DISPENSE:" + coinId + ":";
  while (millis() - startMs < timeoutMs) {
    if (Serial.available()) {
      String line = Serial.readStringUntil('\n');
      line.trim();
      // 前回タイムアウト後に遅れて届いた命令はcoinIdが違うので捨てる。
      if (line == noneResponse || line.startsWith(dispensePrefix)) {
        return line;
      }
    }
  }
  return "";
}

void dispenseIfWon(const String &response) {
  if (response.startsWith("NONE:")) {
    Serial.println("はずれ扱い: どちらのホッパーも動かしません。");
    return;
  }

  // DISPENSE:<coinId>:<reservationId>:<hopper>
  int firstColon = response.indexOf(':');
  int secondColon = response.indexOf(':', firstColon + 1);
  int thirdColon = response.indexOf(':', secondColon + 1);
  if (firstColon < 0 || secondColon < 0 || thirdColon < 0) {
    Serial.println("[WARN] 想定外の応答: " + response);
    return;
  }
  String reservationId = response.substring(secondColon + 1, thirdColon);
  String hopper = response.substring(thirdColon + 1);
  bool success = false;

  if (hopper == "A") {
    Serial.println("当たり: ホッパーAからカプセルを排出します。");
<<<<<<< HEAD
    advanceRotor(
      servoA, servoAAt180, SERVO_A_POSITION_0, SERVO_A_POSITION_180
    );
    return;
=======
    dispenseFrom(servoA, SERVO_A_REST_ANGLE, SERVO_A_DISPENSE_ANGLE);
    success = true;
>>>>>>> 251ce8c766819690cefd0f56fca9b64794677e31
  }
  else if (hopper == "B") {
    Serial.println("はずれ景品: ホッパーBからカプセルを排出します。");
<<<<<<< HEAD
    advanceRotor(
      servoB, servoBAt180, SERVO_B_POSITION_0, SERVO_B_POSITION_180
    );
    return;
=======
    dispenseFrom(servoB, SERVO_B_REST_ANGLE, SERVO_B_DISPENSE_ANGLE);
    success = true;
  } else {
    Serial.println("[WARN] 想定外のホッパー: " + hopper);
>>>>>>> 251ce8c766819690cefd0f56fca9b64794677e31
  }

  String ack = success ? "DONE:" : "FAILED:";
  ack += reservationId;
  Serial.println(ack);
}

void advanceRotor(Servo &servo, bool &at180, int position0, int position180) {
  at180 = !at180;
  servo.write(at180 ? position180 : position0);
  delay(SERVO_SETTLE_MS);
}
