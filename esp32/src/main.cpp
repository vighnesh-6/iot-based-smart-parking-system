#include <Arduino.h>
#include <WiFi.h>
#include <MQTT.h>
#include <cstdarg>
#include <cstdio>
#include <ctime>
#include "mqtt_config.h"

#ifndef PARKING_BOARD_ID
#error "Select a board-specific build: esp32_01, esp32_02 or esp32_03"
#endif

static_assert(PARKING_BOARD_ID >= 1 && PARKING_BOARD_ID <= 3,
              "PARKING_BOARD_ID must be 1, 2 or 3");

// Change this default or supply -DPARKING_OCCUPIED_THRESHOLD_CM=25.0f
// when compiling. Valid distances at or below the threshold are OCCUPIED.
#ifndef PARKING_OCCUPIED_THRESHOLD_CM
#define PARKING_OCCUPIED_THRESHOLD_CM 20.0f
#endif

namespace {

constexpr float kOccupiedThresholdCm = PARKING_OCCUPIED_THRESHOLD_CM;
constexpr float kMinDistanceCm = 2.0f;
constexpr float kMaxDistanceCm = 400.0f;
constexpr unsigned long kEchoTimeoutUs = 30000UL;
constexpr unsigned long kSensorQuietTimeMs = 60UL;
constexpr unsigned long kScanIntervalMs = 1000UL;
constexpr unsigned long kSerialBaud = 115200UL;

static_assert(kOccupiedThresholdCm >= kMinDistanceCm &&
                  kOccupiedThresholdCm <= kMaxDistanceCm,
              "Occupancy threshold must be between 2 and 400 cm");

struct ParkingSlot {
  const char* id;
  uint8_t trigPin;
  uint8_t echoPin;
};

#if PARKING_BOARD_ID == 1
constexpr const char* kBoardName = "ESP32-01";
constexpr const char* kDeviceId = "esp32_01";
constexpr const char* kMqttClientId = "smartparking-esp32_01";
constexpr const char* kTelemetryTopic = "smartparking/esp32_01/telemetry";
constexpr ParkingSlot kSlots[] = {
    {"P1", 13, 34},
    {"P2", 14, 35},
    {"P3", 25, 32},
    {"P4", 26, 33},
};
#elif PARKING_BOARD_ID == 2
constexpr const char* kBoardName = "ESP32-02";
constexpr const char* kDeviceId = "esp32_02";
constexpr const char* kMqttClientId = "smartparking-esp32_02";
constexpr const char* kTelemetryTopic = "smartparking/esp32_02/telemetry";
constexpr ParkingSlot kSlots[] = {
    {"P5", 13, 34},
    {"P6", 14, 35},
    {"P7", 25, 32},
    {"P8", 26, 33},
};
#else
constexpr const char* kBoardName = "ESP32-03";
constexpr const char* kDeviceId = "esp32_03";
constexpr const char* kMqttClientId = "smartparking-esp32_03";
constexpr const char* kTelemetryTopic = "smartparking/esp32_03/telemetry";
constexpr ParkingSlot kSlots[] = {
    {"P9", 13, 34},
    {"P10", 14, 35},
    {"P11", 25, 32},
    {"P12", 26, 33},
};
#endif

static_assert(sizeof(kSlots) / sizeof(kSlots[0]) == 4,
              "Each ESP32 must handle exactly four local sensors");

enum class ReadingStatus { Valid, EchoTimeout, OutOfRange };

struct DistanceReading {
  float distanceCm;
  ReadingStatus status;
};

struct SlotSample {
  DistanceReading reading;
  time_t timestamp;
};

constexpr unsigned long kPublishIntervalMs = PARKING_MQTT_PUBLISH_INTERVAL_MS;
static_assert(kPublishIntervalMs >= 1000UL && kPublishIntervalMs <= 3600000UL,
              "Publish interval must be between one second and one hour");
constexpr size_t kPayloadCapacity = 1536;
WiFiClient gNetwork;
MQTTClient gMqtt(kPayloadCapacity);
bool gWifiAttempted = false;
bool gWasWifiConnected = false;
bool gMqttAttempted = false;
bool gPublishAttempted = false;
unsigned long gWifiLastAttemptMs = 0;
unsigned long gWifiRetryMs = 10000UL;
unsigned long gMqttLastAttemptMs = 0;
unsigned long gMqttRetryMs = 1000UL;
unsigned long gLastPublishAttemptMs = 0;
unsigned long gSequence = 0;

unsigned long nextRetryDelay(unsigned long delayMs) {
  return delayMs < 15000UL ? delayMs * 2UL : 30000UL;
}

void printMqttError(const char* action) {
  Serial.print(kBoardName);
  Serial.print(" | MQTT ");
  Serial.print(action);
  Serial.print(" | last_error=");
  Serial.print(static_cast<int>(gMqtt.lastError()));
  Serial.print(" return_code=");
  Serial.println(static_cast<int>(gMqtt.returnCode()));
}

// No wait-until-connected loops: scans continue during network/broker outages.
// TCP/MQTT connection calls themselves are bounded to approximately one second.
void serviceNetwork() {
  unsigned long now = millis();
  if (WiFi.status() != WL_CONNECTED) {
    if (gWasWifiConnected) {
      Serial.println("Wi-Fi disconnected; sensor scanning continues.");
      gWasWifiConnected = false;
      gMqtt.disconnect();
    }
    if (!gWifiAttempted || now - gWifiLastAttemptMs >= gWifiRetryMs) {
      gWifiAttempted = true;
      gWifiLastAttemptMs = now;
      WiFi.begin(PARKING_WIFI_SSID, PARKING_WIFI_PASSWORD, PARKING_WIFI_CHANNEL);
      gWifiRetryMs = nextRetryDelay(gWifiRetryMs);
      Serial.println("Wi-Fi connection requested.");
    }
    return;
  }
  if (!gWasWifiConnected) {
    gWasWifiConnected = true;
    gWifiRetryMs = 10000UL;
    gMqttAttempted = false;
    gMqttRetryMs = 1000UL;
    // Asynchronous SNTP; do not block scanning while waiting for wall time.
    configTime(0, 0, "pool.ntp.org", "time.google.com");
    Serial.println("Wi-Fi connected; UTC clock synchronization requested.");
  }
  if (gMqtt.connected()) {
    gMqtt.loop();
    if (gMqtt.connected()) return;
  }
  now = millis();
  if (!gMqttAttempted || now - gMqttLastAttemptMs >= gMqttRetryMs) {
    gMqttAttempted = true;
    gMqttLastAttemptMs = now;
#if PARKING_MQTT_LOG_PAYLOAD
    Serial.print(kBoardName);
    Serial.print(" | MQTT connect attempt: client=");
    Serial.print(kMqttClientId);
    Serial.print(" broker=");
    Serial.print(PARKING_MQTT_HOST);
    Serial.print(":");
    Serial.println(PARKING_MQTT_PORT);
#endif
    const bool connected = PARKING_MQTT_USERNAME[0] != '\0'
        ? gMqtt.connect(kMqttClientId, PARKING_MQTT_USERNAME, PARKING_MQTT_PASSWORD)
        : gMqtt.connect(kMqttClientId);
    if (connected) {
      gMqttRetryMs = 1000UL;
      gPublishAttempted = false; // Send a fresh scan after every reconnect.
      Serial.print("MQTT connected: ");
      Serial.println(kTelemetryTopic);
    } else {
      gMqttRetryMs = nextRetryDelay(gMqttRetryMs);
      printMqttError("connection failed; retry scheduled");
    }
  }
}

void waitWithNetwork(unsigned long durationMs) {
  const unsigned long started = millis();
  while (millis() - started < durationMs) {
    serviceNetwork();
    const unsigned long elapsed = millis() - started;
    if (elapsed >= durationMs) break;
    const unsigned long remaining = durationMs - elapsed;
    delay(remaining < 10UL ? remaining : 10UL);
  }
}

bool timestampJson(time_t epoch, char (&output)[24]) {
  // An unsynchronized ESP32 clock normally starts at the Unix epoch.
  if (epoch < 1704067200) {
    snprintf(output, sizeof(output), "null");
    return false;
  }
  struct tm utc;
#ifdef _WIN32
  const bool valid = gmtime_s(&utc, &epoch) == 0;
#else
  const bool valid = gmtime_r(&epoch, &utc) != nullptr;
#endif
  if (!valid || strftime(output, sizeof(output), "\"%Y-%m-%dT%H:%M:%SZ\"", &utc) == 0) {
    snprintf(output, sizeof(output), "null");
    return false;
  }
  return true;
}

bool appendJson(char* buffer, size_t capacity, size_t& used, const char* format, ...) {
  if (used >= capacity) return false;
  va_list arguments;
  va_start(arguments, format);
  const int written = vsnprintf(buffer + used, capacity - used, format, arguments);
  va_end(arguments);
  if (written < 0 || static_cast<size_t>(written) >= capacity - used) return false;
  used += static_cast<size_t>(written);
  return true;
}

bool buildTelemetry(const SlotSample (&samples)[4], char* buffer, size_t capacity,
                    unsigned long sequence, time_t publishedAt) {
  size_t used = 0;
  char timestamp[24];
  const bool clockSynced = timestampJson(publishedAt, timestamp);
  if (!appendJson(buffer, capacity, used,
      "{\"schema_version\":1,\"device_id\":\"%s\",\"sequence\":%lu,"
      "\"timestamp\":%s,\"clock_synced\":%s,\"uptime_ms\":%lu,\"slots\":[",
      kDeviceId, sequence, timestamp, clockSynced ? "true" : "false", millis())) return false;
  for (size_t i = 0; i < 4; ++i) {
    const auto& sample = samples[i];
    timestampJson(sample.timestamp, timestamp);
    char distance[24] = "null";
    const char* status = "UNKNOWN";
    if (sample.reading.status == ReadingStatus::Valid) {
      snprintf(distance, sizeof(distance), "%.1f", sample.reading.distanceCm);
      status = sample.reading.distanceCm <= kOccupiedThresholdCm ? "OCCUPIED" : "VACANT";
    }
    if (!appendJson(buffer, capacity, used,
        "%s{\"slot_id\":\"%s\",\"distance_cm\":%s,\"occupancy_status\":\"%s\",\"timestamp\":%s}",
        i ? "," : "", kSlots[i].id, distance, status, timestamp)) return false;
  }
  return appendJson(buffer, capacity, used, "]}");
}

void publishTelemetry(const SlotSample (&samples)[4]) {
  const bool connected = gMqtt.connected();
  const unsigned long now = millis();
  const bool due = !gPublishAttempted || now - gLastPublishAttemptMs >= kPublishIntervalMs;
#if PARKING_MQTT_LOG_PAYLOAD
  Serial.print(kBoardName);
  Serial.print(" | MQTT publish check: connected=");
  Serial.print(connected ? "yes" : "no");
  Serial.print(" due=");
  Serial.println(due ? "yes" : "no");
#endif
  if (!connected || !due) return;
  gPublishAttempted = true;
  gLastPublishAttemptMs = now;
  char payload[kPayloadCapacity];
  if (!buildTelemetry(samples, payload, sizeof(payload), gSequence, time(nullptr))) {
    Serial.println("Telemetry exceeds buffer; nothing published.");
    return;
  }
  // QoS 1, non-retained. Duplicate delivery is possible; no old scan replay.
#if PARKING_MQTT_LOG_PAYLOAD
  Serial.print(kBoardName);
  Serial.print(" | MQTT publish attempt: ");
  Serial.println(kTelemetryTopic);
#endif
  if (gMqtt.publish(kTelemetryTopic, payload, false, 1)) {
    ++gSequence;
    Serial.print("MQTT telemetry published: ");
    Serial.println(kTelemetryTopic);
#if PARKING_MQTT_LOG_PAYLOAD
    Serial.print(kBoardName);
    Serial.print(" | MQTT acknowledged payload: ");
    Serial.println(payload);
#endif
  } else {
    printMqttError("publish failed; next interval uses a fresh scan");
  }
}

DistanceReading measureDistance(const ParkingSlot& slot) {
  digitalWrite(slot.trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(slot.trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(slot.trigPin, LOW);

  const unsigned long pulseUs = pulseIn(slot.echoPin, HIGH, kEchoTimeoutUs);
  if (pulseUs == 0) {
    return {0.0f, ReadingStatus::EchoTimeout};
  }

  // HC-SR04 round-trip echo duration: approximately 58 us per centimeter.
  const float distanceCm = static_cast<float>(pulseUs) / 58.0f;
  if (distanceCm < kMinDistanceCm || distanceCm > kMaxDistanceCm) {
    return {distanceCm, ReadingStatus::OutOfRange};
  }

  return {distanceCm, ReadingStatus::Valid};
}

void printReading(const ParkingSlot& slot, const DistanceReading& reading) {
  Serial.print(kBoardName);
  Serial.print(" | ");
  Serial.print(slot.id);
  Serial.print(" | TRIG=");
  Serial.print(slot.trigPin);
  Serial.print(" ECHO=");
  Serial.print(slot.echoPin);
  Serial.print(" | distance_cm=");

  if (reading.status == ReadingStatus::EchoTimeout) {
    Serial.println("N/A | state=UNKNOWN | reason=ECHO_TIMEOUT");
    return;
  }

  Serial.print(reading.distanceCm, 1);
  if (reading.status == ReadingStatus::OutOfRange) {
    Serial.println(" | state=UNKNOWN | reason=OUT_OF_RANGE");
    return;
  }

  Serial.print(" | state=");
  Serial.println(reading.distanceCm <= kOccupiedThresholdCm ? "OCCUPIED"
                                                           : "VACANT");
}

}  // namespace

void setup() {
  Serial.begin(kSerialBaud);

  for (const ParkingSlot& slot : kSlots) {
    pinMode(slot.trigPin, OUTPUT);
    digitalWrite(slot.trigPin, LOW);
    // GPIO 34/35 are input-only and do not support internal pull resistors.
    pinMode(slot.echoPin, INPUT);
  }

  delay(200);
  Serial.print("Smart Parking: ");
  Serial.print(kBoardName);
  Serial.println(" | four local sensors / twelve total slots | MQTT Phase 1");
  Serial.print("OCCUPIED when valid distance_cm <= ");
  Serial.println(kOccupiedThresholdCm, 1);
  Serial.println("Invalid readings are UNKNOWN, never VACANT.");
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  gNetwork.setConnectionTimeout(1000);
  gMqtt.begin(PARKING_MQTT_HOST, PARKING_MQTT_PORT, gNetwork);
  gMqtt.setOptions(30, true, 1000);
  serviceNetwork();
}

void loop() {
  const unsigned long scanStartedMs = millis();
  Serial.print("--- scan_ms=");
  Serial.print(scanStartedMs);
  Serial.println(" ---");

  // Trigger one sensor at a time, leaving a quiet interval to reduce crosstalk.
  SlotSample samples[4];
  for (size_t i = 0; i < 4; ++i) {
    serviceNetwork();
    samples[i] = {measureDistance(kSlots[i]), time(nullptr)};
    printReading(kSlots[i], samples[i].reading);
    waitWithNetwork(kSensorQuietTimeMs);
  }
  publishTelemetry(samples);

  // Unsigned subtraction also works when millis() wraps around.
  const unsigned long elapsedMs = millis() - scanStartedMs;
  if (elapsedMs < kScanIntervalMs) {
    waitWithNetwork(kScanIntervalMs - elapsedMs);
  }
}
