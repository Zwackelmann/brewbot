static uint8_t pdu_format(const uint32_t pgn);
static uint8_t is_pdu_format_1(const uint32_t pgn);
static uint8_t is_pdu_format_2(const uint32_t pgn);
static uint32_t pgn_to_can_id(const uint32_t pgn, const uint8_t priority, const uint8_t src_addr, const uint8_t dest_addr);

static uint32_t can_id_to_pgn(const uint32_t can_id);
static uint8_t can_id_to_src_addr(const uint32_t can_id);
static uint8_t can_id_to_dest_addr(const uint32_t can_id);
static uint8_t can_id_to_priority(const uint32_t can_id);

static void array_shift(uint8_t *data, size_t dlen, int by);

static bool encode_uint(uint32_t n, uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size);
static bool encode_int(int32_t n, uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size);
static bool encode_str(std::string& s, uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size, bool zero_terminate=true, uint8_t pad_byte=0xFF);

static uint32_t decode_uint(const uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size);
static int32_t decode_int(const uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size);
static std::string decode_str(const uint8_t *data, size_t dlen, size_t start_bit, size_t signal_size, bool stop_at_zero=true, uint8_t pad_byte=0xFF);

static bool inject(uint8_t *data, size_t dlen, uint8_t *num, size_t nlen, size_t start_bit, size_t signal_size);
static void project(const uint8_t *data, size_t dlen, uint8_t *num, size_t nlen, size_t start_bit, size_t signal_size);