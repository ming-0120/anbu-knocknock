#include <WiFi.h>
#include <HTTPClient.h>

#define DOOR_PIN 27

const char* ssid = "코리아IT아카데미";
const char* password = "15885890";

const char* serverUrl = "http://192.168.0.151:8000/sensor-events/";

int lastState = HIGH;

void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(DOOR_PIN, INPUT_PULLUP);

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(ssid, password);

  Serial.println("Boot complete");
}

void loop() {

  // WiFi 상태 계속 출력
  Serial.print("WiFi status: ");
  Serial.print(WiFi.status());
  Serial.print("  IP: ");
  Serial.println(WiFi.localIP());

  // WiFi 연결됐을 때만 동작
  if (WiFi.status() == WL_CONNECTED) {

    int currentState = digitalRead(DOOR_PIN);

    if (currentState != lastState) {

      HTTPClient http;
      http.begin(serverUrl);
      http.addHeader("Content-Type", "application/json");

      String json = "{";
      json += "\"sensor_id\":2,";
      json += "\"event_type\":\"";
      json += (currentState == HIGH ? "door_open" : "door_close");
      json += "\",";
      json += "\"event_value\":";
      json += String(currentState);
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