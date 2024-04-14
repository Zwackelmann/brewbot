class Util {
public:
  static uint8_t pdu_format(const uint32_t pgn);
  static uint8_t is_pdu_format_1(const uint32_t pgn);
  static uint8_t is_pdu_format_2(const uint32_t pgn);
  static uint32_t pgn_to_can_id(const uint32_t pgn, const uint8_t priority, const uint8_t src_addr, const uint8_t dest_addr);

  static uint32_t can_id_to_pgn(const uint32_t can_id);
  static uint8_t can_id_to_src_addr(const uint32_t can_id);
  static uint8_t can_id_to_dest_addr(const uint32_t can_id);
  static uint8_t can_id_to_priority(const uint32_t can_id);
};

uint8_t Util::pdu_format(const uint32_t pgn) {
  return ((pgn >> 8) & 0xFF);
}

uint8_t Util::is_pdu_format_1(const uint32_t pgn) {
  return Util::pdu_format(pgn) < 0xF0;
}

uint8_t Util::is_pdu_format_2(const uint32_t pgn) {
  return Util::pdu_format(pgn) >= 0xF0;
}

uint32_t Util::pgn_to_can_id(const uint32_t pgn, const uint8_t priority, const uint8_t src_addr, const uint8_t dest_addr) {
  uint32_t pgn_encoded = pgn;
  if(Util::is_pdu_format_1(pgn)) {
    pgn_encoded |= (dest_addr & 0xFF);
  }

  uint8_t dp = (pgn_encoded >> 16) & 0x1;
  uint8_t pf = (pgn_encoded >> 8) & 0xFF;
  uint8_t ps = pgn_encoded & 0xFF;

  uint32_t can_id = 0;
  can_id |= ((uint32_t)(priority & 0x7)) << 26;
  can_id |= ((uint32_t)(dp & 0x1)) << 24;
  can_id |= ((uint32_t)(pf & 0xFF)) << 16;
  can_id |= ((uint32_t)(ps & 0xFF)) << 8;
  can_id |= ((uint32_t)(src_addr & 0xFF)) << 0;
  
  return can_id;
}

uint32_t Util::can_id_to_pgn(const uint32_t can_id) {
  uint32_t ps = (can_id >> 8) & 0xFF;
  uint32_t pf = (can_id >> 16) & 0xFF;
  uint32_t dp = (can_id >> 24) & 0x1;
  uint32_t priority = (can_id >> 26) & 0x7;

  uint32_t pgn = ps;
  pgn |= (pf << 8);
  pgn |= (dp << 16);

  uint32_t dest_addr;
  if(is_pdu_format_1(pgn)) {
    dest_addr = (pgn & 0xFF);
    pgn = (pgn & 0x1FF00);
  } else {
    dest_addr = 0x00;
  }

  return pgn;
}

uint8_t Util::can_id_to_src_addr(const uint32_t can_id) {
  return can_id & 0xFF;
}

uint8_t Util::can_id_to_dest_addr(const uint32_t can_id) {
  uint32_t pgn = (can_id >> 8) & 0x1FFFF;
  
  if(is_pdu_format_1(pgn)) {
    return pgn & 0xFF;
  } else {
    return 0x00;
  }
}

uint8_t Util::can_id_to_priority(const uint32_t can_id) {
  return (can_id >> 26) & 0x7;
}
