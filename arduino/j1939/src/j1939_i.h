uint8_t J1939::pdu_format(const uint32_t pgn) {
  return ((pgn >> 8) & 0xFFu);
}


uint8_t J1939::is_pdu_format_1(const uint32_t pgn) {
  return J1939::pdu_format(pgn) < 0xF0u;
}


uint8_t J1939::is_pdu_format_2(const uint32_t pgn) {
  return J1939::pdu_format(pgn) >= 0xF0u;
}


uint32_t J1939::pgn_to_can_id(const uint32_t pgn, const uint8_t priority, const uint8_t src_addr, const uint8_t dest_addr) {
  uint32_t pgn_encoded = pgn;
  if(J1939::is_pdu_format_1(pgn)) {
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


uint32_t J1939::can_id_to_pgn(const uint32_t can_id) {
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


uint8_t J1939::can_id_to_src_addr(const uint32_t can_id) {
  return can_id & 0xFFu;
}


uint8_t J1939::can_id_to_dest_addr(const uint32_t can_id) {
  uint32_t pgn = (can_id >> 8) & 0x1FFFFu;

  if(is_pdu_format_1(pgn)) {
    return pgn & 0xFFu;
  } else {
    return 0xFFu;
  }
}


uint8_t J1939::can_id_to_priority(const uint32_t can_id) {
  return (can_id >> 26) & 0x7u;
}


bool J1939::encode_uint(uint32_t n, uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size) {
  size_t n_bytes = (signal_size + 7) / 8;
  if (n_bytes > 4) n_bytes = 4;

  uint8_t num[4] = {0};

  // MSB-first packing into num[]
  for(size_t i=0; i<n_bytes; ++i) {
    const size_t shift = 8 * (n_bytes - 1 - i);
    num[i] = (uint8_t)((n >> shift) & 0xFFu);
  }

  return J1939::inject(data, dlen, num, n_bytes, start_bit, signal_size);
}


bool J1939::encode_int(int32_t n, uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size) {
  uint32_t u;
  if (signal_size == 0) {
    return false;
  } else if (signal_size >= 32) {
    u = (uint32_t)n;  // natural two's complement
  } else {
    const uint32_t mask = (1UL << signal_size) - 1UL;
    u = ((uint32_t)n) & mask;
  }

  return encode_uint(u, data, dlen, start_bit, signal_size);
}


bool J1939::encode_str(std::string& s, uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size, bool zero_terminate, uint8_t pad_byte) {
  // enforce byte-aligned strings
  if ((signal_size == 0) || (start_bit % 8) || (signal_size % 8)) return false;

  const size_t field_bytes = signal_size / 8;
  if (field_bytes == 0 || field_bytes > 8) return false;

  // strict write policy: refuse if it would spill
  if (start_bit + signal_size > dlen * 8) return false;

  uint8_t tmp[8];

  for (size_t i=0; i<field_bytes; ++i) tmp[i] = pad_byte;

  if (zero_terminate) {
    // leave room for '\0'
    const size_t to_copy = (s.size() < (field_bytes - 1)) ? s.size() : (field_bytes - 1);
    for (size_t i=0; i<to_copy; ++i) tmp[i] = (uint8_t)s[i];
    tmp[to_copy] = 0x00;
  } else {
    const size_t to_copy = (s.size() < field_bytes) ? s.size() : field_bytes;
    for (size_t i=0; i<to_copy; ++i) tmp[i] = (uint8_t)s[i];
    // rest already padded with pad_byte
  }

  // inject whole field
  return J1939::inject(data, dlen, tmp, field_bytes, start_bit, signal_size);
}


uint32_t J1939::decode_uint(const uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size) {
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


int32_t J1939::decode_int(const uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size) {
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


std::string J1939::decode_str(const uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size, bool stop_at_zero, uint8_t pad_byte) {
  // enforce byte-aligned strings
  if ((signal_size == 0) || (start_bit % 8) || (signal_size % 8)) return std::string();

  const size_t field_bytes = signal_size / 8;
  if (field_bytes == 0 || field_bytes > 8) return std::string();

  uint8_t tmp[8] = {0};
  J1939::project(data, dlen, tmp, field_bytes, start_bit, signal_size);

  // Build string
  if (stop_at_zero) {
    // stop at first NUL
    size_t n = 0;
    while (n < field_bytes && tmp[n] != 0x00) ++n;
    return std::string(reinterpret_cast<const char*>(tmp), n);
  } else {
    // trim trailing pad bytes
    size_t n = field_bytes;
    while (n > 0 && tmp[n-1] == pad_byte) --n;
    return std::string(reinterpret_cast<const char*>(tmp), n);
  }
}


void J1939::array_shift(uint8_t *data, size_t dlen, int by) {
  if(dlen == 0 || by == 0) {
    return;
  }

  bool shift_right = by > 0;
  if(!shift_right) {
    by = -by;
  }

  if (by >= (int)(dlen * 8)) {
    memset(data, 0, dlen);
    return;
  }

  size_t by_bytes = by/8;
  size_t by_bits = by%8;

  if(by_bytes != 0) {
    if(shift_right) {
      for(size_t i=0; i<dlen-by_bytes; ++i) {
        data[dlen-1-i] = data[dlen-1-i-by_bytes];
      }

      for(size_t i=0; i<by_bytes; ++i) {
        data[i] = 0x00u;
      }
    } else {
      for(size_t i=0; i<dlen-by_bytes; ++i) {
        data[i] = data[i+by_bytes];
      }

      for(size_t i=0; i<by_bytes; ++i) {
        data[dlen-i-1] = 0x00u;
      }
    }
  }

  if(by_bits != 0) {
    if(shift_right) {
      for(size_t i=dlen-1; i>0; --i) {
        data[i] = (data[i] >> by_bits);
        data[i] = (data[i] | ((data[i-1] & (0xFFu >> (8-by_bits))) << (8-by_bits)));
      }

      data[0] = (data[0] >> by_bits);
    } else {
      for(size_t i=0; i<dlen-1; ++i) {
        data[i] = (data[i] << by_bits);
        data[i] = (data[i] | ((data[i+1] & (0xFFu << (8-by_bits))) >> (8-by_bits)));
      }

      data[dlen-1] = (data[dlen-1] << by_bits);
    }
  }
}


void inject_mask(uint8_t *mask, const size_t signal_size, const size_t n_bytes) {
  for(size_t i=0; i<n_bytes; ++i) {
    size_t hb = (signal_size-1) / 8;
    size_t mb = static_cast<size_t>(n_bytes-hb-1);

    if(i < mb) {
      mask[i] = 0x00u;
    } else if (i == mb) {
      mask[i] = 0xFFu >> ((8 - (signal_size % 8)) % 8);
    } else {
      mask[i] = 0xFFu;
    }
  }
}


bool J1939::inject(uint8_t *data, size_t dlen, uint8_t *num, size_t nlen, size_t start_bit, size_t signal_size) {
  if (signal_size == 0 || nlen == 0) return false;

  const size_t n_bytes = ((start_bit + signal_size - 1) / 8) - (start_bit / 8) + 1;

  uint8_t mask[9] = {0};
  uint8_t shift[9] = {0};

  inject_mask(mask, signal_size, n_bytes);
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


void J1939::project(const uint8_t *data, size_t dlen, uint8_t *num, size_t nlen, size_t start_bit, size_t signal_size) {
  const size_t lo = start_bit;
  const size_t hi = start_bit + signal_size;

  const size_t r_bytes = ((hi-1)/8) - (start_bit / 8) + 1;

  for(size_t i=0; i<r_bytes; i++) {
    size_t d_idx = (start_bit / 8) + r_bytes - 1 - i;
    if (d_idx < dlen) {
      num[i] = data[d_idx];
    }
  }

  uint8_t tail_mask = 0xFF >> ((8 - (hi % 8)) % 8);
  num[0] = num[0] & tail_mask;
  array_shift(num, nlen, lo%8);
}