/* 自家人 · 流体动效运行时 v1.0
 * 零依赖，ES5+ 语法，可直接 <script src> 引入
 * 对齐 Apple 流体交互五要素：即时响应 / 连续运动 / 携带动量 / 边界阻力 / 可打断
 *
 * 用法（全站接入，每页两行）：
 *   <script src="../fluid-motion.js" defer></script>
 *   <script>Fluid.autobind()</script>
 * 或手动：
 *   Fluid.press(el)                     按压即时反馈
 *   Fluid.sheet(el, { open: false })    可拖拽底部抽屉
 *   Fluid.spring({ to, onUpdate })      通用弹簧
 */
(function (global) {
  'use strict';

  var doc = global.document;

  /* ---------- 环境探测 ---------- */
  var reduceMQ = global.matchMedia
    ? global.matchMedia('(prefers-reduced-motion: reduce)')
    : null;
  function reduced() { return !!(reduceMQ && reduceMQ.matches); }

  /* ---------- 状态存储：每个元素每把 key 独立保存 value / velocity ---------- */
  var store = new WeakMap();
  function state(el, key) {
    var m = store.get(el);
    if (!m) { m = {}; store.set(el, m); }
    if (!m[key]) m[key] = { value: null, v: 0, raf: 0 };
    return m[key];
  }

  /* ---------- 参数换算：阻尼比 + 响应时间 -> 刚度 k / 阻尼 c ----------
   * Apple 官方给的是 dampingRatio(ζ) 与 response(s)。
   * 这里按 5% 稳定判据换算： 3.0 = ζ · ωn · response
   *   ωn = 3.0 / (ζ · response)      k = ωn²      c = 2ζωn
   * 官方推荐值：sheet ζ=0.8 / 0.3s；移动缩放 ζ=1.0 / 0.4s；旋转 ζ=0.8 / 0.4s
   */
  function params(zeta, response) {
    var z = zeta == null ? 0.8 : zeta;
    var r = response == null ? 0.3 : response;
    var wn = 3.0 / (z * r);
    return { k: wn * wn, c: 2 * z * wn };
  }

  /* ---------- 苹果官方橡胶边界公式 ---------- */
  function rubber(over, dim, c) {
    c = c == null ? 0.55 : c;
    return (over * dim * c) / (dim + c * over);
  }

  /* ---------- 苹果官方动量投射公式 ---------- */
  function project(velocity, rate) {
    rate = rate == null ? 0.998 : rate;
    return (velocity / 1000) * (rate / (1 - rate));
  }

  /* ---------- 核心：可打断的弹簧积分器（半隐式欧拉，dt 限幅） ---------- */
  function spring(cfg) {
    var el = cfg.el;
    var st = state(el, cfg.key || 'default');
    if (st.raf) { cancelAnimationFrame(st.raf); st.raf = 0; }

    if (cfg.from != null) st.value = cfg.from;
    if (st.value == null) st.value = cfg.to;
    if (cfg.velocity != null) st.v = cfg.velocity;

    /* 减弱动效：直接落位，不做物理模拟 */
    if (reduced()) {
      st.value = cfg.to; st.v = 0;
      cfg.onUpdate(st.value, true);
      if (cfg.onComplete) cfg.onComplete();
      return;
    }

    var p = cfg.spring || params(cfg.zeta, cfg.response);
    var eps = cfg.epsilon == null ? 0.4 : cfg.epsilon;
    var minV = cfg.minVelocity == null ? 4 : cfg.minVelocity;
    var prev = global.performance.now();

    st.raf = requestAnimationFrame(function step(now) {
      var dt = Math.min((now - prev) / 1000, 1 / 30);
      prev = now;
      var a = -p.k * (st.value - cfg.to) - p.c * st.v;
      st.v += a * dt;
      st.value += st.v * dt;

      if (Math.abs(st.value - cfg.to) < eps && Math.abs(st.v) < minV) {
        st.value = cfg.to; st.v = 0; st.raf = 0;
        cfg.onUpdate(st.value, true);
        if (cfg.onComplete) cfg.onComplete();
        return;
      }
      cfg.onUpdate(st.value, false);
      st.raf = requestAnimationFrame(step);
    });
  }

  /* ---------- 按压即时反馈：pointerdown 当帧就动，不等抬起 ----------
   * 取代 :active —— :active 在移动端有 ~100ms 判定延迟，且不可打断
   * 按下走临界阻尼（干脆），抬起走欠阻尼（轻回弹），符合 Apple 手感
   */
  function press(el, opts) {
    opts = opts || {};
    var to = opts.scale == null ? 0.96 : opts.scale;
    var prop = opts.property || 'scale';

    function render(v) {
      if (prop === 'scale') {
        el.style.transform = 'scale(' + v + ')';
      } else {
        el.style.transform = 'translate3d(0,' + v + 'px,0)';
      }
    }

    function down(e) {
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      spring({
        el: el, key: 'press', to: to, from: 1,
        zeta: 1.0, response: 0.12, epsilon: 0.004, minVelocity: 0.05,
        onUpdate: render
      });
    }
    function up() {
      spring({
        el: el, key: 'press', to: 1,
        zeta: 0.6, response: 0.32, epsilon: 0.004, minVelocity: 0.05,
        onUpdate: function (v, done) {
          render(v);
          if (done) el.style.transform = '';
        }
      });
    }

    el.addEventListener('pointerdown', down);
    el.addEventListener('pointerup', up);
    el.addEventListener('pointercancel', up);
    el.addEventListener('pointerleave', up);
    el.style.willChange = 'transform';
  }

  /* ---------- 可拖拽底部抽屉 ----------
   * 手指全程 1:1 跟随；松手移交速度；动量投射决定吸附点；越过边界走橡胶缓冲
   */
  function sheet(el, opts) {
    opts = opts || {};
    var scrim = opts.scrim || null;
    var onToggle = opts.onToggle || null;
    var st = state(el, 'sheet');
    var H = 0, dragging = false, sy = 0, sp = 0, pv = 0, pt = 0, opened = false;

    function measure() { H = el.offsetHeight || 1; }
    function render(v) {
      el.style.transform = 'translate3d(0,' + v + 'px,0)';
      if (scrim) {
        scrim.style.opacity = String(Math.max(0, Math.min(1, 1 - v / H)));
        scrim.style.pointerEvents = v < H - 1 ? 'auto' : 'none';
      }
    }

    measure();
    if (st.value == null) st.value = opts.open ? 0 : H;
    opened = st.value < H / 2;
    render(st.value);

    el.style.willChange = 'transform';
    el.style.touchAction = 'none';
    if (scrim && scrim.addEventListener) {
      scrim.addEventListener('click', function () { api.close(); });
    }

    function animate(to, velocity) {
      opened = to < H / 2;
      if (onToggle) onToggle(opened);
      spring({
        el: el, key: 'sheet', to: to, velocity: velocity,
        zeta: opts.zeta == null ? 0.8 : opts.zeta,
        response: opts.response == null ? 0.3 : opts.response,
        epsilon: 0.5, minVelocity: 5,
        onUpdate: render
      });
    }

    el.addEventListener('pointerdown', function (e) {
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      measure();
      if (st.raf) { cancelAnimationFrame(st.raf); st.raf = 0; }
      dragging = true;
      sy = e.clientY;
      sp = st.value;
      pv = st.value;
      pt = global.performance.now();
      st.v = 0;
      el.style.cursor = 'grabbing';
      if (el.setPointerCapture) el.setPointerCapture(e.pointerId);
    });

    el.addEventListener('pointermove', function (e) {
      if (!dragging) return;
      var raw = sp + (e.clientY - sy);
      if (raw < 0) raw = -rubber(-raw, H);
      else if (raw > H) raw = H + rubber(raw - H, H * 0.6);
      st.value = raw;
      var n = global.performance.now();
      var d = Math.max(n - pt, 1);
      st.v = (st.value - pv) / (d / 1000);
      pv = st.value; pt = n;
      render(st.value);
    });

    function end() {
      if (!dragging) return;
      dragging = false;
      el.style.cursor = '';
      /* 速度移交：用苹果官方投射公式预测落点，再看落点离哪端更近 */
      var projected = st.value + project(st.v);
      var shouldOpen = projected < H * 0.5;
      /* 高速轻扫直接判定，不看位置 */
      if (st.v < -700) shouldOpen = true;
      if (st.v > 700) shouldOpen = false;
      animate(shouldOpen ? 0 : H, st.v);
    }
    el.addEventListener('pointerup', end);
    el.addEventListener('pointercancel', end);
    global.addEventListener('resize', function () {
      measure();
      if (st.raf) return;
      st.value = opened ? 0 : H;
      render(st.value);
    });

    var api = {
      open: function () { measure(); animate(0); },
      close: function () { measure(); animate(H); },
      toggle: function () { measure(); animate(st.value < H / 2 ? H : 0); },
      get isOpen() { return opened; }
    };
    return api;
  }

  /* ---------- 自动绑定：给全站页面加两行即可生效 ----------
   * [data-fluid-press]                  任意元素 -> 按压反馈
   * [data-fluid-sheet]                  底部抽屉容器
   * [data-fluid-sheet-scrim]            与之配套的遮罩
   * [data-fluid-open]  / [close] / [toggle]  触发按钮，值为目标选择器
   */
  function autobind(root) {
    root = root || doc;
    var list = root.querySelectorAll('[data-fluid-press]');
    for (var i = 0; i < list.length; i++) {
      press(list[i], {
        scale: parseFloat(list[i].getAttribute('data-fluid-press')) || 0.96
      });
    }

    var sheets = root.querySelectorAll('[data-fluid-sheet]');
    for (var j = 0; j < sheets.length; j++) {
      var el = sheets[j];
      var scrimSel = el.getAttribute('data-fluid-sheet-scrim');
      var inst = sheet(el, {
        open: el.getAttribute('data-fluid-sheet') === 'open',
        scrim: scrimSel ? root.querySelector(scrimSel) : null
      });
      bindTriggers(root, '[data-fluid-open="' + sel(el) + '"]', function () { inst.open(); });
      bindTriggers(root, '[data-fluid-close="' + sel(el) + '"]', function () { inst.close(); });
      bindTriggers(root, '[data-fluid-toggle="' + sel(el) + '"]', function () { inst.toggle(); });
    }
  }

  function bindTriggers(root, selector, fn) {
    var list = root.querySelectorAll(selector);
    for (var i = 0; i < list.length; i++) list[i].addEventListener('click', fn);
  }
  function sel(el) {
    return el.id ? '#' + el.id : el.getAttribute('data-fluid-sheet');
  }

  global.Fluid = {
    spring: spring,
    press: press,
    sheet: sheet,
    autobind: autobind,
    params: params,
    rubber: rubber,
    project: project,
    reduced: reduced
  };
})(window);
