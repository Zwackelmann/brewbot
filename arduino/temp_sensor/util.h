#define  MSG_SIZE  8

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
  
  static uint8_t decode_uint8(uint8_t *data, size_t dlen, size_t bits);
  static uint32_t decode_uint32(uint8_t *data, size_t dlen, size_t bits);
  static int32_t decode_int32(uint8_t *data, size_t dlen, size_t bits);

  static void encode_uint8(uint8_t n, size_t bits, uint8_t *num);
  static void encode_uint32(uint32_t n, size_t bits, uint8_t *num);
  static void encode_int32(int32_t n, size_t bits, uint8_t *num);
  
  static void project(uint8_t *data, size_t dlen, uint8_t *num, size_t nlen, size_t off, size_t len);
  static void inject(uint8_t *data, size_t dlen, uint8_t *num, size_t nlen, size_t off, size_t len);
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


uint8_t Util::decode_uint8(uint8_t *data, size_t dlen, size_t bits) {
  size_t bits_in_type = 8;
  uint8_t max_uvalue = 0xFF;
  
  size_t n_bytes = (bits / 8) + (bits % 8 == 0 ? 0 : 1);

  uint8_t n = 0;
  for(size_t i=0; i<n_bytes; i++) {
    n |= ((uint8_t)(data[dlen-(i+1)]) << (i*8));
  }

  return n & (max_uvalue >> (bits_in_type - bits));
}


uint32_t Util::decode_uint32(uint8_t *data, size_t dlen, size_t bits) {
  size_t bits_in_type = 32;
  uint32_t max_uvalue = 0xFFFFFFFF;
  
  size_t n_bytes = (bits / 8) + (bits % 8 == 0 ? 0 : 1);

  uint32_t n = 0;
  for(size_t i=0; i<n_bytes; i++) {
    n |= ((uint8_t)(data[dlen-(i+1)]) << (i*8));
  }

  return n & (max_uvalue >> (bits_in_type - bits));
}


int32_t Util::decode_int32(uint8_t *data, size_t dlen, size_t bits) {
  size_t bits_in_type = 32;
  uint32_t max_unsigned_value = 0xFFFFFFFF;

  uint32_t u = decode_uint32(data, dlen, bits);
  if((u & (((uint32_t)(1)) << (bits - 1))) == 0) {
    // positive value => same represenation for signed and unsigned
    return (int32_t)(u);
  } else {
    // For negative values all leading bits exceeding `bits` need to become 1's.
    // E.g. to represent a negative 6 bit value with an 8 bit signed integer, the first 3 bits will be 1's (2 filling
    // up from 6 to 8 and 1 for negative sign) and the remaning 5 bits will be taken from the unsigned value.
    uint32_t neg_mask = (max_unsigned_value << (bits - 1));
    uint32_t num_mask = (bits == 1) ? 0 : (max_unsigned_value >> (bits_in_type - bits + 1));
    return (int32_t)(neg_mask | (u & num_mask));
  }
}


void Util::encode_uint8(uint8_t n, size_t bits, uint8_t *num) {
  size_t bits_in_type = 8;
  size_t n_bytes = (bits / 8) + (bits % 8 == 0 ? 0 : 1);

  for(size_t i=0; i<n_bytes; i++) {
    num[i] = n >> (8 * (n_bytes - 1 - i));
  }

  if(bits % 8 != 0) {
    uint8_t mask = 0xFF >> (8 - (bits % 8));
    num[0] = num[0] & mask;
  }
}


void Util::encode_uint32(uint32_t n, size_t bits, uint8_t *num) {
  size_t bits_in_type = 32;
  size_t n_bytes = (bits / 8) + (bits % 8 == 0 ? 0 : 1);

  for(size_t i=0; i<n_bytes; i++) {
    num[i] = n >> (8 * (n_bytes - 1 - i));
  }

  if(bits % 8 != 0) {
    uint8_t mask = 0xFF >> (8 - (bits % 8));
    num[0] = num[0] & mask;
  }
}


void Util::encode_int32(int32_t n, size_t bits, uint8_t *num) {
  size_t bits_in_type = 32;
  uint32_t max_unsigned_value = 0xFFFFFFFF;

  if(n < 0) {
    uint32_t num_mask = (bits == 1) ? 0 : (max_unsigned_value >> (bits_in_type - bits + 1));
    encode_uint32((uint32_t)(n & num_mask), bits, num);
    uint8_t neg_bit = (1) << ((bits - 1) % 8);
    num[0] = num[0] | neg_bit;
  } else {
    encode_uint32((uint32_t)(n), bits, num);
    uint32_t num_mask = (bits % 8 == 1) ? 0x00 : (0xFF >> ((((8 - bits) % 8) + 1) % 8));
    num[0] = num[0] & num_mask;
  }
}


void Util::array_shift(uint8_t *data, size_t dlen, int by) {
  if(dlen == 0 || by == 0) {
    return;
  }

  bool shift_right = by > 0;
  if(!shift_right) {
    by = -by;
  }

  int bytes = by/8;
  if(bytes != 0) {
    if(shift_right) {
      for(int i=0; i<dlen-bytes; i++) {
        data[dlen-1-i] = data[dlen-1-i-bytes];
      }

      for(int i=0; i<bytes; i++) {
        data[i] = 0x00;
      }
    } else {
      for(int i=0; i<dlen-bytes; i++) {
        data[i] = data[i+bytes];
      }

      for(int i=0; i<bytes; i++) {
        data[dlen-i-1] = 0x00;
      }
    }

    by = by % 8;
  }

  if(shift_right) {
    for(int i=dlen-1; i>0; i--) {
      data[i] = (data[i] >> by);
      data[i] = (data[i] | ((data[i-1] & (0xFF >> (8-by))) << (8-by)));
    }

    data[0] = (data[0] >> by);
  } else {
    for(int i=0; i<dlen-1; i++) {
      data[i] = (data[i] << by);
      data[i] = (data[i] | ((data[i+1] & (0xFF << (8-by))) >> (8-by)));
    }

    data[dlen-1] = (data[dlen-1] << by);
  }
}


void mask_vec(uint8_t *mask, size_t mlen, const size_t len, const size_t n_bytes) {
  for(int i=0; i<n_bytes; i++) {
    size_t hb = (len-1) / 8;
    int mb = static_cast<int>(n_bytes-hb-1);

    if(i < mb) {
      mask[i];
    } else if (i == mb) {
      mask[i] = 0xFF >> ((8 - (len % 8)) % 8);
    } else {
      mask[i] = 0xFF;
    }
  }
}


void Util::project(uint8_t *data, size_t dlen, uint8_t *num, size_t nlen, size_t off, size_t len) {
  const size_t lo = off;
  const size_t hi = off + len;

  const size_t r_bytes = ((hi-1)/8) - (off/8) + 1;
  const size_t w_bytes = (len/8) + (len%8 == 0 ? 0 : 1);

  for(size_t i=0; i<r_bytes; i++) {
    size_t d_idx = (off/8) + r_bytes - 1 - i;
    num[i] = data[d_idx];
  }

  uint8_t tail_mask = 0xFF >> ((8 - (hi % 8)) % 8);
  num[0] = num[0] & tail_mask;
  
  array_shift(num, nlen, lo%8);
}


void Util::inject(uint8_t *data, size_t dlen, uint8_t *num, size_t nlen, size_t off, size_t len) {
  const size_t n_bytes = ((off + len - 1) / 8) - (off / 8) + 1;

  size_t mlen = n_bytes;
  uint8_t mask[mlen];
  for(int i=0; i<mlen; i++) {
    mask[i] = 0x00;
  }

  mask_vec(mask, mlen, len, n_bytes);
  array_shift(mask, mlen, -(off%8));
  
  size_t slen = mlen;
  uint8_t shift[slen];
  for(int i=0; i<(mlen-nlen); i++) {
    shift[i] = 0x00;
  }
  for(int i=0; i<nlen; i++) {
    shift[(mlen-nlen)+i] = num[i];
  }
  array_shift(shift, slen, -(off%8));

  for(int i=0; i<dlen; i++) {
    if(i >= (off / 8) && i < (off / 8) + nlen) {
      int n_idx = ((off + len - 1) / 8) - i;
      data[i] = (data[i] & ~mask[n_idx]) | (shift[n_idx] & mask[n_idx]);
    }
  }
}
