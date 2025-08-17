#include <SPI.h>
#include <stdint.h>
#include <mcp2515.h>

#define RELAY_PIN      3
#define LOOP_DELAY     5
#define CS_PIN        10

#define SEND_STATUS_INTERVAL 100

static void print_hex(const uint8_t *b, size_t n) {
  for (size_t i=0;i<n;i++) { if (b[i] < 0x10) Serial.print('0'); Serial.print(b[i], HEX); Serial.print(' '); }
}

/* generated */

#include "util.h"



/*void j1939_process_frame(const struct can_frame* frame) {
    if (!frame) return;

    const uint32_t can_id   = frame->can_id & CAN_ID_MASK;
    const uint32_t pgn  = Util::can_id_to_pgn(can_id);
    const uint8_t  src  = Util::can_id_to_src_addr(can_id);
    const uint8_t  dest = Util::can_id_to_dest_addr(can_id);

    for (uint8_t i = 0; i < (uint8_t)(sizeof msg_table / sizeof msg_table[0]); ++i) {
        const j1939_msg_desc_t *m = &msg_table[i];
        if (pgn == m->pgn &&
            (m->src  == J1939_ANY || src  == m->src) &&
            (m->dest == J1939_ANY || dest == m->dest) &&
            frame->can_dlc == m->dlc)
        {
            m->decode_and_call(frame->data);
            break;
        }
    }
}*/

/* END generated */


// MCP2515 mcp2515(CS_PIN);
uint8_t curr_relay_state;
unsigned long next_status_send_time;

void setup() {
  // pinMode(RELAY_PIN, OUTPUT);
  // Set relay pin off initially
  // curr_relay_state = 0x00;
  // next_status_send_time = millis();

  // j1939_register_relay_cmd_handler(handle_relay_state_cmd);

  // set_relay();

  // mcp2515.reset();
  // mcp2515.setBitrate(CAN_125KBPS, MCP_16MHZ);
  // mcp2515.setNormalMode();

  Serial.begin(9600);
}



// SG_ RELAY_STATE : 0|1@1+ (1,0) [0|1] "" MASTER_NODE
/* #define RELAY_STATE_off 0
#define RELAY_STATE_len 1
void write_RELAY_STATE(uint8_t n, uint8_t *data, size_t dlen) {
  Util::encode_uint(n, data, CAN_DLC, RELAY_STATE_off, RELAY_STATE_len);
}*/


/*void send_relay_status() {
  struct can_frame frame;
  frame.can_id = Util::pgn_to_can_id(RELAY_STATE_PGN, PRIORITY, NODE_ADDR, 0xFF);
  frame.can_id |= CAN_EFF_FLAG;

  frame.can_dlc = CAN_DLC;
  write_RELAY_STATE(curr_relay_state, frame.data, CAN_DLC);

  mcp2515.sendMessage(&frame);
}*/



/*void read_loop() {
  struct can_frame frame;

  if (mcp2515.readMessage(&frame) == MCP2515::ERROR_OK) {
    j1939_process_frame(&frame);
  }
}*/


/*void write_loop() {
  if (millis() > next_status_send_time) {
    send_relay_status();
    next_status_send_time = next_status_send_time + SEND_STATUS_INTERVAL;
  }
}*/


/*void set_relay() {
  if (curr_relay_state == 0x00) {
    digitalWrite(RELAY_PIN, LOW);
  } else if (curr_relay_state == 0x01) {
    digitalWrite(RELAY_PIN, HIGH);
  }
}*/


void loop() {
  // read_loop();
  // write_loop();
  // set_relay();
  delay(LOOP_DELAY);
}
