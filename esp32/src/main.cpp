#include <Arduino.h>

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

constexpr ParkingSlot kSlots[] = {
    {"P1", 13, 34},
    {"P2", 14, 35},
    {"P3", 25, 32},
    {"P4", 26, 33},
};

enum class ReadingStatus { Valid, EchoTimeout, OutOfRange };

struct DistanceReading {
  float distanceCm;
  ReadingStatus status;
};

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
  Serial.println("Smart Parking: four HC-SR04 sensors, Serial only");
  Serial.print("OCCUPIED when valid distance_cm <= ");
  Serial.println(kOccupiedThresholdCm, 1);
  Serial.println("Invalid readings are UNKNOWN, never VACANT.");
}

void loop() {
  const unsigned long scanStartedMs = millis();
  Serial.print("--- scan_ms=");
  Serial.print(scanStartedMs);
  Serial.println(" ---");

  // Trigger one sensor at a time, leaving a quiet interval to reduce crosstalk.
  for (const ParkingSlot& slot : kSlots) {
    const DistanceReading reading = measureDistance(slot);
    printReading(slot, reading);
    delay(kSensorQuietTimeMs);
  }

  // Unsigned subtraction also works when millis() wraps around.
  const unsigned long elapsedMs = millis() - scanStartedMs;
  if (elapsedMs < kScanIntervalMs) {
    delay(kScanIntervalMs - elapsedMs);
  }
}
