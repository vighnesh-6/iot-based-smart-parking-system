#pragma once
// Copy to ignored config.cloud.h only for explicitly selected *_cloud targets.
// Enter credentials privately; never commit the configured header or build outputs.
#define PARKING_MQTT_HOST "YOUR_DEPLOYMENT.emqxsl.com"
#define PARKING_MQTT_PORT 8883
#define PARKING_MQTT_USERNAME ""
#define PARKING_MQTT_PASSWORD ""
// Paste the broker's PUBLIC CA certificate as a C++ raw string. Never use setInsecure.
#define PARKING_MQTT_CA_CERT ""
// Preserve the verified five-second publish cadence; run only during demonstrations.
