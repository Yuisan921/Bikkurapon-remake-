#include <Servo.h>

const char FIRMWARE_VERSION[] = "2.7.2";

// コイン通路を挟んでLEDとCdSを向かい合わせ、コインが光を遮る変化を検知する。
// LED: D4 -- 220〜330Ω -- LED -- GND
// CdS分圧: 5V -- CdS -- A0 -- 10kΩ -- GND
#ifndef COIN_SENSOR_USE_CDS
#define COIN_SENSOR_USE_CDS true
#endif
const int COIN_LED_PIN = 4;
const int COIN_CDS_PIN = A0;

// 以前のデジタル赤外線センサーへ戻す場合だけCOIN_SENSOR_USE_CDSをfalseにする。
const int COIN_SENSOR_PIN = 2;
const int COIN_DETECTED_LEVEL = LOW;

// 起動時の「LEDが直接当たっている明るさ」から何%以上暗くなればコインとみなすか。
// 誤反応するときは割合を上げ、反応しにくいときは下げる。
const int CDS_BLOCK_DROP_PERCENT = 25;
const int CDS_BLOCK_MIN_DROP = 80;  // 0〜1023の読み値で最低限必要な差
const int CDS_MIN_LIT_VALUE = 150;  // これ未満ならLED・CdS・抵抗の配線を確認

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
// 当たり側の個体では1600µsが停止帯に近く回らなかったため、1700µsへ広げる。
const int SERVO_A_RUN_US = 1700;
// はずれ側は機構が反対向きなので、停止値を挟んでA側と逆方向へ回す。
// この値は通常排出と管理画面の長押し調整の両方に使われる。
const int SERVO_B_RUN_US = 1400;
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
const unsigned long SENSOR_BLOCK_CONFIRM_MS = 20;
const unsigned long SENSOR_CLEAR_MS = 150;
const unsigned long RESPONSE_TIMEOUT_MS = 3000;
const unsigned long MANUAL_SERVO_TIMEOUT_MS = 2000;

Servo servoA;
Servo servoB;

unsigned long lastTriggerMs = 0;
unsigned long coinSequence = 0;
unsigned long sensorBlockedSinceMs = 0;
unsigned long sensorClearSinceMs = 0;
bool coinArmed = true;
int coinLightBaseline = 0;
bool manualServoActive = false;
String manualServoHopper = "";
unsigned long manualServoLastCommandMs = 0;

void setup() {
  Serial.begin(115200);
  Serial.println("FIRMWARE:" + String(FIRMWARE_VERSION));

  if (COIN_SENSOR_USE_CDS) {
    pinMode(COIN_LED_PIN, OUTPUT);
    digitalWrite(COIN_LED_PIN, HIGH);
    calibrateCoinLight();
  } else {
    pinMode(COIN_SENSOR_PIN, INPUT_PULLUP);
    Serial.println("SENSOR:DIGITAL");
  }

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
    if (command.startsWith("MANUAL:")) {
      handleManualServoCommand(command);
    } else if (command.startsWith("RUN:")) {
      handleTimedCommand(command);
    } else if (isTestCommand(command)) {
      dispenseIfWon(command);
    }
  }

  if (manualServoActive && millis() - manualServoLastCommandMs >= MANUAL_SERVO_TIMEOUT_MS) {
    stopManualServos();
    Serial.println("MANUAL:TIMEOUT");
  }
  if (manualServoActive) {
    // 位置調整中の遮光をコインとして数えない。
    sensorBlockedSinceMs = 0;
    sensorClearSinceMs = 0;
    delay(20);
    return;
  }

  bool coinDetected = isCoinDetected();
  unsigned long now = millis();

  if (coinDetected) {
    sensorClearSinceMs = 0;
    if (sensorBlockedSinceMs == 0) {
      sensorBlockedSinceMs = now;
    }
    if (now - sensorBlockedSinceMs >= SENSOR_BLOCK_CONFIRM_MS) {
      if (coinArmed && now - lastTriggerMs > DEBOUNCE_MS) {
        lastTriggerMs = now;
        coinArmed = false;
        handleCoinInserted();
      }
    }
  }
  else {
    sensorBlockedSinceMs = 0;
    if (!coinArmed) {
      // 光が一瞬戻っただけで再受付すると、1枚のコインを複数回数えることが
      // あるため、センサーが一定時間空いたことを確認してから次を受け付けます。
      if (sensorClearSinceMs == 0) {
        sensorClearSinceMs = now;
      }
      else if (now - sensorClearSinceMs >= SENSOR_CLEAR_MS) {
        coinArmed = true;
      }
    }
  }

  delay(20);
}

void calibrateCoinLight() {
  // LEDとCdSの値が安定してから、コインが無い状態の平均を基準にする。
  delay(300);
  long total = 0;
  const int samples = 32;
  for (int i = 0; i < samples; ++i) {
    total += analogRead(COIN_CDS_PIN);
    delay(8);
  }
  coinLightBaseline = total / samples;
  Serial.println("SENSOR:CDS:" + String((unsigned long)coinLightBaseline));
  if (coinLightBaseline < CDS_MIN_LIT_VALUE) {
    Serial.println("[WARN] CdSが暗すぎます。LED・A0・10kΩ抵抗を確認してください");
  }
}

bool isCoinDetected() {
  if (!COIN_SENSOR_USE_CDS) {
    return digitalRead(COIN_SENSOR_PIN) == COIN_DETECTED_LEVEL;
  }

  int reading = analogRead(COIN_CDS_PIN);
  int fullDrop = coinLightBaseline * CDS_BLOCK_DROP_PERCENT / 100;
  if (fullDrop < CDS_BLOCK_MIN_DROP) fullDrop = CDS_BLOCK_MIN_DROP;

  // 検知後は半分の差まで戻るまで遮光中とするヒステリシスで、境界のちらつきを防ぐ。
  int requiredDrop = coinArmed ? fullDrop : fullDrop / 2;
  bool blocked = coinLightBaseline - reading >= requiredDrop;

  // コインが無い間だけゆっくり基準値を追従させ、LEDや周囲光の変動を吸収する。
  if (coinArmed && !blocked) {
    coinLightBaseline = (coinLightBaseline * 31L + reading) / 32L;
  }
  return blocked;
}

void startManualServo(const String &hopper) {
  if (manualServoActive && manualServoHopper == hopper) {
    manualServoLastCommandMs = millis();
    return;
  }

  // 別側が動いていた場合も含め、必ず両方を止めてから選択側だけ動かす。
  stopServo(servoA, SERVO_A_CONTINUOUS, SERVO_A_REST_ANGLE, SERVO_A_STOP_US);
  stopServo(servoB, SERVO_B_CONTINUOUS, SERVO_B_REST_ANGLE, SERVO_B_STOP_US);
  if (hopper == "A") {
    if (SERVO_A_CONTINUOUS) servoA.writeMicroseconds(SERVO_A_RUN_US);
    else servoA.write(SERVO_A_DISPENSE_ANGLE);
  } else if (hopper == "B") {
    if (SERVO_B_CONTINUOUS) servoB.writeMicroseconds(SERVO_B_RUN_US);
    else servoB.write(SERVO_B_DISPENSE_ANGLE);
  } else {
    return;
  }
  manualServoActive = true;
  manualServoHopper = hopper;
  manualServoLastCommandMs = millis();
}

void stopManualServos() {
  stopServo(servoA, SERVO_A_CONTINUOUS, SERVO_A_REST_ANGLE, SERVO_A_STOP_US);
  stopServo(servoB, SERVO_B_CONTINUOUS, SERVO_B_REST_ANGLE, SERVO_B_STOP_US);
  manualServoActive = false;
  manualServoHopper = "";
  manualServoLastCommandMs = 0;
}

void handleManualServoCommand(const String &command) {
  // MANUAL:A:START / MANUAL:A:STOP（B側も同様）
  int separator = command.indexOf(':', 7);
  if (separator < 0) return;
  String hopper = command.substring(7, separator);
  String action = command.substring(separator + 1);
  if (hopper != "A" && hopper != "B") return;

  if (action == "START") {
    startManualServo(hopper);
    Serial.println("MANUAL:STARTED:" + hopper);
  } else if (action == "STOP") {
    stopManualServos();
    Serial.println("MANUAL:STOPPED:" + hopper);
  }
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

  // PC v2.4.1以降は、旧ファームウェアでも認識できるDISPENSE形式を維持しつつ、
  // 予約番号の末尾へ「~回転時間ms」を付ける。ACKには末尾付きの番号を返す。
  unsigned long runMs = 0;
  int timingSeparator = reservationId.indexOf('~');
  if (timingSeparator >= 0) {
    String duration = reservationId.substring(timingSeparator + 1);
    if (!parseRunMilliseconds(duration, runMs)) {
      Serial.println("FAILED:" + reservationId);
      return;
    }
  }

  executeDispense(reservationId, hopper, runMs);
}

bool parseRunMilliseconds(const String &duration, unsigned long &runMs) {
  runMs = 0;
  bool valid = duration.length() > 0 && duration.length() <= 4;
  for (unsigned int i = 0; valid && i < duration.length(); ++i) {
    if (duration[i] < '0' || duration[i] > '9') valid = false;
    else runMs = runMs * 10 + (duration[i] - '0');
  }
  return valid && runMs >= 50 && runMs <= 2000;
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
  if (!parseRunMilliseconds(duration, runMs)) {
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
