#include <Servo.h>

const int COIN_SENSOR_PIN = 2;

const int SERVO_A_PIN = 9;   // 当たり
const int SERVO_B_PIN = 10;  // はずれ

const int SERVO_A_REST_ANGLE = 0;
const int SERVO_A_DISPENSE_ANGLE = 90;
const int SERVO_B_REST_ANGLE = 0;
const int SERVO_B_DISPENSE_ANGLE = 90;

const unsigned long SERVO_HOLD_MS = 1000;
const unsigned long DEBOUNCE_MS = 300;
const unsigned long RESPONSE_TIMEOUT_MS = 3000;

Servo servoA;
Servo servoB;

unsigned long lastTriggerMs = 0;
unsigned long coinSequence = 0;
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
  bool coinLow = digitalRead(COIN_SENSOR_PIN) == LOW;

  if (coinLow && coinArmed) {
    unsigned long now = millis();

    if (now - lastTriggerMs > DEBOUNCE_MS) {
      lastTriggerMs = now;
      coinArmed = false;
      handleCoinInserted();
    }
  }
  else if (!coinLow) {
    coinArmed = true;
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

void dispenseIfWon(
  const String &response
) {

  if (response.startsWith("NONE:")) {
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
    thirdColon < 0
  ) {
    Serial.println(
      "[WARN] 想定外の応答"
    );
    return;
  }

  String reservationId =
    response.substring(
      secondColon + 1,
      thirdColon
    );

  String hopper =
    response.substring(
      thirdColon + 1
    );

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