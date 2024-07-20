#include <SPI.h>
#include <stdint.h>
#include <mcp2515.h>
#include "util.h"

#define TEMP_STATE_PNG  0xFFC1
#define PRIORITY     6
#define NODE_ADDR    0x70
#define MASTER_ADDR  0x10

#define TEMP_VOLTAGE_PIN  A0
#define LOOP_DELAY         5
#define CAN_DLC            8
#define CS_PIN            10

// 29 bit mask
#define CAN_ID_MASK  0x1FFFFFFF

// voltage assumed when analog read returns maximum value
#define V_MAX 5.0
// maximum value for analog voltage reading
#define VINT_MAX ((1 << 10) - 1)
// sloap for voltage to temperature conversion
#define V_TO_TEMP_M 23.69448038
// constant shift for voltage to temperature conversion
#define V_TO_TEMP_B -4.59983094

#define SEND_STATUS_INTERVAL 100

MCP2515 mcp2515(CS_PIN);
unsigned long next_status_send_time;

void setup() {
  pinMode(TEMP_VOLTAGE_PIN, INPUT);

  next_status_send_time = millis();

  mcp2515.reset();
  mcp2515.setBitrate(CAN_125KBPS, MCP_16MHZ);
  mcp2515.setNormalMode();

  // Serial.begin(9600);
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
  uint32_t temp_vint = analogRead(TEMP_VOLTAGE_PIN);

  double temp_v = ((double)temp_vint * V_MAX) / VINT_MAX;
  double temp_c = (temp_v * V_TO_TEMP_M) + V_TO_TEMP_B;

  struct can_frame frame;
  frame.can_id = Util::pgn_to_can_id(TEMP_STATE_PNG, PRIORITY, NODE_ADDR, 0xFF);
  frame.can_id |= CAN_EFF_FLAG;

  frame.can_dlc = CAN_DLC;
  write_TEMP_V(temp_v, frame.data, CAN_DLC);
  write_TEMP_C(temp_c, frame.data, CAN_DLC);

  mcp2515.sendMessage(&frame);
}


void write_loop() {
  if (millis() > next_status_send_time) {
    send_temp_status();
    next_status_send_time = next_status_send_time + SEND_STATUS_INTERVAL;
  }
}


void loop() {
  write_loop();
  delay(LOOP_DELAY);
}
