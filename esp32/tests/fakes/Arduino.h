#pragma once

// Host-only Arduino seam. This file is never on the ESP32 firmware include path.
#include <cstdint>
#include <deque>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

constexpr int LOW = 0;
constexpr int HIGH = 1;
constexpr int INPUT = 0;
constexpr int OUTPUT = 1;

inline unsigned long fakeMillis = 0;
inline std::deque<unsigned long> fakePulses;
inline std::vector<std::pair<uint8_t, int>> fakePinModes;
inline std::vector<std::pair<uint8_t, int>> fakeWrites;
inline std::vector<uint8_t> fakeEchoPins;
inline std::vector<unsigned long> fakeTimeouts;
inline std::vector<unsigned long> fakeDelays;
inline std::vector<unsigned int> fakeMicroDelays;

struct FakeSerial {
  unsigned long baud = 0;
  std::ostringstream output;
  void begin(unsigned long value) { baud = value; }
  template <class T> void print(const T& value) { output << value; }
  void print(uint8_t value) { output << static_cast<unsigned int>(value); }
  void print(float value, int digits) {
    output << std::fixed << std::setprecision(digits) << value;
  }
  template <class T> void println(const T& value) { print(value); output << '\n'; }
  void println(float value, int digits) { print(value, digits); output << '\n'; }
  void clear() { output.str(""); output.clear(); }
};

inline FakeSerial Serial;
inline void pinMode(uint8_t pin, int mode) { fakePinModes.emplace_back(pin, mode); }
inline void digitalWrite(uint8_t pin, int value) { fakeWrites.emplace_back(pin, value); }
inline void delayMicroseconds(unsigned int value) { fakeMicroDelays.push_back(value); }
inline unsigned long millis() { return fakeMillis; }
inline void delay(unsigned long value) {
  fakeDelays.push_back(value);
  fakeMillis += value;
}
inline unsigned long pulseIn(uint8_t pin, int level, unsigned long timeout) {
  if (level != HIGH || fakePulses.empty()) {
    throw std::runtime_error("Unexpected pulseIn call");
  }
  fakeEchoPins.push_back(pin);
  fakeTimeouts.push_back(timeout);
  const unsigned long pulse = fakePulses.front();
  fakePulses.pop_front();
  fakeMillis += ((pulse == 0 ? timeout : pulse) + 999) / 1000;
  return pulse;
}
