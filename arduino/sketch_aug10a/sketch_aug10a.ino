const byte STATE_IDLE = 0xF0;
const byte STATE_INIT_CONFIG = 0xF1;
const byte STATE_CONFIG = 0xF2;
const byte STATE_INIT_MAIN = 0xF3;
const byte STATE_MAIN = 0xF4;
const byte STATE_FAIL = 0xF5;

const byte MSG_AWAIT_CONFIG = 0xF0;
const byte MSG_WRITE = 0xF1;
const byte MSG_READ = 0xF2;
const byte MSG_FAIL = 0xF3;
const byte MSG_STATE_SET = 0xF4;
const byte MSG_CONFIG_SESSION = 0xF5;
const byte MSG_CONFIG_PINMODE = 0xF6;
const byte MSG_CONFIG_GET_ANALOG_OFFSET = 0xF7;
const byte MSG_CONFIG_FINALIZE = 0xF8;
const byte MSG_ANALOG_OFFSET = 0xF9;
const byte MSG_TXT = 0xFA;
const byte MSG_HEARTBEAT = 0xFB;
const byte MSG_BUF_DUMP = 0xFC;

byte msgSizes[MSG_BUF_DUMP-MSG_AWAIT_CONFIG+1];

const byte PIN_DIGITAL = 0x0;
const byte PIN_ANALOG = 0x1;

const byte PIN_INPUT = 0x0;
const byte PIN_OUTPUT = 0x1;

const byte PIN_UNUSED = 0xF;

const int inBufSize = 32;
const int nPins = 19;
byte pinConfig[nPins];

byte inBuf[inBufSize];
byte nBuf = 0;
byte pos = 0;
byte state = STATE_IDLE;
uint16_t session = 0;
const uint16_t SUPER_SESSION = 0xFFFF;
unsigned long lastHeartbeatReceived = 0l;
unsigned int inHeartbeatTimeout = 1000;

void setup() {
  msgSizes[MSG_AWAIT_CONFIG-MSG_AWAIT_CONFIG] = 3;
  msgSizes[MSG_WRITE-MSG_AWAIT_CONFIG] = 6;
  msgSizes[MSG_READ-MSG_AWAIT_CONFIG] = 6;
  msgSizes[MSG_FAIL-MSG_AWAIT_CONFIG] = 3;
  msgSizes[MSG_STATE_SET-MSG_AWAIT_CONFIG] = 4;
  msgSizes[MSG_CONFIG_SESSION-MSG_AWAIT_CONFIG] = 5;
  msgSizes[MSG_CONFIG_PINMODE-MSG_AWAIT_CONFIG] = 6;
  msgSizes[MSG_CONFIG_GET_ANALOG_OFFSET-MSG_AWAIT_CONFIG] = 3;
  msgSizes[MSG_CONFIG_FINALIZE-MSG_AWAIT_CONFIG] = 3;
  msgSizes[MSG_ANALOG_OFFSET-MSG_AWAIT_CONFIG] = 4;
  msgSizes[MSG_TXT-MSG_AWAIT_CONFIG] = 32;
  msgSizes[MSG_HEARTBEAT-MSG_AWAIT_CONFIG] = 3;
  msgSizes[MSG_BUF_DUMP-MSG_AWAIT_CONFIG] = inBufSize + 3;

  Serial.begin(115200);
  reset();

  // byte data[] = {0x01, 0x02, 0x03};
  // memcpy(&inBuf[0], data, sizeof(data));
}

void loop() {
  readSerial();
  superSetStep();
  
  switch(state) {
    case STATE_IDLE: {
      delay(100);
    } break;
    case STATE_FAIL: {
      failStep();
      delay(100);
    } break;
    case STATE_INIT_CONFIG: {
      initConfigStep();
    } break;
    case STATE_CONFIG: {
      configStep();
    } break;
    case STATE_INIT_MAIN: {
      initMainStep();
    } break;
    case STATE_MAIN: {
      mainStep();
    } break;
    default: {
      state = STATE_FAIL;
    }
  }
  
  delay(1);
}


void sendBufDump() {
  byte msg[msgSize(MSG_BUF_DUMP)];
  msg[0] = (SUPER_SESSION >> 8) & 0xFF;
  msg[1] = SUPER_SESSION & 0xFF;
  msg[2] = MSG_BUF_DUMP;

  for(byte i=0; i<inBufSize; i++) {
    msg[i+3] = inBuf[i];
  }

  Serial.write(msg, msgSize(MSG_BUF_DUMP));
}


void superSetStep() {
  int msgIdx;
  byte querySeq[] = {(SUPER_SESSION >> 8) & 0xFF, SUPER_SESSION & 0xFF, MSG_STATE_SET};
  msgIdx = findByteSeq(querySeq, sizeof(querySeq), nBuf);

  if(msgIdx != -1 && pos + msgIdx + 1 <= nBuf) {
    consume(msgIdx);
    state = relInBuf(3);
    consume(msgSize(MSG_STATE_SET));
  }
}

void failStep() {
  reset();
  state = STATE_FAIL;
  byte msg[] = {(SUPER_SESSION >> 8) & 0xFF, SUPER_SESSION & 0xFF, MSG_FAIL};
  Serial.write(msg, msgSize(MSG_FAIL));
}


void initConfigStep() {
  reset();
  state = STATE_CONFIG;
  byte msg[] = {(byte)((SUPER_SESSION >> 8) & 0xFF), (byte)(SUPER_SESSION & 0xFF), MSG_AWAIT_CONFIG};
  Serial.write(msg, msgSize(MSG_AWAIT_CONFIG));
}


void configStep() {
  byte querySeq[] = {(SUPER_SESSION >> 8) & 0xFF, SUPER_SESSION & 0xFF};
  int msgIdx = findByteSeq(querySeq, sizeof(querySeq), 0);

  if(msgIdx != -1 && hasBuf(msgIdx + 3) && relInBuf(2) >= MSG_CONFIG_SESSION && relInBuf(2) <= MSG_ANALOG_OFFSET) {
    consume(msgIdx);
    
    byte configMsg = relInBuf(2);
    
    if(hasBuf(msgSize(configMsg))) {
      switch(configMsg) {
        case MSG_CONFIG_SESSION: {
          session = relInBuf(4);
          session |= (relInBuf(3) << 8);
          consume(msgSize(MSG_CONFIG_SESSION));
        } break;
        case MSG_CONFIG_PINMODE: {
          byte pin = relInBuf(3);
          byte mode = relInBuf(4);
          byte anaDigi = relInBuf(5);

          byte conf = 0x00;
          conf |= (mode << 4);
          conf |= anaDigi;

          pinConfig[pin] = conf;
          consume(msgSize(MSG_CONFIG_PINMODE));
        } break;
        case MSG_CONFIG_GET_ANALOG_OFFSET: {
          consume(msgIdx);
          
          byte msg[] = {(SUPER_SESSION >> 8) & 0xFF, SUPER_SESSION & 0xFF, MSG_ANALOG_OFFSET, (byte)A0};
          Serial.write(msg, msgSize(MSG_ANALOG_OFFSET));
          consume(msgSize(MSG_CONFIG_GET_ANALOG_OFFSET));
        } break;
        case MSG_CONFIG_FINALIZE: {
          state = STATE_INIT_MAIN;
          consume(msgSize(MSG_CONFIG_FINALIZE));
        } break;
        default: {
          state = STATE_FAIL;
        }
      }
    } else {
      state = STATE_FAIL;
    }
  }
}

void initMainStep() {
  for(byte pin=0; pin<nPins; pin++) {
    byte pinConf = pinConfig[pin];
    byte pinMod = pinConf >> 4;
    byte anaDigi = pinConf & 0xF;
    
    switch(pinMod) {
      case PIN_INPUT: {
        switch(anaDigi) {
          case PIN_DIGITAL: {
            pinMode(pin, INPUT);
          } break;
          case PIN_ANALOG: {
            pinMode(pin, INPUT);
          } break;
          case PIN_UNUSED: {
            state = STATE_FAIL;
          } break;
          default: {
            state = STATE_FAIL;
          }
        }
      } break;
      case PIN_OUTPUT: {
        switch(anaDigi) {
          case PIN_DIGITAL: {
            pinMode(pin, OUTPUT);
          } break;
          case PIN_ANALOG: {
            pinMode(pin, OUTPUT);
          } break;
          case PIN_UNUSED: {
            state = STATE_FAIL;
          } break;
          default: {
            state = STATE_FAIL;
          }
        }
      } break;
      case PIN_UNUSED: {
        switch(anaDigi) {
          case PIN_DIGITAL: {
            state = STATE_FAIL;
          } break;
          case PIN_ANALOG: {
            state = STATE_FAIL;
          } break;
          case PIN_UNUSED: {
            // pass
          } break;
          default: {
            state = STATE_FAIL;
          }
        }
      } break;
      default: {
        state = STATE_FAIL;
      }
    }
  }

  lastHeartbeatReceived = millis();
  state = STATE_MAIN;
}


void mainDispatchOutput() {
  for(byte pin=0; pin<nPins; pin++) {
    byte pinConf = pinConfig[pin];
    byte pinMod = pinConf >> 4;
    byte anaDigi = pinConf & 0xF;
    
    if(pinMod == PIN_INPUT) {
      switch(anaDigi) {
        case PIN_DIGITAL: {
          byte val = (byte)digitalRead(pin);
          byte msg[] = {(byte)((session >> 8) & 0xFF), (byte)(session & 0xFF), MSG_READ, pin, 0x00, val};
          Serial.write(msg, msgSize(MSG_READ));
        } break;
        case PIN_ANALOG: {
          short val = (short)analogRead(pin);
          byte msg[] = {(byte)((session >> 8) & 0xFF), (byte)(session & 0xFF), MSG_READ, pin, (byte)((val >> 8) & 0xFF), (byte)(val & 0xFF)};
          Serial.write(msg, msgSize(MSG_READ));
        } break;
        default: {
          state = STATE_FAIL;
          return;
        }
      }
    }

  }
}

bool mainDispatchMsg() {
  byte querySeq[] = {(byte)((session >> 8) & 0xFF), (byte)(session & 0xFF)};
  int msgIdx = findByteSeq(querySeq, sizeof(querySeq), 0);
  
  if(msgIdx != -1 && hasBuf(msgIdx + 3) && (relInBuf(2) == MSG_WRITE || relInBuf(2) == MSG_HEARTBEAT)) {
    consume(msgIdx);
    byte mainMsg = relInBuf(2);
    
    if(hasBuf(msgSize(mainMsg))) {
      switch(mainMsg) {
        case MSG_WRITE: {
          byte pin = relInBuf(3);
          byte val1 = relInBuf(4);
          byte val2 = relInBuf(5);

          byte pinConf = pinConfig[pin];
          byte pinMod = (pinConf >> 4) & 0xF;
          byte anaDigi = pinConf & 0xF;

          consume(msgSize(MSG_WRITE));

          switch(pinMod) {
            case PIN_OUTPUT: {
              switch(anaDigi) {
                case PIN_DIGITAL: {
                  if(val2 == 0x0) {
                    digitalWrite(pin, LOW);
                  } else {
                    digitalWrite(pin, HIGH);
                  }
                  return true;
                } break;
                case PIN_ANALOG: {
                  short val = (((short)val2) | (((short)val1) << 8));
                  analogWrite(pin, val);
                  return true;
                } break;
                default: {
                  state = STATE_FAIL;
                  return false;
                }
              }
            } break;
            case PIN_INPUT: {
              state = STATE_FAIL;
              return false;
            } break;
            default: {
              state = STATE_FAIL;
              return false;
            }
          }
        } break;
        case MSG_HEARTBEAT: {
          consume(msgSize(MSG_HEARTBEAT));
          lastHeartbeatReceived = millis();
          return true;
        } break;
        default: {
          return false;
        }
      }
      return true;
    } else {
      return false;
    }
  } else {
    return false;
  }
}


void mainStep() {
  if(millis() < (lastHeartbeatReceived + inHeartbeatTimeout)) {
    mainDispatchOutput();
  }
  
  while(mainDispatchMsg()) {
    // pass
  }
}


void readSerial() {
  int nAvailBytes = Serial.available();
  if(nAvailBytes > 0) {
    byte nReadBytes = min(nAvailBytes, inBufSize);
    
    if(nReadBytes > 0) {
      byte data[nReadBytes];
      Serial.readBytes(data, nReadBytes);
      appendData(data, nReadBytes);
    }
  }
}


void appendData(byte data[], byte dataLen) {
  if(dataLen > freeBuf()) {
    state = STATE_FAIL;
    return;
  }
  
  cycleBuffer(mod(inBufSize - nBuf - pos, inBufSize));

  for(byte i=0; i<dataLen; i++) {
    inBuf[i] = data[i];
  }
  
  nBuf = nBuf + dataLen;
}

void sendTxt(String txt) {
  return sendTxt(txt, "\n\r");
}

void sendTxt(String txt, String terminal) {
  byte maxPayloadSize = msgSize(MSG_TXT)-3;
  byte textBuf[maxPayloadSize];
  byte msg[msgSize(MSG_TXT)];

  txt = txt + terminal;

  while(true) {
    for(byte i=0; i<maxPayloadSize; i++) {
      textBuf[i] = 0x00;
    }
    
    byte msgPayloadSize = min(txt.length(), maxPayloadSize);
    txt.getBytes(textBuf, msgPayloadSize+1);
    
    msg[0] = (byte)((SUPER_SESSION >> 8) & 0xFF);
    msg[1] = (byte)(SUPER_SESSION & 0xFF);
    msg[2] = MSG_TXT;
    for(byte i=0; i<maxPayloadSize; i++) {
      msg[i+3] = textBuf[i];
    }
    
    Serial.write(msg, msgSize(MSG_TXT));

    if(msgPayloadSize >= txt.length()) {
      break;
    }
    
    txt = txt.substring(msgPayloadSize);
  }
}


void clearSerialBuffer() {
  while(Serial.available() > 0) {
    Serial.read();
  }
}

void consume(byte i) {
  pos += i;
  nBuf -= i;
}

byte mod(byte i, byte divisor) {
  while(i < 0) {
    i += divisor;
  }

  return i % divisor;
}

void reset() {
  nBuf = 0;
  pos = 0;
  state = STATE_IDLE;
  session = SUPER_SESSION;
  lastHeartbeatReceived = 0l;

  for(byte pin=0; pin<nPins; pin++) {
    byte pinConf = 0;
    pinConf |= (PIN_UNUSED << 4);
    pinConf |= PIN_UNUSED;
    pinConfig[pin] = pinConf;

    pinMode(pin, INPUT);
  }
  
  clearSerialBuffer();
}


byte msgSize(byte state) {
  byte idxOffset = MSG_AWAIT_CONFIG;
  return msgSizes[state - idxOffset];
}

void cycleBuffer(int cycleBy) {
  cycleBy = mod(cycleBy, inBufSize);
  if(cycleBy == 0) {
    return;
  }

  int remaining = inBufSize-cycleBy;
  byte cycleBuf[cycleBy];
  
  for(int j=0; j<cycleBy; j++) {
    cycleBuf[j] = inBuf[remaining+j];
  }

  for(int j=0; j<remaining; j++) {
    inBuf[cycleBy+j] = inBuf[j];
  }

  for(int j=0; j<cycleBy; j++) {
    inBuf[j] = cycleBuf[j];
  }

  pos = mod(pos + cycleBy, inBufSize);
}

byte relInBuf(byte idx) {
  if(idx >= nBuf) {
    state = STATE_FAIL;
    return 0x00;
  } else {
    return inBuf[mod(pos+idx, inBufSize)];
  }
}

bool hasBuf(byte n) {
  return nBuf >= n;
}

byte freeBuf() {
  return inBufSize - nBuf;
}


int findByteSeq(byte seq[], byte seqLen, byte maxIdx) {
  byte nItemsFound = 0;
  byte nCheckItems = min(maxIdx+seqLen, nBuf);
  int foundAt = -1;
  
  for(byte i=0; i<nCheckItems; i++) {
    if(relInBuf(i) == seq[nItemsFound]) {
      nItemsFound++;
    } else {
      nItemsFound=0;
    }

    if(nItemsFound == seqLen) {
      foundAt = i - seqLen + 1;
      break;
    }
  }
  
  return foundAt;
}
