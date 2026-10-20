#include <Servo.h>

// 赤外線センサーのデジタル出力(OUT)をD2へ接続します。
// 一般的な障害物センサーモジュールは遮られたときLOWになります。
// お使いのセンサーが逆の場合は LOW を HIGH に変えてください。
const int COIN_SENSOR_PIN = 2;
const int COIN_DETECTED_LEVEL = LOW;

const int SERVO_A_PIN = 9;   // 当たり
const int SERVO_B_PIN = 10;  // はずれ

// 今回の連続回転サーボ用。通常の角度指定サーボを使う側だけ false に変更。
#ifndef SERVO_A_CONTINUOUS
#define SERVO_A_CONTINUOUS true
#endif
#ifndef SERVO_B_CONTINUOUS
#define SERVO_B_CONTINUOUS true
#endif

// 連続回転型では角度ではなく、停止・速度と回転時間を指定する。
// 停止中にゆっくり動く個体はSTOP_USを5〜10ずつ調整する。
const int SERVO_A_STOP_US = 1500;
const int SERVO_B_STOP_US = 1500;
const int SERVO_A_RUN_US = 1600;
const int SERVO_B_RUN_US = 1600;
// 実測0.3秒で約70度 → 半回転の目安は0.77秒。PC管理画面でも調整できる。
const unsigned long SERVO_A_RUN_MS = 770;
const unsigned long SERVO_B_RUN_MS = 770;

// 以下の角度は CONTINUOUS が false のサーボだけに使う。
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

  // 最初の信号から停止値になるよう、attachより先に値を設定する。
  stopServo(servoA, SERVO_A_CONTINUOUS, SERVO_A_REST_ANGLE, SERVO_A_STOP_US);
  servoA.attach(SERVO_A_PIN);
  stopServo(servoB, SERVO_B_CONTINUOUS, SERVO_B_REST_ANGLE, SERVO_B_STOP_US);
  servoB.attach(SERVO_B_PIN);
}

void loop() {
  // 管理画面の実機テストはコイン投入なしで届く。
  // 古いコインへの応答を誤って実行しないよう、予約番号だけの形式を受け付ける。
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    if (command.startsWith("RUN:")) {
      handleTimedCommand(command);
    } else if (isTestCommand(command)) {
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

      if (line.startsWith("RUN:")) {
        handleTimedCommand(line);
        continue;
      }

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

  executeDispense(reservationId, hopper, 0);
}

void handleTimedCommand(const String &command) {
  // RUN:<reservationId>:<hopper>:<milliseconds> は演出終了後にPCから届く。
  int second = command.indexOf(':', 4);
  int third = command.indexOf(':', second + 1);
  if (second <= 4 || third < 0) return;
  String reservationId = command.substring(4, second);
  String hopper = command.substring(second + 1, third);
  String duration = command.substring(third + 1);
  unsigned long runMs = 0;
  bool valid = duration.length() > 0 && duration.length() <= 4;
  for (unsigned int i = 0; valid && i < duration.length(); ++i) {
    if (duration[i] < '0' || duration[i] > '9') valid = false;
    else runMs = runMs * 10 + (duration[i] - '0');
  }
  if (!valid || runMs < 50 || runMs > 2000) {
    Serial.println("FAILED:" + reservationId);
    return;
  }
  executeDispense(reservationId, hopper, runMs);
}

void executeDispense(const String &reservationId, const String &hopper, unsigned long runMs) {
  bool success = false;

  if (hopper == "A") {

    Serial.println(
      "ホッパーA排出"
    );

    dispenseFrom(
      servoA,
      SERVO_A_CONTINUOUS,
      SERVO_A_REST_ANGLE,
      SERVO_A_DISPENSE_ANGLE,
      SERVO_A_STOP_US,
      SERVO_A_RUN_US,
      runMs ? runMs : SERVO_A_RUN_MS
    );

    success = true;
  }

  else if (hopper == "B") {

    Serial.println(
      "ホッパーB排出"
    );

    dispenseFrom(
      servoB,
      SERVO_B_CONTINUOUS,
      SERVO_B_REST_ANGLE,
      SERVO_B_DISPENSE_ANGLE,
      SERVO_B_STOP_US,
      SERVO_B_RUN_US,
      runMs ? runMs : SERVO_B_RUN_MS
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

void stopServo(Servo &servo, bool continuous, int restAngle, int stopUs) {
  if (continuous) {
    servo.writeMicroseconds(stopUs);
  } else {
    servo.write(restAngle);
  }
}

void dispenseFrom(Servo &servo, bool continuous, int restAngle, int dispenseAngle,
                  int stopUs, int runUs, unsigned long runMs) {
  if (continuous) {
    servo.writeMicroseconds(runUs);
    delay(runMs);
  } else {
    servo.write(dispenseAngle);
    delay(SERVO_HOLD_MS);
  }
  stopServo(servo, continuous, restAngle, stopUs);
  // 停止信号の送出周期を待ってから完了通知する。実排出の検知ではない。
  delay(40);
}
