export const jarvisCoreVisualHtml = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Jarvis Core Visual - Scaled</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #050505; overflow: hidden; }
    canvas { display: block; }
    .hud { position: fixed; inset: 0; pointer-events: none; z-index: 10; }
    .scan-overlay {
      position: absolute; inset: 0;
      background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255, 80, 0, 0.015) 2px, rgba(255, 80, 0, 0.015) 4px);
    }
    @keyframes pulseRing {
      0% { transform: translate(-50%, -50%) scale(0.85); opacity: 0.4; }
      100% { transform: translate(-50%, -50%) scale(1.15); opacity: 0; }
    }
    .pulse-ring-container {
      position: absolute;
      top: 0; left: 0; width: 100%; height: 100%;
      pointer-events: none;
    }
    .pulse-ring {
      position: absolute; top: 50%; left: 50%;
      width: 104px; height: 104px; border-radius: 50%;
      border: 1px solid #ff660055;
      animation: pulseRing 3s ease-out infinite;
      pointer-events: none;
    }
    .pulse-ring:nth-child(2) { animation-delay: 1s; width: 143px; height: 143px; border-color: #ff440033; }
    .pulse-ring:nth-child(3) { animation-delay: 2s; width: 181px; height: 181px; border-color: #ff220022; }
  </style>
</head>
<body>
  <canvas id="c"></canvas>
  <div class="hud">
    <div class="scan-overlay"></div>
    <div class="pulse-ring-container" id="pulse-container">
      <div class="pulse-ring"></div>
      <div class="pulse-ring"></div>
      <div class="pulse-ring"></div>
    </div>
  </div>

  <script type="importmap">
  { "imports": {
      "three": "https://cdnjs.cloudflare.com/ajax/libs/three.js/0.162.0/three.module.min.js",
      "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.162.0/examples/jsm/"
  }}
  </script>
  <script type="module">
  import * as THREE from "three";
  import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
  import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
  import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
  import { OrbitControls } from "three/addons/controls/OrbitControls.js";

  // GLOBAL PARAMETERS
  const SF = 0.6492; // Scale factor
  const PX = -3.4; // Default horizontal position
  const PX_SPEAK_HIDDEN = 0.0; // Center position when speak mode is active and conversation is hidden
  const PX_SMOOTHING = 0.08;
  const BASE_SPEED_MULTIPLIER = 3.3;
  let currentPx = PX;
  let targetPx = PX;
  let speakingActive = false;
  let speakingBoost = 0;
  const speakingSpeedProfile = {
    // Per-component speaking speed levels (min 4, max 10).
    core: 5,
    rings: 10,
    ladders: 7,
    sparks: 6,
    spokes: 4,
    pulse: 7,
  };

  let _s = 42;
  function srnd() { _s ^= _s << 13; _s ^= _s >> 7; _s ^= _s << 17; return (_s >>> 0) / 4294967296; }
  function sr(a, b) { return a + srnd() * (b - a); }

  const NT = new Float32Array(1024);
  for (let i = 0; i < 1024; i++) NT[i] = Math.random() * 2 - 1;
  function n1(x) { const i = Math.floor(x) & 1023, f = x - Math.floor(x), t = f * f * (3 - 2 * f); return NT[i] * (1 - t) + NT[(i + 1) & 1023] * t; }
  function fbm(x, o = 4) { let v = 0, a = 0.5, fr = 1; for (let i = 0; i < o; i++) { v += n1(x * fr) * a; a *= 0.5; fr *= 2.1; } return v; }

  const canvas = document.getElementById("c");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setSize(innerWidth, innerHeight);
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.8;

  const scene = new THREE.Scene();
  
  // Container for the structure (kept at origin 0,0,0)
  const mainGroup = new THREE.Group();
  scene.add(mainGroup);

  scene.fog = new THREE.FogExp2(0x000000, 0.035 / SF);

  const camera = new THREE.PerspectiveCamera(52, innerWidth / innerHeight, 0.01, 1000);
  camera.position.set(0, 1.5, 14.0);

  // LENS SHIFT LOGIC: 
  // We override the projection matrix to shift the center of the view.
  // This moves the structure to the side without orbiting or changing its size.
  const applyLensShift = () => {
      camera.updateProjectionMatrix();
      // elements[8] is the horizontal projection center. 
      // A value of 1.0 shifts the scene center by half the screen width.
      camera.projectionMatrix.elements[8] = -currentPx / 10; 
      
      // Sync CSS HUD Pulse Rings
      const pulseContainer = document.getElementById("pulse-container");
      if (pulseContainer) {
          // Sync the CSS rings to match the 3D projection shift
          pulseContainer.style.transform = \`translateX(\${currentPx * 5}vw)\`;
      }
  };

  const updateTargetPxFromMode = (payload = {}) => {
    const speakModeOn = Boolean(payload.speakModeOn);
    const conversationHidden = Boolean(payload.conversationHidden);
    speakingActive = Boolean(payload.isSpeaking);
    targetPx = speakModeOn && conversationHidden ? PX_SPEAK_HIDDEN : PX;
  };

  window.addEventListener("message", (event) => {
    const data = event?.data;
    if (!data || typeof data !== "object" || data.type !== "jarvis-visual-mode") {
      return;
    }
    updateTargetPxFromMode(data.payload);
  });

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = 0.05;
  controls.autoRotate = true; controls.autoRotateSpeed = 0.5;
  controls.minDistance = 5 * SF; controls.maxDistance = 25;
  controls.target.set(0, 0, 0); // Always stay focused on the sphere at origin

  const C = { gold: 0xffaa00, amber: 0xff8800, orange: 0xff5500, red: 0xff2200, white: 0xffffff, hot: 0xffdd88 };
  const lm = (c, o = 0.9) => new THREE.LineBasicMaterial({ color: c, transparent: true, opacity: o, blending: THREE.AdditiveBlending, depthWrite: false });
  const mm = (c, o = 0.9) => new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: o, blending: THREE.AdditiveBlending, depthWrite: false });

  function buildLadder({ innerR, outerR, arcStart, arcEnd, rungCount, color, tiltX = 0, tiltY = 0, tiltZ = 0, opacity = 0.85, nOff = 0, extraChaos = false }) {
    const g = new THREE.Group();
    const S = 120, ipts = [], opts = [];
    
    const sInnerR = innerR * SF;
    const sOuterR = outerR * SF;

    for (let i = 0; i <= S; i++) {
      const t = i / S, a = arcStart + t * (arcEnd - arcStart);
      const dai = fbm(nOff + t * 5.7, 4) * 0.28, dao = fbm(nOff + 50 + t * 5.3, 4) * 0.28;
      const ri = sInnerR + fbm(nOff + 10 + t * 4.1, 4) * (0.55 * SF);
      const ro = sOuterR + fbm(nOff + 20 + t * 3.9, 4) * (0.6 * SF);
      const zi = fbm(nOff + 30 + t * 6, 3) * (0.35 * SF), zo = fbm(nOff + 40 + t * 5.5, 3) * (0.35 * SF);
      ipts.push(new THREE.Vector3(Math.cos(a + dai) * ri, Math.sin(a + dai) * ri, zi));
      opts.push(new THREE.Vector3(Math.cos(a + dao) * ro, Math.sin(a + dao) * ro, zo));
    }
    g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(ipts), lm(color, opacity)));
    g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(opts), lm(color, opacity)));
    
    for (let i = 0; i <= rungCount; i++) {
      const t0 = i / rungCount;
      const t = Math.min(1, Math.max(0, t0 + (srnd() - 0.5) * 0.08));
      const idx = Math.min(Math.floor(t * S), S);
      const p1 = ipts[idx].clone(), p2 = opts[idx].clone();
      const reach = 0.35 + srnd() * 0.65;
      const p2p = p1.clone().lerp(p2, reach);
      const ro2 = opacity * (0.35 + srnd() * 0.6);
      const rc = srnd() > 0.7 ? C.white : (srnd() > 0.5 ? C.hot : color);
      g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([p1, p2p]), lm(rc, ro2)));
      const dot = new THREE.Mesh(new THREE.SphereGeometry((0.02 + srnd() * 0.05) * SF, 5, 5), mm(srnd() > 0.4 ? C.white : color, 0.6 + srnd() * 0.35));
      dot.position.copy(p1); g.add(dot);
      if (srnd() > 0.55) {
        const perp = new THREE.Vector3(-(p2.y - p1.y), (p2.x - p1.x), 0).normalize().multiplyScalar((0.1 + srnd() * 0.25) * SF);
        const b1 = p1.clone().add(perp), b2 = p1.clone().sub(perp);
        g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([b1, b2]), lm(color, ro2 * 0.6)));
      }
      if (srnd() > 0.5) {
        const bs = p1.clone().lerp(p2p, 0.2 + srnd() * 0.6);
        const noise = new THREE.Vector3((srnd() - 0.5) * SF, (srnd() - 0.5) * SF, (srnd() - 0.5) * (0.6 * SF));
        const be = bs.clone().add(noise);
        const mid = bs.clone().lerp(be, 0.5).add(new THREE.Vector3((srnd() - 0.5) * (0.3 * SF), (srnd() - 0.5) * (0.3 * SF), 0));
        g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([bs, mid, be]), lm(color, opacity * 0.28)));
      }
      if (srnd() > 0.45) {
        const d2 = new THREE.Mesh(new THREE.SphereGeometry((0.015 + srnd() * 0.03) * SF, 5, 5), mm(C.white, 0.5));
        d2.position.copy(p2p); g.add(d2);
      }
    }
    const midPts = [], midR = (sInnerR + sOuterR) / 2;
    for (let i = 0; i <= 80; i++) {
      const t = i / 80, a = arcStart + t * (arcEnd - arcStart);
      const r = midR + fbm(nOff + 70 + t * 7, 4) * (0.65 * SF);
      const da = fbm(nOff + 80 + t * 5, 3) * 0.32;
      const z = fbm(nOff + 90 + t * 6, 3) * (0.5 * SF);
      midPts.push(new THREE.Vector3(Math.cos(a + da) * r, Math.sin(a + da) * r, z));
    }
    g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(midPts), lm(color, opacity * 0.42)));
    if (extraChaos || srnd() > 0.35) {
      for (let e = 0; e < 2; e++) {
        const xPts = [];
        const xR = sInnerR + srnd() * (sOuterR - sInnerR);
        for (let i = 0; i <= 60; i++) {
          const t = i / 60, a = arcStart + t * (arcEnd - arcStart);
          const r = xR + fbm(nOff + 120 + e * 50 + t * 8, 3) * (0.7 * SF);
          const da = fbm(nOff + 130 + e * 50 + t * 6, 2) * 0.4;
          const z = fbm(nOff + 140 + e * 50 + t * 5, 2) * (0.5 * SF);
          xPts.push(new THREE.Vector3(Math.cos(a + da) * r, Math.sin(a + da) * r, z));
        }
        g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(xPts), lm(color, opacity * 0.28)));
      }
    }
    g.rotation.set(tiltX, tiltY, tiltZ);
    return g;
  }

  const ladders = [];
  let ns = 0;
  function spawn(opts) {
    const m = buildLadder({ ...opts, nOff: ns++ * 17.3 });
    ladders.push({ mesh: m, speed: sr(0.0003, 0.0012), dir: srnd() > 0.5 ? 1 : -1, axis: ["x", "y", "z"][Math.floor(srnd() * 3)] });
    mainGroup.add(m);
  }

  const PI = Math.PI, TAU = PI * 2;
  [
    { innerR: 5.8, outerR: 7.2, arcStart: -0.6, arcEnd: 2.0, rungCount: 24, color: C.gold, tiltX: PI / 2, tiltY: 0, tiltZ: 0, extraChaos: true },
    { innerR: 5.8, outerR: 7.2, arcStart: 2.2, arcEnd: 4.8, rungCount: 24, color: C.gold, tiltX: PI / 2, tiltY: 0, tiltZ: 0, extraChaos: true },
    { innerR: 5.6, outerR: 6.9, arcStart: 4.9, arcEnd: 6.5, rungCount: 16, color: C.amber, tiltX: PI / 2, tiltY: 0, tiltZ: 0 },
    { innerR: 5.4, outerR: 6.8, arcStart: 0.3, arcEnd: 2.5, rungCount: 18, color: C.gold, tiltX: 0.42, tiltY: 0.25, tiltZ: PI * 0.55, extraChaos: true },
    { innerR: 5.4, outerR: 6.8, arcStart: 3.0, arcEnd: 5.2, rungCount: 18, color: C.amber, tiltX: 0.42, tiltY: 0.25, tiltZ: PI * 0.55 },
    { innerR: 5.4, outerR: 6.8, arcStart: 0.3, arcEnd: 2.5, rungCount: 18, color: C.gold, tiltX: -0.42, tiltY: -0.25, tiltZ: -PI * 0.55, extraChaos: true },
    { innerR: 5.4, outerR: 6.8, arcStart: 3.0, arcEnd: 5.2, rungCount: 18, color: C.amber, tiltX: -0.42, tiltY: -0.25, tiltZ: -PI * 0.55 },
    { innerR: 5.0, outerR: 6.8, arcStart: -0.5, arcEnd: 0.5, rungCount: 12, color: C.gold, tiltX: 0, tiltY: PI / 2, tiltZ: PI / 2 },
    { innerR: 5.0, outerR: 6.8, arcStart: 2.6, arcEnd: 3.6, rungCount: 12, color: C.gold, tiltX: 0, tiltY: PI / 2, tiltZ: PI / 2 },
    { innerR: 5.0, outerR: 6.8, arcStart: -0.5, arcEnd: 0.5, rungCount: 12, color: C.amber, tiltX: 0, tiltY: -PI / 2, tiltZ: PI / 2 },
    { innerR: 4.8, outerR: 6.5, arcStart: 0.2, arcEnd: 2.2, rungCount: 14, color: C.orange, tiltX: 1.25, tiltY: 0.55, tiltZ: 0.35, extraChaos: true },
    { innerR: 4.8, outerR: 6.5, arcStart: 0.2, arcEnd: 2.2, rungCount: 14, color: C.red, tiltX: -1.25, tiltY: -0.55, tiltZ: 0.35 },
    { innerR: 4.8, outerR: 6.5, arcStart: 3.5, arcEnd: 5.6, rungCount: 14, color: C.orange, tiltX: 0.95, tiltY: -1.1, tiltZ: 1.1, extraChaos: true },
    { innerR: 5.0, outerR: 6.3, arcStart: 1.0, arcEnd: 3.2, rungCount: 16, color: C.gold, tiltX: 0.65, tiltY: 1.6, tiltZ: 0.9 },
    { innerR: 5.2, outerR: 6.6, arcStart: 0.8, arcEnd: 2.6, rungCount: 13, color: C.amber, tiltX: 0.2, tiltY: 0.9, tiltZ: 1.8 },
    { innerR: 5.2, outerR: 6.6, arcStart: 3.2, arcEnd: 5.0, rungCount: 13, color: C.gold, tiltX: -0.2, tiltY: -0.9, tiltZ: 1.8, extraChaos: true },
  ].forEach((o) => spawn(o));

  [
    { innerR: 3.3, outerR: 4.7, arcStart: 0, arcEnd: PI * 0.95, rungCount: 18, color: C.gold, tiltX: PI / 2, tiltY: 0, tiltZ: 0.25, extraChaos: true },
    { innerR: 3.3, outerR: 4.7, arcStart: PI, arcEnd: PI * 1.95, rungCount: 18, color: C.amber, tiltX: PI / 2, tiltY: 0, tiltZ: 0.25, extraChaos: true },
    { innerR: 3.2, outerR: 4.6, arcStart: 0, arcEnd: PI * 0.85, rungCount: 15, color: C.gold, tiltX: 0.55, tiltY: 0.35, tiltZ: 0.85, extraChaos: true },
    { innerR: 3.2, outerR: 4.6, arcStart: 0, arcEnd: PI * 0.85, rungCount: 15, color: C.amber, tiltX: -0.55, tiltY: -0.35, tiltZ: 0.85 },
    { innerR: 3.0, outerR: 4.2, arcStart: 0.4, arcEnd: 2.3, rungCount: 13, color: C.red, tiltX: 1.1, tiltY: 0, tiltZ: 1.6 },
    { innerR: 3.0, outerR: 4.2, arcStart: 0.4, arcEnd: 2.3, rungCount: 13, color: C.red, tiltX: -1.1, tiltY: 0, tiltZ: -1.6 },
    { innerR: 3.3, outerR: 4.5, arcStart: 1.0, arcEnd: 3.6, rungCount: 16, color: C.gold, tiltX: 0.85, tiltY: 1.3, tiltZ: 0.55, extraChaos: true },
    { innerR: 3.0, outerR: 4.3, arcStart: 0, arcEnd: TAU, rungCount: 20, color: C.amber, tiltX: 0.4, tiltY: 0.7, tiltZ: 1.4 },
  ].forEach((o) => spawn(o));

  [
    { innerR: 1.6, outerR: 3.0, arcStart: 0, arcEnd: TAU, rungCount: 28, color: C.gold, tiltX: PI / 2, tiltY: 0, tiltZ: 0, extraChaos: true },
    { innerR: 1.6, outerR: 3.0, arcStart: 0, arcEnd: TAU, rungCount: 28, color: C.amber, tiltX: 0.75, tiltY: 0.55, tiltZ: 0, extraChaos: true },
    { innerR: 1.6, outerR: 3.0, arcStart: 0, arcEnd: TAU, rungCount: 28, color: C.red, tiltX: -0.75, tiltY: -0.55, tiltZ: 0, extraChaos: true },
    { innerR: 1.8, outerR: 2.9, arcStart: 0.2, arcEnd: 3.1, rungCount: 18, color: C.gold, tiltX: 0, tiltY: 0, tiltZ: 1.3, extraChaos: true },
    { innerR: 1.8, outerR: 2.9, arcStart: 3.4, arcEnd: 6.1, rungCount: 18, color: C.amber, tiltX: 0, tiltY: 0, tiltZ: 1.3, extraChaos: true },
    { innerR: 1.5, outerR: 2.6, arcStart: 0.5, arcEnd: 2.9, rungCount: 16, color: C.red, tiltX: 1.4, tiltY: 0.75, tiltZ: 0.5, extraChaos: true },
    { innerR: 1.5, outerR: 2.6, arcStart: 0, arcEnd: TAU, rungCount: 22, color: C.orange, tiltX: 0, tiltY: PI / 2, tiltZ: 0.3, extraChaos: true },
  ].forEach((o) => spawn(o));

  const ringGrp = new THREE.Group();
  function wRing(radius, tx, ty, tz, color, opacity, nOff) {
    const pts = [], S = 240;
    const sRadius = radius * SF;
    for (let i = 0; i <= S; i++) {
      const t = i / S, a = t * TAU;
      const r = sRadius + fbm(nOff + t * 7, 4) * (0.3 * SF);
      const da = fbm(nOff + 55 + t * 5, 3) * 0.15;
      const z = fbm(nOff + 105 + t * 4, 3) * (0.22 * SF);
      pts.push(new THREE.Vector3(Math.cos(a + da) * r, Math.sin(a + da) * r, z));
    }
    const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), lm(color, opacity));
    l.rotation.set(tx, ty, tz);
    return l;
  }
  [
    { r: 5.5, tx: PI / 2, ty: 0, tz: 0, c: C.gold, o: 0.8, n: 1.1 },
    { r: 5.5, tx: PI / 2, ty: 0, tz: 0.5, c: C.amber, o: 0.55, n: 2.3 },
    { r: 5.2, tx: 0.35, ty: 0.12, tz: 0, c: C.gold, o: 0.5, n: 3.7 },
    { r: 4.0, tx: PI * 0.6, ty: 0.22, tz: 0.45, c: C.amber, o: 0.55, n: 5.1 },
    { r: 6.5, tx: 0.85, ty: 0.55, tz: 0, c: C.red, o: 0.3, n: 6.5 },
    { r: 2.8, tx: 0.45, ty: PI * 0.3, tz: 1.1, c: C.red, o: 0.45, n: 7.9 },
    { r: 3.6, tx: PI * 0.4, ty: 0.7, tz: 0.6, c: C.gold, o: 0.4, n: 9.3 },
    { r: 7.0, tx: 0.15, ty: 0.05, tz: 0.2, c: C.amber, o: 0.2, n: 11.1 },
  ].forEach(({ r, tx, ty, tz, c, o, n }) => ringGrp.add(wRing(r, tx, ty, tz, c, o, n)));
  mainGroup.add(ringGrp);
  const ringMotions = ringGrp.children.map((_, index) => ({
    phase: sr(index * 0.3, index * 0.3 + TAU),
    speedFactor: 0.78 + index * 0.09,
    crossFactor: 0.62 + (index % 3) * 0.12,
  }));

  const spokeGrp = new THREE.Group();
  for (let i = 0; i < 38; i++) {
    const theta = (i / 38) * TAU, phi = Math.acos(2 * (i / 38) - 1);
    const dir = new THREE.Vector3(Math.sin(phi) * Math.cos(theta), Math.sin(phi) * Math.sin(theta), Math.cos(phi));
    const len = (2.5 + srnd() * 2.8) * SF, pts = [];
    for (let s = 0; s <= 14; s++) {
      const t = s / 14, p = dir.clone().multiplyScalar((0.85 * SF) + t * len);
      p.x += (srnd() - 0.5) * t * (0.35 * SF); p.y += (srnd() - 0.5) * t * (0.35 * SF); pts.push(p);
    }
    const sc = i % 4 === 0 ? C.red : (i % 3 === 0 ? C.gold : C.amber);
    spokeGrp.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), lm(sc, 0.12 + srnd() * 0.22)));
  }
  mainGroup.add(spokeGrp);

  const coreGrp = new THREE.Group();
  coreGrp.add(new THREE.Mesh(new THREE.SphereGeometry(0.28 * SF, 32, 32), new THREE.MeshBasicMaterial({ color: 0xffaa44, transparent: true, opacity: 0.33 })));
  const shells = [
    { r: 0.65, c: 0xffbb66, o: 0.21 }, { r: 1.1, c: 0xff8800, o: 0.12 }, { r: 1.8, c: 0xff4400, o: 0.06 }, { r: 2.5, c: 0xff2200, o: 0.03 },
  ].map(({ r, c, o }) => { const m = new THREE.Mesh(new THREE.SphereGeometry(r * SF, 32, 32), mm(c, o)); coreGrp.add(m); return m; });

  const crPts = [];
  const crRadius = 0.95 * SF;
  for (let i = 0; i <= 200; i++) { const a = (i / 200) * TAU; crPts.push(new THREE.Vector3(Math.cos(a) * crRadius, Math.sin(a) * crRadius, 0)); }
  const coreRing = new THREE.Line(new THREE.BufferGeometry().setFromPoints(crPts), lm(C.white, 0.21));
  coreRing.rotation.x = PI / 2; coreGrp.add(coreRing);

  const cr2pts = [];
  const baseR2 = 1.3 * SF;
  for (let i = 0; i <= 160; i++) { const a = (i / 160) * TAU, r = baseR2 + fbm(i * 0.05, 2) * (0.15 * SF); cr2pts.push(new THREE.Vector3(Math.cos(a) * r, Math.sin(a) * r, fbm(i * 0.08, 2) * (0.12 * SF))); }
  const cr2 = new THREE.Line(new THREE.BufferGeometry().setFromPoints(cr2pts), lm(C.gold, 0.18));
  cr2.rotation.x = PI / 2; cr2.rotation.z = 0.3; coreGrp.add(cr2);
  mainGroup.add(coreGrp);

  function sparks(count, rMin, rMax, color, size, opacity) {
    const pos = new Float32Array(count * 3);
    const srMin = rMin * SF, srMax = rMax * SF;
    for (let i = 0; i < count; i++) {
      const r = srMin + Math.random() * (srMax - srMin), th = Math.random() * TAU, ph = Math.acos(2 * Math.random() - 1);
      pos[i * 3] = r * Math.sin(ph) * Math.cos(th); pos[i * 3 + 1] = r * Math.sin(ph) * Math.sin(th); pos[i * 3 + 2] = r * Math.cos(ph);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    return new THREE.Points(g, new THREE.PointsMaterial({ color, size: size * SF, transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false }));
  }

  const sparkSystems = [
    sparks(5000, 5.5, 8.0, C.gold, 0.06, 0.55),
    sparks(2500, 3.0, 5.5, C.amber, 0.05, 0.45),
    sparks(1200, 1.5, 3.0, C.red, 0.045, 0.5),
    sparks(800, 6.8, 10.0, C.amber, 0.07, 0.22),
    sparks(600, 7.5, 11.0, C.orange, 0.08, 0.12),
    sparks(300, 0.3, 1.5, C.white, 0.04, 0.25),
  ];
  sparkSystems.forEach((s) => mainGroup.add(s));

  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  composer.addPass(new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 2.7, 0.5, 0.02));

  // Init lens shift on load
  applyLensShift();

  const clock = new THREE.Clock();
  function animate() {
    requestAnimationFrame(animate);
    const t = clock.getElapsedTime();
    const beat = 0.5 + 0.5 * Math.sin(t * BASE_SPEED_MULTIPLIER * 4.2);
    const beat2 = 0.5 + 0.5 * Math.sin(t * BASE_SPEED_MULTIPLIER * 2.1 + 1.5);

    currentPx += (targetPx - currentPx) * PX_SMOOTHING;
    applyLensShift();

    const pulseContainer = document.getElementById("pulse-container");
    if (pulseContainer) {
      pulseContainer.style.opacity = "0.55";
      pulseContainer.style.transform = \`translateX(\${currentPx * 5}vw) scale(1.0)\`;
    }

    shells[0].scale.setScalar(1 + beat * 0.3); shells[1].scale.setScalar(1 + beat * 0.18);
    shells[2].scale.setScalar(1 + beat2 * 0.1); shells[3].scale.setScalar(1 + beat2 * 0.06);
    shells[0].material.opacity = 0.11 + beat * 0.11; shells[1].material.opacity = 0.05 + beat * 0.07;
    shells[2].material.opacity = 0.02 + beat * 0.04; shells[3].material.opacity = 0.01 + beat2 * 0.02;

    coreRing.material.opacity = 0.15 + beat * 0.11;
    coreRing.rotation.z += BASE_SPEED_MULTIPLIER * 0.012;
    cr2.rotation.z += BASE_SPEED_MULTIPLIER * 0.007;
    coreGrp.scale.setScalar(1);
    mainGroup.rotation.z = 0;

    const rc = ringGrp.children;
    rc.forEach((ring, index) => {
      const dir = index % 2 === 0 ? 1 : -1;
      const motion = ringMotions[index];
      const spinBase = BASE_SPEED_MULTIPLIER * (0.001 + index * 0.00018);

      ring.rotation.z += dir * spinBase;
      ring.rotation.y += -dir * (spinBase * 0.72);
      ring.rotation.x += 0.00001 * Math.sin(t * BASE_SPEED_MULTIPLIER * (1.6 + index * 0.12) + motion.phase);
      ring.position.x += (0 - ring.position.x) * 0.1;
      ring.position.y += (0 - ring.position.y) * 0.1;
    });

    ladders.forEach(({ mesh, speed, dir, axis }) => {
      const speakingMultiplier = speakingActive ? speakingSpeedProfile.ladders : 1;
      const ladderStep = speed * BASE_SPEED_MULTIPLIER * speakingMultiplier;
      mesh.rotation[axis] += ladderStep * dir;
      mesh.rotation[axis === "y" ? "z" : "y"] += ladderStep * 0.25 * dir;
    });

    renderer.toneMappingExposure = 1.02 + beat * 0.18;

    sparkSystems.forEach((s, i) => {
      s.rotation.y += 0.0008 * BASE_SPEED_MULTIPLIER * (i % 2 ? 1 : -1);
      s.rotation.x += 0.0004 * BASE_SPEED_MULTIPLIER * (i % 3 ? 1 : -1);
      s.material.opacity = (i < 3 ? 0.42 : 0.2) + Math.sin(t * BASE_SPEED_MULTIPLIER * 2 + i) * 0.09;
    });

    spokeGrp.rotation.y += BASE_SPEED_MULTIPLIER * 0.001;
    controls.update();
    composer.render();
  }
  animate();

  window.addEventListener("resize", () => {
    camera.aspect = innerWidth / innerHeight;
    applyLensShift(); // Re-apply shift on resize
    renderer.setSize(innerWidth, innerHeight);
    composer.setSize(innerWidth, innerHeight);
  });
  </script>
</body>
</html>
`;