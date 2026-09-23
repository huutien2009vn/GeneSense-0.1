const RANGES = {
  heart_rate: { min: 45, max: 125, healthy: [60, 100], label: "bpm" },
  spo2: { min: 88, max: 101, healthy: [95, 100], label: "%" },
  systolic: { min: 75, max: 170, healthy: [90, 129], label: "mmHg" },
  glucose: { min: 50, max: 250, healthy: [70, 140], label: "mg/dL" },
};

export class VitalChart {
  constructor(canvas) {
    this.canvas = canvas;
    this.context = canvas.getContext("2d");
    this.metric = "heart_rate";
    this.data = [];
    this.resizeObserver = new ResizeObserver(() => this.draw());
    this.resizeObserver.observe(canvas.parentElement);
  }

  setData(metric, data) {
    this.metric = metric;
    this.data = data.slice(-30);
    this.draw();
  }

  draw() {
    const rect = this.canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    this.canvas.width = Math.round(rect.width * ratio);
    this.canvas.height = Math.round(rect.height * ratio);
    const ctx = this.context;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);

    const base = RANGES[this.metric];
    const actual = this.data.map(item => item.value);
    const bounds = { ...base, min: Math.min(base.min, ...actual.map(v => v - 5)), max: Math.max(base.max, ...actual.map(v => v + 5)) };
    const padding = { top: 16, right: 14, bottom: 27, left: 37 };
    const width = rect.width - padding.left - padding.right;
    const height = rect.height - padding.top - padding.bottom;
    const y = (value) => padding.top + (bounds.max - value) / (bounds.max - bounds.min) * height;
    const x = (index) => padding.left + (this.data.length <= 1 ? width / 2 : index / (this.data.length - 1) * width);

    ctx.fillStyle = "rgba(21, 139, 104, 0.07)";
    ctx.fillRect(padding.left, y(bounds.healthy[1]), width, y(bounds.healthy[0]) - y(bounds.healthy[1]));

    ctx.font = "12px Manrope, sans-serif";
    ctx.fillStyle = "#8b99aa";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (let index = 0; index <= 4; index += 1) {
      const value = bounds.min + (bounds.max - bounds.min) * index / 4;
      const rowY = y(value);
      ctx.beginPath();
      ctx.strokeStyle = "#e7eef4";
      ctx.lineWidth = 1;
      ctx.moveTo(padding.left, rowY);
      ctx.lineTo(padding.left + width, rowY);
      ctx.stroke();
      ctx.fillText(Math.round(value), padding.left - 7, rowY);
    }

    [bounds.healthy[0], bounds.healthy[1]].forEach((value) => {
      ctx.beginPath();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = "#9fb9b1";
      ctx.moveTo(padding.left, y(value));
      ctx.lineTo(padding.left + width, y(value));
      ctx.stroke();
    });
    ctx.setLineDash([]);

    if (!this.data.length) return;
    const points = this.data.map((item, index) => ({ x: x(index), y: y(item.value) }));
    const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + height);
    gradient.addColorStop(0, "rgba(11, 107, 203, 0.24)");
    gradient.addColorStop(1, "rgba(11, 107, 203, 0)");
    ctx.beginPath();
    ctx.moveTo(points[0].x, padding.top + height);
    points.forEach((point) => ctx.lineTo(point.x, point.y));
    ctx.lineTo(points.at(-1).x, padding.top + height);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    ctx.beginPath();
    ctx.strokeStyle = "#0b6bcb";
    ctx.lineWidth = 2.25;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    points.forEach((point, index) => index ? ctx.lineTo(point.x, point.y) : ctx.moveTo(point.x, point.y));
    ctx.stroke();
    const last = points.at(-1);
    ctx.beginPath();
    ctx.fillStyle = "white";
    ctx.strokeStyle = "#0b6bcb";
    ctx.lineWidth = 2.5;
    ctx.arc(last.x, last.y, 4.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = "#8b99aa";
    ctx.textAlign = "left";
    ctx.textBaseline = "bottom";
    ctx.fillText("Cũ hơn", padding.left, rect.height - 4);
    ctx.textAlign = "right";
    ctx.fillText("Mới nhất", rect.width - padding.right, rect.height - 4);
  }
}
