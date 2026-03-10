import json
from espnode_manager.esp_communication import send_command

device_mapping = {
    1: {  # Livingroom (espID: 1)
        "led1": "boolean",  # Light
        "motor1": "integer",  # Fan
    },
    2: {  # Hallway (espID: 2)
        "led1": "boolean",  # Left Light
        "led2": "boolean",  # Right Light
        "motor1": "integer",  # Fan
        "motor2": "integer",  # Main Door motor
    },
    3: {  # Bedroom + Balcony (espID: 3)
        "led1": "boolean",  # Room light
        "led2": "boolean",  # Bed light
        "led3": "boolean",  # Balcony light
        "motor1": "integer",  # Fan
        "motor2": "integer",  # Window cover (curtain)
        "servo": "boolean",  # Lock
        "pump": "boolean",  # Bonsai watering pump
    }
}

def control_appliance(espID, device_name, value):
    # Check if espID and device_name exist in the mapping
    if espID not in device_mapping:
        return {"error": "Invalid espID"}
    
    if device_name not in device_mapping[espID]:
        return {"error": "Invalid device_name for the given espID"}
    
    # Get the expected data type for the device
    expected_type = device_mapping[espID][device_name]
    
    # Validate the value based on expected data type
    if expected_type == "boolean" and isinstance(value, bool):
        value_type = "boolean"
    elif expected_type == "integer" and isinstance(value, int) and 0 <= value <= 100:
        value_type = "integer"
    else:
        return {"error": f"Invalid value for {device_name}, expected {expected_type}"}

    
    result = {
        "espID": espID,
        "device_type": "actuator",
        "device_name": device_name,
        "action": "set",
        "value": value
    }

    return result


if __name__ == "__main__":
    # Livingroom (espID: 1)
    print(control_appliance(1, "led1", True))    # Living room LED light (boolean)
    print(control_appliance(1, "motor1", 75))     # Living room Fan (integer)

    # Hallway (espID: 2)
    print(control_appliance(2, "led1", True))    # Hallway Left Light (boolean)
    print(control_appliance(2, "led2", False))   # Hallway Right Light (boolean)
    print(control_appliance(2, "motor1", 50))    # Hallway Fan (integer)
    print(control_appliance(2, "motor2", 60))    # Hallway Main Door Motor (integer)

    # Bedroom + Balcony (espID: 3)
    print(control_appliance(3, "led1", True))    # Bedroom Room light (boolean)
    print(control_appliance(3, "led2", False))   # Bedroom Bed light (boolean)
    print(control_appliance(3, "led3", True))    # Bedroom Balcony light (boolean)
    print(control_appliance(3, "motor1", 40))    # Bedroom Fan (integer)
    print(control_appliance(3, "motor2", 20))    # Bedroom Window Cover (Curtain) (integer)
    print(control_appliance(3, "servo", True))   # Bedroom Lock (boolean)
    print(control_appliance(3, "pump", True))    # Bedroom Bonsai Watering Pump (boolean)