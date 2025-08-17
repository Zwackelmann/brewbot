#include <SPI.h>
#include <stdint.h>
#include <mcp2515.h>

#define RELAY_PIN      3
#define LOOP_DELAY     5
#define CS_PIN        10

#define SEND_STATUS_INTERVAL 100

#include "util.h"

MCP2515 mcp2515(CS_PIN);
uint8_t curr_relay_state;

J1939 bus;
RelayCmdDisp relay;
Scheduler<2> sched;

void setup() {
  pinMode(RELAY_PIN, OUTPUT);
  
  // Set relay pin off initially
  curr_relay_state = 0x00;
  set_relay();

  mcp2515.reset();
  mcp2515.setBitrate(CAN_125KBPS, MCP_16MHZ);
  mcp2515.setNormalMode();

  relay.set_handler(handle_relay_cmd);
  bus.register_disp<RelayCmdDisp>(&relay, MASTER_ADDR, NODE_ADDR);

  sched.items[0] = { 1000u, millis(), send_node_info    };
  sched.items[1] = {  250u, millis(), send_relay_status };

  // Serial.begin(9600);
}


void send_node_info() {
  can_frame frame{};

  NodeInfoDisp::prepare(&frame, NODE_ADDR, MASTER_ADDR);
  NodeInfoDisp::encode_signal_node_type(&frame, static_cast<uint8_t>(NODE_TYPE));
  NodeInfoDisp::encode_signal_node_id(&frame, NODE_ID);
  NodeInfoDisp::encode_signal_version_major(&frame, VERSION_MAJOR);
  NodeInfoDisp::encode_signal_version_minor(&frame, VERSION_MINOR);
  NodeInfoDisp::encode_signal_version_patch(&frame, VERSION_PATCH);
  NodeInfoDisp::encode_signal_uptime(&frame, millis()/1000);

  mcp2515.sendMessage(&frame);
}


void send_relay_status() {
  can_frame frame{};
  RelayStatusDisp::prepare(&frame, NODE_ADDR, MASTER_ADDR);
  RelayStatusDisp::encode_signal_on(&frame, curr_relay_state);

  mcp2515.sendMessage(&frame);
}


void handle_relay_cmd(uint8_t on, void* ctx) {
  curr_relay_state = on;
  set_relay();
}


void set_relay() {
  if (curr_relay_state == 0x00) {
    digitalWrite(RELAY_PIN, LOW);
  } else if (curr_relay_state == 0x01) {
    digitalWrite(RELAY_PIN, HIGH);
  }
}


void read_loop() {
  struct can_frame frame;
  if (mcp2515.readMessage(&frame) == MCP2515::ERROR_OK) {
    bus.process_frame(&frame);
  }
}


void loop() {
  read_loop();
  sched.tick();
  delay(LOOP_DELAY);
}
