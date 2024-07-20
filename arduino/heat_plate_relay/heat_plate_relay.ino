#include <SPI.h>
#include <stdint.h>
#include <mcp2515.h>
#include "util.h"

#define HEAT_PLATE_CMD_PGN    0xFFA0
#define HEAT_PLATE_STATE_PGN  0xFFA1
#define PRIORITY     6
#define NODE_ADDR    0x80
#define MASTER_ADDR  0x10

#define RELAY_PIN      3
#define LOOP_DELAY     5
#define CAN_DLC        8
#define CS_PIN        10

// 29 bit mask
#define CAN_ID_MASK  0x1FFFFFFF

#define SEND_STATUS_INTERVAL 100

MCP2515 mcp2515(CS_PIN);
uint8_t curr_relay_state;
unsigned long next_status_send_time;

void setup() {
  pinMode(RELAY_PIN, OUTPUT);
  // Set relay pin off initially
  curr_relay_state = 0x00;
  next_status_send_time = millis();
  
  set_relay();

  mcp2515.reset();
  mcp2515.setBitrate(CAN_125KBPS, MCP_16MHZ);
  mcp2515.setNormalMode();

  // Serial.begin(9600);
}

// SG_ RELAY_STATE : 0|1@1+ (1,0) [0|1] "" HEAT_PLATE_NODE
#define RELAY_STATE_off 0
#define RELAY_STATE_len 1
uint8_t read_RELAY_STATE(uint8_t *data, size_t dlen) {
  uint8_t num[] = {0x00};
  const size_t nlen = 1;
  
  Util::project(data, dlen, num, nlen, RELAY_STATE_off, RELAY_STATE_len);
  return Util::decode_uint8(num, nlen, RELAY_STATE_len);
}

// SG_ RELAY_STATE : 0|1@1+ (1,0) [0|1] "" MASTER_NODE
#define RELAY_STATE_off 0
#define RELAY_STATE_len 1
void write_RELAY_STATE(uint8_t n, uint8_t *data, size_t dlen) {
  uint8_t num[] = {0x00};
  const size_t nlen = 1;

  Util::encode_uint8(n, RELAY_STATE_len, num);
  Util::inject(data, dlen, num, nlen, RELAY_STATE_off, RELAY_STATE_len);
}

void handle_relay_cmd(can_frame& frame) {
  curr_relay_state = read_RELAY_STATE(frame.data, CAN_DLC);
}

void send_relay_status() {
  struct can_frame frame;
  frame.can_id = Util::pgn_to_can_id(HEAT_PLATE_STATE_PGN, PRIORITY, NODE_ADDR, 0xFF);
  frame.can_id |= CAN_EFF_FLAG;

  frame.can_dlc = CAN_DLC;
  write_RELAY_STATE(curr_relay_state, frame.data, CAN_DLC);

  mcp2515.sendMessage(&frame);
}


void read_loop() {
  struct can_frame frame;

  if (mcp2515.readMessage(&frame) == MCP2515::ERROR_OK) {
    uint32_t can_id = frame.can_id & CAN_ID_MASK;
    uint32_t msg_pgn = Util::can_id_to_pgn(can_id);
    uint8_t msg_src = Util::can_id_to_src_addr(can_id);
    uint8_t msg_dest = Util::can_id_to_dest_addr(can_id);
    
    if(msg_pgn == HEAT_PLATE_CMD_PGN &&
       msg_src == MASTER_ADDR &&
       frame.can_dlc == CAN_DLC &&
       (msg_dest == 0xFF || msg_dest == NODE_ADDR)
    ) {
      handle_relay_cmd(frame);
    }
  }
}


void write_loop() {
  if (millis() > next_status_send_time) {
    send_relay_status();
    next_status_send_time = next_status_send_time + SEND_STATUS_INTERVAL;
  }
}


void set_relay() {
  if (curr_relay_state == 0x00) {
    digitalWrite(RELAY_PIN, LOW);
  } else if (curr_relay_state == 0x01) {
    digitalWrite(RELAY_PIN, HIGH);
  }
}


void loop() {
  read_loop();
  write_loop();
  set_relay();
  delay(LOOP_DELAY);
}
