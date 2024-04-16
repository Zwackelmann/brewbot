#include <SPI.h>
#include <stdint.h>
#include <mcp2515.h>
#include "util.h"

#define PGN        0xFFB0
#define PRIORITY   6
#define SRC_ADDR   0x70
#define DEST_ADDR  0x00

#define TEMP_VOLTAGE_PIN  A0
#define LOOP_DELAY       100
#define CAN_DLC            8
#define CS_PIN            10

// 29 bit mask
#define CAN_ID_MASK  0x1FFFFFFF

MCP2515 mcp2515(CS_PIN);

void setup() {
  pinMode(TEMP_VOLTAGE_PIN, INPUT);

  mcp2515.reset();
  mcp2515.setBitrate(CAN_125KBPS, MCP_16MHZ);
  mcp2515.setNormalMode();

  // Serial.begin(9600);
}

// SG_ TEMP_VOLTAGE : 0|10@1+ (1,0) [0|1023] "V" MASTER
#define TEMP_VOLTAGE_off 0
#define TEMP_VOLTAGE_len 10
void write_TEMP_VOLTAGE(uint32_t n, uint8_t *data, size_t dlen) {
  uint8_t num[] = {0x00, 0x00};
  const size_t nlen = 2;

  Util::encode_uint32(n, TEMP_VOLTAGE_len, num);
  Util::inject(data, dlen, num, nlen, TEMP_VOLTAGE_off, TEMP_VOLTAGE_len);
}

void loop() {
  uint32_t temp_v = analogRead(TEMP_VOLTAGE_PIN);
  
  struct can_frame frame;
  frame.can_id = Util::pgn_to_can_id(PGN, PRIORITY, SRC_ADDR, DEST_ADDR);
  frame.can_id |= CAN_EFF_FLAG;
  
  frame.can_dlc = CAN_DLC;
  write_TEMP_VOLTAGE(temp_v, frame.data, CAN_DLC);

  mcp2515.sendMessage(&frame);

  delay(LOOP_DELAY);
}
