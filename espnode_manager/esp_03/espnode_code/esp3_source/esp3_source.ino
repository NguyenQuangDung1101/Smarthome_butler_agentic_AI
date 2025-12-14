#include <WiFi.h>
#include <ArduinoJson.h>
#include "DHT.h"

// tem
#define DHTPIN 4      // D4 (GPIO 4)
#define DHTTYPE DHT11 // sensor type DHT11

DHT dht(DHTPIN, DHTTYPE);

#define LED_BUILTIN 2



const char* ssid     = "Crack";
const char* password = "20062004";

WiFiServer server(5000);

// ===== Global state for espID = 3 appliances =====
int espID = 3;

// Actuators
bool led1_value   = false;   // Room light (boolean)
bool led2_value   = false;   // Bed light (boolean)
bool led3_value   = false;   // Balcony light (boolean)
int  motor1_value = 0;      // Fan 0–100 (%)
int  motor2_value = 0;      // Curtain slider 0–100 (%)
bool servo_value  = false;   // Lock (boolean)
bool pump_value   = false;   // Pump (boolean)

// Sensors
bool  pir_value   = false;  // PIR sensor (boolean)
float tem_value   = 25.0;   // Temperature (°C)
float tem_out_value = 25.0; // Outside temperature (°C)
float mois_value    = 50.0;  // Moisture (float)

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

void handle_led2(WiFiClient &client, const char* action, JsonVariant valueField) {
  if (strcmp(action, "get") == 0) {
    Serial.print("current value of led2: ");
    Serial.println(led2_value ? "true" : "false");
  } else if (strcmp(action, "set") == 0) {
    bool newValue = valueField.isNull() ? led2_value : valueField.as<bool>();
    Serial.print("Old value of led2: ");
    Serial.print(led2_value ? "true" : "false");
    Serial.print(", New value of: ");
    Serial.println(newValue ? "true" : "false");
    led2_value = newValue;
  } else {
    Serial.println("Unknown action for led2.");
  }

  // Send back the current value
  send_response(client, "actuator", "led2", led2_value);
}

void handle_led3(WiFiClient &client, const char* action, JsonVariant valueField) {
  if (strcmp(action, "get") == 0) {
    Serial.print("current value of led3: ");
    Serial.println(led3_value ? "true" : "false");
  } else if (strcmp(action, "set") == 0) {
    bool newValue = valueField.isNull() ? led3_value : valueField.as<bool>();
    Serial.print("Old value of led3: ");
    Serial.print(led3_value ? "true" : "false");
    Serial.print(", New value of: ");
    Serial.println(newValue ? "true" : "false");
    led3_value = newValue;
  } else {
    Serial.println("Unknown action for led3.");
  }

  // Send back the current value
  send_response(client, "actuator", "led3", led3_value);
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
    motor1_value = newValue;
  } else {
    Serial.println("Unknown action for motor1.");
  }

  // Send back the current value
  send_response(client, "actuator", "motor1", motor1_value);
}

void handle_motor2(WiFiClient &client, const char* action, JsonVariant valueField) {
  if (strcmp(action, "get") == 0) {
    Serial.print("current value of motor2: ");
    Serial.println(motor2_value);
  } else if (strcmp(action, "set") == 0) {
    int newValue = valueField.isNull() ? motor2_value : valueField.as<int>();
    Serial.print("Old value of motor2: ");
    Serial.print(motor2_value);
    Serial.print(", New value of: ");
    Serial.println(newValue);
    motor2_value = newValue;
  } else {
    Serial.println("Unknown action for motor2.");
  }

  // Send back the current value
  send_response(client, "actuator", "motor2", motor2_value);
}

void handle_servo(WiFiClient &client, const char* action, JsonVariant valueField) {
  if (strcmp(action, "get") == 0) {
    Serial.print("current value of servo: ");
    Serial.println(servo_value ? "true" : "false");
  } else if (strcmp(action, "set") == 0) {
    bool newValue = valueField.isNull() ? servo_value : valueField.as<bool>();
    Serial.print("Old value of servo: ");
    Serial.print(servo_value ? "true" : "false");
    Serial.print(", New value of: ");
    Serial.println(newValue ? "true" : "false");
    servo_value = newValue;
  } else {
    Serial.println("Unknown action for servo.");
  }

  // Send back the current value
  send_response(client, "actuator", "servo", servo_value);
}

void handle_pump(WiFiClient &client, const char* action, JsonVariant valueField) {
  if (strcmp(action, "get") == 0) {
    Serial.print("current value of pump: ");
    Serial.println(pump_value ? "true" : "false");
  } else if (strcmp(action, "set") == 0) {
    bool newValue = valueField.isNull() ? pump_value : valueField.as<bool>();
    Serial.print("Old value of pump: ");
    Serial.print(pump_value ? "true" : "false");
    Serial.print(", New value of: ");
    Serial.println(newValue ? "true" : "false");
    pump_value = newValue;
  } else {
    Serial.println("Unknown action for pump.");
  }

  // Send back the current value
  send_response(client, "actuator", "pump", pump_value);
}

void handle_pir(WiFiClient &client, const char* action, JsonVariant valueField) {
  if (strcmp(action, "get") == 0) {
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

void handle_tem_out(WiFiClient &client, const char* action, JsonVariant valueField) {
  if (strcmp(action, "get") == 0) {
    Serial.print("current value of tem_out: ");
    Serial.println(tem_out_value, 2);
  } else {
    Serial.println("Unknown action for tem_out.");
  }

  // Send back the current value
  send_response(client, "sensor", "tem_out", tem_out_value);
}

void handle_mois(WiFiClient &client, const char* action, JsonVariant valueField) {
  if (strcmp(action, "get") == 0) {
    Serial.print("current value of mois: ");
    Serial.println(mois_value, 2);
  } else {
    Serial.println("Unknown action for mois.");
  }

  // Send back the current value
  send_response(client, "sensor", "mois", mois_value);
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
    } else if (strcmp(device_name, "led2") == 0) {
      handle_led2(client, action, valueField);
    } else if (strcmp(device_name, "led3") == 0) {
      handle_led3(client, action, valueField);
    } else if (strcmp(device_name, "motor1") == 0) {
      handle_motor1(client, action, valueField);
    } else if (strcmp(device_name, "motor2") == 0) {
      handle_motor2(client, action, valueField);
    } else if (strcmp(device_name, "servo") == 0) {
      handle_servo(client, action, valueField);
    } else if (strcmp(device_name, "pump") == 0) {
      handle_pump(client, action, valueField);
    } else {
      Serial.println("Unknown actuator device_name.");
    }
  } else if (strcmp(device_type, "sensor") == 0) {
    if (strcmp(device_name, "pir") == 0) {
      handle_pir(client, action, valueField);
    } else if (strcmp(device_name, "tem") == 0) {
      handle_tem(client, action, valueField);
    } else if (strcmp(device_name, "tem_out") == 0) {
      handle_tem_out(client, action, valueField);
    } else if (strcmp(device_name, "mois") == 0) {
      handle_mois(client, action, valueField);
    } else {
      Serial.println("Unknown sensor device_name.");
    }
  } else {
    Serial.println("Unknown device_type.");
  }
}

void setup() {
  Serial.begin(115200);

  // init pins and sensors
  pinMode(LED_BUILTIN, OUTPUT);
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
    delay(300);
    digitalWrite(LED_BUILTIN, LOW);
    delay(300);
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
