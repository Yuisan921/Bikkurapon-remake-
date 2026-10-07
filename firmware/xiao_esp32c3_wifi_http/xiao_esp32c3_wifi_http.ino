/*
 * びっくらポン ハードウェア担当ファームウェア(Seeed XIAO ESP32-C3用)
 *
 * 当たり用・はずれ用、それぞれ専用のホッパー(サーボ)を1個ずつ、
 * 計2個のサーボをこの1枚のESP32で制御する。
 *
 * コインセンサーの投入を検知したら、ノートPCで動いているFlaskサーバーの
 * /api/insert_coin にPOSTする。レスポンスのJSONの "hopper" フィールドが
 * "a" なら当たり用ホッパー、"b" ならはずれ用ホッパーのサーボを動かして
 * カプセルを排出する。null ならどちらも動かさない。排出後は
 * /api/dispense_ack へ完了応答を送り、それを受けて在庫と当選画面が確定する。
 * APIには共有トークンを付け、同じWiFiにいる他端末からの不正な抽選を防ぐ。
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
// config/settings.json の device_token と同じ16文字以上の値にする
const char *DEVICE_TOKEN = "change-this-device-token";

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
<<<<<<< HEAD
bool coinWasLow = false;
=======
bool coinArmed = true;
>>>>>>> 251ce8c766819690cefd0f56fca9b64794677e31

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
    coinArmed = true;
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
  http.addHeader("X-Bikkurapon-Token", DEVICE_TOKEN);
  int statusCode = http.POST("{}");

  if (statusCode == 200) {
    String payload = http.getString();
    Serial.println("抽選結果: " + payload);
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, payload);
    if (err) {
      Serial.print("JSON解析に失敗しました: ");
      Serial.println(err.c_str());
      http.end();
      return;
    }

    if (doc["hopper"].isNull() || doc["reservation_id"].isNull()) {
      Serial.println("どちらのホッパーも動かしません。");
      http.end();
      return;
    }

    String reservationId = doc["reservation_id"].as<String>();
    String hopper = doc["hopper"].as<String>();
    // 次のACK送信用HTTP接続を開く前に、抽選リクエストの接続を閉じる。
    http.end();
    bool success = dispenseIfWon(hopper.c_str());
    sendDispenseAck(reservationId, success);
    return;
  } else {
    Serial.printf("サーバー通信エラー: %d\n", statusCode);
  }

  http.end();
}

bool dispenseIfWon(const char *hopper) {
  if (strcmp(hopper, "a") == 0) {
    Serial.println("当たり: ホッパーAからカプセルを排出します。");
<<<<<<< HEAD
    advanceRotor(
      servoA, servoAAt180, SERVO_A_POSITION_0, SERVO_A_POSITION_180
    );
  } else if (strcmp(hopper, "b") == 0) {
    Serial.println("はずれ景品: ホッパーBからカプセルを排出します。");
    advanceRotor(
      servoB, servoBAt180, SERVO_B_POSITION_0, SERVO_B_POSITION_180
    );
=======
    dispenseFrom(servoA, SERVO_A_REST_ANGLE, SERVO_A_DISPENSE_ANGLE);
    return true;
  } else if (strcmp(hopper, "b") == 0) {
    Serial.println("はずれ景品: ホッパーBからカプセルを排出します。");
    dispenseFrom(servoB, SERVO_B_REST_ANGLE, SERVO_B_DISPENSE_ANGLE);
    return true;
>>>>>>> 251ce8c766819690cefd0f56fca9b64794677e31
  } else {
    Serial.printf("[WARN] 想定外のhopper値: %s\n", hopper);
    return false;
  }
}

<<<<<<< HEAD
void advanceRotor(Servo &servo, bool &at180, int position0, int position180) {
  at180 = !at180;
  servo.write(at180 ? position180 : position0);
  delay(SERVO_SETTLE_MS);
=======
void sendDispenseAck(const String &reservationId, bool success) {
  String ackUrl = SERVER_URL;
  ackUrl.replace("/api/insert_coin", "/api/dispense_ack");

  JsonDocument ackDoc;
  ackDoc["reservation_id"] = reservationId;
  ackDoc["success"] = success;
  String body;
  serializeJson(ackDoc, body);

  // 応答だけ失われた場合にも届くよう最大3回送る。サーバーが既に処理済みの
  // 場合は409を返すので、それも到達済みとして終了する。
  for (int attempt = 0; attempt < 3; attempt++) {
    HTTPClient ackHttp;
    ackHttp.begin(ackUrl);
    ackHttp.addHeader("Content-Type", "application/json");
    ackHttp.addHeader("X-Bikkurapon-Token", DEVICE_TOKEN);
    int statusCode = ackHttp.POST(body);
    ackHttp.end();
    if (statusCode == 200 || statusCode == 409) {
      return;
    }
    delay(250);
  }
  Serial.println("[WARN] 排出完了ACKをサーバーへ送れませんでした。");
}

void dispenseFrom(Servo &servo, int restAngle, int dispenseAngle) {
  servo.write(dispenseAngle);
  delay(SERVO_HOLD_MS);
  servo.write(restAngle);
>>>>>>> 251ce8c766819690cefd0f56fca9b64794677e31
}
