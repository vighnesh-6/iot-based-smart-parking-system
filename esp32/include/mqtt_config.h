#pragma once

// Optional private overrides. config.h is excluded by the repository .gitignore.
#if defined(PARKING_MQTT_TLS) && PARKING_MQTT_TLS
#if __has_include("config.cloud.h")
#include "config.cloud.h"
#endif
#elif __has_include("config.h")
#include "config.h"
#endif

#ifndef PARKING_MQTT_TLS
#define PARKING_MQTT_TLS 0
#endif
#ifndef PARKING_MQTT_CA_CERT
#define PARKING_MQTT_CA_CERT ""
#endif

#ifndef PARKING_WIFI_SSID
#define PARKING_WIFI_SSID "Wokwi-GUEST"
#endif
#ifndef PARKING_WIFI_PASSWORD
#define PARKING_WIFI_PASSWORD ""
#endif
#ifndef PARKING_WIFI_CHANNEL
#define PARKING_WIFI_CHANNEL 6
#endif
#ifndef PARKING_MQTT_HOST
#define PARKING_MQTT_HOST "host.wokwi.internal"
#endif
#ifndef PARKING_MQTT_PORT
#define PARKING_MQTT_PORT 1883
#endif
#ifndef PARKING_MQTT_USERNAME
#define PARKING_MQTT_USERNAME ""
#endif
#ifndef PARKING_MQTT_PASSWORD
#define PARKING_MQTT_PASSWORD ""
#endif
#ifndef PARKING_MQTT_PUBLISH_INTERVAL_MS
#define PARKING_MQTT_PUBLISH_INTERVAL_MS 5000UL
#endif
#ifndef PARKING_MQTT_LOG_PAYLOAD
#define PARKING_MQTT_LOG_PAYLOAD 1
#endif
