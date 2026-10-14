(function () {
  function getQueryParam(name) {
    return new URLSearchParams(location.search).get(name) || '';
  }

  function getSafeReturnTo() {
    const returnTo = getQueryParam('returnTo');
    return returnTo.startsWith('/') ? returnTo : '';
  }

  function setMessage(msgEl, type, text) {
    if (!msgEl) return;
    msgEl.className = 'msg ' + type;
    msgEl.textContent = text;
  }

  function showSessionNote(sessionNote, sessionText, user, text) {
    if (!sessionNote || !sessionText || !user) return;
    sessionText.textContent = text;
    sessionNote.classList.add('show');
  }

  function resolveTarget(user) {
    const returnTo = getSafeReturnTo();
    if (returnTo
      && returnTo !== '/student/login.html'
      && returnTo !== '/login'
      && !returnTo.startsWith('/student/login')) {
      return returnTo;
    }
    if (user && user.homePath) {
      return user.homePath;
    }
    if (user && user.activeRole === 'student') {
      return '/student/home';
    }
    return '/login.html';
  }

  function reasonText(roleLabel) {
    const reason = getQueryParam('reason');
    if (reason === 'forbidden') {
      if (roleLabel && roleLabel.indexOf('管理') >= 0) {
        return '当前账号无管理权限。请返回教师工作台，或使用管理员账号登录。';
      }
      return '当前账号无权进入「' + roleLabel + '」入口。请先退出，再使用对应身份登录。';
    }
    if (reason === 'unauthorized') {
      return '登录状态已失效，请重新完成身份认证。';
    }
    return '';
  }

  function setAuthFormVisible(form, visible) {
    if (!form) return;
    form.style.display = visible ? '' : 'none';
    form.setAttribute('aria-hidden', visible ? 'false' : 'true');
  }

  function isWrongRoleSession(loggedUser, targetRole) {
    if (!loggedUser || !targetRole) return false;
    const active = String(loggedUser.activeRole || '').toLowerCase();
    const want = String(targetRole || '').toLowerCase();
    if (!active || !want) return false;
    // 学生入口允许「已登录学生但缺 edunexus_token」再输一次密码的特例，不视为错身份
    if (want === 'student' && active === 'student') return false;
    return active !== want;
  }

  function animateSwap() {
    const card = document.querySelector('.panel-card');
    if (!card) return;
    card.classList.remove('auth-switching');
    void card.offsetWidth;
    card.classList.add('auth-switching');
    setTimeout(function () {
      card.classList.remove('auth-switching');
    }, 320);
  }

  function bindAuxiliaryActions() {
    document.querySelectorAll('[data-feedback]').forEach(function (item) {
      item.addEventListener('click', function (e) {
        e.preventDefault();
        const message = item.getAttribute('data-feedback') || '该能力正在接入中';
        const msg = document.getElementById('authMessage');
        setMessage(msg, 'ok', message);
      });
    });

    document.querySelectorAll('[data-lang]').forEach(function (item) {
      item.addEventListener('click', function (e) {
        e.preventDefault();
        const lang = item.getAttribute('data-lang');
        const msg = document.getElementById('authMessage');
        setMessage(msg, 'ok', lang === 'en' ? 'English UI is being prepared.' : '当前为中文界面。');
      });
    });

    document.querySelectorAll('.role-switch-link').forEach(function (item) {
      item.addEventListener('click', animateSwap);
    });
  }

  function initLogoutAction(logoutEl, onDone) {
    if (!logoutEl) return;
    logoutEl.addEventListener('click', async function (e) {
      e.preventDefault();
      if (window.AppStore && window.AppStore.logout) {
        await window.AppStore.logout();
      }
      if (typeof onDone === 'function') {
        onDone();
      }
    });
  }

  async function initLogin(config) {
    const role = config.role;
    const roleLabel = window.AppStore.roleLabel(role);
    const form = document.getElementById('authForm');
    const msg = document.getElementById('authMessage');
    const sessionNote = document.getElementById('sessionNote');
    const sessionText = document.getElementById('sessionText');
    const returnHomeLink = document.getElementById('returnHomeLink');
    const logoutHere = document.getElementById('logoutHere');
    const submitBtn = document.getElementById('submitBtn');

    bindAuxiliaryActions();

    const initialReason = reasonText(roleLabel);
    if (initialReason) {
      setMessage(msg, 'err', initialReason);
    }

    const loggedUser = window.AppStore && window.AppStore.refreshCurrentUser
      ? await window.AppStore.refreshCurrentUser()
      : null;
    const hasStudentToken = !!localStorage.getItem('edunexus_token');
    if (loggedUser) {
      if (role === 'student' && !hasStudentToken && String(loggedUser.activeRole || '').toLowerCase() === 'student') {
        setAuthFormVisible(form, true);
        showSessionNote(
          sessionNote,
          sessionText,
          loggedUser,
          '当前账号：' + (loggedUser.username || '学生') + '。请再输入一次密码完成进入学生主页。'
        );
        if (returnHomeLink) {
          returnHomeLink.style.display = 'none';
        }
        setMessage(msg, 'err', '登录尚未完成，请再输入一次账号密码进入学生主页。');
      } else if (isWrongRoleSession(loggedUser, role)) {
        setAuthFormVisible(form, false);
        showSessionNote(
          sessionNote,
          sessionText,
          loggedUser,
          '当前账号：' + (loggedUser.username || '未命名用户') + '，身份：'
            + (window.AppStore ? window.AppStore.roleLabel(loggedUser.activeRole) : loggedUser.activeRole)
            + '。要进入' + roleLabel + '，请先退出当前账号再登录。'
        );
        if (returnHomeLink) {
          returnHomeLink.href = loggedUser.homePath || config.homePath || '/teacher/home.html';
          returnHomeLink.textContent = '返回当前工作台';
          returnHomeLink.style.display = '';
        }
        if (logoutHere) {
          logoutHere.textContent = '退出并切换到' + roleLabel;
        }
        setMessage(msg, 'err', '已登录其他身份，表单已隐藏。请退出后使用' + roleLabel + '账号登录。');
      } else {
        setAuthFormVisible(form, true);
        showSessionNote(
          sessionNote,
          sessionText,
          loggedUser,
          '当前账号：' + (loggedUser.username || '未命名用户') + '，当前身份：'
            + (window.AppStore ? window.AppStore.roleLabel(loggedUser.activeRole) : loggedUser.activeRole)
            + '。如需切换到' + roleLabel + '入口，请先退出并重新登录。'
        );
        if (returnHomeLink) {
          returnHomeLink.href = loggedUser.homePath || config.homePath || '/student/home';
          returnHomeLink.style.display = '';
        }
      }
    }

    initLogoutAction(logoutHere, function () {
      if (sessionNote) sessionNote.classList.remove('show');
      setAuthFormVisible(form, true);
      if (logoutHere) logoutHere.textContent = '退出当前账号';
      setMessage(msg, 'ok', '已退出当前账号，可以重新登录。');
    });

    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      const username = form.username.value.trim();
      const password = form.password.value;

      if (!username || !password) {
        setMessage(msg, 'err', '请输入账号和密码。');
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = config.loadingText || '提交中...';
      try {
        const ret = window.AppStore && window.AppStore.login
          ? await window.AppStore.login(username, password, role)
          : { ok: false, message: '登录服务未初始化' };
        if (!ret.ok) {
          setMessage(msg, 'err', ret.message || '登录失败。');
          return;
        }
        const hasToken = !!(ret.zhixuetiSynced || localStorage.getItem('edunexus_token'));
        if (role === 'student' && !hasToken) {
          setMessage(msg, 'err', '登录未完成：学生服务尚未就绪。请确认已用「启动智课共生」启动后，用同一账号密码再登一次。');
          return;
        }
        setMessage(msg, 'ok', config.successText || '登录成功，正在进入系统...');
        const target = resolveTarget(ret.user);
        setTimeout(function () {
          window.location.replace(target);
        }, 300);
      } catch (err) {
        setMessage(msg, 'err', err.message || '登录失败。');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = config.submitText || '立即登录';
      }
    });
  }

  async function initRegister(config) {
    const form = document.getElementById('authForm');
    const msg = document.getElementById('authMessage');
    const sessionNote = document.getElementById('sessionNote');
    const sessionText = document.getElementById('sessionText');
    const logoutHere = document.getElementById('logoutHere');
    const submitBtn = document.getElementById('submitBtn');

    bindAuxiliaryActions();

    const loggedUser = window.AppStore && window.AppStore.refreshCurrentUser
      ? await window.AppStore.refreshCurrentUser()
      : null;
    if (loggedUser) {
      setAuthFormVisible(form, false);
      showSessionNote(
        sessionNote,
        sessionText,
        loggedUser,
        '当前账号：' + (loggedUser.username || '未命名用户') + '。若需开通新账号，请先退出当前会话。'
      );
      if (logoutHere) {
        logoutHere.textContent = '退出后继续开通';
      }
      setMessage(msg, 'err', '已有登录会话，开通表单已隐藏。请先退出再开通新账号。');
    }

    initLogoutAction(logoutHere, function () {
      if (sessionNote) sessionNote.classList.remove('show');
      setAuthFormVisible(form, true);
      if (logoutHere) logoutHere.textContent = '退出当前账号';
      setMessage(msg, 'ok', '已退出当前账号，现在可以继续开通新账号。');
    });

    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      const username = form.username.value.trim();
      const password = form.password.value;
      const confirmPassword = form.confirmPassword.value;

      if (!username || !password || !confirmPassword) {
        setMessage(msg, 'err', '请完整填写账号开通信息。');
        return;
      }
      if (password.length < 6) {
        setMessage(msg, 'err', '密码至少需要 6 位。');
        return;
      }
      if (password !== confirmPassword) {
        setMessage(msg, 'err', '两次输入的密码不一致。');
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = config.loadingText || '提交中...';
      try {
        const ret = window.AppStore && window.AppStore.register
          ? await window.AppStore.register(username, password, config.role)
          : { ok: false, message: '注册服务未初始化' };
        if (!ret.ok) {
          setMessage(msg, 'err', ret.message || '开通失败。');
          return;
        }
        const hasToken = !!(ret.zhixuetiSynced || localStorage.getItem('edunexus_token'));
        if (config.role === 'student' && !hasToken) {
          // 宿主侧可能已写入账号；不再拆成「两套系统」，引导用同一账号再登完成进入
          setMessage(msg, 'err', '开通未完成：学生服务尚未就绪。请确认智课共生已完全启动后，到登录页用同一账号密码再登一次即可进入。');
          return;
        }
        setMessage(msg, 'ok', config.successText || '开通成功，正在进入系统...');
        const target = resolveTarget(ret.user);
        setTimeout(function () {
          window.location.replace(target);
        }, 300);
      } catch (err) {
        setMessage(msg, 'err', err.message || '开通失败。');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = config.submitText || '立即开通';
      }
    });
  }

  window.AuthPages = {
    initLogin: initLogin,
    initRegister: initRegister
  };
})();
