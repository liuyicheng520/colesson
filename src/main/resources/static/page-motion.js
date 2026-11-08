(function () {
  if (window.ZkMotion) return;
  if (!document.body || document.body.classList.contains('auth-body')) return;
  if (!window.matchMedia('(pointer: fine)').matches) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  document.body.classList.add('has-pointer');

  var mx = 70, my = 18, tx = 70, ty = 18, raf = 0;
  function step() {
    mx += (tx - mx) * 0.12;
    my += (ty - my) * 0.12;
    document.body.style.setProperty('--mx', mx.toFixed(2) + '%');
    document.body.style.setProperty('--my', my.toFixed(2) + '%');
    if (Math.abs(tx - mx) > 0.08 || Math.abs(ty - my) > 0.08) {
      raf = requestAnimationFrame(step);
    } else {
      raf = 0;
    }
  }
  function kick() { if (!raf) raf = requestAnimationFrame(step); }

  window.addEventListener('pointermove', function (e) {
    tx = Math.min(100, Math.max(0, e.clientX / window.innerWidth * 100));
    ty = Math.min(100, Math.max(0, e.clientY / window.innerHeight * 100));
    kick();
  });

  var selector = '.card, .stat, .topbar, .home-stat, .home-tile, .stage-card, .quick a, .todo a, .panel';
  document.querySelectorAll(selector).forEach(function (el) {
    if (el.querySelector('table, input, textarea, select')) return;
    el.classList.add('ptr-ready');
    el.addEventListener('pointermove', function (e) {
      var r = el.getBoundingClientRect();
      el.style.setProperty('--gx', ((e.clientX - r.left) / r.width * 100).toFixed(1) + '%');
      el.style.setProperty('--gy', ((e.clientY - r.top) / r.height * 100).toFixed(1) + '%');
    });
    el.addEventListener('pointerenter', function () { el.classList.add('ptr-on'); });
    el.addEventListener('pointerleave', function () { el.classList.remove('ptr-on'); });
  });

  window.ZkMotion = true;
})();
