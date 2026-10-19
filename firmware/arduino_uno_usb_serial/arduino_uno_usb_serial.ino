#include <Servo.h>

// 赤外線センサーのデジタル出力(OUT)をD2へ接続します。
// 一般的な障害物センサーモジュールは遮られたときLOWになります。
// お使いのセンサーが逆の場合は LOW を HIGH に変えてください。
const int COIN_SENSOR_PIN = 2;
const int COIN_DETECTED_LEVEL = LOW;

const int SERVO_A_PIN = 9;   // 当たり
const int SERVO_B_PIN = 10;  // はずれ

const int SERVO_A_REST_ANGLE = 0;
const int SERVO_A_DISPENSE_ANGLE = 90;
const int SERVO_B_REST_ANGLE = 0;
const int SERVO_B_DISPENSE_ANGLE = 90;

const unsigned long SERVO_HOLD_MS = 1000;
const unsigned long DEBOUNCE_MS = 300;
const unsigned long SENSOR_CLEAR_MS = 150;
const unsigned long RESPONSE_TIMEOUT_MS = 3000;

Servo servoA;
Servo servoB;

unsigned long lastTriggerMs = 0;
unsigned long coinSequence = 0;
unsigned long sensorClearSinceMs = 0;
bool coinArmed = true;

void setup() {
  Serial.begin(115200);

  pinMode(COIN_SENSOR_PIN, INPUT_PULLUP);

  servoA.attach(SERVO_A_PIN);
  servoA.write(SERVO_A_REST_ANGLE);

  servoB.attach(SERVO_B_PIN);
  servoB.write(SERVO_B_REST_ANGLE);
}

void loop() {
  // 管理画面の実機テストはコイン投入なしで届く。
  // 古いコインへの応答を誤って実行しないよう、予約番号だけの形式を受け付ける。
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    if (isTestCommand(command)) {
      dispenseIfWon(command);
    }
  }

  bool coinDetected = digitalRead(COIN_SENSOR_PIN) == COIN_DETECTED_LEVEL;
  unsigned long now = millis();

  if (coinDetected) {
    sensorClearSinceMs = 0;
    if (now - lastTriggerMs > DEBOUNCE_MS) {
      if (coinArmed) {
        lastTriggerMs = now;
        coinArmed = false;
        handleCoinInserted();
      }
    }
  }
  else if (!coinArmed) {
    // 光が一瞬戻っただけで再受付すると、1枚のコインを複数回数えることが
    // あるため、センサーが一定時間空いたことを確認してから次を受け付けます。
    if (sensorClearSinceMs == 0) {
      sensorClearSinceMs = now;
    }
    else if (now - sensorClearSinceMs >= SENSOR_CLEAR_MS) {
      coinArmed = true;
    }
  }

  delay(20);
}

void handleCoinInserted() {
  String coinId = String(++coinSequence);

  Serial.println("COIN:" + coinId);

  String response = waitForResponse(
    coinId,
    RESPONSE_TIMEOUT_MS
  );

  if (response.length() == 0) {
    Serial.println("[WARN] PCからの応答がタイムアウトしました");
    return;
  }

  dispenseIfWon(response);
}

String waitForResponse(
  const String &coinId,
  unsigned long timeoutMs
) {
  unsigned long startMs = millis();

  String noneResponse =
    "NONE:" + coinId;

  String dispensePrefix =
    "DISPENSE:" + coinId + ":";

  while (millis() - startMs < timeoutMs) {

    if (Serial.available()) {

      String line =
        Serial.readStringUntil('\n');

      line.trim();

      // コインの応答待ち中に管理画面からテスト命令が届いた場合も処理する。
      if (isTestCommand(line)) {
        dispenseIfWon(line);
        continue;
      }

      if (
        line == noneResponse ||
        line.startsWith(dispensePrefix)
      ) {
        return line;
      }
    }
  }

  return "";
}

bool isTestCommand(const String &command) {
  // テスト: DISPENSE:<reservationId>:<hopper>
  // コイン: DISPENSE:<coinId>:<reservationId>:<hopper>
  if (!command.startsWith("DISPENSE:")) return false;
  int separator = command.indexOf(':', 9);
  return separator > 9 && command.indexOf(':', separator + 1) < 0;
}

void dispenseIfWon(
  const String &response
) {

  if (response == "NONE" || response.startsWith("NONE:")) {
    Serial.println(
      "排出なし"
    );
    return;
  }

  int firstColon =
    response.indexOf(':');

  int secondColon =
    response.indexOf(
      ':',
      firstColon + 1
    );

  int thirdColon =
    response.indexOf(
      ':',
      secondColon + 1
    );

  if (
    firstColon < 0 ||
    secondColon < 0 ||
    !response.startsWith("DISPENSE:")
  ) {
    Serial.println(
      "[WARN] 想定外の応答"
    );
    return;
  }

  // コイン番号の有無に応じて予約番号を取り出す。
  int reservationStart = thirdColon < 0 ? firstColon + 1 : secondColon + 1;
  int reservationEnd = thirdColon < 0 ? secondColon : thirdColon;
  String reservationId = response.substring(reservationStart, reservationEnd);
  String hopper = response.substring(reservationEnd + 1);
  if (reservationId.length() == 0) return;

  bool success = false;

  if (hopper == "A") {

    Serial.println(
      "ホッパーA排出"
    );

    dispenseFrom(
      servoA,
      SERVO_A_REST_ANGLE,
      SERVO_A_DISPENSE_ANGLE
    );

    success = true;
  }

  else if (hopper == "B") {

    Serial.println(
      "ホッパーB排出"
    );

    dispenseFrom(
      servoB,
      SERVO_B_REST_ANGLE,
      SERVO_B_DISPENSE_ANGLE
    );

    success = true;
  }

  else {
    Serial.println(
      "[WARN] 不明なホッパー"
    );
  }

  String ack =
    success ? "DONE:" : "FAILED:";

  ack += reservationId;

  Serial.println(ack);
}

void dispenseFrom(
  Servo &servo,
  int restAngle,
  int dispenseAngle
) {
  servo.write(dispenseAngle);

  delay(SERVO_HOLD_MS);

  servo.write(restAngle);
}
