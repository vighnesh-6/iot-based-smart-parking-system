#pragma once
#include <cstdint>
#include <string>

constexpr int WIFI_STA = 1;
constexpr int WL_CONNECTED = 3;
constexpr int WL_DISCONNECTED = 6;

struct WiFiClient {
  uint32_t timeout = 0;
  void setConnectionTimeout(uint32_t value) { timeout = value; }
};
struct FakeWiFi {
  int state = WL_DISCONNECTED;
  unsigned int attempts = 0;
  int channel = 0;
  bool autoReconnect = false;
  std::string ssid;
  void mode(int) {}
  void setAutoReconnect(bool value) { autoReconnect = value; }
  int status() { return state; }
  void begin(const char* name, const char*, int value) {
    ++attempts; ssid = name; channel = value;
  }
};
inline FakeWiFi WiFi;
inline unsigned int fakeNtpRequests = 0;
inline void configTime(long, int, const char*, const char*) { ++fakeNtpRequests; }
