
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

  static void array_shift(uint8_t *data, size_t dlen, int by);

  static uint32_t decode_uint(const uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size);
  static int32_t decode_int(const uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size);

  static bool encode_uint(uint32_t n, uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size);
  static bool encode_int(int32_t n, uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size);

  static void project(const uint8_t *data, size_t dlen, uint8_t *num, size_t nlen, size_t start_bit, size_t signal_size);
  static bool inject(uint8_t *data, size_t dlen, uint8_t *num, size_t nlen, size_t start_bit, size_t signal_size);
};


uint8_t Util::pdu_format(const uint32_t pgn) {
  return ((pgn >> 8) & 0xFFu);
}


uint8_t Util::is_pdu_format_1(const uint32_t pgn) {
  return Util::pdu_format(pgn) < 0xF0u;
}


uint8_t Util::is_pdu_format_2(const uint32_t pgn) {
  return Util::pdu_format(pgn) >= 0xF0u;
}


uint32_t Util::pgn_to_can_id(const uint32_t pgn, const uint8_t priority, const uint8_t src_addr, const uint8_t dest_addr) {
  uint32_t pgn_encoded = pgn;
  if(Util::is_pdu_format_1(pgn)) {
    pgn_encoded &= 0xFF00u;  // clear dest_addr part
    pgn_encoded |= (dest_addr & 0xFFu);
  }

  uint8_t dp = (pgn_encoded >> 16) & 0x1u;
  uint8_t pf = (pgn_encoded >> 8) & 0xFFu;
  uint8_t ps = pgn_encoded & 0xFFu;

  uint32_t can_id = 0;
  can_id |= ((uint32_t)(priority & 0x7u)) << 26;
  can_id |= ((uint32_t)(dp & 0x1u)) << 24;
  can_id |= ((uint32_t)(pf & 0xFFu)) << 16;
  can_id |= ((uint32_t)(ps & 0xFFu)) << 8;
  can_id |= ((uint32_t)(src_addr & 0xFFu)) << 0;

  return can_id;
}


uint32_t Util::can_id_to_pgn(const uint32_t can_id) {
  uint32_t ps = (can_id >> 8) & 0xFFu;
  uint32_t pf = (can_id >> 16) & 0xFFu;
  uint32_t dp = (can_id >> 24) & 0x1u;

  uint32_t pgn = ps;
  pgn |= (pf << 8);
  pgn |= (dp << 16);

  if(is_pdu_format_1(pgn)) {
    pgn = (pgn & 0x1FF00u);
  }

  return pgn;
}


uint8_t Util::can_id_to_src_addr(const uint32_t can_id) {
  return can_id & 0xFFu;
}


uint8_t Util::can_id_to_dest_addr(const uint32_t can_id) {
  uint32_t pgn = (can_id >> 8) & 0x1FFFFu;

  if(is_pdu_format_1(pgn)) {
    return pgn & 0xFFu;
  } else {
    return 0xFFu;
  }
}


uint8_t Util::can_id_to_priority(const uint32_t can_id) {
  return (can_id >> 26) & 0x7u;
}


uint32_t Util::decode_uint(const uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size) {
  size_t r_bytes = ((start_bit + signal_size - 1) / 8) - (start_bit / 8) + 1;
  if(r_bytes > 5) r_bytes = 5;

  uint8_t num[5] = {0};  // up to 32 bits
  project(data, dlen, num, r_bytes, start_bit, signal_size);

  uint32_t v = 0;
  for (size_t i=0; i<r_bytes; ++i) {
    v = (v << 8) | num[i];
  }

  if (signal_size < 32) {
    const uint32_t mask = (signal_size == 32) ? 0xFFFFFFFFUL : ((1UL << signal_size) - 1UL);
    v &= mask;
  }

  return v;
}


int32_t Util::decode_int(const uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size) {
  uint32_t u = decode_uint(data, dlen, start_bit, signal_size);

  if (signal_size == 0) {
    return 0;
  } else if(signal_size < 32) {
    const uint32_t sign_mask = 1UL << (signal_size - 1);
    if (u & sign_mask) {
      // sign-extend
      const uint32_t ext = ~((1UL << signal_size) - 1UL);
      u |= ext;
    }
  }
  return (int32_t)u;
}


bool Util::encode_uint(uint32_t n, uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size) {
  const size_t n_bytes = min((signal_size + 7) / 8, 4);
  uint8_t num[4] = {0};

  // MSB-first packing into num[]
  for(size_t i=0; i<n_bytes; ++i) {
    const size_t shift = 8 * (n_bytes - 1 - i);
    num[i] = (uint8_t)((n >> shift) & 0xFFu);
  }

  return Util::inject(data, dlen, num, n_bytes, start_bit, signal_size);
}


bool Util::encode_int(int32_t n, uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size) {
  uint32_t u;
  if (signal_size == 0) {
    return;
  } else if (signal_size >= 32) {
    u = (uint32_t)n;  // natural two's complement
  } else {
    const uint32_t mask = (1UL << signal_size) - 1UL;
    u = ((uint32_t)n) & mask;
  }
  
  return encode_uint(u, data, dlen, start_bit, signal_size);
}


void Util::array_shift(uint8_t *data, size_t dlen, int by) {
  if(dlen == 0 || by == 0) {
    return;
  }

  bool shift_right = by > 0;
  if(!shift_right) {
    by = -by;
  }

  if (by >= dlen * 8) {
    memset(data, 0, dlen);
    return;
  }

  int by_bytes = by/8;
  int by_bits = by%8;

  if(by_bytes != 0) {
    if(shift_right) {
      for(int i=0; i<dlen-by_bytes; i++) {
        data[dlen-1-i] = data[dlen-1-i-by_bytes];
      }

      for(int i=0; i<by_bytes; i++) {
        data[i] = 0x00u;
      }
    } else {
      for(int i=0; i<dlen-by_bytes; i++) {
        data[i] = data[i+by_bytes];
      }

      for(int i=0; i<by_bytes; i++) {
        data[dlen-i-1] = 0x00u;
      }
    }
  }

  if(by_bits != 0) {
    if(shift_right) {
      for(int i=dlen-1; i>0; i--) {
        data[i] = (data[i] >> by_bits);
        data[i] = (data[i] | ((data[i-1] & (0xFFu >> (8-by_bits))) << (8-by_bits)));
      }

      data[0] = (data[0] >> by_bits);
    } else {
      for(int i=0; i<dlen-1; i++) {
        data[i] = (data[i] << by_bits);
        data[i] = (data[i] | ((data[i+1] & (0xFFu << (8-by_bits))) >> (8-by_bits)));
      }

      data[dlen-1] = (data[dlen-1] << by_bits);
    }
  }
}


void signal_mask_vec(uint8_t *mask, size_t mlen, const size_t signal_size, const size_t n_bytes) {
  for(int i=0; i<n_bytes; i++) {
    size_t hb = (signal_size-1) / 8;
    int mb = static_cast<int>(n_bytes-hb-1);

    if(i < mb) {
      mask[i] = 0x00u;
    } else if (i == mb) {
      mask[i] = 0xFFu >> ((8 - (signal_size % 8)) % 8);
    } else {
      mask[i] = 0xFFu;
    }
  }
}

void Util::project(const uint8_t *data, size_t dlen, uint8_t *num, size_t nlen, size_t start_bit, size_t signal_size) {
  const size_t lo = start_bit;
  const size_t hi = start_bit + signal_size;

  const size_t r_bytes = ((hi-1)/8) - (start_bit / 8) + 1;
  const size_t w_bytes = (signal_size / 8) + (signal_size % 8 == 0 ? 0 : 1);

  for(size_t i=0; i<r_bytes; i++) {
    size_t d_idx = (start_bit / 8) + r_bytes - 1 - i;
    num[i] = data[d_idx];
  }

  uint8_t tail_mask = 0xFF >> ((8 - (hi % 8)) % 8);
  num[0] = num[0] & tail_mask;
  array_shift(num, nlen, lo%8);
}


bool Util::inject(uint8_t *data, size_t dlen, uint8_t *num, size_t nlen, size_t start_bit, size_t signal_size) {
  if (signal_size == 0 || nlen == 0) return false;

  const size_t n_bytes = ((start_bit + signal_size - 1) / 8) - (start_bit / 8) + 1;

  uint8_t mask[8] = {0};
  uint8_t shift[8] = {0};

  signal_mask_vec(mask, n_bytes, signal_size, n_bytes);
  array_shift(mask, n_bytes, -(int)(start_bit % 8));

  const size_t pad = (n_bytes > nlen) ? (n_bytes - nlen) : 0;
  for (size_t i = 0; i < n_bytes; ++i) {
    shift[i] = (i < pad) ? 0 : num[i - pad];
  }
  array_shift(shift, n_bytes, -(int)(start_bit % 8));

  const size_t first = start_bit / 8;
  for (size_t i = 0; i < n_bytes; ++i) {
    const size_t di = first + i;
    if (di >= dlen) break;
    const size_t n_idx = n_bytes - 1 - i;
    data[di] = (uint8_t)((data[di] & (uint8_t)~mask[n_idx]) | (shift[n_idx] & mask[n_idx]));
  }

  return true;
}
