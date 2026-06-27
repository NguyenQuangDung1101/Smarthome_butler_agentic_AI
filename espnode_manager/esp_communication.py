import json
import socket
import time

# ESP_IP, ESP_PORT: adjust as needed
# esp_id_port_map = [
#     ("192.168.69.230",5000),  # ESP ID 1
#     ("192.168.69.165",5000),  # ESP ID 2
#     ("192.168.69.157",5000),  # ESP ID 3
# ]
# esp_id_port_map = [
#     ("172.20.41.230",5000),  # ESP ID 1
#     ("172.20.41.165",5000),  # ESP ID 2
#     ("172.20.41.157",5000),  # ESP ID 3
# ]
# esp_id_port_map = [
#     ("172.25.130.230",5000),  # ESP ID 1
#     ("172.25.130.165",5000),  # ESP ID 2
#     ("172.25.130.157",5000),  # ESP ID 3
# ]
# esp_id_port_map = [
#     ("10.105.10.230",5000),  # ESP ID 1
#     ("10.105.10.165",5000),  # ESP ID 2
#     ("10.105.10.157",5000),  # ESP ID 3
# ]

# esp_id_port_map = [
#     ("10.246.116.230",5000),  # ESP ID 1
#     ("10.246.116.165",5000),  # ESP ID 2
#     ("10.246.116.157",5000),  # ESP ID 3
# ]

esp_id_port_map = [
    ("10.187.164.230",5000),  # ESP ID 1
    ("10.187.164.165",5000),  # ESP ID 2
    ("10.187.164.158",5000),  # ESP ID 3
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

# if __name__ == "__main__":
#     REPEAT = 3
#     SLEEP_BETWEEN = 0.1  # seconds

#     appliances = {
#         1: {
#             "room": "Livingroom",
#             "actuators": {
#                 "led1": [False, True],
#                 "motor1": [0, 50, 100],
#             },
#             "sensors": ["pir", "tem"],
#         },
#         2: {
#             "room": "Hallway",
#             "actuators": {
#                 "led1": [False, True],
#                 "led2": [False, True],
#                 "motor1": [0, 50, 100],
#                 "motor2": [0, 50, 100],
#             },
#             "sensors": ["pir", "tem"],
#         },
#         3: {
#             "room": "Bedroom + balcony",
#             "actuators": {
#                 "led1": [False, True],
#                 "led2": [False, True],
#                 "led3": [False, True],
#                 "motor1": [0, 50, 100],
#                 "motor2": [0, 50, 100],
#                 "servo": [False, True],
#                 "pump": [False, True],
#             },
#             "sensors": ["pir", "tem", "tem_out", "mois"],
#         },
#     }

#     def test_command(cmd, idx):
#         times = []

#         for _ in range(REPEAT):
#             start = time.perf_counter()
#             send_command(cmd, idx)
#             end = time.perf_counter()

#             elapsed_ms = (end - start) * 1000
#             times.append(elapsed_ms)

#             time.sleep(SLEEP_BETWEEN)

#         avg = sum(times) / len(times)
#         return times, avg

#     for esp_id, info in appliances.items():
#         idx = esp_id - 1

#         print("\n" + "=" * 80)
#         print(f"Room: {info['room']} | ESP ID: {esp_id}")
#         print("=" * 80)
#         print(f"{'Device':<10} {'Action':<10} {'Value':<8} {'Time 1':<12} {'Time 2':<12} {'Time 3':<12} {'Average':<12}")
#         print("-" * 80)

#         # Actuator GET and SET
#         for device_name, test_values in info["actuators"].items():
#             # GET actuator
#             cmd = {
#                 "espID": esp_id,
#                 "device_type": "actuator",
#                 "device_name": device_name,
#                 "action": "get",
#             }

#             times, avg = test_command(cmd, idx)

#             print(
#                 f"{device_name:<10} "
#                 f"{'get':<10} "
#                 f"{'-':<8} "
#                 f"{times[0]:<12.2f} "
#                 f"{times[1]:<12.2f} "
#                 f"{times[2]:<12.2f} "
#                 f"{avg:<12.2f}"
#             )

#             # SET actuator
#             for value in test_values:
#                 cmd = {
#                     "espID": esp_id,
#                     "device_type": "actuator",
#                     "device_name": device_name,
#                     "action": "set",
#                     "value": value,
#                 }

#                 times, avg = test_command(cmd, idx)

#                 print(
#                     f"{device_name:<10} "
#                     f"{'set':<10} "
#                     f"{str(value):<8} "
#                     f"{times[0]:<12.2f} "
#                     f"{times[1]:<12.2f} "
#                     f"{times[2]:<12.2f} "
#                     f"{avg:<12.2f}"
#                 )

#         # Sensor GET only
#         for device_name in info["sensors"]:
#             cmd = {
#                 "espID": esp_id,
#                 "device_type": "sensor",
#                 "device_name": device_name,
#                 "action": "get",
#             }

#             times, avg = test_command(cmd, idx)

#             print(
#                 f"{device_name:<10} "
#                 f"{'get':<10} "
#                 f"{'-':<8} "
#                 f"{times[0]:<12.2f} "
#                 f"{times[1]:<12.2f} "
#                 f"{times[2]:<12.2f} "
#                 f"{avg:<12.2f}"
#             )