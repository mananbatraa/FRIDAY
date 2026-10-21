// Interactive background: a floor of textured cubes that rise and glow under the
// cursor, but only over empty background (not over panels, text or controls).
// Injected into the dashboard page once by dashboard.py; runs in the page itself.
(() => {
  if (document.getElementById("friday-cubes")) return;

  const CELL = 44;       // matches the HUD grid size
  const RADIUS = 150;    // how far from the cursor cubes react
  const LIFT = 12;       // how high a cube rises, in pixels
  const EASE = 0.12;     // how quickly cubes follow the cursor
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

  // A small speckled tile, repeated over every cube face for a brushed-metal texture.
  const grain = document.createElement("canvas");
  grain.width = grain.height = 64;
  const g = grain.getContext("2d");
  for (let i = 0; i < 1100; i++) {
    const light = Math.random() > 0.55;
    g.fillStyle = light ? `rgba(140,225,240,${0.03 + Math.random() * 0.07})` : `rgba(0,0,0,${0.08 + Math.random() * 0.12})`;
    g.fillRect((Math.random() * 64) | 0, (Math.random() * 64) | 0, 1, 1 + ((Math.random() * 2) | 0));
  }
  let texture;

  let width, height, cols, rows, lift;
  let mouseX = -1e4, mouseY = -1e4, overBackground = false, running = false;

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cols = Math.ceil(width / CELL) + 1;
    rows = Math.ceil(height / CELL) + 1;
    lift = new Float32Array(cols * rows);
    texture = ctx.createPattern(grain, "repeat");
    start();
  }

  function cube(x, y, h) {
    const size = CELL - 3;
    const o = h * LIFT;
    const tx = x - o, ty = y - o;
    if (o > 0.3) {
      // Side faces join the raised top face back down to the floor.
      ctx.fillStyle = "rgba(3,9,18,.95)";
      ctx.beginPath();
      ctx.moveTo(tx + size, ty); ctx.lineTo(x + size, y); ctx.lineTo(x + size, y + size); ctx.lineTo(tx + size, ty + size);
      ctx.fill();
      ctx.fillStyle = "rgba(7,17,31,.95)";
      ctx.beginPath();
      ctx.moveTo(tx, ty + size); ctx.lineTo(tx + size, ty + size); ctx.lineTo(x + size, y + size); ctx.lineTo(x, y + size);
      ctx.fill();
    }
    const top = ctx.createLinearGradient(tx, ty, tx + size, ty + size);
    top.addColorStop(0, `rgba(${18 + h * 30},${36 + h * 90},${58 + h * 95},${0.55 + h * 0.35})`);
    top.addColorStop(1, `rgba(${9 + h * 12},${20 + h * 40},${36 + h * 50},${0.55 + h * 0.35})`);
    ctx.fillStyle = top;
    ctx.fillRect(tx, ty, size, size);
    ctx.fillStyle = texture;
    ctx.fillRect(tx, ty, size, size);
    ctx.strokeStyle = `rgba(45,226,230,${0.05 + h * 0.55})`;
    ctx.lineWidth = 1;
    if (h > 0.35) {
      ctx.shadowColor = "rgba(45,226,230,.6)";
      ctx.shadowBlur = 12 * h;
    }
    ctx.strokeRect(tx + 0.5, ty + 0.5, size - 1, size - 1);
    ctx.shadowBlur = 0;
  }

  function frame() {
    ctx.clearRect(0, 0, width, height);
    let moving = false;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const i = r * cols + c;
        const x = c * CELL, y = r * CELL;
        let target = 0;
        if (overBackground && !still) {
          const d = Math.hypot(x + CELL / 2 - mouseX, y + CELL / 2 - mouseY);
          target = d < RADIUS ? (1 - d / RADIUS) ** 2 : 0;
        }
        lift[i] += (target - lift[i]) * EASE;
        if (Math.abs(target - lift[i]) > 0.002) moving = true;
        cube(x, y, lift[i]);
      }
    }
    // Only keep animating while cubes are still moving; otherwise wait for the mouse.
    running = moving;
    if (moving) window.requestAnimationFrame(frame);
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
