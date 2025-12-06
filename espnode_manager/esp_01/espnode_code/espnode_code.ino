#include <WiFi.h>
#include <ArduinoJson.h>

const char* ssid     = "Crack";
const char* password = "20062004";

WiFiServer server(5000);

// ===== Global state for espID = 1 appliances =====
int espID = 1;

// Actuators
bool led1_value   = true;   // Light (boolean)
int  motor1_value = 0;      // Fan 0–100 (%)

// Sensors
bool  pir_value   = false;  // PIR sensor (boolean)
float tem_value   = 25.0;   // Temperature (°C)

// ===== Per-appliance handlers =====
void handle_led1(const char* action, JsonVariant valueField) {
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
}

void handle_motor1(const char* action, JsonVariant valueField) {
  if (strcmp(action, "get") == 0) {
    Serial.print("current value of motor1: ");
    Serial.println(motor1_value);
  } else if (strcmp(action, "set") == 0) {
    int newValue = valueField.isNull() ? motor1_value : valueField.as<int>();
    Serial.print("Old value of motor1: ");
    Serial.print(motor1_value);
    Serial.print(", New value of: ");
    Serial.println(newValue);
    motor1_value = newValue;
  } else {
    Serial.println("Unknown action for motor1.");
  }
}

void handle_pir(const char* action, JsonVariant valueField) {
  if (strcmp(action, "get") == 0) {
    Serial.print("current value of pir: ");
    Serial.println(pir_value ? "true" : "false");
  } else if (strcmp(action, "set") == 0) {
    bool newValue = valueField.isNull() ? pir_value : valueField.as<bool>();
    Serial.print("Old value of pir: ");
    Serial.print(pir_value ? "true" : "false");
    Serial.print(", New value of: ");
    Serial.println(newValue ? "true" : "false");
    pir_value = newValue;
  } else {
    Serial.println("Unknown action for pir.");
  }
}

void handle_tem(const char* action, JsonVariant valueField) {
  if (strcmp(action, "get") == 0) {
    Serial.print("current value of tem: ");
    Serial.println(tem_value, 2);
  } else if (strcmp(action, "set") == 0) {
    float newValue = valueField.isNull() ? tem_value : valueField.as<float>();
    Serial.print("Old value of tem: ");
    Serial.print(tem_value, 2);
    Serial.print(", New value of: ");
    Serial.println(newValue, 2);
    tem_value = newValue;
  } else {
    Serial.println("Unknown action for tem.");
  }
}

// ===== Handle ONE command object =====
// {
//   "espID": 1,
//   "device_type": "actuator" | "sensor",
//   "device_name": "led1" | "motor1" | "pir" | "tem",
//   "action": "get" | "set",
//   "value": ...   // only for "set"
// }
void handleCommand(JsonObject obj) {
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
      handle_led1(action, valueField);
    } else if (strcmp(device_name, "motor1") == 0) {
      handle_motor1(action, valueField);
    } else {
      Serial.println("Unknown actuator device_name.");
    }
  } else if (strcmp(device_type, "sensor") == 0) {
    if (strcmp(device_name, "pir") == 0) {
      handle_pir(action, valueField);
    } else if (strcmp(device_name, "tem") == 0) {
      handle_tem(action, valueField);
    } else {
      Serial.println("Unknown sensor device_name.");
    }
  } else {
    Serial.println("Unknown device_type.");
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

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

  // Read entire JSON array (one line)
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
      // Expect a JSON array: [ {cmd1}, {cmd2}, ... ]
      if (doc.is<JsonArray>()) {
        JsonArray arr = doc.as<JsonArray>();
        for (JsonObject obj : arr) {
          handleCommand(obj);
        }
      } else if (doc.is<JsonObject>()) {
        // fallback: single command as object
        JsonObject obj = doc.as<JsonObject>();
        handleCommand(obj);
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
