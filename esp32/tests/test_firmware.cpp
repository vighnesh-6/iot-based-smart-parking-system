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
}

void testAssignmentAndSetup() {
  clearFakes();
  const uint8_t expectedTrig[] = {13, 14, 25, 26};
  const uint8_t expectedEcho[] = {34, 35, 32, 33};
  setup();
  assert(Serial.baud == 115200);
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
  assert(fakeDelays.size() == 5);
  for (unsigned int i = 0; i < 4; ++i) assert(fakeDelays[i] == 60);
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
  std::cout << kBoardName << ": PASS host logic tests (not a Wokwi runtime test)\n";
}
