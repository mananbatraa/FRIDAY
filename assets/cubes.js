// Interactive background: a floor of small 3D (isometric) cubes that rise and glow
// under the cursor, but only over empty background (not over panels, text or controls).
// Injected into the dashboard page once by dashboard.py; runs in the page itself.
(() => {
  if (document.getElementById("friday-cubes")) return;

  const EDGE = 16;                     // cube edge length in pixels (smaller = more, finer cubes)
  const W = EDGE * Math.sqrt(3);       // width of a cube's top face on screen
  const RADIUS = 130;                  // how far from the cursor cubes react
  const LIFT = 24;                     // how high the tallest cubes rise under the cursor, in pixels
  const RIPPLE = 3;                    // gentle resting height variation, so the sides show
  const EASE = 0.14;                   // how quickly cubes follow the cursor
  // Anything matching this counts as content, so the cubes stay down beneath it.
  const CONTENT = [
    '[data-testid="stElementContainer"]', 'div[class*="st-key-tile_"]', '[data-testid="stHeader"]',
    '[role="dialog"]', '[data-baseweb="popover"]', "button", "input", "textarea", "a",
  ].join(",");
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const canvas = document.createElement("canvas");
  canvas.id = "friday-cubes";
  Object.assign(canvas.style, {
    position: "fixed", inset: "0", width: "100vw", height: "100vh", zIndex: "-1", pointerEvents: "none",
  });
  document.body.prepend(canvas);
  const ctx = canvas.getContext("2d");

  // A speckled tile laid over the cubes for a brushed-metal texture.
  const grain = document.createElement("canvas");
  grain.width = grain.height = 96;
  const g = grain.getContext("2d");
  for (let i = 0; i < 2200; i++) {
    const light = Math.random() > 0.55;
    g.fillStyle = light ? `rgba(150,230,245,${0.025 + Math.random() * 0.05})` : `rgba(0,0,0,${0.06 + Math.random() * 0.1})`;
    g.fillRect((Math.random() * 96) | 0, (Math.random() * 96) | 0, 1, 1);
  }
  let texture;

  // Cubes sit in staggered rows: row r is EDGE/2 lower than row r-1 and shifted half a cube sideways.
  let width, height, cols, rows, rest, shade, jitter, lift;
  let mouseX = -1e4, mouseY = -1e4, overBackground = false, running = false;
  let dirty = null;

  const at = (r, c) => [c * W + (r % 2 ? W / 2 : 0), r * EDGE / 2];

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cols = Math.ceil(width / W) + 2;
    rows = Math.ceil(height / (EDGE / 2)) + 4;
    const n = rows * cols;
    rest = new Float32Array(n);
    shade = new Float32Array(n);
    lift = new Float32Array(n);
    jitter = new Float32Array(n);
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const [x, y] = at(r, c);
        const i = r * cols + c;
        // Smooth, low hills so the floor reads as 3D even when nothing is moving.
        rest[i] = RIPPLE * (0.5 + 0.5 * Math.sin(x / 97 + Math.cos(y / 131) * 2) * Math.cos(y / 83 - x / 211));
        shade[i] = Math.random() * 8 - 4;
        // Each cube rises a different amount, so neighbours step up and down and their sides show.
        jitter[i] = 0.3 + Math.random() * 0.7;
      }
    }
    texture = ctx.createPattern(grain, "repeat");
    paint(0, 0, width, height);
  }

  function cube(x, y, z, h, v) {
    const s = EDGE / 2, w = W / 2;
    const ty = y - z;
    const down = z + EDGE;  // sides reach below the floor so no gaps show
    // Left face
    ctx.fillStyle = `rgb(${8 + v},${17 + h * 50 + v},${28 + h * 60 + v})`;
    ctx.beginPath();
    ctx.moveTo(x - w, ty); ctx.lineTo(x, ty + s); ctx.lineTo(x, ty + s + down); ctx.lineTo(x - w, ty + down);
    ctx.fill();
    // Right face
    ctx.fillStyle = `rgb(${4 + v},${9 + h * 30 + v},${17 + h * 40 + v})`;
    ctx.beginPath();
    ctx.moveTo(x, ty + s); ctx.lineTo(x + w, ty); ctx.lineTo(x + w, ty + down); ctx.lineTo(x, ty + s + down);
    ctx.fill();
    // Top face, brighter and cyan-tinted as it rises
    ctx.fillStyle = `rgb(${12 + h * 40 + v},${26 + h * 160 + v},${42 + h * 170 + v})`;
    ctx.beginPath();
    ctx.moveTo(x, ty - s); ctx.lineTo(x + w, ty); ctx.lineTo(x, ty + s); ctx.lineTo(x - w, ty);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = `rgba(45,226,230,${0.05 + h * 0.6})`;
    ctx.stroke();
  }

  // Redraw every cube that overlaps the rectangle, back to front, clipped to it.
  function paint(x0, y0, x1, y1) {
    // Whole pixels, so the edge of a repainted area never leaves a faint seam.
    x0 = Math.floor(x0); y0 = Math.floor(y0); x1 = Math.ceil(x1); y1 = Math.ceil(y1);
    ctx.save();
    ctx.beginPath();
    ctx.rect(x0, y0, x1 - x0, y1 - y0);
    ctx.clip();
    ctx.fillStyle = "#060b14";
    ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
    ctx.lineWidth = 0.75;
    const rFrom = Math.max(0, Math.floor(y0 / (EDGE / 2)) - 2);
    const rTo = Math.min(rows - 1, Math.ceil((y1 + LIFT + RIPPLE + EDGE) / (EDGE / 2)) + 2);
    const cFrom = Math.max(0, Math.floor(x0 / W) - 1);
    const cTo = Math.min(cols - 1, Math.ceil(x1 / W) + 1);
    for (let r = rFrom; r <= rTo; r++) {
      for (let c = cFrom; c <= cTo; c++) {
        const i = r * cols + c;
        const [x, y] = at(r, c);
        cube(x, y, rest[i] + lift[i], lift[i] / LIFT, shade[i]);
      }
    }
    ctx.fillStyle = texture;
    ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
    ctx.restore();
  }

  function frame() {
    let moving = false;
    let bx0 = Infinity, by0 = Infinity, bx1 = -Infinity, by1 = -Infinity;
    const reach = RADIUS + W;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const i = r * cols + c;
        const [x, y] = at(r, c);
        let goal = 0;
        if (overBackground && !still && Math.abs(x - mouseX) < reach && Math.abs(y - mouseY) < reach) {
          const d = Math.hypot(x - mouseX, y - mouseY);
          goal = d < RADIUS ? LIFT * jitter[i] * (1 - d / RADIUS) ** 1.5 : 0;
        }
        const before = lift[i];
        lift[i] += (goal - lift[i]) * EASE;
        if (Math.abs(goal - lift[i]) < 0.02) lift[i] = goal;
        if (lift[i] !== before) {
          moving = true;
          bx0 = Math.min(bx0, x - W); bx1 = Math.max(bx1, x + W);
          by0 = Math.min(by0, y - LIFT - RIPPLE - EDGE); by1 = Math.max(by1, y + EDGE * 2);
        }
      }
    }
    if (moving) {
      // Repaint where cubes moved this frame and last frame, so nothing is left behind.
      const box = [bx0, by0, bx1, by1];
      const area = dirty ? [Math.min(box[0], dirty[0]), Math.min(box[1], dirty[1]),
        Math.max(box[2], dirty[2]), Math.max(box[3], dirty[3])] : box;
      paint(...area);
      dirty = box;
      window.requestAnimationFrame(frame);
    } else {
      if (dirty) paint(...dirty);
      dirty = null;
      running = false;
    }
  }

  function start() {
    if (!running) {
      running = true;
      window.requestAnimationFrame(frame);
    }
  }

  document.addEventListener("mousemove", (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
    overBackground = !(e.target.closest && e.target.closest(CONTENT));
    start();
  }, { passive: true });
  document.documentElement.addEventListener("mouseleave", () => { overBackground = false; start(); });
  window.addEventListener("resize", resize);
  resize();
})();
