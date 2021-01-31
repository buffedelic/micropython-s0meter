import json
power_topic = []
power_topic = [
    "power/meter/total/current",
    "power/meter/heater/current",
    "power/meter/ftx/current",
    "power/meter/household/current",
]

for i in range(len(power_topic)):
    sensor = power_topic[i].split('/')[2]
    print(sensor)
    msg = str(json.dumps({
        'name': "uPower {}".format(sensor.replace('_', ' ')),
        'state_topic': "{}".format(power_topic[i]),
        'unique_id': "upower_{}".format(sensor),
        'device_class': "energy",
        'unit_of_meas': "W",
        'device': {
            'name': "uPower",
            'model': "ESP 8266 with RTC and OLED",
            'manufacturer': "Buffedelic AB",
            "identifiers": ["UPOW1"]
            }
        }))
    print(msg)
