#ifndef J1939_ARDUINO_ARDUINO_SHIM_H
#define J1939_ARDUINO_ARDUINO_SHIM_H

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <chrono>
#include <thread>
#include <iostream>
#include <algorithm>

#ifndef F
// Arduino's flash string helper — as no-op on host
#define F(x) x
#endif

#ifndef PROGMEM
#define PROGMEM
#endif

// Minimal Serial replacement
struct Serial_t {
  void begin(unsigned long) {}
  template<typename T>
  void print(const T& v)       { std::cout << v; }
  void print(const char* s)    { std::cout << s; }
  void print(char c)           { std::cout << c; }
  void print(unsigned v, int)  { std::cout << v; }     // HEX/DEC ignored
  void println()               { std::cout << std::endl; }
  template<typename T>
  void println(const T& v)     { std::cout << v << std::endl; }
} inline Serial;

// millis()/delay() stubs
inline unsigned long millis() {
  using namespace std::chrono;
  static const auto t0 = steady_clock::now();
  return (unsigned long)duration_cast<milliseconds>(steady_clock::now() - t0).count();
}
inline void delay(unsigned long ms) {
  std::this_thread::sleep_for(std::chrono::milliseconds(ms));
}

// Random stubs (optional)
inline long random(long max) { return std::rand() % max; }
inline long random(long minv, long maxv) { return minv + std::rand() % (maxv - minv); }
inline void randomSeed(unsigned long s) { std::srand((unsigned)s); }

template<typename T>
constexpr const T& max(const T& a, const T& b) {
  return (a > b) ? a : b;
}

template<typename T>
constexpr const T& min(const T& a, const T& b) {
  return (a < b) ? a : b;
}

static void dump_hex(const uint8_t* data, size_t len) {
  std::string hex_letters = "0123456789ABCDEF";
  for (size_t i=0; i<len; i++) {
    uint8_t hex_1 = (data[i] >> 4) & 0x0F;
    uint8_t hex_2 = data[i] & 0x0F;

    std::cout <<  hex_letters[hex_1] << hex_letters[hex_2] << " ";
  }
  std::cout << std::endl;
}

#endif