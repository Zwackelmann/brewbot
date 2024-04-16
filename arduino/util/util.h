#ifndef SPEEDBOAT_UTIL_UTIL
#define SPEEDBOAT_UTIL_UTIL

#include <vector>
#include <iostream>
#include <string>
#include <stdexcept>
#include <sstream>
#include <limits>
#include <fmt/core.h>
#include <json/json.h>
#include <fstream>
#include <tuple>
#include <chrono>
#include <optional>
#include <algorithm>


class Util {

public:
   /**
    * Shifts binary data encoded as uint8_t vector as if it was one continuous bit mask
    *
    * \param data Data vector to be shifted
    * \param by Number of bits to shift the data array. Negative values shift to the left and positive values to the right
    */
   static void array_shift(std::vector<uint8_t>& data, int by);

   /**
    * Projects the data to a given slice
    *
    * \param data Data
    * \param off Offset
    * \param len Length
    * \return Data vector projected to given slice
    */
   static const std::vector<uint8_t> project(const std::vector<uint8_t>& data, size_t off, size_t len);
   static const std::vector<uint8_t> inject(const std::vector<uint8_t>& data, const std::vector<uint8_t>& n_vec, size_t off, size_t len);

   template<typename uint_t>
   static uint_t decode_uint(const std::vector<uint8_t>& data, size_t bits) {
     constexpr size_t bits_in_type = 8 * sizeof(uint_t);
     constexpr uint_t max_uvalue = std::numeric_limits<uint_t>::max();
     size_t n_bytes = (bits / 8) + (bits % 8 == 0 ? 0 : 1);

     if(bits < 1 || bits > bits_in_type) {
       throw std::runtime_error(fmt::format("bits must be between 1 and {}", bits_in_type));
     }

     if(data.size() < n_bytes) {
       throw std::runtime_error(fmt::format("too few data to decode uint{}", bits_in_type));
     }

     uint_t n = 0;
     for(size_t i=0; i<n_bytes; i++) {
       n |= (static_cast<uint_t>(data[data.size()-(i+1)]) << (i*8));
     }

     return n & (max_uvalue >> (bits_in_type - bits));
   }

   template<typename uint_t>
   static const std::vector<uint8_t> encode_uint(uint_t n, size_t bits) {
     constexpr size_t bits_in_type = 8 * sizeof(uint_t);
     size_t n_bytes = (bits / 8) + (bits % 8 == 0 ? 0 : 1);

     if(bits < 1 || bits > bits_in_type) {
       throw std::runtime_error(fmt::format("bits must be between 1 and {}", bits_in_type));
     }

     std::vector<uint8_t> data(n_bytes, 0x00);
     for(size_t i=0; i<n_bytes; i++) {
       data[i] = n >> (8 * (n_bytes - 1 - i));
     }

     if(bits % 8 != 0) {
       uint8_t mask = 0xFF >> (8 - (bits % 8));
       data[0] = data[0] & mask;
     }

     return data;
   }

   template<typename sint_t>
   static sint_t decode_int(const std::vector<uint8_t>& data, size_t bits) {
     using uint_t = typename std::make_unsigned<sint_t>::type;

     constexpr size_t bits_in_type = 8 * sizeof(sint_t);
     constexpr uint_t max_unsigned_value = std::numeric_limits<uint_t>::max();

     uint_t u = Util::decode_uint<uint_t>(data, bits);
     if((u & (static_cast<uint_t>(1) << (bits - 1))) == 0) {
       // positive value => same represenation for signed and unsigned
       return static_cast<sint_t>(u);
     } else {
       // For negative values all leading bits exceeding `bits` need to become 1's.
       // E.g. to represent a negative 6 bit value with an 8 bit signed integer, the first 3 bits will be 1's (2 filling
       // up from 6 to 8 and 1 for negative sign) and the remaning 5 bits will be taken from the unsigned value.
       uint_t neg_mask = (max_unsigned_value << (bits - 1));
       uint_t num_mask = (bits == 1) ? 0 : (max_unsigned_value >> (bits_in_type - bits + 1));
       return static_cast<sint_t>(neg_mask | (u & num_mask));
     }
   }

   template<typename sint_t>
   static const std::vector<uint8_t> encode_int(sint_t n, size_t bits) {
     using uint_t = typename std::make_unsigned<sint_t>::type;
     constexpr size_t bits_in_type = 8 * sizeof(sint_t);
     constexpr uint_t max_unsigned_value = std::numeric_limits<uint_t>::max();

     if(n < 0) {
       uint_t num_mask = (bits == 1) ? 0 : (max_unsigned_value >> (bits_in_type - bits + 1));
       std::vector<uint8_t> data = Util::encode_uint<uint_t>(static_cast<uint_t>(n & num_mask), bits);
       uint8_t neg_bit = (1) << ((bits - 1) % 8);
       data[0] = data[0] | neg_bit;
       return data;
     } else {
       std::vector<uint8_t> data = Util::encode_uint<uint_t>(static_cast<uint_t>(n), bits);
       uint_t num_mask = (bits % 8 == 1) ? 0x00 : (0xFF >> ((((8 - bits) % 8) + 1) % 8));
       data[0] = data[0] & num_mask;
       return data;
     }
   }

   static double decode_double(const std::vector<uint8_t>& data, size_t bits, bool sig=true);
   static const std::vector<uint8_t> encode_double(double d, size_t bits, bool sig=true);

   static const std::string hex_str(const std::vector<uint8_t>& data);
   static const std::string join(const std::vector<std::string>& buf, const std::string& delimiter);

   static double median(const std::vector<double>& values);

   static const Json::Value load_json(const std::string& file_path);
   static const Json::Value json_reads(const std::string json_string);
   static const std::string json_dumps(const Json::Value val);

   static uint8_t pdu_format(const uint32_t pgn);
   static uint8_t is_pdu_format_1(const uint32_t pgn);
   static uint8_t is_pdu_format_2(const uint32_t pgn);

   static std::tuple<uint32_t, uint8_t, uint8_t, uint8_t> can_id_to_pgn(const uint32_t can_id);
   static uint32_t pgn_to_can_id(const uint32_t pgn, const uint8_t priority, const uint8_t src_addr, const uint8_t dest_addr);
   static uint32_t pgn_to_can_id(const uint32_t pgn, const uint8_t priority, const uint8_t src_addr);

   static std::chrono::system_clock::time_point system_zero;
   static void set_system_zero();
   static uint64_t millis();
   static int tm_gmtoff();
   static std::chrono::system_clock::time_point create_time_point(int year, int month, int day, int hour, int minute, int second);
   static const std::vector<uint8_t> obc_time_data(std::chrono::system_clock::time_point t);

   static const std::optional<std::string> read_mod_status(const std::string& path);
};

#endif /* SPEEDBOAT_UTIL_UTIL */