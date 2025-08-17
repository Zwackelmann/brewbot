#include <gtest/gtest.h>
#include <cstdint>
#include <cstring>
#include "util.h"


static inline void clear8(uint8_t *b) { std::memset(b, 0, 8); }

// ---------- Unsigned roundtrip ----------
struct UCase { uint32_t v; size_t sbit; size_t bits; };

class UnsignedRoundtrip : public ::testing::TestWithParam<UCase> {};

TEST_P(UnsignedRoundtrip, EncodeDecode) {
  auto p = GetParam();
  uint8_t d[8]; clear8(d);

  ASSERT_TRUE(J1939::encode_uint(p.v, d, 8, p.sbit, p.bits));
  const uint32_t got = J1939::decode_uint(d, 8, p.sbit, p.bits);
  const uint32_t mask = p.bits ? ((p.bits==32)?0xFFFFFFFFUL:((1UL<<p.bits)-1UL)) : 0UL;
  EXPECT_EQ(got, (p.v & mask));
}

INSTANTIATE_TEST_SUITE_P(
  Core, UnsignedRoundtrip,
  ::testing::Values(
    UCase{1,0,1},
    UCase{3,0,2},
    UCase{5,0,3},
    UCase{1,8,1},
    UCase{0xAA,8,8},
    UCase{0xABC,0,12},
    UCase{0x55,4,8},     // straddle
    UCase{0xDEADBEEF,0,32},
    UCase{0x7F,56,8},
    UCase{0xA5,3,8},
    UCase{0x123,7,12},
    UCase{0x7F,15,7},
    UCase{0xBEEF,0,16},
    UCase{0xC0FFEEu & 0xFFFF,16,16},
    UCase{1,31,1},
    UCase{3,30,2}
  )
);

// ---------- Signed roundtrip ----------
struct SCase { int32_t v; size_t sbit; size_t bits; };

class SignedRoundtrip : public ::testing::TestWithParam<SCase> {};

TEST_P(SignedRoundtrip, EncodeDecode) {
  auto p = GetParam();
  uint8_t d[8]; clear8(d);

  ASSERT_TRUE(J1939::encode_int(p.v, d, 8, p.sbit, p.bits));
  const int32_t got = J1939::decode_int(d, 8, p.sbit, p.bits);

  // expected = value wrapped to width (two's complement), then sign-extended to 32
  int32_t want;
  if (p.bits >= 32) {
    want = p.v;
  } else if (p.bits == 0) {
    want = 0;
  } else {
    const uint32_t mask = (1UL << p.bits) - 1UL;
    uint32_t u = ((uint32_t)p.v) & mask;
    const uint32_t sign = 1UL << (p.bits - 1);
    if (u & sign) u |= ~mask;
    want = (int32_t)u;
  }
  EXPECT_EQ(got, want);
}

INSTANTIATE_TEST_SUITE_P(
  Core, SignedRoundtrip,
  ::testing::Values(
    SCase{-1,0,1}, SCase{-5,0,4}, SCase{-5,5,5}, SCase{-123,9,13},
    SCase{ 123,9,13}, SCase{-32768,0,16}, SCase{32767,0,16},
    SCase{-42,27,8}, SCase{-1,0,32}, SCase{-1,56,8},
    SCase{0x7F,56,8}, SCase{-0x80,56,8}
  )
);

// ---------- Near end-of-frame clamping roundtrip ----------
struct ClampCase { uint32_t v; size_t sbit; size_t bits; };

class ClampRoundtrip : public ::testing::TestWithParam<ClampCase> {};

TEST_P(ClampRoundtrip, EncodeDecode) {
  auto p = GetParam();
  uint8_t d[8]; clear8(d);

  ASSERT_TRUE(J1939::encode_int(p.v, d, 8, p.sbit, p.bits));
  const int32_t got = J1939::decode_int(d, 8, p.sbit, p.bits);

  size_t fit = std::min(p.bits, (size_t)(8*8 - p.sbit));
  uint32_t mask = (fit == 0) ? 0UL : (fit == 32 ? 0xFFFFFFFFUL : ((1UL << fit) - 1UL));
  uint32_t want = p.v & mask;

  EXPECT_EQ(got, want);
}


INSTANTIATE_TEST_SUITE_P(
  Core, ClampRoundtrip,
  ::testing::Values(
    ClampCase{0xAA, 60, 8}, ClampCase{0x3FF, 60, 10}, ClampCase{0x7, 63, 3}
  )
);

// ---------- PGN/CAN helpers ----------
TEST(CANHelpers, Roundtrips) {
  const uint32_t pgn1 = 0x00F004; // PF2 global
  auto id1 = J1939::pgn_to_can_id(pgn1, 3, 0x81, 0xFF);
  EXPECT_EQ(J1939::can_id_to_pgn(id1), pgn1);

  const uint32_t pgn2 = 0x000123; // PF1, dest in PS
  auto id2 = J1939::pgn_to_can_id(pgn2, 6, 0x81, 0x10);
  EXPECT_EQ(J1939::can_id_to_pgn(id2), (pgn2 & 0x1FF00));
  EXPECT_EQ(J1939::can_id_to_dest_addr(id2), 0x10);
}


// ---------- Packed frame: case A (your exact spec) ----------
TEST(PackedFrame, CaseA) {
  uint8_t d[8]; clear8(d);

  // Fields:
  // - 6-bit  int   @0   : -7
  // - 6-bit  int   @6   : 13
  // - 2-bit  uint  @12  : 2
  // - 1-bit  uint  @14  : 1
  // - 1-bit  uint  @15  : 0
  // - 16-bit int   @16  : -12345
  // - 4-bit  int   @32  : -5
  // - 24-bit int   @36  : -54321
  ASSERT_TRUE(J1939::encode_int (-7,      d, 8,  0,  6));
  ASSERT_TRUE(J1939::encode_int (13,      d, 8,  6,  6));
  ASSERT_TRUE(J1939::encode_uint(2,       d, 8, 12,  2));
  ASSERT_TRUE(J1939::encode_uint(1,       d, 8, 14,  1));
  ASSERT_TRUE(J1939::encode_uint(0,       d, 8, 15,  1));
  ASSERT_TRUE(J1939::encode_int (-12345,  d, 8, 16, 16));
  ASSERT_TRUE(J1939::encode_int (-5,      d, 8, 32,  4));
  ASSERT_TRUE(J1939::encode_int (-54321,  d, 8, 36, 24));

  // Now decode & check
  EXPECT_EQ(J1939::decode_int (d, 8,  0,  6), -7);
  EXPECT_EQ(J1939::decode_int (d, 8,  6,  6), 13);
  EXPECT_EQ(J1939::decode_uint(d, 8, 12,  2), 2u);
  EXPECT_EQ(J1939::decode_uint(d, 8, 14,  1), 1u);
  EXPECT_EQ(J1939::decode_uint(d, 8, 15,  1), 0u);
  EXPECT_EQ(J1939::decode_int (d, 8, 16, 16), -12345);
  EXPECT_EQ(J1939::decode_int (d, 8, 32,  4), -5);
  EXPECT_EQ(J1939::decode_int (d, 8, 36, 24), -54321);
}


TEST(PackedFrame, CaseB) {
  uint8_t d[8]; clear8(d);

  // Layout (non-overlapping, spans 0..63):
  // - 1-bit  int   @0   : -1
  // - 11-bit uint  @1   : 0x7FF (max)
  // - 1-bit  uint  @12  : 0
  // - 5-bit  int   @13  : -8 (min)
  // - 16-bit uint  @18  : 0xFFFF (max)   (unsigned here deliberately)
  // - 7-bit  int   @34  : 63 (max +)
  // - 10-bit uint  @41  : 0x2AA
  // - 13-bit int   @51  : -1 (exactly to bit 63)
  ASSERT_TRUE(J1939::encode_int (-1,     d, 8,  0,  1));
  ASSERT_TRUE(J1939::encode_uint(0x7FF,  d, 8,  1, 11));
  ASSERT_TRUE(J1939::encode_uint(0,      d, 8, 12,  1));
  ASSERT_TRUE(J1939::encode_int (-8,     d, 8, 13,  5));
  ASSERT_TRUE(J1939::encode_uint(0xFFFF, d, 8, 18, 16));
  ASSERT_TRUE(J1939::encode_int (63,     d, 8, 34,  7));
  ASSERT_TRUE(J1939::encode_uint(0x2AA,  d, 8, 41, 10));
  ASSERT_TRUE(J1939::encode_int (-1,     d, 8, 51, 13));

  // Decode & check
  EXPECT_EQ(J1939::decode_int (d, 8,  0,  1), -1);
  EXPECT_EQ(J1939::decode_uint(d, 8,  1, 11), 0x7FFu);
  EXPECT_EQ(J1939::decode_uint(d, 8, 12,  1), 0u);
  EXPECT_EQ(J1939::decode_int (d, 8, 13,  5), -8);
  EXPECT_EQ(J1939::decode_uint(d, 8, 18, 16), 0xFFFFu);
  EXPECT_EQ(J1939::decode_int (d, 8, 34,  7), 63);
  EXPECT_EQ(J1939::decode_uint(d, 8, 41, 10), 0x2AAu);
  EXPECT_EQ(J1939::decode_int (d, 8, 51, 13), -1);
}


TEST(StringFrame, FullFrame) {
  uint8_t d[8];

  // full frame with pad bytes only
  {
    clear8(d);
    std::string s = "ABCDEFGH";
    ASSERT_TRUE(J1939::encode_str(s, d, 8,  0,  64, false, 0xFF));
    EXPECT_EQ(J1939::decode_str (d, 8,  0,  64, false, 0xFF), "ABCDEFGH");
  }

  // full frame with \0 terminated string
  {
    clear8(d);
    std::string s = "ABCDEFG";
    ASSERT_TRUE(J1939::encode_str(s, d, 8,  0,  64, true, 0xFF));
    EXPECT_EQ(J1939::decode_str (d, 8,  0,  64, true, 0xFF), "ABCDEFG");
  }
}


TEST(StringFrame, CropOverflow) {
  uint8_t d[8];

  // full frame with pad bytes only
  {
    clear8(d);
    std::string s = "ABCDEFGHI"; // 9 characters -> last one is dropped
    ASSERT_TRUE(J1939::encode_str(s, d, 8,  0,  64, false, 0xFF));
    EXPECT_EQ(J1939::decode_str (d, 8,  0,  64, false, 0xFF), "ABCDEFGH");
  }

  // full frame with \0 terminated string
  {
    clear8(d);
    std::string s = "ABCDEFGH"; // 8 characters -> last one is dropped
    ASSERT_TRUE(J1939::encode_str(s, d, 8,  0,  64, true, 0xFF));
    EXPECT_EQ(J1939::decode_str (d, 8,  0,  64, true, 0xFF), "ABCDEFG");
  }
}


TEST(StringFrame, HalfFrame) {
  uint8_t d[8];

  // full frame with pad bytes only
  {
    clear8(d);
    std::string s = "ABCD";
    ASSERT_TRUE(J1939::encode_str(s, d, 8,  0,  32, false, 0xFF));
    std::string s2 = "EFGH";
    ASSERT_TRUE(J1939::encode_str(s2, d, 8,  32,  32, false, 0xFF));

    EXPECT_EQ(J1939::decode_str (d, 8,  0,  32, false, 0xFF), "ABCD");
    EXPECT_EQ(J1939::decode_str (d, 8,  32,  32, false, 0xFF), "EFGH");
  }

  // full frame with \0 terminated string
  {
    clear8(d);
    std::string s = "ABC";
    ASSERT_TRUE(J1939::encode_str(s, d, 8,  0,  32, true, 0xFF));
    std::string s2 = "DEF";
    ASSERT_TRUE(J1939::encode_str(s2, d, 8,  32,  32, true, 0xFF));

    EXPECT_EQ(J1939::decode_str (d, 8,  0,  32, true, 0xFF), "ABC");
    EXPECT_EQ(J1939::decode_str (d, 8,  32,  32, true, 0xFF), "DEF");
  }
}


TEST(StringFrame, RejectHalfByteStrings) {
  uint8_t d[8];

  // reject string starting with offset 4
  {
    clear8(d);
    std::string s = "ABC";
    ASSERT_FALSE(J1939::encode_str(s, d, 8,  4,  32, false, 0xFF));
    EXPECT_EQ(J1939::decode_str (d, 8,  4,  32, false, 0xFF), "");
  }

  // reject string with signal size no multiple of 8
  {
    clear8(d);
    std::string s = "ABC"; // 8 characters -> last one is dropped
    ASSERT_FALSE(J1939::encode_str(s, d, 8,  0,  60, true, 0xFF));
    EXPECT_EQ(J1939::decode_str (d, 8,  0,  60, true, 0xFF), "");
  }
}


TEST(PackedFrame, CaseC) {
  uint8_t d[8]; clear8(d);

  // Layout (non-overlapping, spans 0..63):
  // - 1-bit  uint  @0   : 1
  // - 15-bit uint  @1   : 0x7FFF (max)
  // - 24-bit str   @16  : "ABC"
  // - 24-bit int   @40  : -8000
  ASSERT_TRUE(J1939::encode_uint(1,      d, 8,  0,  1));
  ASSERT_TRUE(J1939::encode_uint(0x7FFF, d, 8,  1, 15));
  std::string s = "ABC";
  ASSERT_TRUE(J1939::encode_str (s,      d, 8, 16, 24, false));
  ASSERT_TRUE(J1939::encode_int (-8000,  d, 8, 40, 24));

  // Decode & check
  EXPECT_EQ(J1939::decode_uint(d, 8,  0,  1), 1);
  EXPECT_EQ(J1939::decode_uint(d, 8,  1, 15), 0x7FFF);
  EXPECT_EQ(J1939::decode_str (d, 8, 16,  24, false), "ABC");
  EXPECT_EQ(J1939::decode_int (d, 8, 40,  24), -8000);
}


TEST(CanFrame, RelayCmdThroughJ1939) {
  RelayCmd relay;
  struct Spy { bool called=false; uint8_t on=0; } spy;
  relay.set_handler(
    [](uint8_t on, void* ctx){
      auto* s = static_cast<Spy*>(ctx);
      s->called = true; s->on = on;
    },
    &spy
  );

  J1939 bus;
  ASSERT_TRUE(bus.append_rx_msg<RelayCmd>(&relay, MASTER_ADDR, NODE_ADDR));

  can_frame f{};
  f.can_id  = J1939::pgn_to_can_id(RelayCmd::PGN, RelayCmd::PRIORITY, MASTER_ADDR, NODE_ADDR) | CAN_EFF_FLAG;
  f.can_dlc = RelayCmd::DLC;
  std::memset(f.data, 0, sizeof f.data);
  ASSERT_TRUE(RelayCmd::encode_signal_on(1, f.data));

  bus.process_frame(&f);

  EXPECT_TRUE(spy.called);
  EXPECT_EQ(spy.on, 1u);
}
