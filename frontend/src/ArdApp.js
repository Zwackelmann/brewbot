class ArdApp {
  baudrate
  inBufSize
  heartbeatRate
  readInterval
  minReadSleep
  readSerialTimeout

  constructor(baudrate = 115200, pins = "", inBufSize = 128, heartbeatRate = 100, readInterval = 5, minReadSleep = 5,
      readSerialTimeout = 100) {
    this.baudrate = baudrate
    this.pins = pins
    this.inBufSize = inBufSize
    this.heartbeatRate = heartbeatRate
    this.readInterval = readInterval
    this.minReadSleep = minReadSleep
    this.readSerialTimeout = readSerialTimeout
  }

  paramObj() {
    return {
      "inBufSize": this.inBufSize, "heartbeatRate": this.heartbeatRate, "readInterval": this.readInterval,
      "minReadSleep": this.minReadSleep, "readSerialTimeout": this.readSerialTimeout
    }
  }

  qstr() {
    return (Object.entries(this.paramObj()).map(([key, value]) => {
      return key + "=" + value.toString()
    })).join("&")
  }
}


class LedApp extends ArdApp {
  ledPin

  constructor(ledPin, baudrate = 115200) {
    let pins = ledPin + ",out,d"
    super(baudrate = baudrate, pins = pins)
    this.ledPin = ledPin;
  }
}

export { ArdApp, LedApp }
