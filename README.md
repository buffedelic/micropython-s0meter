# Micropython s0 meter

## Description

ESP82266 module I had laying around. It incorporates a sd1306 OLED screen and PCF8563 RTC clock. 1wire counters are on its own monitoring s0 pulses, or blinking led, from power meters. Can be used for any meter with a s0 pulse connection.
I have written this code specifically for my needs, but it is in general easy to adapt to other situations.

During startup led blinks until WiFi is connected. When setup checks is complete led turns off to indicate normal operation.

Processed counter data is send out via MQTT
MQTT Discovery in Homeassistant ensures easy configuring

---

![HA](https://github.com/buffedelic/micropython-s0meter/tree/master/img/ha-dev.png "Homeassistant automatic device configuration")

---

### Hardware

* ESP8266, ESP-12f, ESP32
* SSD1306 i2c oled
* OneWire Counters, DS2423P

### Wiring

* Uses i2c pins 4 and 5.
* IO0 is used for 1wire bus and needs a 0, 8 to 1, 5 kOhms pullup resistor to 3, 3v
