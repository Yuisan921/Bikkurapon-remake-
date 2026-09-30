/*
 * びっくらポン ハードウェア担当ファームウェア(Seeed XIAO ESP32-C3用)
 *
 * 当たり用・はずれ用、それぞれ専用のホッパー(サーボ)を1個ずつ、
 * 計2個のサーボをこの1枚のESP32で制御する。
 *
 * コインセンサーの投入を検知したら、ノートPCで動いているFlaskサーバーの
 * /api/insert_coin にPOSTする。レスポンスのJSONの "hopper" フィールドが
 * "a" なら当たり用ホッパー、"b" ならはずれ用ホッパーのサーボを動かして
 * カプセルを排出する。null ならどちらも動かさない。
 * サーボの角度自体はこのファームウェアの固定値(ホッパーごとの現物合わせ)
 * で、サーバー側は「どちらのホッパーか」だけを指定する。
 *
 * 必要なライブラリ(Arduino IDEのライブラリマネージャからインストール):
 *   - ESP32Servo (by Kevin Harrington)
 *   - ArduinoJson 7.x (by Benoit Blanchon)
 * ボード設定: "XIAO_ESP32C3" を選択(esp32 by Espressif Systems のボードパッケージ内)
 *
 * 配線例:
 *   - コインセンサー信号線 -> D0(内部プルアップ、投入でLOWになる想定)
 *   - 当たり用ホッパーのサーボ信号線 -> D1
 *   - はずれ用ホッパーのサーボ信号線 -> D2
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

  connectToWifi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectToWifi();
  }

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

  if (doc["hopper"].isNull()) {
    Serial.println("どちらのホッパーも動かしません。");
    return;
  }

  const char *hopper = doc["hopper"];

  if (strcmp(hopper, "a") == 0) {
    Serial.println("当たり: ホッパーAからカプセルを排出します。");
    advanceRotor(
      servoA, servoAAt180, SERVO_A_POSITION_0, SERVO_A_POSITION_180
    );
  } else if (strcmp(hopper, "b") == 0) {
    Serial.println("はずれ景品: ホッパーBからカプセルを排出します。");
    advanceRotor(
      servoB, servoBAt180, SERVO_B_POSITION_0, SERVO_B_POSITION_180
    );
  } else {
    Serial.printf("[WARN] 想定外のhopper値: %s\n", hopper);
  }
}

void advanceRotor(Servo &servo, bool &at180, int position0, int position180) {
  at180 = !at180;
  servo.write(at180 ? position180 : position0);
  delay(SERVO_SETTLE_MS);
}
