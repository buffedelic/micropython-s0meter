#!/usr/bin/env python3
import time
from machine import Pin
from machine import I2C
from machine import reset
import network
from include import ds2423
import onewire
from include import ssd1306
from include import mqtt
from include import i2c_pcf8563
from micropython import const
import json

_DEBUG = False
_ERROR = False

# ##################
# Constants
# ##################

_OLED_W = const(128)
_OLED_H = const(64)
_OLED_HEADER_TEXT = "  Power usage"
_I2C_SDA = const(4)
_I2C_SCL = const(5)
_ONEWIRE_PIN = const(0)


_MQTT_BROKER = "192.168.1.219"
_MQTT_USER = "buff"
_MQTT_PASSWORD = "mammas"
_MQTT_PORT = const(1883)
_MQTT_CLIENT = "uPowerESP8266"

_PUBLISH_PREFIX = "homeassistant/"
_POWER_TOPIC = "/power"

# ##################
# Hardware init
# ##################

_led = Pin(2, Pin.OUT)  # create LED object from pin2,Set Pin2 to output
_i2c = I2C(scl=Pin(_I2C_SCL), sda=Pin(_I2C_SDA))
_oled = ssd1306.SSD1306_I2C(_OLED_W, _OLED_H, _i2c, 0x3c)
_ow = onewire.OneWire(Pin(_ONEWIRE_PIN))
_wlan = network.WLAN(network.STA_IF)
_rtc = i2c_pcf8563.PCF8563(_i2c, 0x51, zone=2)
_onewire_bus = ds2423.DS2423(_ow)


def debug_print(text):
    if _DEBUG:
        _rtc_time = _rtc.datetime()
        _time = "{:0>2d}-{:0>2d}-{:0>2d} {:0>2d}:{:0>2d}:{:0>2d}".format(
            _rtc_time[0], _rtc_time[1], _rtc_time[2], _rtc_time[3], _rtc_time[4], _rtc_time[5])
        print("{} {}".format(_time, text))


def handle_error():
    while _ERROR:
        _reboot = False
        i = 5
        initialize_screen("    !!ERROR!!")
        update_screen("ERROR!", "REBOOTING", 50)
        time.sleep(3)
        clear_screen()
        update_screen(" REBOOTING IN", "", 20)
        while not _reboot:
            update_screen("       {}".format(i), "", 40)
            i -= 1
            time.sleep(1)
            if i == 0:
                _reboot = True
        _oled.fill(0)
        _oled.show()
        reset()
        time.sleep(2)


def initialize_hardware():
    global _ERROR
    update_screen('Connecting WiFi', "", 10)
    update_screen("::", "...", 20)
    wlan_connect()  # Endless loop if not possible
    # time.sleep(2)
    update_screen("::", _wlan.ifconfig()[0], 20)
    # time.sleep(2)

    update_screen("MQTT", "", 30)
    try:
        mqtt_setup()
    except:
        debug_print("MQTT Error")
        update_screen("MQTT", "ERROR", 30)
        _ERROR = True
    else:
        update_screen("MQTT", "OK", 30)
    # time.sleep(2)

    # { 0x1D, 0x6C, 0xEC, 0x0C, 0x00, 0x00, 0x00, 0x94 }; total
    # { 0x1D, 0x00, 0xFD, 0x0C, 0x00, 0x00, 0x00, 0x9B }; heatpump
    _counters_present = len(_onewire_bus.scan())
    debug_print("Counters on bus: {}".format(_counters_present))
    if _counters_present == 0:
        _ERROR = True
    update_screen("Counters:", str(_counters_present), 40)

# ##################
# MQTT functions
# ##################


def settimeout(duration):
    pass


def mqtt_setup():
    global client
    # print(_MQTT_BROKER)
    client = mqtt.MQTTClient(_MQTT_CLIENT,
                             _MQTT_BROKER,
                             port=_MQTT_PORT,
                             user=_MQTT_USER,
                             password=_MQTT_PASSWORD
                             )

    client.settimeout = settimeout
    client.connect()

    power_topic = []
    power_topic = [
        "power/meter/total/current",
        "power/meter/heater/current",
        "power/meter/ftx/current",
        "power/meter/household/current",
    ]
    debug_print("Setting up devices for MQTT Discovery")
    for i in range(len(power_topic)):
        sensor = power_topic[i].split('/')[2]
        _sensor = sensor[0].upper() + sensor[1:].replace('_', ' ')
        client.publish(
            "homeassistant/sensor/uPower/upower-{}/config".format(sensor),
            str(json.dumps({
                'name': "uPower {}".format(_sensor),
                'state_topic': "{}".format(power_topic[i]),
                'state_class': 'measurement',
                'unique_id': "upower_{}".format(sensor),
                'device_class': "power",
                'unit_of_meas': "W",
                'last_reset': '1970-01-01T00:00:00+00:00',
                'device': {
                    'name': "uPower",
                    'model': "ESP 8266 with RTC and OLED",
                    'manufacturer': "Buffedelic AB",
                    "identifiers": ["UPOW1"]
                    }
            })),
            True,
            1
        )


def publish_usage(watt_total, watt_heater, watt_ftx, watt_household):
    client.publish(
        "power/meter/total/current",
        str(watt_total), False, 0)
    client.publish(
        "power/meter/heater/current",
        str(watt_heater), False, 0)
    client.publish(
        "power/meter/ftx/current",
        str(watt_ftx), False, 0)
    client.publish(
        "power/meter/household/current",
        str(watt_household), False, 0)
    update_screen("", "Publish!", 50)
    time.sleep(0.5)
    debug_print("publishing to broker: {}".format(_MQTT_BROKER))


# ##################
# WiFi Functions
# ##################


def wlan_connect():
    _wlan.active(True)
    if not _wlan.isconnected():
        print('Connecting to network...')
        _wlan.connect('Nescafe', 'nopassword')
        while not _wlan.isconnected():
            _led.value(1)  # turn off
            time.sleep(2.0)
            _led.value(0)  # turn on
            time.sleep(0.1)
    print('network config:', _wlan.ifconfig())

# ##################
# OLED Functions
# ##################


def update_screen(text_l='', text_r='', row=30):
    '''
    - Clears and updates specific row
    - If strings overlap '###' is displayed on specified row
    - Function sets a border and inverted Header
    - Takes left justified text and right justified text as arguments.
    - Frambuf yields 16 char wide text. 1 char is 8 pixels wide
    - Rows 10, 20, 30, 40, 50 are available for text
    '''
    # printbuf = []
    # if printbuf[row] == "" or None:
    #     printbuf[row] = text

    if (len(text_l) + len(text_r)) <= 16:
        # Clears characters from row
        _oled.fill_rect(0 + 1, row, _OLED_W - 2, 8, 0x0000)
        if text_l != "" or None:
            _oled.text("{}".format(text_l), 2, row)
        if text_r != "" or None:
            _pos = _OLED_W - (len(text_r) * 8) - 3
            _oled.text("{}".format(text_r), _pos, row)
    else:
        _oled.text("################", 0, row)
    _oled.show()


def clear_screen():
    _oled.fill_rect(0 + 1, 0 + 10, _OLED_W - 2, _OLED_H - 13, 0x0000)
    _oled.show()


def initialize_screen(text):
    clear_screen()
    _oled.fill_rect(0, 0, 128, 8, 0xffff)
    _oled.rect(0, 0, _OLED_W, _OLED_H, 0xffff)
    _oled.text(text, 0, 0, 0x0000)
    _oled.show()

# ##################
# Main
# ##################


def main():
    global _ERROR
    _ERROR = False
    first_run = True
    _error_count = 0
    _millis_last = time.ticks_ms()
    _led.value(0)  # turn on
    watt_ftx = 0
    watt_total = 0
    watt_household = 0
    watt_heater = 0

    initialize_screen("  Setting up..")

    initialize_hardware()

    handle_error()

    _rtc.settime('ntp')
    update_screen("Setup complete", "", 50)
    time.sleep(2)

    # ####################################
    # ####################################
    # Total, None
    counter_1 = ds2423.DS2423(_ow)
    counter_1.begin(bytearray(b'\x1d\x6c\xec\x0c\x00\x00\x00\x94'))
    # Heater, FTX
    counter_2 = ds2423.DS2423(_ow)
    counter_2.begin(bytearray(b'\x1d\x00\xfd\x0c\x00\x00\x00\x9b'))
    # ####################################
    # ####################################

    clear_screen()
    debug_print("Device testing ok")
    initialize_screen(_OLED_HEADER_TEXT)
    _led.value(1)  # turn off

    total_last = counter_1.get_count("DS2423_COUNTER_A")
    heater_last = counter_2.get_count("DS2423_COUNTER_A")
    ftx_last = counter_2.get_count("DS2423_COUNTER_B")

    while True:
        # 39540831 current count counter1 - A
        total = counter_1.get_count("DS2423_COUNTER_A")
        heater = counter_2.get_count("DS2423_COUNTER_A")
        ftx = counter_2.get_count("DS2423_COUNTER_B")

        _millis_interval = time.ticks_ms() - _millis_last
        _millis_last = time.ticks_ms()

        # P(w) = (3600 / T(s)) / ppwh
        # watt = (3600 / ((interval_millis / interval_count)) / 1000) or 800

        _tdiff = (total - total_last)
        try:
            watt_total = (3600000 / (_millis_interval / _tdiff)) / 1
        except ZeroDivisionError:
            watt_total = 0
        total_last = total

        _hdiff = (heater - heater_last)
        try:
            watt_heater = (3600000 / (_millis_interval / _hdiff)) / 0.8
        except ZeroDivisionError:
            watt_heater = 0
        heater_last = heater

        _fdiff = (ftx - ftx_last)
        try:
            watt_ftx = (3600000 / (_millis_interval / _fdiff)) / 1
        except ZeroDivisionError:
            watt_ftx = 0
        ftx_last = ftx

        watt_household = watt_total - watt_heater - watt_ftx

        debug_print("Total: {}W".format(watt_total))
        debug_print("Heater: {}W".format(watt_heater))
        debug_print("FTX: {}W".format(watt_ftx))
        debug_print("Household: {}W".format(watt_household))
        debug_print("Interval: {}s".format(_millis_interval / 1000))
        print("Interval: {}s".format(_millis_interval / 1000))

        update_screen("Total:", "{}W".format(int(watt_total)), 10)
        update_screen("Heater:", "{}W".format(int(watt_heater)), 20)
        update_screen("FTX:", "{}W".format(int(watt_ftx)), 30)
        update_screen("House:", "{}W".format(int(watt_household)), 40)

        if not _wlan.isconnected():
            wlan_connect()
            client.connect()
            # if not _wlan.isconnected():
            #     _ERROR = True
            #     handle_error()
        if not first_run:
            if _millis_interval >= 62000:
                # skip publish
                _error_count += 1
                if _error_count == 5:
                    _ERROR = True
                print("Will not publish! Interval: {}s, error count: {}".format((_millis_interval / 1000), _error_count))
            else:
                try:
                    publish_usage(watt_total, watt_heater, watt_ftx, watt_household)
                except OSError:
                    wlan_connect()
                    client.connect()
                    publish_usage(watt_total, watt_heater, watt_ftx, watt_household)
            if _millis_interval >= 86400000:
                _rtc.settime('ntp')
        else:
            first_run = False
        for t in range(0, 30):
            update_screen("", "_", 50)
            time.sleep(0.9)
            update_screen("", "", 50)
            time.sleep(0.9)


if __name__ == '__main__':
    main()


""" links
- https://docs.micropython.org/en/latest/esp8266/quickref.html#delay-and-timing
- https://eds.zendesk.com/hc/en-us/articles/214484283-Reading-the-DS2423-external-counters-using-the-OW-SERVER-v2-low-level-commands
- https://awesome-micropython.com
- https://github.com/gwvsol/ESP8266-RTC-PCF8563
- https://docs.pycom.io/tutorials/hardware/owd/

"""
