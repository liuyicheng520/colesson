/* ===== 鼠标互动效果（仅精确指针设备，尊重减弱动效偏好） ===== */
    (function () {
      if (!window.matchMedia('(pointer: fine)').matches) return;
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

      // 1) 标题逐字 pop
      document.querySelectorAll('.hero-copy .ch').forEach(function (ch) {
        ch.addEventListener('pointerenter', function () {
          if (ch.classList.contains('pop')) return;
          ch.classList.add('pop');
          ch.addEventListener('animationend', function () { ch.classList.remove('pop'); }, { once: true });
        });
      });

      // 2) Hero 聚光灯 + 光斑视差（--mx/--my 由 rAF 插值，画一层平滑跟随）
      const hero = document.querySelector('.hero-panel');
      if (hero) {
        hero.classList.add('has-pointer');
        let mx = 50, my = 50, tx = 50, ty = 50, raf = 0;
        const step = function () {
          mx += (tx - mx) * 0.14;
          my += (ty - my) * 0.14;
          hero.style.setProperty('--mx', mx.toFixed(2));
          hero.style.setProperty('--my', my.toFixed(2));
          if (Math.abs(tx - mx) > 0.05 || Math.abs(ty - my) > 0.05) {
            raf = requestAnimationFrame(step);
          } else {
            raf = 0;
          }
        };
        const kick = function () { if (!raf) raf = requestAnimationFrame(step); };
        hero.addEventListener('pointermove', function (e) {
          const r = hero.getBoundingClientRect();
          tx = Math.min(100, Math.max(0, (e.clientX - r.left) / r.width * 100));
          ty = Math.min(100, Math.max(0, (e.clientY - r.top) / r.height * 100));
          kick();
        });
        hero.addEventListener('pointerleave', function () { tx = 50; ty = 50; kick(); });
      }

      // 3) 身份卡 3D 倾斜 + 光泽跟随
      // 先把卡片内容包进 .tilt-face 视觉层：外框静止（命中区稳定），形变只作用于视觉层
      document.querySelectorAll('.choice-card').forEach(function (card) {
        if (card.querySelector('.tilt-face')) return;
        const face = document.createElement('span');
        face.className = 'tilt-face';
        while (card.firstChild) face.appendChild(card.firstChild);
        card.appendChild(face);
        card.classList.add('tilt-ready');
      });

      document.querySelectorAll('.choice-card').forEach(function (card) {
        let rx = 0, ry = 0, trx = 0, tryv = 0, gx = 50, gy = 50, tgx = 50, tgy = 50, raf = 0, hovering = false;
        const step = function () {
          rx += (trx - rx) * 0.16;
          ry += (tryv - ry) * 0.16;
          gx += (tgx - gx) * 0.2;
          gy += (tgy - gy) * 0.2;
          card.style.setProperty('--rx', rx.toFixed(2) + 'deg');
          card.style.setProperty('--ry', ry.toFixed(2) + 'deg');
          card.style.setProperty('--gx', gx.toFixed(1) + '%');
          card.style.setProperty('--gy', gy.toFixed(1) + '%');
          const active = hovering
            || Math.abs(trx - rx) > 0.05
            || Math.abs(tryv - ry) > 0.05
            || Math.abs(tgx - gx) > 0.2
            || Math.abs(tgy - gy) > 0.2;
          raf = active ? requestAnimationFrame(step) : 0;
        };
        const kick = function () { if (!raf) raf = requestAnimationFrame(step); };
        card.addEventListener('pointerenter', function () { hovering = true; kick(); });
        card.addEventListener('pointermove', function (e) {
          const r = card.getBoundingClientRect();
          const px = (e.clientX - r.left) / r.width;
          const py = (e.clientY - r.top) / r.height;
          tryv = (px - 0.5) * 9;
          trx = (0.5 - py) * 9;
          tgx = px * 100;
          tgy = py * 100;
          kick();
        });
        card.addEventListener('pointerleave', function () {
          hovering = false;
          trx = 0; tryv = 0; tgx = 50; tgy = 50;
          kick();
        });
      });
    })();
