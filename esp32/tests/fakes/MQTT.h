#pragma once
#include "WiFi.h"
#include <string>
#include <vector>

struct FakePublication {
  std::string topic;
  std::string payload;
  bool retained;
  int qos;
};
struct MQTTClient {
  bool online = false;
  bool connectResult = true;
  bool publishResult = true;
  unsigned int loopCalls = 0;
  unsigned int publishCalls = 0;
  std::string host;
  int port = 0;
  std::vector<std::string> clientIds;
  std::vector<FakePublication> published;
  explicit MQTTClient(size_t) {}
  void begin(const char* value, int number, WiFiClient&) { host=value; port=number; }
  void setOptions(int, bool, int) {}
  bool connected() { return online; }
  bool loop() { ++loopCalls; return online; }
  void disconnect() { online = false; }
  bool connect(const char* id) {
    clientIds.emplace_back(id); online = connectResult; return online;
  }
  bool connect(const char* id, const char*, const char*) { return connect(id); }
  bool publish(const char* topic, const char* payload, bool retained, int qos) {
    ++publishCalls;
    if (!online || !publishResult) return false;
    published.push_back({topic,payload,retained,qos});
    return true;
  }
};
