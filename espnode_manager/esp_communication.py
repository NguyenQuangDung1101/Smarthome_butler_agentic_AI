import paho.mqtt.client as mqtt

BROKER = "test.mosquitto.org"
PORT = 1883
TOPIC = "esp32/led_blink"

def main():
    client = mqtt.Client()
    client.connect(BROKER, PORT, 60)

    print("Connected to MQTT broker.")
    print("Type a number (times to blink). Type 'q' to quit.\n")

    while True:
        user_input = input("Enter blink count: ")

        if user_input.lower() == 'q':
            break

        # try to ensure it's a valid integer
        try:
            n = int(user_input)
            if n < 0:
                print("Please enter a non-negative integer.")
                continue
        except ValueError:
            print("Please enter a valid integer.")
            continue

        # publish as string
        result = client.publish(TOPIC, str(n))
        status = result[0]
        if status == 0:
            print(f"Sent '{n}' to topic '{TOPIC}'")
        else:
            print("Failed to send message")

    client.disconnect()
    print("Disconnected.")

if __name__ == "__main__":
    main()
