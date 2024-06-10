class Buffer:
    def __init__(self, size):
        self._buf = bytearray(size)
        self.pos = 0
        self.num_buffered = 0

    def cycle_buffer(self, by):
        by = by % self.size
        if by == 0:
            return

        remaining = self.size-by
        cycle_buf = self._buf[remaining:]
        self._buf[by:] = self._buf[:remaining]
        self._buf[:by] = cycle_buf

        self.pos = (self.pos + by) % self.size

    def has_buf(self, n):
        return len(self) >= n

    @property
    def size(self):
        return len(self._buf)

    @property
    def free(self):
        return self.size - len(self)

    def append(self, data):
        data = bytes(data)

        if len(data) > self.free:
            raise ValueError()

        self.cycle_buffer((self.size - len(self) - self.pos) % self.size)
        self._buf[:len(data)] = data
        self.num_buffered += len(data)

    def __getitem__(self, item):
        if isinstance(item, slice):
            start = item.start
            stop = item.stop
            step = item.step

            if start is None:
                start = 0

            if stop is None:
                stop = len(self)

            if step is None:
                step = 1

            if start < 0:
                start = len(self) + start

            if stop < 0:
                stop = len(self) + stop

            if stop <= start:
                return b''

            start = max(start, 0)
            stop = min(stop, len(self))

            return bytes([self[i] for i in range(start, stop, step)])
        else:
            idx = item
            if idx < 0:
                idx = len(self) + idx

            if not 0 <= idx < len(self):
                raise IndexError(f'Index out of bounds: {idx} not in [0, {len(self)}]')

            pos = (self.pos + idx) % self.size
            return self._buf[pos]

    def __len__(self):
        return self.num_buffered

    def __str__(self):
        return f"Buffer({self[:]})"

    def __repr__(self):
        return str(self)

    def find(self, seq, max_idx=None):
        seq = bytes(seq)

        if max_idx is None:
            max_idx = len(self)-len(seq)+1
        else:
            max_idx = min(max_idx, len(self)-len(seq)+1)

        for i in range(max_idx+1):
            if self[i:i+len(seq)] == seq:
                return i

        return None

    def consume(self, n):
        if n <= 0:
            return

        consumed_bytes = self[:n]
        self.pos = (self.pos + n) % self.size
        self.num_buffered -= n

        return consumed_bytes

    def clear(self):
        self._buf = bytearray(len(self._buf))
        self.pos = 0
        self.num_buffered = 0
