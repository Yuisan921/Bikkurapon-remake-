// Native test doubles: compile and execute the actual Uno sketch without hardware.
#pragma once
#include <algorithm>
#include <deque>
#include <string>
#include <vector>

class String : public std::string {
 public:
  using std::string::string;
  String(const std::string &value) : std::string(value) {}
  String(unsigned long value) : std::string(std::to_string(value)) {}
  bool startsWith(const String &prefix) const { return rfind(prefix, 0) == 0; }
  int indexOf(char value, unsigned int from = 0) const {
    auto pos = find(value, from);
    return pos == npos ? -1 : static_cast<int>(pos);
  }
  String substring(unsigned int from, size_t to = npos) const {
    if (from >= size()) return "";
    return substr(from, std::min<size_t>(to, size()) - from);
  }
  void trim() {
    auto first = find_first_not_of(" \t\r\n");
    if (first == npos) { clear(); return; }
    assign(substr(first, find_last_not_of(" \t\r\n") - first + 1));
  }
};

constexpr int LOW = 0, HIGH = 1, INPUT_PULLUP = 2;
inline unsigned long fakeTime = 1000;
inline int sensorLevel = HIGH;
inline unsigned long millis() { return fakeTime++; }
inline void delay(unsigned long ms) { fakeTime += ms; }
inline void pinMode(int, int) {}
inline int digitalRead(int) { return sensorLevel; }

class Servo {
 public:
  std::vector<int> angles;
  void attach(int) {}
  void write(int angle) { angles.push_back(angle); }
  void writeMicroseconds(int pulse) { angles.push_back(pulse); }
};

struct FakeSerial {
  std::deque<String> incoming;
  std::vector<String> outgoing;
  void begin(int) {}
  bool available() { return !incoming.empty(); }
  String readStringUntil(char) {
    String line = incoming.front();
    incoming.pop_front();
    return line;
  }
  void println(const String &line) { outgoing.push_back(line); }
};
inline FakeSerial Serial;

// Arduino's build preprocessor normally generates these declarations.
void handleCoinInserted();
String waitForResponse(const String &, unsigned long);
bool isTestCommand(const String &);
void dispenseIfWon(const String &);
void handleTimedCommand(const String &);
void executeDispense(const String &, const String &, unsigned long);
void stopServo(Servo &, bool, int, int);
void dispenseFrom(Servo &, bool, int, int, int, int, unsigned long);
