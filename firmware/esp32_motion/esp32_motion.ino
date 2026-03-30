#include <WiFi.h>
#include <HTTPClient.h>

#define PIR_PIN 27  // <-- PIR OUT 연결 핀으로 수정 가능

const char* ssid = "코리아IT아카데미";
const char* password = "15885890";

// 서버는 main.py 기준 /sensor-events/
const char* serverUrl = "http://192.168.0.151:8000/sensor-events/";

// 모션 센서의 sensor_id (문센서=2를 이미 쓰고 있으니, 모션은 3 등으로 분리 권장)
const int SENSOR_ID = 3;

int lastState = LOW;

void setup() {
  Serial.begin(115200);
  delay(300);

  // HC-SR501 OUT은 보통 HIGH/LOW로 출력. 보드에 따라 풀다운 권장.
  // ESP32는 INPUT_PULLDOWN 지원(핀에 따라 다를 수 있음). 문제 있으면 그냥 INPUT로.
  pinMode(PIR_PIN, INPUT_PULLDOWN);

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(ssid, password);

  Serial.println("Boot complete (PIR)");
}

void loop() {
  Serial.print("WiFi status: ");
  Serial.print(WiFi.status());
  Serial.print("  IP: ");
  Serial.println(WiFi.localIP());

  if (WiFi.status() == WL_CONNECTED) {
    int currentState = digitalRead(PIR_PIN);  // LOW=움직임 없음, HIGH=움직임 감지(일반적)

    if (currentState != lastState) {
      HTTPClient http;
      http.begin(serverUrl);
      http.addHeader("Content-Type", "application/json");

      String json = "{";
      json += "\"sensor_id\": " + String(SENSOR_ID) + ",";
      json += "\"event_type\":\"motion\",";
      json += "\"event_value\":";
      json += String(currentState == HIGH ? 1 : 0);
      json += "}";

      int code = http.POST(json);

      Serial.print("HTTP code: ");
      Serial.println(code);

      http.end();

      lastState = currentState;
    }
  }

  delay(2000);
}