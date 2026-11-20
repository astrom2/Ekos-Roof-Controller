// Jarnan Observatory - roof controller page (served by the ESP itself).
// Talks to the ESPHome web_server: /events (SSE) and POST /<domain>/<name>/<action>.
(() => {
  const TRAVEL = 28;                       // s, same as travel_s in the YAML
  const HOLD_MS = 650;                     // press-and-hold time for open / close
  const N = {                              // entity names in the YAML
    open: 'Roof Open', close: 'Roof Close', stop: 'Roof Stop', restart: 'Roof Controller Restart',
    remote: 'Remote Enabled', swap: 'Swap Directions', state: 'Roof State',
    left: 'Roof Travel Left', position: 'Roof Position', wifi: 'Roof Controller WiFi', uptime: 'Roof Controller Uptime',
    markOpen: 'Mark Roof Open', markClosed: 'Mark Roof Closed', reset: 'Roof Controller Last Reset', heap: 'Roof Controller Free Memory',
  };
  const key = s => s.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');

  // ------------------------------------------------------------------ styles
  const css = `
:root{--bg:#0b1116;--panel:#131c23;--panel2:#1a252e;--line:#26343f;--ink:#eef3f5;--muted:#8fa3ad;
--open:#2fbf71;--close:#3d8bfd;--stop:#ff5a4e;--warn:#f5b041;--sky:#0d2238;--star:#cfe3ff;--roof:#c9d2d8;
--wall:#2a3944;--glow:rgba(47,191,113,.35);color-scheme:dark}
html.night{--bg:#070000;--panel:#120303;--panel2:#1a0505;--line:#3a0b0b;--ink:#ff5c5c;--muted:#a33a3a;
--open:#ff3b3b;--close:#d42a2a;--stop:#ff7070;--warn:#ff6b6b;--sky:#160202;--star:#ff4d4d;--roof:#7a1d1d;--wall:#2b0707;--glow:rgba(255,59,59,.25)}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink)}
body{font:16px/1.5 "Noto Sans Arabic","Segoe UI",Tahoma,system-ui,sans-serif;-webkit-tap-highlight-color:transparent}
esp-app{display:none}
.wrap{max-width:560px;margin:0 auto;padding:14px max(16px,env(safe-area-inset-left)) 40px max(16px,env(safe-area-inset-right));display:grid;gap:14px}
header{display:flex;align-items:center;justify-content:space-between;gap:10px}
h1{margin:0;font-size:1.25rem;font-weight:800}h1 small{display:block;font-size:.8rem;font-weight:400;color:var(--muted)}
.pill{display:flex;align-items:center;gap:6px;font-size:.8rem;color:var(--muted);background:var(--panel);border:1px solid var(--line);border-radius:99px;padding:5px 10px;white-space:nowrap}
.dot{width:9px;height:9px;border-radius:50%;background:var(--stop)}.on .dot{background:var(--open)}
.icon-btn{background:var(--panel);border:1px solid var(--line);color:var(--ink);border-radius:12px;width:42px;height:42px;font-size:1.2rem;cursor:pointer}
.card{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:16px}
.scene{border-radius:14px;overflow:hidden;background:var(--sky)}svg{display:block;width:100%;height:auto}
.status{display:flex;align-items:baseline;justify-content:space-between;margin-top:12px;gap:8px}
.status b{font-size:1.9rem;font-weight:800}.status span{color:var(--muted);font-size:.9rem;font-variant-numeric:tabular-nums}
.bar{height:8px;background:var(--panel2);border-radius:99px;overflow:hidden;margin-top:10px}
.bar i{display:block;height:100%;width:0;background:var(--warn);border-radius:99px;transition:width .6s linear}
.note{color:var(--muted);font-size:.78rem;margin-top:8px}
.actions{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.big{position:relative;overflow:hidden;border:0;border-radius:20px;min-height:118px;color:#fff;font-family:inherit;font-weight:800;font-size:1.45rem;line-height:1.2;cursor:pointer;
display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;touch-action:none;user-select:none;-webkit-user-select:none;transition:transform .12s,filter .2s}
.big small{font-size:.78rem;font-weight:500;opacity:.85}.big .ar{font-size:2rem;line-height:1}
.big:active{transform:scale(.98)}.big[disabled]{filter:grayscale(.7) brightness(.55);cursor:default}
.big .fill{position:absolute;inset:0;background:rgba(255,255,255,.28);transform:scaleX(0);transform-origin:right;pointer-events:none}
.b-open{background:linear-gradient(160deg,var(--open),color-mix(in srgb,var(--open) 70%,#000))}
.b-close{background:linear-gradient(160deg,var(--close),color-mix(in srgb,var(--close) 70%,#000))}
.b-stop{grid-column:1/-1;min-height:88px;background:linear-gradient(160deg,var(--stop),color-mix(in srgb,var(--stop) 65%,#000));flex-direction:row;gap:12px}
.moving .b-stop{box-shadow:0 0 0 4px color-mix(in srgb,var(--stop) 35%,transparent);animation:pulse 1.2s infinite}
@keyframes pulse{50%{box-shadow:0 0 0 9px color-mix(in srgb,var(--stop) 10%,transparent)}}
.row{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 0;border-top:1px solid var(--line)}
.row:first-of-type{border-top:0}.row div{min-width:0}.row b{display:block;font-weight:700}.row small{color:var(--muted);font-size:.8rem}
.sw{position:relative;width:58px;height:32px;flex:none;border-radius:99px;border:0;background:var(--panel2);box-shadow:inset 0 0 0 1px var(--line);cursor:pointer}
.sw::after{content:"";position:absolute;top:4px;right:4px;width:24px;height:24px;border-radius:50%;background:var(--muted);transition:.2s}
.sw[aria-checked=true]{background:var(--open)}.sw[aria-checked=true]::after{right:30px;background:#fff}
details summary{cursor:pointer;font-weight:700;list-style:none;display:flex;justify-content:space-between}details summary::after{content:"＋";color:var(--muted)}
details[open] summary::after{content:"－"}
.btn{background:var(--panel2);color:var(--ink);border:1px solid var(--line);border-radius:12px;padding:10px 14px;font-family:inherit;font-weight:600;font-size:.9rem;cursor:pointer}
.btn.danger{color:var(--stop)}
.log{direction:ltr;text-align:left;font:12px/1.5 ui-monospace,Menlo,Consolas,monospace;background:#05080b;color:#9fb3bd;border-radius:12px;padding:10px;max-height:260px;overflow:auto;white-space:pre-wrap;margin-top:10px}
html.night .log{background:#0a0000;color:#c33}
.log .i{color:#5ad18a}.log .w{color:#f5b041}.log .e{color:#ff6b6b}
.kv{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;font-size:.88rem;margin-top:10px}.kv dt{color:var(--muted)}.kv dd{margin:0;font-variant-numeric:tabular-nums}
.toast{position:fixed;left:50%;bottom:calc(18px + env(safe-area-inset-bottom));transform:translateX(-50%) translateY(140%);background:var(--ink);color:var(--bg);padding:10px 18px;border-radius:99px;font-weight:700;transition:transform .25s;z-index:9;max-width:90vw;text-align:center}
.toast.show{transform:translateX(-50%) translateY(0)}
input[type=file]{color:var(--muted);max-width:100%}
.prog{height:6px;background:var(--panel2);border-radius:9px;overflow:hidden;margin-top:8px}.prog i{display:block;height:100%;width:0;background:var(--close)}
#roof{transition:transform .6s linear}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
`;
  document.head.insertAdjacentHTML('beforeend',
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#0b1116">');
  const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
  document.documentElement.lang = 'ar'; document.documentElement.dir = 'rtl';
  document.title = 'سقف مرصد جرنان';
  try { if (localStorage.getItem('night') === '1') document.documentElement.classList.add('night'); } catch (e) {}

  // ------------------------------------------------------------------ page
  const stars = Array.from({ length: 26 }, (_, i) => {
    const x = (i * 73) % 340 + 10, y = (i * 37) % 70 + 8, r = (i % 3) * .4 + .6;
    return `<circle cx="${x}" cy="${y}" r="${r}" fill="var(--star)" opacity="${.35 + (i % 4) * .15}"/>`;
  }).join('');
  document.body.insertAdjacentHTML('afterbegin', `
<div class="wrap" id="app">
  <header>
    <h1>سقف مرصد جرنان<small>تحكم محلي · ESP8266</small></h1>
    <div style="display:flex;gap:8px;align-items:center">
      <div class="pill" id="conn"><span class="dot"></span><span id="connTxt">يتصل…</span></div>
      <button class="icon-btn" id="night" title="وضع الرصد الليلي (أحمر)" aria-label="وضع الرصد الليلي">☾</button>
    </div>
  </header>

  <section class="card">
    <div class="scene">
      <svg viewBox="0 0 360 190" role="img" aria-label="رسم السقف">
        ${stars}
        <rect x="0" y="168" width="360" height="22" fill="var(--panel2)"/>
        <rect x="70" y="92" width="190" height="76" fill="var(--wall)"/>
        <rect x="70" y="92" width="190" height="6" fill="color-mix(in srgb,var(--wall) 60%,#000)"/>
        <g fill="var(--muted)"><rect x="160" y="138" width="10" height="30"/><rect x="146" y="164" width="38" height="5" rx="2"/>
          <rect x="150" y="104" width="52" height="16" rx="5" transform="rotate(-28 165 128)"/></g>
        <rect x="262" y="96" width="92" height="5" rx="2" fill="var(--line)"/>
        <g id="roof"><rect x="66" y="74" width="198" height="20" rx="3" fill="var(--roof)"/>
          <path d="M66 74 L165 58 L264 74 Z" fill="var(--roof)" opacity=".85"/>
          <rect x="66" y="90" width="198" height="4" fill="#000" opacity=".2"/></g>
      </svg>
    </div>
    <div class="status"><b id="stateTxt">—</b><span id="leftTxt"></span></div>
    <div class="bar"><i id="bar"></i></div>
    <div class="note">الموقع محسوب من وقت الحركة (28 ثانية من مغلق إلى مفتوح). الكاميرا و Ekos هما التأكيد الحقيقي.</div>
  </section>

  <section class="actions" id="actions">
    <button class="big b-open" id="bOpen" aria-label="فتح السقف، اضغط مطولاً"><span class="fill"></span><span class="ar" dir="ltr">⇤ ⇥</span>فتح السقف<small>اضغط مطولاً</small></button>
    <button class="big b-close" id="bClose" aria-label="إغلاق السقف، اضغط مطولاً"><span class="fill"></span><span class="ar" dir="ltr">⇥ ⇤</span>إغلاق السقف<small>اضغط مطولاً</small></button>
    <button class="big b-stop" id="bStop"><span class="ar">■</span>إيقاف</button>
  </section>

  <section class="card">
    <div class="row"><div><b>ريموت 433MHz</b><small>يرجع مطفأً بعد كل انقطاع كهرباء</small></div>
      <button class="sw" id="swRemote" role="switch" aria-checked="false" aria-label="ريموت 433"></button></div>
    <details class="row" style="display:block"><summary>الإعدادات</summary>
      <div class="row" style="border-top:0"><div><b>عكس الفتح والإغلاق</b><small>لو زر «فتح» يقفل السقف، شغّل هذا المفتاح. يُحفظ في الجهاز.</small></div>
        <button class="sw" id="swSwap" role="switch" aria-checked="false" aria-label="عكس الفتح والإغلاق"></button></div>
      <div class="row"><div><b>تحديث البرنامج</b><small>ملف firmware.bin من الماك</small>
        <div style="margin-top:8px"><input type="file" id="fw" accept=".bin"></div><div class="prog"><i id="fwBar"></i></div></div>
        <button class="btn" id="fwBtn">رفع</button></div>
      <div class="row"><div><b>تصحيح الحالة</b><small>لو الحالة المعروضة خطأ. لا يحرّك السقف، فقط يصحح ما يتذكره الجهاز.</small>
        <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap"><button class="btn" id="mOpen">السقف مفتوح الآن</button><button class="btn" id="mClosed">السقف مغلق الآن</button></div></div></div>
      <div class="row"><div><b>إعادة تشغيل الجهاز</b><small>لا يحرّك السقف</small></div><button class="btn danger" id="rst">إعادة تشغيل</button></div>
      <dl class="kv"><dt>الواي فاي</dt><dd id="wifi">—</dd><dt>يعمل منذ</dt><dd id="up">—</dd><dt>آخر إعادة تشغيل</dt><dd id="rst2">—</dd><dt>الذاكرة الحرة</dt><dd id="heap">—</dd><dt>العنوان</dt><dd>${location.host}</dd></dl>
    </details>
    <details class="row" style="display:block"><summary>السجل</summary><div class="log" id="log"></div></details>
  </section>
</div>
<div class="toast" id="toast"></div>`);
  document.querySelectorAll('esp-app').forEach(e => e.remove());

  const $ = id => document.getElementById(id);
  const S = {};                                   // entity states by key
  let pos = 0.0;                                   // 0 closed .. 1 open (drawing)

  const toast = (t) => { const el = $('toast'); el.textContent = t; el.classList.add('show'); clearTimeout(toast.t); toast.t = setTimeout(() => el.classList.remove('show'), 2200); };

  // ------------------------------------------------------------------ REST
  async function act(domain, name, action) {
    const tryUrl = async (n) => fetch(`/${domain}/${encodeURIComponent(n)}/${action}`, { method: 'POST' });
    try {
      let r = await tryUrl(name);
      if (r.status === 404) r = await tryUrl(key(name));     // older ESPHome: object id
      if (!r.ok) throw new Error(r.status);
      return true;
    } catch (e) { toast('تعذّر الإرسال، تأكد من الاتصال'); return false; }
  }

  // ------------------------------------------------------------------ rendering
  const LABEL = { open: 'مفتوح', closed: 'مغلق', opening: 'يفتح…', closing: 'يُغلق…', stopped: 'متوقف', unknown: 'غير معروف' };
  function render() {
    const state = S[key(N.state)] || 'unknown';
    const left = +(S[key(N.left)] || 0);
    const moving = state === 'opening' || state === 'closing';
    const pp = S[key(N.position)];
    if (pp != null && state !== 'unknown') pos = Math.min(1, Math.max(0, pp / 100));
    else if (state === 'open') pos = 1; else if (state === 'closed' || state === 'unknown') pos = 0;
    const secs = Math.round(pos * TRAVEL);
    $('roof').style.transform = `translateX(${pos * 192}px)`;
    $('stateTxt').textContent = LABEL[state] || state;
    $('leftTxt').textContent = moving ? `${secs} من ${TRAVEL} ث · باقي ${Math.round(left)} ث`
      : state === 'stopped' ? `مفتوح ${secs} من ${TRAVEL} ث (${Math.round(pos * 100)}%)` : '';
    $('bar').style.width = state === 'unknown' ? '0%' : `${Math.round(pos * 100)}%`;
    $('bar').style.background = moving ? 'var(--warn)' : 'var(--open)';
    $('app').classList.toggle('moving', moving);
    $('bOpen').disabled = state === 'opening' || state === 'open';
    $('bClose').disabled = state === 'closing' || state === 'closed';
    $('bStop').disabled = !moving;
    $('bOpen').querySelector('small').textContent = state === 'opening' ? 'يفتح الآن' : state === 'open' ? 'مفتوح بالفعل' : (state === 'stopped' ? 'اضغط مطولاً للإكمال' : 'اضغط مطولاً');
    $('bClose').querySelector('small').textContent = state === 'closing' ? 'يُغلق الآن' : state === 'closed' ? 'مغلق بالفعل' : (state === 'stopped' ? 'اضغط مطولاً للإكمال' : 'اضغط مطولاً');
    const sw = (id, k) => $(id).setAttribute('aria-checked', S[key(k)] === true ? 'true' : 'false');
    sw('swRemote', N.remote); sw('swSwap', N.swap);
    const w = S[key(N.wifi)]; $('wifi').textContent = w != null ? `\u2066${Math.round(w)} dBm\u2069 ${w > -60 ? '(ممتاز)' : w > -72 ? '(جيد)' : '(ضعيف)'}` : '—';
    const u = +S[key(N.uptime)]; if (u) { const d = Math.floor(u / 86400), h = Math.floor(u % 86400 / 3600), m = Math.floor(u % 3600 / 60);
      $('up').textContent = (d ? d + ' يوم ' : '') + (h ? h + ' ساعة ' : '') + m + ' دقيقة'; }
  }

  const RESET_AR = [[/power|External System/i, 'انقطاع أو توصيل كهرباء'], [/Software|restart/i, 'إعادة تشغيل من البرنامج أو التحديث'],
    [/Watchdog|WDT/i, 'تعليق (Watchdog)'], [/Exception/i, 'خطأ في البرنامج'], [/Deep-Sleep/i, 'استيقاظ']];
  function renderDiag() {
    const r = S[key(N.reset)]; if (r != null) { const m = RESET_AR.find(([re]) => re.test(r)); $('rst2').textContent = (m ? m[1] + ' · ' : '') + r; }
    const h = S[key(N.heap)]; if (h != null) $('heap').textContent = `\u2066${Math.round(h / 1024 * 10) / 10} KB\u2069`;
  }

  // ------------------------------------------------------------------ events
  let es, alive = 0;
  function setConn(ok) { $('conn').classList.toggle('on', ok); $('connTxt').textContent = ok ? 'متصل' : 'غير متصل'; }
  function connect() {
    es = new EventSource('/events');
    es.addEventListener('ping', () => { alive = Date.now(); setConn(true); });
    es.addEventListener('state', (e) => {
      alive = Date.now(); setConn(true);
      let d; try { d = JSON.parse(e.data); } catch (x) { return; }
      const id = String(d.id || ''); const name = id.includes('/') ? id.split('/').slice(1).join('/') : id.replace(/^[a-z_]+-/, '');
      S[key(d.name || name)] = d.value !== undefined ? d.value : d.state;
      render(); renderDiag();
    });
    es.addEventListener('log', (e) => {
      const line = String(e.data).replace(/\x1b\[[0-9;]*m/g, '');
      const div = document.createElement('div');
      div.className = /^\[E\]|\[E\]\[/.test(line) ? 'e' : /\[W\]/.test(line) ? 'w' : /roof|Remote|Directions/.test(line) ? 'i' : '';
      div.textContent = line; const log = $('log'); log.appendChild(div);
      while (log.childElementCount > 120) log.firstChild.remove();
      log.scrollTop = log.scrollHeight;
    });
    es.onerror = () => setConn(false);
  }
  setInterval(() => { if (Date.now() - alive > 35000) setConn(false); }, 5000);

  // ------------------------------------------------------------------ press and hold
  function hold(btn, onDone) {
    const fill = btn.querySelector('.fill'); let t0 = 0, raf = 0, done = false;
    const frame = () => { const k = Math.min(1, (performance.now() - t0) / HOLD_MS); fill.style.transform = `scaleX(${k})`;
      if (k >= 1) { done = true; stop(); navigator.vibrate && navigator.vibrate(40); onDone(); } else raf = requestAnimationFrame(frame); };
    const start = (e) => { if (btn.disabled || e.button > 0) return; e.preventDefault(); done = false; t0 = performance.now(); raf = requestAnimationFrame(frame); btn.setPointerCapture && btn.setPointerCapture(e.pointerId); };
    const stop = () => { cancelAnimationFrame(raf); fill.style.transition = 'transform .25s'; fill.style.transform = 'scaleX(0)'; setTimeout(() => fill.style.transition = '', 260); };
    btn.addEventListener('pointerdown', start);
    ['pointerup', 'pointercancel', 'pointerleave'].forEach(ev => btn.addEventListener(ev, () => { if (!done) { stop(); if (ev === 'pointerup' && t0 && performance.now() - t0 < HOLD_MS) toast('اضغط مطولاً حتى يمتلئ الزر'); } t0 = 0; }));
    btn.addEventListener('keydown', (e) => { if ((e.key === 'Enter' || e.key === ' ') && !btn.disabled) { e.preventDefault(); onDone(); } });
    btn.addEventListener('contextmenu', e => e.preventDefault());
  }
  hold($('bOpen'), async () => { if (await act('button', N.open, 'press')) toast('أُرسل أمر الفتح'); });
  hold($('bClose'), async () => { if (await act('button', N.close, 'press')) toast('أُرسل أمر الإغلاق'); });
  $('bStop').addEventListener('click', async () => { if (await act('button', N.stop, 'press')) toast('أُرسل أمر الإيقاف'); });

  const toggle = (id, name, on, off) => $(id).addEventListener('click', async () => {
    const want = $(id).getAttribute('aria-checked') !== 'true';
    if (await act('switch', name, want ? 'turn_on' : 'turn_off')) toast(want ? on : off);
  });
  toggle('swRemote', N.remote, 'الريموت مفعّل', 'الريموت مطفأ');
  toggle('swSwap', N.swap, 'تم عكس الاتجاه، جرّب زر الفتح', 'رجع الاتجاه الأصلي');

  const mark = (id, name, msg) => $(id).addEventListener('click', async () => { if (await act('button', name, 'press')) toast(msg); });
  mark('mOpen', N.markOpen, 'تم: الجهاز يعتبر السقف مفتوحاً');
  mark('mClosed', N.markClosed, 'تم: الجهاز يعتبر السقف مغلقاً');

  let rstArmed = 0;
  $('rst').addEventListener('click', async () => {
    if (Date.now() - rstArmed > 3000) { rstArmed = Date.now(); $('rst').textContent = 'اضغط مرة ثانية للتأكيد'; setTimeout(() => $('rst').textContent = 'إعادة تشغيل', 3000); return; }
    if (await act('button', N.restart, 'press')) toast('الجهاز يعيد التشغيل…');
  });

  $('night').addEventListener('click', () => { const on = document.documentElement.classList.toggle('night');
    try { localStorage.setItem('night', on ? '1' : '0'); } catch (e) {} });

  $('fwBtn').addEventListener('click', () => {
    const f = $('fw').files[0]; if (!f) { toast('اختر ملف firmware.bin أولاً'); return; }
    if (!/\.bin$/i.test(f.name)) { toast('الملف لازم يكون .bin وليس .yaml'); return; }
    const fd = new FormData(); fd.append('update', f, f.name);
    const x = new XMLHttpRequest(); x.open('POST', '/update');
    x.upload.onprogress = (e) => { if (e.lengthComputable) $('fwBar').style.width = (e.loaded / e.total * 100) + '%'; };
    x.onload = () => { const ok = x.status === 200 && /success/i.test(x.responseText); toast(ok ? 'تم التحديث، الجهاز يعيد التشغيل' : 'فشل التحديث'); };
    x.onerror = () => toast('انقطع الاتصال أثناء الرفع'); x.send(fd); toast('يرفع البرنامج…');
  });

  render(); connect();
})();
