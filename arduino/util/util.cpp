#include <speedboat/util/util.h>


void Util::array_shift(std::vector<uint8_t>& data, int by) {
  if(data.size() == 0 || by == 0) {
    return;
  }

  bool shift_right = by > 0;
  if(!shift_right) {
    by = -by;
  }

  int bytes = by/8;
  if(bytes != 0) {
    if(shift_right) {
      for(int i=0; i<data.size()-bytes; i++) {
        data[data.size()-1-i] = data[data.size()-1-i-bytes];
      }

      for(int i=0; i<bytes; i++) {
        data[i] = 0x00;
      }
    } else {
      for(int i=0; i<data.size()-bytes; i++) {
        data[i] = data[i+bytes];
      }

      for(int i=0; i<bytes; i++) {
        data[data.size()-i-1] = 0x00;
      }
    }

    by = by % 8;
  }

  if(shift_right) {
    for(int i=data.size()-1; i>0; i--) {
      data[i] = (data[i] >> by);
      data[i] = (data[i] | ((data[i-1] & (0xFF >> (8-by))) << (8-by)));
    }

    data[0] = (data[0] >> by);
  } else {
    for(int i=0; i<data.size()-1; i++) {
      data[i] = (data[i] << by);
      data[i] = (data[i] | ((data[i+1] & (0xFF << (8-by))) >> (8-by)));
    }

    data[data.size()-1] = (data[data.size()-1] << by);
  }
}

std::vector<uint8_t> mask_vec(const size_t len, const size_t n_bytes) {
  std::vector<uint8_t> mask;

  for(int i=0; i<n_bytes; i++) {
    size_t hb = (len-1) / 8;
    int mb = static_cast<int>(n_bytes-hb-1);

    if(i < mb) {
      mask.push_back(0x00);
    } else if (i == mb) {
      mask.push_back(0xFF >> ((8 - (len % 8)) % 8));
    } else {
      mask.push_back(0xFF);
    }
  }

  return mask;
}

const std::vector<uint8_t> Util::project(const std::vector<uint8_t>& data, size_t off, size_t len) {
  const size_t lo = off;
  const size_t hi = off + len;

  const size_t r_bytes = ((hi-1)/8) - (off/8) + 1;
  const size_t w_bytes = (len/8) + (len%8 != 0 ? 1 : 0);

  std::vector<uint8_t> dat;
  for(size_t i=0; i<r_bytes; i++) {
    size_t d_idx = (off/8) + r_bytes - 1 - i;
    dat.push_back(data[d_idx]);
  }

  uint8_t tail_mask = 0xFF >> ((8 - (hi % 8)) % 8);
  dat[0] = dat[0] & tail_mask;
  array_shift(dat, lo%8);

  while(dat.size() > w_bytes) {
    dat.erase(dat.begin());
  }

  return dat;
}


const std::vector<uint8_t> Util::inject(const std::vector<uint8_t>& data, const std::vector<uint8_t>& n_vec, size_t off, size_t len) {
  const size_t n_bytes = ((off + len - 1) / 8) - (off / 8) + 1;

  std::vector<uint8_t> n_mask = mask_vec(len, n_bytes);
  Util::array_shift(n_mask, -(off%8));

  std::vector<uint8_t> n_vec_shift(n_mask.size()-n_vec.size(), 0x00);
  for(uint8_t n : n_vec) {
    n_vec_shift.push_back(n);
  }
  Util::array_shift(n_vec_shift, -(off%8));

  std::vector<uint8_t> res;
  for(int i=0; i<data.size(); i++) {
    if(i >= (off / 8) && i < (off / 8) + n_mask.size()) {
      int n_idx = ((off + len - 1) / 8) - i;
      res.push_back((data[i] & ~n_mask[n_idx]) | (n_vec_shift[n_idx] & n_mask[n_idx]));
    } else {
      res.push_back(data[i]);
    }
  }

  return res;
}

double Util::decode_double(const std::vector<uint8_t>& data, size_t bits, bool sig) {
  if(bits < 1 || bits > 64) {
    throw std::runtime_error("bits must be between 1 and 64");
  } else if(bits <= 8 && sig) {
    return static_cast<double>(Util::decode_int<int8_t>(data, bits));
  } else if(bits <= 8 && !sig) {
    return static_cast<double>(Util::decode_uint<uint8_t>(data, bits));
  } else if(bits <= 16 && sig) {
    return static_cast<double>(Util::decode_int<int16_t>(data, bits));
  } else if(bits <= 16 && !sig) {
    return static_cast<double>(Util::decode_uint<uint16_t>(data, bits));
  } else if(bits <= 32 && sig) {
    return static_cast<double>(Util::decode_int<int32_t>(data, bits));
  } else if(bits <= 32 && !sig) {
    return static_cast<double>(Util::decode_uint<uint32_t>(data, bits));
  } else if(bits <= 64 && sig) {
    return static_cast<double>(Util::decode_int<int64_t>(data, bits));
  } else if(bits <= 64 && !sig) {
    return static_cast<double>(Util::decode_uint<uint64_t>(data, bits));
  } else {
    throw std::runtime_error("Unexpected bit length");
  }
}

const std::vector<uint8_t> Util::encode_double(double d, size_t bits, bool sig) {
  if(bits < 1 || bits > 53) {
    // Excact conversion from double to int only possible for < 53 bits
    throw std::runtime_error("bits must be between 1 and 53");
  } else if(!sig) {
    if(d < 0 || d > (std::numeric_limits<uint64_t>::max() >> (64 - bits))) {
      throw std::runtime_error(fmt::format("Value out of bounds for {} bit unsigned int", bits));
    } else {
      return encode_uint(static_cast<uint64_t>(d), bits);
    }
  } else {
    if(d < (std::numeric_limits<int64_t>::min() >> (64 - bits)) || d > (std::numeric_limits<int64_t>::max() >> (64 - bits))) {
      throw std::runtime_error(fmt::format("Value out of bounds for {} bit int", bits));
    } else {
      return encode_int(static_cast<int64_t>(d), bits);
    }
  }
}


const std::string Util::hex_str(const std::vector<uint8_t>& data) {
  const std::vector<char> hex_digits({'0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F'});
  std::vector<char> out;

  for(uint8_t byte : data) {
    out.push_back(hex_digits[byte >> 4]);
    out.push_back(hex_digits[byte & 0x0F]);
    out.push_back(' ');
  }

  if(out.size() > 0) {
    out.pop_back();
  }

  return std::string(out.begin(), out.end());
}


const std::string Util::join(const std::vector<std::string>& buf, const std::string& delimiter) {
  std::ostringstream result;

  for(size_t i=0; i<buf.size(); i++) {
    result << buf[i];
    if (i < buf.size() - 1) {
      result << delimiter;
    }
  }

  return result.str();
}

double Util::median(const std::vector<double>& values) {
  if(values.size() == 0) {
    throw std::runtime_error("cannot get median from empty values");
  } else {
    std::vector<double> values_sorted(values.begin(), values.end());
    std::sort(values_sorted.begin(), values_sorted.end());
    if (values.size() % 2 == 0) {
      return (values_sorted[(values.size()/2)-1] + values_sorted[values.size()/2])/2;
    } else {
      return values_sorted[values.size()/2];
    }
  }
}

const Json::Value Util::load_json(const std::string& file_path) {
  std::ifstream fileInput(file_path);
  Json::CharReaderBuilder reader;
  Json::Value parsed;
  std::string errs;
  Json::parseFromStream(reader, fileInput, &parsed, &errs);
  fileInput.close();

  return parsed;
}

const Json::Value Util::json_reads(const std::string json_string) {
  Json::Value parsed;
  Json::CharReaderBuilder builder;
  std::string errs;
  std::istringstream stream(json_string);

  if (!Json::parseFromStream(builder, stream, &parsed, &errs)) {
    throw std::runtime_error(fmt::format("Failed to parse string as json: {}", json_string));
  }

  return parsed;
}

const std::string Util::json_dumps(const Json::Value val) {
  Json::StreamWriterBuilder builder;
  builder["indentation"] = "";
  std::string json_string = Json::writeString(builder, val);
  return json_string;
}

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
  can_id |= (priority & 0x7) << 26;
  can_id |= (dp & 0x1) << 24;
  can_id |= (pf & 0xFF) << 16;
  can_id |= (ps & 0xFF) << 8;
  can_id |= src_addr & 0xFF;

  return can_id;
}

uint32_t Util::pgn_to_can_id(const uint32_t pgn, const uint8_t priority, const uint8_t src_addr) {
  return Util::pgn_to_can_id(pgn, priority, src_addr, 0x00);
}

std::tuple<uint32_t, uint8_t, uint8_t, uint8_t> Util::can_id_to_pgn(const uint32_t can_id) {
  uint8_t src_addr = can_id & 0xFF;
  uint8_t ps = (can_id >> 8) & 0xFF;
  uint8_t pf = (can_id >> 16) & 0xFF;
  uint8_t dp = (can_id >> 24) & 0x1;
  uint8_t priority = (can_id >> 26) & 0x7;

  uint32_t pgn = ps;
  pgn |= (pf << 8);
  pgn |= (dp << 16);

  uint8_t dest_addr;
  if(is_pdu_format_1(pgn)) {
    dest_addr = (pgn & 0xFF);
    pgn = (pgn & 0x1FF00);
  } else {
    dest_addr = 0x00;
  }

  return std::make_tuple(pgn, priority, src_addr, dest_addr);
}

std::chrono::system_clock::time_point Util::system_zero = std::chrono::system_clock::now();

void Util::set_system_zero() {
  Util::system_zero = std::chrono::system_clock::now();
}

uint64_t Util::millis() {
  auto now = std::chrono::system_clock::now();
  uint64_t millis = std::chrono::duration_cast<std::chrono::milliseconds>(now - Util::system_zero).count();
  return millis;
}

int Util::tm_gmtoff() {
  std::time_t t = std::time(nullptr);
  std::tm* local_time = std::localtime(&t);
  return local_time->tm_gmtoff;
}

std::chrono::system_clock::time_point Util::create_time_point(int year, int month, int day, int hour, int minute, int second) {
  std::tm tm = {};
  tm.tm_year = year - 1900; // Year since 1900
  tm.tm_mon = month;        // Month of the year (0-11)
  tm.tm_mday = day;         // Day of the month (1-31)
  tm.tm_hour = hour;        // Hours since midnight (0-23)
  tm.tm_min = minute;       // Minutes after the hour (0-59)
  tm.tm_sec = second;       // Seconds after the minute (0-60)

  // Convert tm structure to time_t as a system-wide time point
  std::time_t time = std::mktime(&tm);

  // And then to a system_clock time point
  return std::chrono::system_clock::from_time_t(time);
}

const std::vector<uint8_t>
Util::obc_time_data(std::chrono::system_clock::time_point t) {
  std::chrono::system_clock::time_point t0 = create_time_point(1900, 0, 1, 0, 0, 0);

  int gmt_off_sec = tm_gmtoff();
  auto gmt_off_duration = std::chrono::seconds(gmt_off_sec);
  auto gmt_time = t - gmt_off_duration;

  std::time_t time_t_val = std::chrono::system_clock::to_time_t(gmt_time);
  std::tm* tm_val = std::localtime(&time_t_val);

  int millis = (std::chrono::duration_cast<std::chrono::milliseconds>(t-t0).count() % 1000);
  uint8_t sec = ((int)(tm_val->tm_sec * 4) + (millis / 250)); // seconds in 0.25s resolution
  uint8_t min = ((int)tm_val->tm_min);
  uint8_t hour = ((int)tm_val->tm_hour);

  // c++'s `time_t` uses 1900 as year 0. The can time format uses year 1985 as year 0
  uint8_t year = ((int)(tm_val->tm_year + 1900 - 1985));
  uint8_t mon = ((int)tm_val->tm_mon) + 1;
  uint8_t mday = ((int)tm_val->tm_mday) * 4; // format expects quarter days

  uint8_t min_offset = (gmt_off_sec % 3600) / 60;
  uint8_t hour_offset = gmt_off_sec / 3600;

  return std::vector<uint8_t>{sec, min, hour, mon, mday, year, min_offset, hour_offset};
}

const std::optional<std::string> Util::read_mod_status(const std::string& path) {
  std::ifstream in_file(path);
  if (!in_file.is_open()) {
    return std::nullopt;
  }

  std::string state;
  if (std::getline(in_file, state)) {
    return state;
  } else {
    return std::nullopt;
  }
}