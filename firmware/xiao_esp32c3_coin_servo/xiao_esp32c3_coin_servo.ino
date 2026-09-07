/*
 * びっくらポン ハードウェア担当ファームウェア(Seeed XIAO ESP32-C3用)
 *
 * コインセンサーの投入を検知したら、ノートPCで動いているFlaskサーバーの
 * /api/insert_coin にPOSTする。レスポンスのJSONに servo_angle が入っていれば
 * (=当選していれば)、その角度までサーボモーターを動かしてカプセルを排出する。
 *
 * 必要なライブラリ(Arduino IDEのライブラリマネージャからインストール):
 *   - ESP32Servo (by Kevin Harrington)
 *   - ArduinoJson 7.x (by Benoit Blanchon)
 * ボード設定: "XIAO_ESP32C3" を選択(esp32 by Espressif Systems のボードパッケージ内)
 *
 * 配線例:
 *   - コインセンサー信号線 -> D0(内部プルアップ、投入でLOWになる想定)
 *   - サーボモーター信号線 -> D1
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>

// ここを会場のWiFiとノートPCのIPアドレスに書き換える
const char *WIFI_SSID = "your-wifi-ssid";
const char *WIFI_PASSWORD = "your-wifi-password";
const char *SERVER_URL = "http://192.168.1.100:5000/api/insert_coin";

const int COIN_SENSOR_PIN = D0;
const int SERVO_PIN = D1;
const int SERVO_REST_ANGLE = 0;
const unsigned long SERVO_HOLD_MS = 1000;
const unsigned long DEBOUNCE_MS = 300;

Servo capsuleServo;
unsigned long lastTriggerMs = 0;

void setup() {
  Serial.begin(115200);
  pinMode(COIN_SENSOR_PIN, INPUT_PULLUP);

  capsuleServo.attach(SERVO_PIN);
  capsuleServo.write(SERVO_REST_ANGLE);

  connectToWifi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectToWifi();
  }

  if (digitalRead(COIN_SENSOR_PIN) == LOW) {
    unsigned long now = millis();
    if (now - lastTriggerMs > DEBOUNCE_MS) {
      lastTriggerMs = now;
      handleCoinInserted();
    }
  }

  delay(20);
}

void connectToWifi() {
  Serial.print("WiFiに接続中: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long startMs = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startMs < 15000) {
    delay(300);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.print("接続完了: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println();
    Serial.println("WiFi接続に失敗しました。次のループで再試行します。");
  }
}

void handleCoinInserted() {
  Serial.println("コイン投入を検知。サーバーに通知します。");

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi未接続のため送信できません。");
    return;
  }

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  int statusCode = http.POST("{}");

  if (statusCode == 200) {
    String payload = http.getString();
    Serial.println("抽選結果: " + payload);
    dispenseIfWon(payload);
  } else {
    Serial.printf("サーバー通信エラー: %d\n", statusCode);
  }

  http.end();
}

void dispenseIfWon(const String &payload) {
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, payload);
  if (err) {
    Serial.print("JSON解析に失敗しました: ");
    Serial.println(err.c_str());
    return;
  }

  if (doc["servo_angle"].isNull()) {
    Serial.println("はずれ: カプセルは排出しません。");
    return;
  }

  int angle = doc["servo_angle"].as<int>();
  Serial.printf("当選: サーボを%d度に動かしてカプセルを排出します。\n", angle);
  capsuleServo.write(angle);
  delay(SERVO_HOLD_MS);
  capsuleServo.write(SERVO_REST_ANGLE);
}
