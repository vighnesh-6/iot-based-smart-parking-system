// Compile this translation unit for each PARKING_BOARD_ID on the host.
// It includes the production source; no second copy of detection logic exists.
#include <cassert>
#include <cstring>
#include <iostream>
#include <limits>

#include "../src/main.cpp"

void clearFakes() {
  fakePulses.clear();
  fakePinModes.clear();
  fakeWrites.clear();
  fakeEchoPins.clear();
  fakeTimeouts.clear();
  fakeDelays.clear();
  fakeMicroDelays.clear();
  Serial.clear();
  fakeMillis = 0;
  WiFi = FakeWiFi{};
  gMqtt = MQTTClient(kPayloadCapacity);
  gNetwork = WiFiClient{};
  fakeNtpRequests = 0;
  gWifiAttempted = gWasWifiConnected = gMqttAttempted = gPublishAttempted = false;
  gWifiLastAttemptMs = gMqttLastAttemptMs = gLastPublishAttemptMs = gSequence = 0;
  gWifiRetryMs = 10000UL;
  gMqttRetryMs = 1000UL;
}

void testAssignmentAndSetup() {
  clearFakes();
  const uint8_t expectedTrig[] = {13, 14, 25, 26};
  const uint8_t expectedEcho[] = {34, 35, 32, 33};
  setup();
  assert(Serial.baud == 115200);
  const std::string device = "esp32_0" + std::to_string(PARKING_BOARD_ID);
  assert(device == kDeviceId);
  assert("smartparking-" + device == kMqttClientId);
  assert("smartparking/" + device + "/telemetry" == kTelemetryTopic);
  assert(fakePinModes.size() == 8 && fakeWrites.size() == 4);
  for (unsigned int i = 0; i < 4; ++i) {
    const std::string id = "P" + std::to_string(4 * (PARKING_BOARD_ID - 1) + i + 1);
    assert(id == kSlots[i].id);
    assert(kSlots[i].trigPin == expectedTrig[i]);
    assert(kSlots[i].echoPin == expectedEcho[i]);
    assert(fakePinModes[2 * i] == std::make_pair(expectedTrig[i], OUTPUT));
    assert(fakePinModes[2 * i + 1] == std::make_pair(expectedEcho[i], INPUT));
    assert(fakeWrites[i] == std::make_pair(expectedTrig[i], LOW));
  }
}

void testReading(unsigned long pulse, ReadingStatus status, const char* text) {
  clearFakes();
  fakePulses.push_back(pulse);
  const auto reading = measureDistance(kSlots[0]);
  assert(reading.status == status);
  assert(fakeEchoPins == std::vector<uint8_t>{34});
  assert(fakeTimeouts == std::vector<unsigned long>{30000});
  assert(fakeMicroDelays == (std::vector<unsigned int>{2, 10}));
  assert(fakeWrites == (std::vector<std::pair<uint8_t, int>>{
      {uint8_t{13}, LOW}, {uint8_t{13}, HIGH}, {uint8_t{13}, LOW}}));
  printReading(kSlots[0], reading);
  assert(Serial.output.str().find(text) != std::string::npos);
  if (status != ReadingStatus::Valid) {
    assert(Serial.output.str().find("state=VACANT") == std::string::npos);
  }
}

void testScan(bool wrapClock) {
  clearFakes();
  if (wrapClock) fakeMillis = std::numeric_limits<unsigned long>::max() - 100;
  const unsigned long started = fakeMillis;
  fakePulses = {580, 5800, 0, 23201}; // occupied, vacant, timeout, out of range
  loop();
  assert(fakePulses.empty());
  assert(fakeEchoPins == (std::vector<uint8_t>{34, 35, 32, 33}));
  assert(!fakeDelays.empty());
  for (const auto delayMs : fakeDelays) assert(delayMs > 0 && delayMs <= 10);
  assert(fakeMillis - started == 1000);
  const std::string log = Serial.output.str();
  const char* expected[] = {"OCCUPIED", "VACANT", "UNKNOWN", "UNKNOWN"};
  for (unsigned int i = 0; i < 4; ++i) {
    const auto start = log.find(std::string(kBoardName) + " | " + kSlots[i].id + " | ");
    assert(start != std::string::npos);
    const auto line = log.substr(start, log.find('\n', start) - start);
    assert(line.find(std::string("state=") + expected[i]) != std::string::npos);
  }
  // Ensure no foreign slot identity is emitted by this board.
  for (unsigned int slot = 1; slot <= 12; ++slot) {
    const bool owned = (slot - 1) / 4 == PARKING_BOARD_ID - 1;
    const std::string marker = " | P" + std::to_string(slot) + " | ";
    assert((log.find(marker) != std::string::npos) == owned);
  }
}

void testTelemetry() {
  clearFakes();
  SlotSample samples[4] = {
      {{10.0f, ReadingStatus::Valid}, 0},
      {{100.0f, ReadingStatus::Valid}, 0},
      {{0.0f, ReadingStatus::EchoTimeout}, 0},
      {{401.0f, ReadingStatus::OutOfRange}, 0}};
  char payload[kPayloadCapacity];
  assert(buildTelemetry(samples, payload, sizeof(payload), 7, 0));
  const std::string json = payload;
  assert(json.find("\"clock_synced\":false") != std::string::npos);
  assert(json.find("\"timestamp\":null") != std::string::npos);
  assert(json.find("\"sequence\":7") != std::string::npos);
  for (const auto& slot : kSlots)
    assert(json.find(std::string("\"slot_id\":\"") + slot.id + "\"") != std::string::npos);
  assert(json.find("\"distance_cm\":10.0,\"occupancy_status\":\"OCCUPIED\"") != std::string::npos);
  assert(json.find("\"distance_cm\":100.0,\"occupancy_status\":\"VACANT\"") != std::string::npos);
  assert(json.find("\"distance_cm\":null,\"occupancy_status\":\"UNKNOWN\"") != std::string::npos);
  char tiny[10];
  assert(!buildTelemetry(samples, tiny, sizeof(tiny), 0, 0));
  char timestamp[24];
  assert(timestampJson(1704067200, timestamp));
  assert(std::string(timestamp) == "\"2024-01-01T00:00:00Z\"");

  gMqtt.online = true;
  publishTelemetry(samples);
  assert(gSequence == 1 && gMqtt.published.size() == 1);
  const auto publication = gMqtt.published.front();
  assert(publication.topic == kTelemetryTopic && !publication.retained && publication.qos == 1);
  fakeMillis += kPublishIntervalMs - 1;
  publishTelemetry(samples);
  assert(gMqtt.publishCalls == 1);
  ++fakeMillis;
  publishTelemetry(samples);
  assert(gSequence == 2 && gMqtt.published.size() == 2);
  gMqtt.publishResult = false;
  fakeMillis += kPublishIntervalMs;
  publishTelemetry(samples);
  assert(gSequence == 2 && gMqtt.publishCalls == 3);
  publishTelemetry(samples);
  assert(gMqtt.publishCalls == 3); // failed publications are rate-limited too
  std::cout << "PAYLOAD " << json << '\n';
}

void testNetworkRecovery() {
  clearFakes();
  setup();
  assert(gMqtt.host == "host.wokwi.internal" && gMqtt.port == 1883);
  assert(WiFi.ssid == "Wokwi-GUEST" && WiFi.channel == 6 && WiFi.autoReconnect);
  assert(gNetwork.timeout == 1000 && WiFi.attempts == 1);
  fakeMillis = gWifiLastAttemptMs + gWifiRetryMs - 1;
  serviceNetwork();
  assert(WiFi.attempts == 1);
  ++fakeMillis;
  serviceNetwork();
  assert(WiFi.attempts == 2);
  WiFi.state = WL_CONNECTED;
  gMqtt.connectResult = false;
  serviceNetwork();
  assert(fakeNtpRequests == 1 && gMqtt.clientIds.size() == 1);
  serviceNetwork();
  assert(gMqtt.clientIds.size() == 1);
  for (unsigned int retry = 0; retry < 7; ++retry) {
    fakeMillis = gMqttLastAttemptMs + gMqttRetryMs;
    serviceNetwork();
    assert(gMqttRetryMs <= 30000UL);
  }
  gMqtt.connectResult = true;
  gPublishAttempted = true;
  fakeMillis = gMqttLastAttemptMs + gMqttRetryMs;
  serviceNetwork();
  assert(gMqtt.connected() && !gPublishAttempted);
  for (const auto& id : gMqtt.clientIds) assert(id == kMqttClientId);
  serviceNetwork();
  assert(gMqtt.loopCalls > 0);
  WiFi.state = WL_DISCONNECTED;
  serviceNetwork();
  assert(!gMqtt.connected());
}

int main() {
  testAssignmentAndSetup();
  testReading(116, ReadingStatus::Valid, "state=OCCUPIED"); // 2 cm
  testReading(580, ReadingStatus::Valid, "state=OCCUPIED"); // 10 cm
  testReading(1160, ReadingStatus::Valid, "state=OCCUPIED"); // 20 cm boundary
  testReading(1161, ReadingStatus::Valid, "state=VACANT"); // just over 20 cm
  testReading(23200, ReadingStatus::Valid, "state=VACANT"); // 400 cm boundary
  testReading(0, ReadingStatus::EchoTimeout, "state=UNKNOWN | reason=ECHO_TIMEOUT");
  testReading(1, ReadingStatus::OutOfRange, "state=UNKNOWN | reason=OUT_OF_RANGE");
  testReading(23201, ReadingStatus::OutOfRange, "state=UNKNOWN | reason=OUT_OF_RANGE");
  testScan(false);
  testScan(true);
  testTelemetry();
  testNetworkRecovery();
  std::cout << kBoardName << ": PASS host logic tests (not a Wokwi runtime test)\n";
}
