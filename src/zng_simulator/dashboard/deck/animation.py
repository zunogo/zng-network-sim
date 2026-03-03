"""Self-contained HTML/CSS/JS for the Battery Swapping Service Architecture
animated slide, rendered via st.html()."""

ARCHITECTURE_ANIMATION_HTML = """
<div style="font-family: 'Inter', -apple-system, sans-serif; background: transparent;
            color: #d1d5db; padding: 1.5rem; max-width: 800px; margin: 0 auto;">
  <style>
    @keyframes swapCollapse {
      0%   { transform: rotate(-0.8deg) translateY(0) scale(1, 1); opacity: 1; }
      100% { transform: rotate(-0.2deg) translateY(50px) scale(1.06, 0); opacity: 0; }
    }
    @keyframes batteryLift {
      0%   { transform: rotate(0.7deg) translateY(0) scale(1); }
      100% { transform: rotate(0.7deg) translateY(-45px) scale(1.05); }
    }
    .arch-layer {
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .arch-box {
      border: 3px solid #ffffff;
      border-radius: 15px;
      transform: rotate(-0.5deg);
      box-shadow: 5px 5px 15px rgba(255,255,255,0.1);
      padding: 24px;
      background: #000;
      max-width: 550px;
      margin: 0 auto;
    }
    .arch-title {
      font-family: 'Comic Sans MS', cursive, sans-serif;
      font-size: 1.3rem;
      font-weight: 700;
      color: #fff;
      text-align: center;
      margin-bottom: 20px;
    }
    .arch-inner {
      position: relative;
      min-height: 220px;
    }
    .layer-chargers {
      border: 2px dashed #ffffff;
      border-radius: 12px;
      padding: 16px;
      transform: rotate(0.5deg);
      box-shadow: 2px 2px 6px rgba(255,255,255,0.1);
      margin-bottom: 16px;
      background: #000;
      z-index: 1;
      position: relative;
    }
    .layer-swap {
      border: 2px dashed #ffffff;
      border-radius: 12px;
      padding: 16px;
      transform: rotate(-0.8deg);
      box-shadow: 2px 2px 6px rgba(255,255,255,0.1);
      background: #000;
      position: absolute;
      width: calc(100% - 0px);
      top: 70px;
      z-index: 1;
      transform-origin: top center;
    }
    .layer-swap.collapsed {
      animation: swapCollapse 0.8s ease-in-out forwards;
      pointer-events: none;
      z-index: 10;
    }
    .layer-battery {
      border: 2px dashed #ffffff;
      border-radius: 12px;
      padding: 16px;
      transform: rotate(0.7deg);
      box-shadow: 2px 2px 6px rgba(255,255,255,0.1);
      background: #000;
      position: relative;
      margin-top: 70px;
      z-index: 2;
    }
    .layer-battery.lifted {
      animation: batteryLift 0.8s ease-in-out forwards;
      transform-origin: bottom center;
    }
    .layer-battery.lifted .battery-label {
      color: #fde68a !important;
    }
    .layer-label {
      font-family: 'Comic Sans MS', cursive, sans-serif;
      font-size: 1rem;
      font-weight: 600;
      color: #fff;
      text-align: center;
    }
    .trigger-btn {
      display: block;
      margin: 24px auto 0;
      padding: 10px 28px;
      background: #fde68a;
      color: #000;
      font-weight: 700;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      font-size: 0.95rem;
      transition: background 0.2s;
    }
    .trigger-btn:hover { background: #facc15; }
    .trigger-btn:disabled {
      background: #4b5563;
      color: #9ca3af;
      cursor: default;
    }
    .desc-grid {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 12px;
      margin-top: 24px;
    }
    .desc-card {
      padding: 12px;
      border-radius: 8px;
      text-align: center;
    }
    .desc-card h4 {
      font-weight: 700;
      margin-bottom: 4px;
      font-size: 0.95rem;
    }
    .desc-card p {
      color: #d1d5db;
      font-size: 0.8rem;
      margin: 0;
    }
  </style>

  <h2 style="text-align:center; font-size:1.6rem; font-weight:700; margin-bottom:20px;">
    Battery Swapping Service Architecture
  </h2>

  <div class="arch-box">
    <div class="arch-title">Battery Swapping Service</div>
    <div class="arch-inner">
      <div class="layer-chargers arch-layer">
        <div class="layer-label" style="transform:rotate(-0.3deg);">Chargers</div>
      </div>
      <div class="layer-swap arch-layer" id="swap-layer">
        <div class="layer-label" style="transform:rotate(0.5deg);">
          Swap Station (or Manual Operations)
        </div>
      </div>
      <div class="layer-battery arch-layer" id="battery-layer">
        <div class="layer-label battery-label" style="transform:rotate(-0.4deg);">
          Battery Pack
        </div>
      </div>
    </div>
  </div>

  <button class="trigger-btn" id="anim-btn" onclick="triggerAnimation()">
    Show Zunogo Innovation
  </button>

  <div class="desc-grid">
    <div class="desc-card" style="background:rgba(30,58,138,0.2);">
      <h4 style="color:#60a5fa;">Chargers</h4>
      <p>Charging infrastructure for battery packs</p>
    </div>
    <div class="desc-card" style="background:rgba(88,28,135,0.2);">
      <h4 style="color:#c084fc;">Swap Station</h4>
      <p>Automated or manual battery exchange infrastructure</p>
    </div>
    <div class="desc-card" style="background:rgba(20,83,45,0.2);">
      <h4 style="color:#4ade80;">Battery Pack</h4>
      <p>Standardized, swappable energy storage units</p>
    </div>
  </div>

  <script>
    let animated = false;
    function triggerAnimation() {
      if (animated) return;
      animated = true;
      document.getElementById('swap-layer').classList.add('collapsed');
      document.getElementById('battery-layer').classList.add('lifted');
      document.querySelector('.battery-label').textContent = 'Zunogo Battery Pack';
      document.getElementById('anim-btn').disabled = true;
      document.getElementById('anim-btn').textContent = 'Zunogo collapses the Swap Station layer';
    }
  </script>
</div>
"""
