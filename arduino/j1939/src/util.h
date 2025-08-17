#ifndef J1939_UTIL_H
#define J1939_UTIL_H

#include "can.h"

/* generated */

#define NODE_INFO_PGN    0xFF00u
#define RELAY_STATE_PGN  0xFF11u


#define NODE_ADDR        0x81u
#define MASTER_ADDR      0x10u

class J1939 {
public:
  static constexpr uint8_t J1939_ANY = 0xFEu;  // not a real address
  static constexpr uint8_t J1939_BROADCAST = 0xFFu;
  static constexpr uint32_t CAN_EFF_ID_MASK = 0x1FFFFFFFu;  // 29 bit mask

  static constexpr size_t MAX_RX_MSG_DEFS = 8;

  // Adapter signature: function pointer + opaque ctx
  // using dispatch_fn_t = void (*)(const uint8_t* data, void* ctx);
  using dispatch_fn_t = void (*)(const uint8_t* data, void* msg_def);

  struct reg_item_t {
    uint32_t     pgn;
    size_t       dlc;
    uint8_t      src;     // J1939_ANY means "any"
    uint8_t      dest;    // J1939_ANY means "any"; J1939_BROADCAST is actual 0xFF
    // dispatch_fn_t fn;     // how to call the message object
    dispatch_fn_t fn;
    void*        msg_def;     // pointer to the message object
  };

  explicit J1939() : _n(0) {}

  #include "j1939_h.h"

  // Templated registration: adapts ANY message class that has
  //   static constexpr PGN, DLC
  //   void thunk_frame(const uint8_t*)
  template<typename MsgDefT>
  bool append_rx_msg(MsgDefT* msg_def, uint8_t src = J1939_ANY, uint8_t dest = J1939_ANY) {
    if (_n >= MAX_RX_MSG_DEFS || !msg_def) return false;
    _reg[_n++] = reg_item_t{
      MsgDefT::PGN,
      MsgDefT::DLC,
      src,
      dest,
      &J1939::thunk_frame_closure<MsgDefT>, 
      msg_def
    };
    return true;
  }

  void process_frame(const can_frame* frame) const;

private:
  template<typename MsgDefT>
  static void thunk_frame_closure(const uint8_t* data, void* msg_def) {
    static_cast<MsgDefT*>(msg_def)->thunk_frame(data);
  }

  reg_item_t _reg[MAX_RX_MSG_DEFS];
  uint8_t    _master, _node;
  size_t     _n;
};

void J1939::process_frame(const can_frame* frame) const {
  if (!frame) return;
  const uint32_t can_id = frame->can_id & CAN_EFF_ID_MASK;
  const uint32_t pgn    = J1939::can_id_to_pgn(can_id);
  const uint8_t  src    = J1939::can_id_to_src_addr(can_id);
  const uint8_t  dest   = J1939::can_id_to_dest_addr(can_id);

  for (size_t i=0; i<_n; ++i) {
    const reg_item_t& reg_msg = _reg[i];
    if (pgn == reg_msg.pgn &&
        (reg_msg.src  == J1939_ANY || src  == reg_msg.src) &&
        (reg_msg.dest == J1939_ANY || dest == reg_msg.dest) &&
        frame->can_dlc == reg_msg.dlc) {
      reg_msg.fn(frame->data, reg_msg.msg_def);
      break;
    }
  }
}

#include "j1939_i.h"

class RelayCmd {
public:
  using handler_t = void (*)(uint8_t on, void* ctx);

  static constexpr uint32_t PGN      = 0x1000u;
  static constexpr uint8_t  PRIORITY = 6u;
  static constexpr size_t   DLC      = 8;

  RelayCmd() : _handler(_handle_noop), _ctx(nullptr) {}

  static inline uint8_t decode_signal_on(const uint8_t *data) {
    return J1939::decode_uint(data, DLC, 0, 1);
  }
  static inline bool encode_signal_on(const uint8_t on, uint8_t *data) {
    return J1939::encode_uint(on, data, DLC, 0, 1);
  }

  void thunk_frame(const uint8_t *data) {
    const uint8_t on = decode_signal_on(data);
    _handler(on, _ctx);
  }

  void set_handler(handler_t h, void* ctx=nullptr) {
    _handler = h ? h : _handle_noop;
    _ctx = ctx;
  }

private:
  static void _handle_noop(uint8_t, void*) {}
  handler_t _handler;
  void* _ctx;
};

/* END generated */

#endif