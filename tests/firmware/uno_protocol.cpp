#include <cassert>
#include "../../firmware/arduino_uno_usb_serial/arduino_uno_usb_serial.ino"

int main() {
  setup();
  const int stopA = SERVO_A_CONTINUOUS ? 1500 : 0;
  const int stopB = SERVO_B_CONTINUOUS ? 1500 : 0;
  const int runA = SERVO_A_CONTINUOUS ? 1600 : 90;
  const int runB = SERVO_B_CONTINUOUS ? 1600 : 90;
  // Startup must send neutral, never a continuous rotation command.
  assert((servoA.angles == std::vector<int>{stopA}));
  assert((servoB.angles == std::vector<int>{stopB}));
  servoA.angles.clear();
  servoB.angles.clear();

  // Exact wire format produced by the PC's hardware test, without a coin.
  Serial.incoming.push_back("DISPENSE:test-a:A\r");
  unsigned long before = fakeTime;
  loop();
  assert((servoA.angles == std::vector<int>{runA, stopA}));
  unsigned long expectedMs = SERVO_A_CONTINUOUS ? 770 : 1000;
  assert(fakeTime - before >= expectedMs && fakeTime - before < expectedMs + 100);
  assert(servoB.angles.empty());
  assert(Serial.outgoing.back() == "DONE:test-a");
  Serial.incoming.push_back("DISPENSE:test-b:B");
  loop();
  assert((servoB.angles == std::vector<int>{runB, stopB}));
  assert(Serial.outgoing.back() == "DONE:test-b");

  // A late response to an old coin must never dispense during idle.
  auto count = Serial.outgoing.size();
  Serial.incoming.push_back("DISPENSE:old:stale:A");
  loop();
  assert(servoA.angles.size() == 2);
  assert(Serial.outgoing.size() == count);

  // Ordinary coin handling still matches the coin ID and returns reservation ACK.
  Serial.incoming = {"DISPENSE:old:stale:A", "DISPENSE:1:coin-b:B"};
  handleCoinInserted();
  assert(Serial.outgoing[count] == "COIN:1");
  assert(Serial.outgoing.back() == "DONE:coin-b");
  assert(servoA.angles.size() == 2);
  assert(servoB.angles.size() == 4);
  assert(servoB.angles.back() == stopB);

  // No-dispense and invalid commands do not drive either motor.
  Serial.incoming = {"NONE:2"};
  handleCoinInserted();
  Serial.incoming = {"DISPENSE:bad:Z"};
  loop();
  assert(Serial.outgoing.back() == "FAILED:bad");
  assert(servoA.angles.size() == 2 && servoB.angles.size() == 4);

  // Test command arriving while awaiting a coin response is also accepted.
  Serial.incoming = {"DISPENSE:overlap:A", "NONE:3"};
  handleCoinInserted();
  assert(servoA.angles.size() == 4);
  assert(servoA.angles.back() == stopA);
  bool acknowledged = false;
  for (const auto &line : Serial.outgoing) {
    if (line == "DONE:overlap") acknowledged = true;
  }
  assert(acknowledged);

  // The PC releases the coin wait with NONE, then sends RUN after the video ends.
  Serial.incoming = {"NONE:4"};
  auto aCount = servoA.angles.size();
  auto bCount = servoB.angles.size();
  handleCoinInserted();
  assert(servoA.angles.size() == aCount && servoB.angles.size() == bCount);
  Serial.incoming = {"RUN:after-video:A:850"};
  before = fakeTime;
  loop();
  expectedMs = SERVO_A_CONTINUOUS ? 850 : 1000;
  assert(fakeTime - before >= expectedMs && fakeTime - before < expectedMs + 100);
  assert(servoA.angles.size() == aCount + 2 && servoA.angles.back() == stopA);
  assert(Serial.outgoing.back() == "DONE:after-video");

  // v2.4.1 PC uses a legacy-compatible DISPENSE command and appends timing to
  // the reservation token. It must use that timing and echo the exact token.
  Serial.incoming = {"DISPENSE:compatible~920:B"};
  before = fakeTime;
  loop();
  expectedMs = SERVO_B_CONTINUOUS ? 920 : 1000;
  assert(fakeTime - before >= expectedMs && fakeTime - before < expectedMs + 100);
  assert(servoB.angles.back() == stopB);
  assert(Serial.outgoing.back() == "DONE:compatible~920");

  for (const auto &bad : {"0", "2001", "-100", "770xyz", "", "99999999"}) {
    Serial.incoming = {String("RUN:invalid:A:") + bad};
    loop();
    assert(Serial.outgoing.back() == "FAILED:invalid");
    assert(servoA.angles.size() == aCount + 2);
  }
}
