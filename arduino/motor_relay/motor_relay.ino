#include <SPI.h>
#include <stdint.h>
#include <mcp2515.h>
#include "util.h"

#define PGN        0xFFA1
#define PRIORITY   6
#define SRC_ADDR   0x80
#define DEST_ADDR  0x00

#define RELAY_PIN      3
#define LOOP_DELAY     5
#define CAN_DLC        8
#define CS_PIN        10

// 29 bit mask
#define CAN_ID_MASK  0x1FFFFFFF

MCP2515 mcp2515(CS_PIN);

void setup() {
  pinMode(RELAY_PIN, OUTPUT);
  // Set relay pin off initially
  digitalWrite(RELAY_PIN, LOW);

  mcp2515.reset();
  mcp2515.setBitrate(CAN_125KBPS, MCP_16MHZ);
  mcp2515.setNormalMode();

  // Serial.begin(9600);
}

// SG_ RELAY_STATE : 0|1@1+ (1,0) [0|1] "" MOTOR
#define RELAY_STATE_off 0
#define RELAY_STATE_len 1
uint8_t read_RELAY_STATE(uint8_t *data, size_t dlen) {
  uint8_t num[] = {0x00};
  const size_t nlen = 1;
  
  Util::project(data, dlen, num, nlen, RELAY_STATE_off, RELAY_STATE_len);
  return Util::decode_uint8(num, nlen, RELAY_STATE_len);
}

void handle_can_frame(can_frame& frame) {
  uint8_t relay_state = read_RELAY_STATE(frame.data, CAN_DLC);

  if (relay_state == 0) {
    digitalWrite(RELAY_PIN, LOW);
  } else if (relay_state == 1) {
    digitalWrite(RELAY_PIN, HIGH);
  }
}

void loop() {
  struct can_frame frame;

  if (mcp2515.readMessage(&frame) == MCP2515::ERROR_OK) {
    uint32_t can_id = frame.can_id & CAN_ID_MASK;

    if(Util::can_id_to_pgn(can_id) == PGN &&
       Util::can_id_to_src_addr(can_id) == SRC_ADDR &&
       frame.can_dlc == CAN_DLC // &&
       // Util::can_id_to_dest_addr(can_id) == DEST_ADDR &&
       // Util::can_id_to_priority(can_id) == PRIORITY
    ) {
      handle_can_frame(frame);
    }
  }

  delay(LOOP_DELAY);
}
