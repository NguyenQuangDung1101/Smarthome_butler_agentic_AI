import json
import socket
import time

# ESP_IP, ESP_PORT: adjust as needed
# esp_id_port_map = [
#     ("192.168.69.230",5000),  # ESP ID 1
#     ("192.168.69.165",5000),  # ESP ID 2
#     ("192.168.69.157",5000),  # ESP ID 3
# ]
esp_id_port_map = [
    ("172.20.41.230",5000),  # ESP ID 1
    ("172.20.41.165",5000),  # ESP ID 2
    ("172.20.41.157",5000),  # ESP ID 3
]

def send_command(command, idx, timeout=20):
    """
    Send exactly ONE command to the ESP32, wait for reply,
    and return the 'value' from the ESP32 response.
    """
    payload = json.dumps(command) + "\n"  # send as single JSON object + newline

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # print(esp_id_port_map[idx])
        s.connect(esp_id_port_map[idx])
        s.sendall(payload.encode("utf-8"))
        s.settimeout(timeout)
        # Read one line of response (ending with '\n')
        data = b""
        start_time = time.time()
        while not data.endswith(b"\n"):
            chunk = s.recv(1024)
            if not chunk:
                break
            data += chunk
            
            if time.time() - start_time > timeout:
                raise RuntimeError(f"Timeout reached while waiting for response from ESP32")

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
        # {"espID": 1, "device_type": "actuator", "device_name": "led1", "action": "set", "value": False},
        # {"espID": 1, "device_type": "actuator", "device_name": "led1", "action": "get"},

        # # set + get motor1
        # {"espID": 1, "device_type": "actuator", "device_name": "motor1", "action": "set", "value": 50},
        # {"espID": 1, "device_type": "actuator", "device_name": "motor1", "action": "get"},

        # # get sensors
        # {"espID": 1, "device_type": "sensor", "device_name": "pir", "action": "get"},
        {"espID": 2, "device_type": "sensor", "device_name": "tem", "action": "get"},
    ]

    for cmd in commands:
        result = send_command(cmd, 1)
        print(f"Command: {cmd['device_name']} ({cmd['action']}) -> Returned value: {result}")
