#include <WiFi.h>
#include <ArduinoJson.h>
#include "DHT.h"


// motor1
#define MOTOR_ENA_PIN 14
#define MOTOR_IN1_PIN 27
#define MOTOR_IN2_PIN 26
const int MOTOR_LEDC_CHANNEL = 0;
const int MOTOR_LEDC_FREQ = 20000; // 20 kHz
const int MOTOR_LEDC_RESOLUTION = 8; // 8-bit (0-255)


#define DHTTYPE DHT11 // sensor type DHT11
// tem
#define DHTPIN 4      // D4 (GPIO 4)
DHT dht(DHTPIN, DHTTYPE);

// PIR
#define PIR_PIN 12



#define LED_BUILTIN 2


const char* ssid     = "Crack";
const char* password = "20062004";

WiFiServer server(5000);

// ===== Global state for espID = 1 appliances (Livingroom) =====
int espID = 1;

// Actuators
bool led1_value   = false;   // Light (boolean)
int  motor1_value = 0;      // Fan 0–100 (%)

// Sensors
bool  pir_value   = false;  // PIR sensor (boolean)
float tem_value   = 25.0;   // Temperature (°C)

// ===== Helper: send JSON response back to Python =====
void send_response(WiFiClient &client,
                   const char* device_type,
                   const char* device_name,
                   bool bool_value)
{
  StaticJsonDocument<128> resp;
  resp["espID"]       = espID;
  resp["device_type"] = device_type;
  resp["device_name"] = device_name;
  resp["value"]       = bool_value;

  serializeJson(resp, client);
  client.print('\n');
}

void send_response(WiFiClient &client,
                   const char* device_type,
                   const char* device_name,
                   int int_value)
{
  StaticJsonDocument<128> resp;
  resp["espID"]       = espID;
  resp["device_type"] = device_type;
  resp["device_name"] = device_name;
  resp["value"]       = int_value;

  serializeJson(resp, client);
  client.print('\n');
}

void send_response(WiFiClient &client,
                   const char* device_type,
                   const char* device_name,
                   float float_value)
{
  StaticJsonDocument<128> resp;
  resp["espID"]       = espID;
  resp["device_type"] = device_type;
  resp["device_name"] = device_name;
  resp["value"]       = float_value;

  serializeJson(resp, client);
  client.print('\n');
}


// ========================================================================================================
// ======================================== Per-appliance handlers ========================================
// ========================================================================================================

void handle_led1(WiFiClient &client, const char* action, JsonVariant valueField) {
  if (strcmp(action, "get") == 0) {
    Serial.print("current value of led1: ");
    Serial.println(led1_value ? "true" : "false");
  } else if (strcmp(action, "set") == 0) {
    bool newValue = valueField.isNull() ? led1_value : valueField.as<bool>();
    Serial.print("Old value of led1: ");
    Serial.print(led1_value ? "true" : "false");
    Serial.print(", New value of: ");
    Serial.println(newValue ? "true" : "false");
    led1_value = newValue;
  } else {
    Serial.println("Unknown action for led1.");
  }

  // Send back the current value
  send_response(client, "actuator", "led1", led1_value);
}

void handle_motor1(WiFiClient &client, const char* action, JsonVariant valueField) {
  if (strcmp(action, "get") == 0) {
    Serial.print("current value of motor1: ");
    Serial.println(motor1_value);
  } else if (strcmp(action, "set") == 0) {
    int newValue = valueField.isNull() ? motor1_value : valueField.as<int>();
    Serial.print("Old value of motor1: ");
    Serial.print(motor1_value);
    Serial.print(", New value of: ");
    Serial.println(newValue);
    // clamp 0-100
    if (newValue < 0) newValue = 0;
    if (newValue > 100) newValue = 100;
    motor1_value = newValue;
    applyMotorSpeed(motor1_value);
  } else {
    Serial.println("Unknown action for motor1.");
  }

  // Send back the current value
  send_response(client, "actuator", "motor1", motor1_value);
}

// Apply speed in percent (0-100)
void applyMotorSpeed(int percent) {
  int duty = map(percent, 0, 100, 0, (1 << MOTOR_LEDC_RESOLUTION) - 1);

  if (percent == 0) {
    ledcWrite(MOTOR_ENA_PIN, 0); // Use the PIN number here
    digitalWrite(MOTOR_IN1_PIN, LOW);
    digitalWrite(MOTOR_IN2_PIN, LOW);
  } else {
    digitalWrite(MOTOR_IN1_PIN, HIGH);
    digitalWrite(MOTOR_IN2_PIN, LOW);
    ledcWrite(MOTOR_ENA_PIN, duty); // Use the PIN number here
  }
}

void handle_pir(WiFiClient &client, const char* action, JsonVariant valueField) {
  if (strcmp(action, "get") == 0) {
    int pir_state = digitalRead(PIR_PIN);
    pir_value = (pir_state == HIGH);
    Serial.print("current value of pir: ");
    Serial.println(pir_value ? "true" : "false");
  } else {
    Serial.println("Unknown action for pir.");
  }

  // Send back the current value
  send_response(client, "sensor", "pir", pir_value);
}

void handle_tem(WiFiClient &client, const char* action, JsonVariant valueField) {
  if (strcmp(action, "get") == 0) {
    float t = dht.readTemperature();
    c = 0
    while (t <= 1.0 || t >= -1.0) {
      delay(200);
      t = dht.readTemperature();
      c++;
      if (c > 2) break;
    }
    if (!isnan(t)) {
      tem_value = t;
    }
    Serial.print("current value of tem: ");
    Serial.println(tem_value, 2);
  } else {
    Serial.println("Unknown action for tem.");
  }

  // Send back the current value
  send_response(client, "sensor", "tem", tem_value);
}

// ========================================================================================================
// ========================================================================================================
// ========================================================================================================

// ===== Handle ONE command object =====
// {
//   "espID": 1,
//   "device_type": "actuator" | "sensor",
//   "device_name": "led1" | "motor1" | "pir" | "tem",
//   "action": "get" | "set",
//   "value": ...   // only for "set"
// }
void handleCommand(WiFiClient &client, JsonObject obj) {
  int cmdEspID = obj["espID"] | -1;
  const char* device_type  = obj["device_type"] | "";
  const char* device_name  = obj["device_name"] | "";
  const char* action       = obj["action"]      | "";

  if (cmdEspID != espID) {
    Serial.println("Command for different espID, ignoring.");
    return;
  }

  Serial.println("=== New command ===");
  Serial.print("device_type: "); Serial.println(device_type);
  Serial.print("device_name: "); Serial.println(device_name);
  Serial.print("action     : "); Serial.println(action);

  JsonVariant valueField = obj["value"];

  if (strcmp(device_type, "actuator") == 0) {
    if (strcmp(device_name, "led1") == 0) {
      handle_led1(client, action, valueField);
    } else if (strcmp(device_name, "motor1") == 0) {
      handle_motor1(client, action, valueField);
    } else {
      Serial.println("Unknown actuator device_name.");
    }
  } else if (strcmp(device_type, "sensor") == 0) {
    if (strcmp(device_name, "pir") == 0) {
      handle_pir(client, action, valueField);
    } else if (strcmp(device_name, "tem") == 0) {
      handle_tem(client, action, valueField);
    } else {
      Serial.println("Unknown sensor device_name.");
    }
  } else {
    Serial.println("Unknown device_type.");
  }
}

void setup() {
  Serial.begin(115200);

  // initialize motor1 pins and PWM (LEDC)
  pinMode(MOTOR_IN1_PIN, OUTPUT);
  pinMode(MOTOR_IN2_PIN, OUTPUT);
  pinMode(MOTOR_ENA_PIN, OUTPUT);
  ledcAttach(MOTOR_ENA_PIN, MOTOR_LEDC_FREQ, MOTOR_LEDC_RESOLUTION);  // configure LEDC PWM
  applyMotorSpeed(motor1_value);  // ensure motor stopped initially
  // init pins and sensors
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(PIR_PIN, INPUT);
  dht.begin();

  delay(1000);

  Serial.print("Connecting to ");
  Serial.println(ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  // signal connected
  for(int i=0; i < 5; i++){
    digitalWrite(LED_BUILTIN, HIGH);
    delay(200);
    digitalWrite(LED_BUILTIN, LOW);
    delay(200);
  }

  Serial.println("\nWiFi connected.");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  server.begin();
  Serial.println("TCP server started on port 5000");
}

void loop() {
  WiFiClient client = server.available();
  if (!client) {
    return;
  }

  Serial.println("Client connected.");
  client.setTimeout(3000);  // 3s timeout

  // Read one JSON line (single command object from Python)
  String line = client.readStringUntil('\n');
  if (line.length() > 0) {
    Serial.print("Received: ");
    Serial.println(line);

    StaticJsonDocument<2048> doc;
    DeserializationError error = deserializeJson(doc, line);
    if (error) {
      Serial.print("deserializeJson() failed: ");
      Serial.println(error.c_str());
    } else {
      // Support both array and object (just in case),
      // but Python is sending a single object now.
      if (doc.is<JsonArray>()) {
        JsonArray arr = doc.as<JsonArray>();
        for (JsonObject obj : arr) {
          handleCommand(client, obj);
        }
      } else if (doc.is<JsonObject>()) {
        JsonObject obj = doc.as<JsonObject>();
        handleCommand(client, obj);
      } else {
        Serial.println("Unknown JSON root type (not array/object).");
      }
    }
  } else {
    Serial.println("No data received before timeout.");
  }

  client.stop();
  Serial.println("Client disconnected.");
}
