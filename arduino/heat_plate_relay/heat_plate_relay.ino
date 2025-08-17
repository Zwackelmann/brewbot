#include <SPI.h>
#include <stdint.h>
// #include <mcp2515.h>

#define RELAY_PIN      3
#define LOOP_DELAY     5
#define CS_PIN        10

#define SEND_STATUS_INTERVAL 100

static void print_hex(const uint8_t *b, size_t n) {
  for (size_t i=0;i<n;i++) { if (b[i] < 0x10) Serial.print('0'); Serial.print(b[i], HEX); Serial.print(' '); }
}

/* generated */

#include "util.h"

/* sentinels */
#define J1939_ANY       0xFEu   // not a real address
#define J1939_BROADCAST 0xFFu

#define NODE_INFO_PGN    0xFF00u
#define RELAY_CMD_PGN    0x1000u
#define RELAY_STATE_PGN  0xFF11u
#define PRIORITY     6
#define NODE_ADDR    0x81u
#define MASTER_ADDR  0x10u

#define CAN_DLC        8

// 29 bit mask
#define CAN_ID_MASK  0x1FFFFFFFu

/* CAN Message table */
typedef struct {
    uint32_t pgn;
    size_t   dlc;
    uint8_t  src;    // J1939_ANY means "any"
    uint8_t  dest;   // J1939_ANY means "any"; J1939_BROADCAST is actual 0xFF
    void (*decode_and_call)(const uint8_t *data);
} j1939_msg_desc_t;

/* == message relay_cmd == */
// handler type
typedef void (*_j1939_relay_cmd_handler_t)(uint8_t on);

// default noop handler
void  _j1939_handle_relay_cmd_noop(uint8_t on) { (void)on; }

// set handler to default noop handler
static _j1939_relay_cmd_handler_t _j1939_relay_cmd_handler = _j1939_handle_relay_cmd_noop;

/* = relay_cmd signal decoders = */
// relay_cmd/on signal decoder
static inline uint8_t _j1939_decode_relay_cmd_on(const uint8_t *data) {
  return Util::decode_uint(data, CAN_DLC, 0 /* start_bit */, 1 /* signal_size */);
}
/* = END relay_cmd signal decoders = */

// decode all signals and call handler
static void _j1939_thunk_relay_cmd(const uint8_t *data) {
    const uint8_t on = _j1939_decode_relay_cmd_on(data);
    _j1939_relay_cmd_handler(on);
}

// register function for the user to override message receive behaviour
//void j1939_register_relay_cmd_handler(_j1939_relay_cmd_handler_t handler) {
//    if (handler) _j1939_relay_cmd_handler = handler;
//}


// Table containing one line for each rx message
static const j1939_msg_desc_t msg_table[] = {
    { RELAY_CMD_PGN, CAN_DLC, MASTER_ADDR, NODE_ADDR, _j1939_thunk_relay_cmd },
};

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

void handle_relay_state_cmd(uint8_t on) {
  curr_relay_state = on;
}

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

  while (!Serial) ; // wait for Serial on Leonardo/Micro

  // randomSeed(analogRead(A0));
  run_more_tests();
}

static void clear8(uint8_t *b) { for (int i=0;i<8;i++) b[i]=0; }

// simple check printer
static void checku(const char* label, uint32_t want, uint32_t got) {
  if (want == got) {
    Serial.print("  [PASS]  ");
  } else {
    Serial.print("  [FAIL]  ");
  }

  Serial.print(label); Serial.print(" -> ");
  Serial.print("want="); Serial.print(want); Serial.print(" got="); Serial.print(got);

  Serial.println();
}

// simple check printer
static void checks(const char* label, int32_t want, int32_t got) {
  if (want == got) {
    Serial.print("  [PASS]  ");
  } else {
    Serial.print("  [FAIL]  ");
  }

  Serial.print(label); Serial.print(" -> ");
  Serial.print("want="); Serial.print(want); Serial.print(" got="); Serial.print(got);

  Serial.println();
}

static void checkok(const char* label, bool ok) {
  Serial.print(label); Serial.println(ok ? " OK" : " FAIL");
}

void run_more_tests() {
  uint8_t d[8];

  Serial.println(F("=== Unsigned straddle/align cases ==="));
  struct UCase { uint32_t v; size_t sbit; size_t bits; };
  const UCase ucases[] = {
    /*{0xA5,  3, 8},     // straddle with odd shift
    {0x123, 7, 12},    // 12 bits starting at bit 7 (hits 3 bytes)
    {0x7F,  15, 7},    // sits in high part of byte2 and low of byte1
    {0x55,  4, 8},     // your prior failing case (regression)
    {0xBEEF, 0, 16},   // aligned 2 bytes
    {0xC0FFEEu & 0xFFFF, 16, 16}, // aligned middle two bytes
    {0x1,   31, 1},    // last bit of first 4 bytes
    {0x3,   30, 2},    // two bits across a byte boundary
    {0xFFFFFFFFu, 1, 32}*/
    {0xFF, 60, 32},
  };

  for (size_t i=0;i<sizeof(ucases)/sizeof(ucases[0]);++i) {
    clear8(d);
    Util::encode_uint(ucases[i].v, d, 8, ucases[i].sbit, ucases[i].bits);
    Serial.println();
    Serial.print(F("UCase ")); Serial.print(i);
    Serial.print(F(": start=")); Serial.print(ucases[i].sbit);
    Serial.print(F(" size="));   Serial.print(ucases[i].bits);
    Serial.print(F(" data="));   print_hex(d, 8); Serial.println();

    uint32_t got = Util::decode_uint(d, 8, ucases[i].sbit, ucases[i].bits);
    uint32_t mask = (ucases[i].bits==32) ? 0xFFFFFFFFUL : ((1UL<<ucases[i].bits)-1UL);
    checku("decode(unsigned)", ucases[i].v & mask, got);
  }

  Serial.println(F("\n=== Signed cases (two's complement, odd widths) ==="));
  struct SCase { int32_t v; size_t sbit; size_t bits; };
  const SCase scases[] = {
    {-1, 60, 32},
    // {0xFF, 60, 32},
    /*{-1, 0, 1},       // 1-bit signed: only -1 and 0/1 edge behavior
    {-1, 1, 1},       // 1-bit signed: only -1 and 1/1 edge behavior
    {-1, 0, 2},       // 2-bit signed: only -1 and 1/2 edge behavior
    {-5, 0, 4},       // 0b1011
    {-5, 5, 5},       // 0b11011 shifted
    {-123, 9, 13},    // 13-bit negative across bytes
    {  123, 9, 13},   // positive same field
    {-32768, 0, 16},  // min 16-bit
    { 32767, 0, 16},  // max 16-bit
    {-42, 27, 8},     // byte-aligned but not at 0
    {-1, 0, 32},      // -1 signed int shifted by 0
    {2147483647, 0, 32},  // max 32-bit signed int shifted by 0
    {-2147483648, 0, 32}, // min 32-bit signed int shifted by 0
    {-1, 1, 32},          // -1 signed int shifted by 1
    {2147483647, 1, 32},  // max 32-bit signed int shifted by 1
    {-2147483648, 1, 32}, // min 32-bit signed int shifted by 1
    {-1, 2, 32},          // -1 signed int shifted by 2
    {2147483647, 2, 32},  // max 32-bit signed int shifted by 2
    {-2147483648, 2, 32}, // min 32-bit signed int shifted by 2
    {-1, 3, 32},          // -1 signed int shifted by 3
    {2147483647, 3, 32},  // max 32-bit signed int shifted by 3
    {-2147483648, 3, 32}, // min 32-bit signed int shifted by 3
    {-1, 4, 32},          // -1 signed int shifted by 4
    {2147483647, 4, 32},  // max 32-bit signed int shifted by 4
    {-2147483648, 4, 32}, // min 32-bit signed int shifted by 4
    {-1, 5, 32},          // -1 signed int shifted by 5
    {2147483647, 5, 32},  // max 32-bit signed int shifted by 5
    {-2147483648, 5, 32}, // min 32-bit signed int shifted by 5
    {-1, 6, 32},          // -1 signed int shifted by 6
    {2147483647, 6, 32},  // max 32-bit signed int shifted by 6
    {-2147483648, 6, 32}, // min 32-bit signed int shifted by 6
    {-1, 7, 32},          // -1 signed int shifted by 7
    {2147483647, 7, 32},  // max 32-bit signed int shifted by 7
    {-2147483648, 7, 32}, // min 32-bit signed int shifted by 7
    {-1, 8, 32},          // -1 signed int shifted by 8
    {2147483647, 8, 32},  // max 32-bit signed int shifted by 8
    {-2147483648, 8, 32}, // min 32-bit signed int shifted by 8
    {-1, 52, 32},          // -1 signed int shifted by 52
    {2147483647, 52, 32},  // max 32-bit signed int shifted by 52
    {-2147483648, 52, 32}, // min 32-bit signed int shifted by 52
    {-1, 53, 32},          // -1 signed int shifted by 53
    {2147483647, 53, 32},  // max 32-bit signed int shifted by 53
    {-2147483648, 53, 32}, // min 32-bit signed int shifted by 53
    {-1, 54, 32},          // -1 signed int shifted by 54
    {2147483647, 54, 32},  // max 32-bit signed int shifted by 54
    {-2147483648, 54, 32}, // min 32-bit signed int shifted by 54
    {-1, 55, 32},          // -1 signed int shifted by 55
    {2147483647, 55, 32},  // max 32-bit signed int shifted by 55
    {-2147483648, 55, 32}, // min 32-bit signed int shifted by 55
    {-1, 56, 32},          // -1 signed int shifted by 56
    {2147483647, 56, 32},  // max 32-bit signed int shifted by 56
    {-2147483648, 56, 32}, // min 32-bit signed int shifted by 56
    {-1, 57, 32},          // -1 signed int shifted by 57
    {2147483647, 57, 32},  // max 32-bit signed int shifted by 57
    {-2147483648, 57, 32}, // min 32-bit signed int shifted by 57
    {-1, 58, 32},          // -1 signed int shifted by 58
    {2147483647, 58, 32},  // max 32-bit signed int shifted by 58
    {-2147483648, 58, 32}, // min 32-bit signed int shifted by 58
    {-1, 59, 32},          // -1 signed int shifted by 59
    {2147483647, 59, 32},  // max 32-bit signed int shifted by 59
    {-2147483648, 59, 32}, // min 32-bit signed int shifted by 59
    {-1, 60, 32},          // -1 signed int shifted by 60
    {2147483647, 60, 32},  // max 32-bit signed int shifted by 60
    {-2147483648, 60, 32}, // min 32-bit signed int shifted by 60*/
  };

  for (size_t i=0;i<sizeof(scases)/sizeof(scases[0]);++i) {
    clear8(d);
    Util::encode_int(scases[i].v, d, 8, scases[i].sbit, scases[i].bits);
    Serial.println();
    Serial.print(F("SCase ")); Serial.print(i);
    Serial.print(F(": start=")); Serial.print(scases[i].sbit);
    Serial.print(F(" size="));   Serial.print(scases[i].bits);
    Serial.print(F(" data="));   print_hex(d, 8); Serial.println();

    int32_t got = Util::decode_int(d, 8, scases[i].sbit, scases[i].bits);

    // compute expected wrap for given width
    int32_t want;
    // if (scases[i].bits >= 32) {
      want = scases[i].v; // natural 32-bit 
    // } else {
      // uint32_t mask = (1UL<<scases[i].bits)-1UL;
      // uint32_t u = ((uint32_t)scases[i].v) & mask;
      // sign-extend back to 32
      // uint32_t sign = 1UL << (scases[i].bits-1);
      // if (u & sign) u |= ~mask;
      // want = (int32_t)u;
    // }
    checks("decode(signed)", (int32_t)want, (int32_t)got);
  }

  /*Serial.println(F("\n=== Near end-of-frame clamping ==="));
  // These write partially beyond 8*8 bits; only the in-range portion should persist.
  struct Edge { uint32_t v; size_t sbit; size_t bits; size_t expect_bits; };
  const Edge edges[] = {
    {0xAA, 60, 8, 8},     // exact last byte
    {0x3FF, 60, 10, 8},   // only 8 bits fit; expect low 8 bits
    {0x7,   63, 3, 1},    // only 1 bit fits at very end
  };
  for (size_t i=0;i<sizeof(edges)/sizeof(edges[0]);++i) {
    clear8(d);
    Util::encode_uint(edges[i].v, d, 8, edges[i].sbit, edges[i].bits);
    Serial.print(F("Edge ")); Serial.print(i);
    Serial.print(F(": start=")); Serial.print(edges[i].sbit);
    Serial.print(F(" size="));   Serial.print(edges[i].bits);
    Serial.print(F(" data="));   print_hex(d, 8); Serial.println();

    size_t fit = min(edges[i].bits, (size_t)(8*8 - edges[i].sbit));
    uint32_t got = Util::decode_uint(d, 8, edges[i].sbit, fit);
    uint32_t mask = (fit==32) ? 0xFFFFFFFFUL : ((fit? (1UL<<fit):0) - (fit?0:0)); // safe for fit==0
    uint32_t want = edges[i].v & mask;
    checku("  decode(end)", want, got);
  }

  Serial.println(F("\n=== PGN/CAN helpers quick sanity ==="));
  {
    const uint32_t pgn1 = 0x00F004; // PF2 (global), dp=0, pf=0xF0, ps ignored
    uint32_t id1 = Util::pgn_to_can_id(pgn1, 3, 0x81, 0xFF);
    uint32_t back1 = Util::can_id_to_pgn(id1);
    checkok(" PF2 roundtrip", back1 == pgn1);

    const uint32_t pgn2 = 0x000123; // PF1 (pdu1), dp=0, pf=0x01, ps=dest
    uint32_t id2 = Util::pgn_to_can_id(pgn2, 6, 0x81, 0x10);
    uint32_t back2 = Util::can_id_to_pgn(id2);
    uint8_t dest2  = Util::can_id_to_dest_addr(id2);
    checkok(" PF1 pgn roundtrip", back2 == (pgn2 & 0x1FF00));
    checkok(" PF1 dest extract",  dest2 == 0x10);
  }*/

  Serial.println(F("\n=== Done ==="));
}

void run_fuzz(unsigned iters=200) {
  uint8_t d[8];
  for (unsigned i=0;i<iters;i++) {
    clear8(d);
    size_t sbit = random(0, 64);
    size_t bits = random(1, 33);
    uint32_t mask = (bits==32) ? 0xFFFFFFFFUL : ((1UL<<bits)-1UL);
    uint32_t v = random(0, 0xFFFFFFFFUL) & mask;
    Util::encode_uint(v, d, 8, sbit, bits);
    size_t fit = (sbit >= 64) ? 0 : min(bits, 64 - sbit);
    uint32_t got = Util::decode_uint(d, 8, sbit, fit);
    if ((v & ((fit==32)?0xFFFFFFFFUL:((fit?(1UL<<fit):0)- (fit?0:0)))) != got) {
      Serial.println(F("FUZZ FAIL"));
      Serial.print(F(" start=")); Serial.print(sbit);
      Serial.print(F(" size="));  Serial.print(bits);
      Serial.print(F(" data="));  print_hex(d, 8); Serial.println();
      break;
    }
  }
  Serial.println(F("Fuzz done"));
}

// SG_ RELAY_STATE : 0|1@1+ (1,0) [0|1] "" MASTER_NODE
#define RELAY_STATE_off 0
#define RELAY_STATE_len 1
void write_RELAY_STATE(uint8_t n, uint8_t *data, size_t dlen) {
  Util::encode_uint(n, data, CAN_DLC, RELAY_STATE_off, RELAY_STATE_len);
}


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
