import json
import socket

ESP_IP = "192.168.96.157"   # your ESP32 IP
ESP_PORT = 5000

def send_commands(commands):
    payload = json.dumps(commands) + "\n"  # JSON array in one line
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ESP_IP, ESP_PORT))
        s.sendall(payload.encode("utf-8"))
        print(f"Sent commands list ({len(commands)} items).")



if __name__ == "__main__":
    commands = [
        # set + get led1
        {"espID": 1, "device_type": "actuator", "device_name": "led1", "action": "set", "value": False},
        {"espID": 1, "device_type": "actuator", "device_name": "led1", "action": "get"},

        # set + get motor1
        {"espID": 1, "device_type": "actuator", "device_name": "motor1", "action": "set", "value": 50},
        {"espID": 1, "device_type": "actuator", "device_name": "motor1", "action": "get"},

        # get sensors
        {"espID": 1, "device_type": "sensor", "device_name": "pir",
         "action": "get"},
        {"espID": 1, "device_type": "sensor", "device_name": "tem", "action": "get"},
    ]

    send_commands(commands)
