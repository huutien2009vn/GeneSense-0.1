export class MovingAverage {
  constructor(size = 5) {
    this.size = size;
    this.values = [];
  }

  next(value) {
    if (!Number.isFinite(value)) return null;
    this.values.push(value);
    if (this.values.length > this.size) this.values.shift();
    return this.values.reduce((sum, item) => sum + item, 0) / this.values.length;
  }
}

const SERVICES = {
  heartRate: { service: 0x180d, characteristic: 0x2a37 },
  bloodPressure: { service: 0x1810, characteristic: 0x2a35 },
  pulseOximeter: { service: 0x1822, characteristic: 0x2a5f },
  glucose: { service: 0x1808, characteristic: 0x2a18 },
};

function readSFloat(view, offset) {
  const raw = view.getUint16(offset, true);
  let mantissa = raw & 0x0fff;
  let exponent = raw >> 12;
  if (mantissa >= 0x0800) mantissa = -(0x1000 - mantissa);
  if (exponent >= 0x0008) exponent = -(0x0010 - exponent);
  return mantissa * 10 ** exponent;
}

function parseHeartRate(view) {
  const flags = view.getUint8(0);
  return { heart_rate: flags & 0x01 ? view.getUint16(1, true) : view.getUint8(1) };
}

function parseBloodPressure(view) {
  const flags = view.getUint8(0);
  const factor = flags & 0x01 ? 7.50062 : 1;
  return {
    systolic: readSFloat(view, 1) * factor,
    diastolic: readSFloat(view, 3) * factor,
  };
}

function parsePulseOximeter(view) {
  // PLX Continuous Measurement: flags byte followed by SpO2 and pulse-rate SFLOAT values.
  if (view.byteLength < 5) throw new Error("Gói SpO₂ không hợp lệ");
  return { spo2: readSFloat(view, 1), heart_rate: readSFloat(view, 3) };
}

function parseGlucose(view) {
  // Glucose Measurement has a 10-byte fixed header; optional time offset shifts concentration.
  const flags = view.getUint8(0);
  let offset = 10;
  if (flags & 0x01) offset += 2;
  if (!(flags & 0x02) || view.byteLength < offset + 2) return {};
  const molPerL = Boolean(flags & 0x04);
  const raw = readSFloat(view, offset);
  // Bluetooth SIG units are kg/L or mol/L. Convert to common mg/dL display.
  return { glucose: molPerL ? raw * 18015.59 : raw * 100000 };
}

const PARSERS = {
  heartRate: parseHeartRate,
  bloodPressure: parseBloodPressure,
  pulseOximeter: parsePulseOximeter,
  glucose: parseGlucose,
};

export class HealthBleClient extends EventTarget {
  constructor(windowSize = 5) {
    super();
    this.device = null;
    this.server = null;
    this.characteristics = [];
    this.filters = new Map([
      ["heart_rate", new MovingAverage(windowSize)],
      ["systolic", new MovingAverage(windowSize)],
      ["diastolic", new MovingAverage(windowSize)],
      ["spo2", new MovingAverage(windowSize)],
      ["glucose", new MovingAverage(windowSize)],
    ]);
  }

  get supported() {
    return Boolean(navigator.bluetooth);
  }

  async connect() {
    if (!this.supported) throw new Error("Trình duyệt này chưa hỗ trợ Web Bluetooth.");
    const optionalServices = Object.values(SERVICES).map((item) => item.service);
    this.device = await navigator.bluetooth.requestDevice({ acceptAllDevices: true, optionalServices });
    this.device.addEventListener("gattserverdisconnected", () => this._emit("disconnected", {}));
    this.server = await this.device.gatt.connect();

    let subscribed = 0;
    for (const [name, definition] of Object.entries(SERVICES)) {
      try {
        const service = await this.server.getPrimaryService(definition.service);
        const characteristic = await service.getCharacteristic(definition.characteristic);
        await characteristic.startNotifications();
        characteristic.addEventListener("characteristicvaluechanged", (event) => {
          try {
            const parsed = PARSERS[name](event.target.value);
            this._publish(parsed);
          } catch (error) {
            this._emit("error", { message: error.message });
          }
        });
        this.characteristics.push(characteristic);
        subscribed += 1;
      } catch (_) {
        // A device normally implements only one or two of these standardized services.
      }
    }
    if (!subscribed) {
      this.device.gatt.disconnect();
      throw new Error("Thiết bị không cung cấp dịch vụ BLE y tế chuẩn được hỗ trợ.");
    }
    this._emit("connected", { name: this.device.name || "Thiết bị BLE", services: subscribed });
    return this.device;
  }

  disconnect() {
    if (this.device?.gatt?.connected) this.device.gatt.disconnect();
  }

  _publish(values) {
    const filtered = {};
    Object.entries(values).forEach(([key, value]) => {
      const average = this.filters.get(key)?.next(Number(value));
      if (average !== null && average !== undefined) filtered[key] = Math.round(average * 10) / 10;
    });
    if (Object.keys(filtered).length) this._emit("data", { values: filtered, timestamp: new Date().toISOString() });
  }

  _emit(name, detail) {
    this.dispatchEvent(new CustomEvent(name, { detail }));
  }
}

export class VitalSimulator extends EventTarget {
  constructor(windowSize = 5) {
    super();
    this.timer = null;
    this.step = 0;
    this.filters = Object.fromEntries(["heart_rate", "systolic", "diastolic", "spo2", "glucose"].map((key) => [key, new MovingAverage(windowSize)]));
  }

  start() {
    this.stop();
    this.step = 0;
    this.dispatchEvent(new CustomEvent("connected", { detail: { name: "Thiết bị mô phỏng" } }));
    this._tick();
    this.timer = window.setInterval(() => this._tick(), 1800);
  }

  stop() {
    if (this.timer) window.clearInterval(this.timer);
    this.timer = null;
  }

  _tick() {
    this.step += 1;
    const noise = () => (Math.random() - 0.5) * 2;
    const raw = {
      heart_rate: 73 + Math.sin(this.step / 2.8) * 4 + noise() * 2.2,
      systolic: 119 + Math.sin(this.step / 4) * 5 + noise() * 2,
      diastolic: 77 + Math.sin(this.step / 4) * 3 + noise() * 1.5,
      spo2: 97.3 + Math.sin(this.step / 3.2) * 0.8 + noise() * 0.35,
      glucose: 104 + Math.sin(this.step / 5) * 8 + noise() * 3,
    };
    const values = Object.fromEntries(Object.entries(raw).map(([key, value]) => [key, Math.round(this.filters[key].next(value) * 10) / 10]));
    this.dispatchEvent(new CustomEvent("data", { detail: { values, timestamp: new Date().toISOString() } }));
  }
}

