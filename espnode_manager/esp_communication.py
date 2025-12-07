import json
import socket

ESP_IP = "192.168.96.157"   # your ESP32 IP
ESP_PORT = 5000


def send_command(command):
    """
    Send exactly ONE command to the ESP32, wait for reply,
    and return the 'value' from the ESP32 response.
    """
    payload = json.dumps(command) + "\n"  # send as single JSON object + newline

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ESP_IP, ESP_PORT))
        s.sendall(payload.encode("utf-8"))
        # Read one line of response (ending with '\n')
        data = b""
        while not data.endswith(b"\n"):
            chunk = s.recv(1024)
            if not chunk:
                break
            data += chunk

    if not data:
        raise RuntimeError("No response from ESP32")

    response_str = data.decode("utf-8").strip()
    # Expect something like:
    # {"espID":1,"device_type":"actuator","device_name":"led1","value":false}
    response = json.loads(response_str)

    # Return only the relevant global variable value
    return response.get("value")


if __name__ == "__main__":
    commands = [
        # set + get led1
        {"espID": 1, "device_type": "actuator", "device_name": "led1", "action": "set", "value": False},
        {"espID": 1, "device_type": "actuator", "device_name": "led1", "action": "get"},

        # set + get motor1
        {"espID": 1, "device_type": "actuator", "device_name": "motor1", "action": "set", "value": 50},
        {"espID": 1, "device_type": "actuator", "device_name": "motor1", "action": "get"},

        # get sensors
        {"espID": 1, "device_type": "sensor", "device_name": "pir", "action": "get"},
        {"espID": 1, "device_type": "sensor", "device_name": "tem", "action": "get"},
    ]

    for cmd in commands:
        result = send_command(cmd)
        print(f"Command: {cmd['device_name']} ({cmd['action']}) -> Returned value: {result}")
