#include <SPI.h>
#include <stdint.h>
#include <mcp2515.h>
#include "util.h"

#define TEMP_VOLTAGE_PIN  A0
#define LOOP_DELAY         5
#define CAN_DLC            8
#define CS_PIN            10

// 29 bit mask
#define CAN_ID_MASK  0x1FFFFFFF

// voltage assumed when analog read returns maximum value
#define V_MAX 5.033
// maximum value for analog voltage reading
#define VINT_MAX ((1 << 10) - 1)

#define SEND_STATUS_INTERVAL 100

#define BOARD_ID 1

#if BOARD_ID == 1
  #define TEMP_STATE_PNG  0xFFC1
  #define NODE_ADDR    0x70

  // x^2 coefficient for v_to_temp function
  #define V_TO_TEMP_X2 3.0980205
  // x^1 coefficient for v_to_temp function
  #define V_TO_TEMP_X1 35.82164965
  // x^0 coefficient for v_to_temp function
  #define V_TO_TEMP_X0 -49.55763119
#elif BOARD_ID == 2
  #define TEMP_STATE_PNG  0xFFC2
  #define NODE_ADDR    0x71
  
  // x^2 coefficient for v_to_temp function
  #define V_TO_TEMP_X2 1.97914111
  // x^1 coefficient for v_to_temp function
  #define V_TO_TEMP_X1 41.73056052
  // x^0 coefficient for v_to_temp function
  #define V_TO_TEMP_X0 -57.66374902
#endif

#define PRIORITY     6
#define MASTER_ADDR  0x10

MCP2515 mcp2515(CS_PIN);
unsigned long next_status_send_time;

uint32_t vint_sum = 0;
uint32_t n_samples = 0;

void setup() {
  pinMode(TEMP_VOLTAGE_PIN, INPUT);

  next_status_send_time = millis();

  mcp2515.reset();
  mcp2515.setBitrate(CAN_125KBPS, MCP_16MHZ);
  mcp2515.setNormalMode();

  // Serial.begin(9600);
}

void read_sample() {
  vint_sum += analogRead(TEMP_VOLTAGE_PIN);
  n_samples += 1;
}

double curr_v() {
  uint32_t vint = vint_sum / n_samples;
  return ((double)vint * V_MAX) / VINT_MAX;
}

double fetch_and_reset_v() {
  double v = curr_v();
  vint_sum = 0;
  n_samples = 0;

  return v;
}

// SG_ TEMP_C : 0|16@1- (0.01,0) [-327.68|327.67] "C" MASTER_NODE
#define TEMP_C_off 0
#define TEMP_C_len 16
void write_TEMP_C(double c, uint8_t *data, size_t dlen) {
  int16_t n = (int16_t)(c * 100);

  uint8_t num[] = {0x00, 0x00};
  const size_t nlen = 2;

  Util::encode_int32(n, TEMP_C_len, num);
  Util::inject(data, dlen, num, nlen, TEMP_C_off, TEMP_C_len);
}

// SG_ TEMP_V : 16|16@1+ (0.001,0) [0|65.535] "V" MASTER_NODE
#define TEMP_V_off 16
#define TEMP_V_len 16
void write_TEMP_V(double v, uint8_t *data, size_t dlen) {
  uint16_t n = (uint16_t)(v * 1000);

  uint8_t num[] = {0x00, 0x00};
  const size_t nlen = 2;

  Util::encode_uint32(n, TEMP_V_len, num);
  Util::inject(data, dlen, num, nlen, TEMP_V_off, TEMP_V_len);
}

void send_temp_status() {
  double temp_v = fetch_and_reset_v();
  double temp_c = (temp_v * temp_v * V_TO_TEMP_X2) + (temp_v * V_TO_TEMP_X1) + V_TO_TEMP_X0;

  struct can_frame frame;
  frame.can_id = Util::pgn_to_can_id(TEMP_STATE_PNG, PRIORITY, NODE_ADDR, 0xFF);
  frame.can_id |= CAN_EFF_FLAG;

  frame.can_dlc = CAN_DLC;
  write_TEMP_V(temp_v, frame.data, CAN_DLC);
  write_TEMP_C(temp_c, frame.data, CAN_DLC);

  mcp2515.sendMessage(&frame);
}

void loop() {
  read_sample();

  if (millis() > next_status_send_time) {
    send_temp_status();
    next_status_send_time = next_status_send_time + SEND_STATUS_INTERVAL;
  }

  delay(LOOP_DELAY);
}
