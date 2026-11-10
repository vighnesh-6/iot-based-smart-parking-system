#pragma once

// Optional: copy to config.h for private local overrides. Never commit config.h.
// Board identity remains in platformio.ini: PARKING_BOARD_ID=1, 2 or 3.
// Public Wokwi defaults below contain no credentials.
#define PARKING_WIFI_SSID "Wokwi-GUEST"
#define PARKING_WIFI_PASSWORD ""
#define PARKING_WIFI_CHANNEL 6
#define PARKING_MQTT_HOST "host.wokwi.internal"
#define PARKING_MQTT_PORT 1883
#define PARKING_MQTT_USERNAME ""
#define PARKING_MQTT_PASSWORD ""
#define PARKING_MQTT_PUBLISH_INTERVAL_MS 5000UL
// Optional sensor threshold override; the default is 20.0f.
// #define PARKING_OCCUPIED_THRESHOLD_CM 25.0f
