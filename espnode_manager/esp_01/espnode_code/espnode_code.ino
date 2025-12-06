#include <WiFi.h>
#include <PubSubClient.h>

#define LED_BUILTIN 2  // Onboard LED (change if your board uses another pin)

// ==== WiFi & MQTT config ====
const char* ssid     = "xvnt758lau2";
const char* password = "xvnt758/26lau2";

const char* mqtt_server = "test.mosquitto.org";
const int   mqtt_port   = 1883;
const char* mqtt_topic  = "esp32/led_blink";

// ==== Global objects ====
WiFiClient espClient;
PubSubClient client(espClient);

// ==== Blink control ====
volatile int blinkRequest = 0;  // number requested from MQTT
bool        isBlinking    = false;
int         remainingBlinks = 0;
unsigned long lastBlinkMillis = 0;
bool        ledState = LOW;
const unsigned long BLINK_INTERVAL = 200;  // 200ms on/off

// ----- WiFi -----
void setup_wifi() {
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi connected.");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

// ----- MQTT callback -----
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("] ");

  // Copy payload to a null-terminated string
  char msg[32];
  if (length >= sizeof(msg)) length = sizeof(msg) - 1;
  for (unsigned int i = 0; i < length; i++) {
    msg[i] = (char)payload[i];
    Serial.print((char)payload[i]);
  }
  msg[length] = '\0';
  Serial.println();

  int n = atoi(msg);  // convert string → int
  if (n < 0) n = 0;

  Serial.print("Blink request: ");
  Serial.println(n);

  blinkRequest = n;
  remainingBlinks = blinkRequest;
  isBlinking = (remainingBlinks > 0);
}

// ----- Reconnect MQTT if needed -----
void reconnect() {
  // Loop until we're reconnected
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    // Create a random client ID
    String clientId = "ESP32Client-";
    clientId += String(random(0xffff), HEX);
    // Attempt to connect
    if (client.connect(clientId.c_str())) {
      Serial.println("connected");
      // Once connected, subscribe
      client.subscribe(mqtt_topic);
      Serial.print("Subscribed to topic: ");
      Serial.println(mqtt_topic);
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  Serial.begin(115200);
  delay(1000);

  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(mqttCallback);
}

void loop() {
  // Keep MQTT alive
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // Handle blinking logic non-blocking
  if (isBlinking && remainingBlinks > 0) {
    unsigned long now = millis();
    if (now - lastBlinkMillis >= BLINK_INTERVAL) {
      lastBlinkMillis = now;

      // Toggle LED
      ledState = !ledState;
      digitalWrite(LED_BUILTIN, ledState);

      // Every full on+off cycle = 1 blink
      // So we count only when LED just turned off
      if (ledState == LOW) {
        remainingBlinks--;
        Serial.print("Remaining blinks: ");
        Serial.println(remainingBlinks);
        if (remainingBlinks == 0) {
          isBlinking = false;
          digitalWrite(LED_BUILTIN, LOW);
        }
      }
    }
  }
}
