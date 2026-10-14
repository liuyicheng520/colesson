(function () {
  const STORE_KEY = 'ai_teacher_store_v1';
  const AUTH_USER_KEY = 'ai_teacher_auth_user_v2';
  const ROLE_META = {
    teacher: {
      label: '教师',
      loginPath: '/teacher/login.html',
      registerPath: '/teacher/register.html',
      homePath: '/teacher/home.html'
    },
    student: {
      label: '学生',
      loginPath: '/student/login.html',
      registerPath: '/student/register.html',
      homePath: '/student/home'
    },
    admin: {
      label: '管理员',
      loginPath: '/admin/login',
      registerPath: '',
      homePath: '/admin/home.html'
    }
  };

  function now() {
    return new Date().toISOString();
  }

  function normalizeRole(role) {
    const value = String(role || '').trim().toLowerCase();
    return ROLE_META[value] ? value : '';
  }

  function roleLabel(role) {
    const normalized = normalizeRole(role);
    return normalized ? ROLE_META[normalized].label : '未分配';
  }

  function roleLoginPath(role) {
    const normalized = normalizeRole(role);
    return normalized ? ROLE_META[normalized].loginPath : '/login.html';
  }

  function roleRegisterPath(role) {
    const normalized = normalizeRole(role);
    return normalized && ROLE_META[normalized].registerPath ? ROLE_META[normalized].registerPath : '/register.html';
  }

  function roleHomePath(role) {
    const normalized = normalizeRole(role);
    return normalized ? ROLE_META[normalized].homePath : '/teacher/home.html';
  }

  function normalizeUser(user) {
    if (!user) {
      return null;
    }
    const roles = Array.isArray(user.roles)
      ? user.roles.map(normalizeRole).filter(Boolean)
      : [];
    const fallbackRole = roles[0] || 'teacher';
    const activeRole = normalizeRole(user.activeRole) || fallbackRole;
    return {
      username: user.username || '',
      loginAt: user.loginAt || '',
      roles: roles.length ? roles : [fallbackRole],
      activeRole: activeRole,
      homePath: user.homePath || roleHomePath(activeRole),
      adminLevel: user.adminLevel || '',
      disabled: !!user.disabled
    };
  }

  function isAuthPortalPath(pathname) {
    const path = String(pathname || '');
    return path.endsWith('/login.html')
      || path.endsWith('/register.html')
      || path.endsWith('/teacher/login.html')
      || path.endsWith('/teacher/register.html')
      || path.endsWith('/student/login.html')
      || path.endsWith('/student/register.html')
      || path.endsWith('/admin/login');
  }

  function loadStore() {
    try {
      const raw = localStorage.getItem(STORE_KEY);
      if (!raw) {
        return { history: [], projects: [] };
      }
      const parsed = JSON.parse(raw);
      return {
        history: Array.isArray(parsed.history) ? parsed.history : [],
        projects: Array.isArray(parsed.projects) ? parsed.projects : []
      };
    } catch (e) {
      return { history: [], projects: [] };
    }
  }

  function saveStore(data) {
    localStorage.setItem(STORE_KEY, JSON.stringify(data));
  }

  function readCachedUser() {
    try {
      const raw = localStorage.getItem(AUTH_USER_KEY);
      return raw ? normalizeUser(JSON.parse(raw)) : null;
    } catch (e) {
      return null;
    }
  }

  function writeCachedUser(user) {
    const normalized = normalizeUser(user);
    if (!normalized) {
      localStorage.removeItem(AUTH_USER_KEY);
      return;
    }
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(normalized));
  }

  async function requestJson(url, options) {
    const response = await fetch(url, {
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      ...options
    });
    const payload = await response.json().catch(function () {
      return { code: 1, message: '服务返回格式异常' };
    });
    if (!response.ok || payload.code !== 0) {
      // 会话过期/无效：统一跳登录页（SPA 页由各自守卫处理）
      if (response.status === 401 && !location.pathname.includes('login')) {
        var loginPage = location.pathname.indexOf('/teacher/') === 0 ? '/teacher/login.html'
          : location.pathname.indexOf('/admin/') === 0 ? '/admin/login'
          : '/login.html';
        location.href = loginPage + '?returnTo=' + encodeURIComponent(location.pathname);
        throw new Error('登录已过期，正在跳转…');
      }
      throw new Error(payload.message || '请求失败');
    }
    return payload;
  }

  function addHistory(type, title, detail) {
    const s = loadStore();
    const user = currentUser();
    s.history.unshift({
      id: Date.now() + '_' + Math.random().toString(16).slice(2),
      ts: now(),
      type: type,
      title: title,
      detail: detail || '',
      username: user ? user.username : ''
    });
    s.history = s.history.slice(0, 200);
    saveStore(s);
  }

  function getCurrentLocation() {
    return location.pathname + location.search + location.hash;
  }

  function buildUrlWithParams(path, params) {
    const url = new URL(path, location.origin);
    Object.keys(params || {}).forEach(function (key) {
      const value = params[key];
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, value);
      }
    });
    return url.pathname + url.search + url.hash;
  }

  function escapeHtml(value) {
    return String(value || '').replace(/[&<>"']/g, function (ch) {
      return {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[ch];
    });
  }

  function redirectToLogin(role, options) {
    const opts = options || {};
    const target = buildUrlWithParams(roleLoginPath(role), {
      returnTo: opts.returnTo || getCurrentLocation(),
      reason: opts.reason || ''
    });
    location.href = target;
  }

  function redirectToHome(user) {
    const normalized = normalizeUser(user);
    const target = normalized ? normalized.homePath || roleHomePath(normalized.activeRole) : '/login.html';
    location.href = target;
  }

  async function addProject(name, meta, options) {
    const extra = options || {};
    const payload = await requestJson('/projects-api', {
      method: 'POST',
      body: JSON.stringify({
        name: name,
        meta: meta || '',
        subjectMode: extra.subjectMode || 'general',
        courseType: extra.courseType || '',
        programmingLanguage: extra.programmingLanguage || '',
        teachingGoal: extra.teachingGoal || ''
      })
    });
    addHistory('project', '创建项目', name || '未命名项目');
    return payload.data && payload.data.project ? payload.data.project : null;
  }

  const ZHIXUETI_TOKEN_KEY = 'edunexus_token';
  const ZHIXUETI_REFRESH_KEY = 'edunexus_refresh_token';

  function clearZhixuetiTokens() {
    try {
      localStorage.removeItem(ZHIXUETI_TOKEN_KEY);
      localStorage.removeItem(ZHIXUETI_REFRESH_KEY);
    } catch (e) { /* ignore */ }
  }

  function storeZhixuetiTokens(data) {
    if (!data || !data.access_token) return false;
    localStorage.setItem(ZHIXUETI_TOKEN_KEY, data.access_token);
    if (data.refresh_token) {
      localStorage.setItem(ZHIXUETI_REFRESH_KEY, data.refresh_token);
    }
    return true;
  }

  /** 学生开通/登录后领取学生端 JWT（同域 /api/v1，对外仍是一套智课共生账号） */
  async function bridgeZhixuetiStudentAuth(username, password) {
    async function postJson(url, body) {
      const controller = new AbortController();
      const timer = setTimeout(function () { controller.abort(); }, 12000);
      try {
        const response = await fetch(url, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: controller.signal
        });
        const payload = await response.json().catch(function () {
          return { code: 1, message: '学生服务返回异常' };
        });
        return { ok: response.ok && payload.code === 0, payload: payload };
      } finally {
        clearTimeout(timer);
      }
    }

    async function once() {
      let syncResult = await postJson('/api/v1/auth/sync-student', {
        username: username,
        password: password
      });
      if (syncResult.ok && storeZhixuetiTokens(syncResult.payload.data)) {
        return true;
      }
      let loginResult = await postJson('/api/v1/auth/login', {
        username: username,
        password: password
      });
      if (loginResult.ok && storeZhixuetiTokens(loginResult.payload.data)) {
        return true;
      }
      await postJson('/api/v1/auth/register', {
        username: username,
        password: password,
        nickname: username,
        user_type: 1
      });
      loginResult = await postJson('/api/v1/auth/login', {
        username: username,
        password: password
      });
      return loginResult.ok && storeZhixuetiTokens(loginResult.payload.data);
    }

    for (let i = 0; i < 3; i++) {
      try {
        if (await once()) return true;
      } catch (e) {
        // retry
      }
      await new Promise(function (r) { setTimeout(r, 800 * (i + 1)); });
    }
    return false;
  }

  async function register(username, password, role) {
    const normalizedRole = normalizeRole(role);
    const payload = await requestJson('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username: username, password: password, role: normalizedRole })
    });
    const user = normalizeUser(payload.data && payload.data.user ? payload.data.user : null);
    writeCachedUser(user);
    let zhixuetiSynced = false;
    if (normalizedRole === 'student') {
      zhixuetiSynced = !!(payload.data && storeZhixuetiTokens(payload.data.zhixueti));
      if (!zhixuetiSynced) {
        try {
          zhixuetiSynced = !!(await withTimeout(bridgeZhixuetiStudentAuth(username, password), 45000));
        } catch (e) {
          zhixuetiSynced = false;
        }
      }
    }
    addHistory('auth', '注册成功', (user ? user.username : username) + ' / ' + roleLabel(normalizedRole));
    return { ok: true, user: user, zhixuetiSynced: zhixuetiSynced };
  }

  async function login(username, password, entryRole) {
    const normalizedRole = normalizeRole(entryRole);
    const payload = await requestJson('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username: username, password: password, entryRole: normalizedRole })
    });
    const user = normalizeUser(payload.data && payload.data.user ? payload.data.user : null);
    writeCachedUser(user);
    const needZhixueti = normalizedRole === 'student' || (user && user.activeRole === 'student');
    let zhixuetiSynced = false;
    if (needZhixueti) {
      zhixuetiSynced = !!(payload.data && storeZhixuetiTokens(payload.data.zhixueti));
      if (!zhixuetiSynced) {
        try {
          zhixuetiSynced = !!(await withTimeout(bridgeZhixuetiStudentAuth(username, password), 45000));
        } catch (e) {
          zhixuetiSynced = false;
        }
      }
    }
    addHistory('auth', '登录成功', (user ? user.username : username) + ' / ' + roleLabel(normalizedRole));
    return { ok: true, user: user, zhixuetiSynced: zhixuetiSynced };
  }

  function withTimeout(promise, ms) {
    return Promise.race([
      promise,
      new Promise(function (_, reject) {
        setTimeout(function () {
          reject(new Error('zhixueti_bridge_timeout'));
        }, ms);
      })
    ]);
  }

  async function logout() {
    try {
      await requestJson('/auth/logout', {
        method: 'POST',
        body: JSON.stringify({})
      });
    } finally {
      const user = currentUser();
      if (user) addHistory('auth', '退出登录', user.username + ' / ' + roleLabel(user.activeRole));
      writeCachedUser(null);
      clearZhixuetiTokens();
    }
  }

  async function refreshCurrentUser() {
    try {
      const payload = await requestJson('/auth/me', { method: 'GET', headers: undefined });
      const user = normalizeUser(payload.data && payload.data.user ? payload.data.user : null);
      writeCachedUser(user);
      return user;
    } catch (e) {
      writeCachedUser(null);
      return null;
    }
  }

  function hasAllowedRole(user, allowedRoles) {
    if (!user) {
      return false;
    }
    if (!Array.isArray(allowedRoles) || !allowedRoles.length) {
      return true;
    }
    return allowedRoles.map(normalizeRole).filter(Boolean).indexOf(user.activeRole) >= 0;
  }

  async function requireRole(allowedRoles, options) {
    const opts = options || {};
    const user = await refreshCurrentUser();
    if (!user) {
      if (!isAuthPortalPath(location.pathname)) {
        redirectToLogin(opts.loginRole || 'teacher', {
          returnTo: opts.returnTo || getCurrentLocation(),
          reason: 'unauthorized'
        });
      }
      return false;
    }
    if (!hasAllowedRole(user, allowedRoles)) {
      if (opts.redirectOnFail !== false) {
        redirectToLogin(opts.loginRole || user.activeRole || 'teacher', {
          returnTo: opts.returnTo || getCurrentLocation(),
          reason: 'forbidden'
        });
      }
      return false;
    }
    return true;
  }

  async function requireLogin(options) {
    return requireRole([], options);
  }

  function currentUser() {
    return readCachedUser();
  }

  function getHistory() {
    const s = loadStore();
    const user = currentUser();
    if (!user) return [];
    return s.history.filter(function (item) {
      return item.username === user.username;
    });
  }

  function clearHistory() {
    const s = loadStore();
    const user = currentUser();
    if (!user) return;
    s.history = s.history.filter(function (item) {
      return item.username !== user.username;
    });
    saveStore(s);
  }

  async function getProjects() {
    const payload = await requestJson('/projects-api', {
      method: 'GET',
      headers: undefined
    });
    return payload.data && Array.isArray(payload.data.items) ? payload.data.items : [];
  }

  async function removeProject(id) {
    await requestJson('/projects-api/' + encodeURIComponent(id), {
      method: 'DELETE',
      headers: undefined
    });
    addHistory('project', '删除项目', id);
  }

  async function getProject(id) {
    const payload = await requestJson('/projects-api/' + encodeURIComponent(id), {
      method: 'GET',
      headers: undefined
    });
    return payload.data && payload.data.project ? payload.data.project : null;
  }

  async function updateProject(id, payload) {
    const ret = await requestJson('/projects-api/' + encodeURIComponent(id), {
      method: 'PUT',
      body: JSON.stringify(payload || {})
    });
    return ret.data && ret.data.project ? ret.data.project : null;
  }

  async function uploadProjectResource(id, file, options) {
    const form = new FormData();
    form.append('file', file);
    const extra = options || {};
    if (extra.resourceType) form.append('resourceType', extra.resourceType);
    if (extra.language) form.append('language', extra.language);
    const ret = await requestJson('/projects-api/' + encodeURIComponent(id) + '/resources', {
      method: 'POST',
      headers: undefined,
      body: form
    });
    return ret.data || {};
  }

  async function deleteProjectResource(id, resourceId) {
    const ret = await requestJson(
      '/projects-api/' + encodeURIComponent(id) + '/resources/' + encodeURIComponent(resourceId),
      { method: 'DELETE', headers: undefined }
    );
    return ret.data && ret.data.project ? ret.data.project : null;
  }

  async function generateLabTask(id) {
    const ret = await requestJson(
      '/projects-api/' + encodeURIComponent(id) + '/lab-tasks/generate',
      { method: 'POST', body: '{}' }
    );
    return ret.data || {};
  }

  async function deleteLabTask(id, taskId) {
    const ret = await requestJson(
      '/projects-api/' + encodeURIComponent(id) + '/lab-tasks/' + encodeURIComponent(taskId),
      { method: 'DELETE', headers: undefined }
    );
    return ret.data && ret.data.project ? ret.data.project : null;
  }

  async function submitLabTask(id, taskId, sourceCode) {
    const ret = await requestJson(
      '/published-lessons/' + encodeURIComponent(id) + '/lab-tasks/' + encodeURIComponent(taskId) + '/submit',
      {
        method: 'POST',
        body: JSON.stringify({ sourceCode: sourceCode || '' })
      }
    );
    return ret.data && ret.data.submission ? ret.data.submission : null;
  }

  async function publishProject(id, payload) {
    const ret = await requestJson('/projects-api/' + encodeURIComponent(id) + '/publish', {
      method: 'POST',
      body: JSON.stringify(payload || {})
    });
    const title = payload && payload.lessonTitle ? payload.lessonTitle : id;
    addHistory('publish', '发布智课', title);
    return ret.data && ret.data.project ? ret.data.project : null;
  }

  async function listTeacherClasses() {
    const payload = await requestJson('/api/v1/classes', {
      method: 'GET',
      headers: undefined
    });
    const items = payload.data && Array.isArray(payload.data.items) ? payload.data.items : [];
    return items.map(function (card) {
      return card && card.class ? card.class : card;
    }).filter(Boolean);
  }

  async function createClassRoom(payload) {
    const ret = await requestJson('/api/v1/classes', {
      method: 'POST',
      body: JSON.stringify(payload || {})
    });
    return ret.data && ret.data.class ? ret.data.class : null;
  }

  async function publishLessonToClass(classId, projectId) {
    const ret = await requestJson('/api/v1/classes/' + encodeURIComponent(classId) + '/publish-lesson', {
      method: 'POST',
      body: JSON.stringify({ projectId: projectId || '' })
    });
    return ret.data && ret.data.class ? ret.data.class : null;
  }

  function buildStudentJoinLink(inviteCode, classId, projectId) {
    // 进班入口统一到学生端 SPA 课程中心（旧 join.html 保留兼容历史链接）
    const params = new URLSearchParams();
    if (inviteCode) params.set('invite', String(inviteCode).trim().toUpperCase());
    if (classId) params.set('classId', String(classId));
    if (projectId) params.set('projectId', String(projectId));
    return location.origin + '/student/course-center?' + params.toString();
  }

  async function getPublishedLessons() {
    const payload = await requestJson('/published-lessons', {
      method: 'GET',
      headers: undefined
    });
    return payload.data && Array.isArray(payload.data.items) ? payload.data.items : [];
  }

  async function getPublishedLesson(id) {
    const payload = await requestJson('/published-lessons/' + encodeURIComponent(id), {
      method: 'GET',
      headers: undefined
    });
    return payload.data && payload.data.project ? payload.data.project : null;
  }

  async function trackLesson(id, payload) {
    const ret = await requestJson('/published-lessons/' + encodeURIComponent(id) + '/track', {
      method: 'POST',
      body: JSON.stringify(payload || {})
    });
    return ret.data && ret.data.project ? ret.data.project : null;
  }

  function adminLevelLabel(level) {
    const map = { super: '超级管理员', ops: '运维管理员', content: '内容管理员' };
    return map[String(level || '').toLowerCase()] || '管理员';
  }

  function getNavLinks(activeRole, adminLevel) {
    if (activeRole === 'student') {
      return [
        { path: '/student/home', key: 'home', label: '首页', icon: 'home' },
        { path: '/student/course-center', key: 'course-center', label: '课程中心', icon: 'course-center' },
        { path: '/student/homework', key: 'homework', label: '班级作业', icon: 'homework' },
        { path: '/student/profile-dialogue', key: 'profile-build', label: '画像构建', icon: 'profile-build' },
        { path: '/student/resources', key: 'resources', label: '资源中心', icon: 'resources' },
        { path: '/student/path', key: 'path', label: '学习路径', icon: 'path' },
        { path: '/student/tutor', key: 'tutor', label: '智能答疑', icon: 'tutor' },
        { path: '/student/dashboard', key: 'dashboard', label: '学习数据', icon: 'dashboard' },
        { path: '/student/center', key: 'center', label: '个人中心', icon: 'center' },
        { path: '/student.html', key: 'student', label: '沉浸工作台', icon: 'student' }
      ];
    }
    if (activeRole === 'admin') {
      const level = String(adminLevel || 'ops').toLowerCase();
      const all = [
        { path: '/admin/home.html', key: 'home', label: '管理首页', levels: ['super', 'ops', 'content'], icon: 'home' },
        { path: '/admin/users.html', key: 'users', label: '账号治理', levels: ['super', 'ops'], icon: 'users' },
        { path: '/admin/resets.html', key: 'resets', label: '重置队列', levels: ['super', 'ops'], icon: 'resets' },
        { path: '/admin/content.html', key: 'content', label: '内容监管', levels: ['super', 'ops', 'content'], icon: 'content' },
        { path: '/admin/audit.html', key: 'audit', label: '操作审计', levels: ['super', 'ops', 'content'], icon: 'audit' },
        { path: '/admin/admins.html', key: 'admins', label: '管理员', levels: ['super'], icon: 'admins' }
      ];
      return all.filter(function (item) {
        return item.levels.indexOf(level) >= 0 || level === 'super';
      }).map(function (item) {
        return { path: item.path, key: item.key, label: item.label, icon: item.icon };
      });
    }
    return [
      { path: '/teacher/home.html', key: 'home', label: '首页', icon: 'home' },
      { path: '/classes.html', key: 'classes', label: '班级中心', icon: 'classes' },
      { path: '/workspace.html', key: 'index', label: '备课台', icon: 'workspace' },
      { path: '/projects.html', key: 'projects', label: '我的备课', icon: 'projects' },
      { path: '/teacher-insight.html', key: 'insight', label: '学情分析', icon: 'insight' },
      { path: '/teacher/center.html', key: 'center', label: '个人中心', icon: 'center' }
    ];
  }

  function navIconSvg(name) {
    const common = 'xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"';
    const icons = {
      home: '<path d="M5 11.2 12 5.5l7 5.7V19a.8.8 0 0 1-.8.8h-4.4v-5.2H10.2v5.2H5.8A.8.8 0 0 1 5 19v-7.8Z"/>',
      classes: '<circle cx="9" cy="8" r="2.6"/><path d="M4.5 18.5c.4-2.6 2.4-4 4.5-4s4.1 1.4 4.5 4"/><circle cx="16.8" cy="8.4" r="2.1"/><path d="M15.2 18.5c.2-1.7 1.5-2.9 3.1-2.9 1.2 0 2.2.6 2.7 1.7"/>',
      workspace: '<rect x="5" y="5.5" width="14" height="9.5" rx="1.6"/><path d="M9.5 18.5h5"/><path d="M12 15v3.5"/>',
      projects: '<path d="M12 5.2 18.2 8.7v6.6L12 18.8l-6.2-3.5V8.7L12 5.2Z"/><path d="M12 12 5.8 8.7"/><path d="M12 12v6.8"/><path d="m12 12 6.2-3.3"/>',
      insight: '<path d="M5 18.5h14"/><path d="M8 15.8V11"/><path d="M12 15.8V7.5"/><path d="M16 15.8v-3.2"/>',
      center: '<circle cx="12" cy="8.2" r="2.8"/><path d="M6.2 18.5a5.8 5.8 0 0 1 11.6 0"/>',
      'course-center': '<path d="M6 7.2A2 2 0 0 1 8 5.5h10.5v12.5H8A2 2 0 0 0 6 20V7.2Z"/><path d="M9.2 9.5h6.5"/><path d="M9.2 12.5h5"/>',
      homework: '<path d="M8 5.5h5.2L17.5 9.8V18a.8.8 0 0 1-.8.8H8.8A.8.8 0 0 1 8 18V5.5Z"/><path d="M13.2 5.5V9.8H17.5"/><path d="M10 13h4.5"/><path d="M10 15.5h3"/>',
      'profile-build': '<circle cx="11" cy="8.2" r="2.6"/><path d="M5.5 18.5a5.5 5.5 0 0 1 11 0"/><path d="M18 7.5v4"/><path d="M16 9.5h4"/>',
      resources: '<path d="M5.5 8h5l1.6 1.6H18.5v8.2a.8.8 0 0 1-.8.8H6.3a.8.8 0 0 1-.8-.8V8Z"/>',
      path: '<circle cx="7" cy="7" r="2"/><circle cx="17" cy="12" r="2"/><circle cx="8.5" cy="17.5" r="2"/><path d="M8.7 8.5 15.2 11"/><path d="M15.4 13.6 10.2 16"/>',
      tutor: '<path d="M18.5 14.5a2.2 2.2 0 0 1-2.2 2.2H9.2L6 19V7.2A2.2 2.2 0 0 1 8.2 5h8.1a2.2 2.2 0 0 1 2.2 2.2v7.3Z"/><path d="M9 9h6"/><path d="M9 12h4"/>',
      dashboard: '<rect x="5" y="5" width="6" height="6" rx="1.2"/><rect x="13" y="5" width="6" height="4" rx="1.2"/><rect x="13" y="11" width="6" height="8" rx="1.2"/><rect x="5" y="13" width="6" height="6" rx="1.2"/>',
      student: '<rect x="5" y="6" width="14" height="9" rx="1.6"/><path d="M9 18.5h6"/><path d="M12 15v3.5"/>',
      users: '<circle cx="9" cy="8" r="2.6"/><path d="M4.5 18.5c.4-2.6 2.4-4 4.5-4s4.1 1.4 4.5 4"/><circle cx="16.8" cy="8.4" r="2.1"/><path d="M15.2 18.5c.2-1.7 1.5-2.9 3.1-2.9 1.2 0 2.2.6 2.7 1.7"/>',
      resets: '<path d="M6.2 9.2A6.5 6.5 0 1 1 5.5 12"/><path d="M5.5 6.2V9.8H9"/>',
      content: '<path d="M8 5.5h5.2L17.5 9.8V18a.8.8 0 0 1-.8.8H8.8A.8.8 0 0 1 8 18V5.5Z"/><path d="M13.2 5.5V9.8H17.5"/><path d="M10 13h4.5"/><path d="M10 15.5h3"/>',
      audit: '<path d="M9.5 6.5H8a1.5 1.5 0 0 0-1.5 1.5v10A1.5 1.5 0 0 0 8 19.5h8a1.5 1.5 0 0 0 1.5-1.5v-10A1.5 1.5 0 0 0 16 6.5h-1.5"/><rect x="9.5" y="4.5" width="5" height="3.2" rx=".8"/><path d="m9.8 13.2 1.6 1.6 3.2-3.2"/>',
      admins: '<path d="M12 5.2 17.8 8.2v5.2c0 3.4-2.2 5.6-5.8 6.4-3.6-.8-5.8-3-5.8-6.4V8.2L12 5.2Z"/><path d="M12 10.5v3.5"/><path d="M10.2 12.2h3.6"/>'
    };
    const body = icons[name] || icons.home;
    return '<span class="nav-ico-wrap"><svg class="nav-ico" ' + common + '>' + body + '</svg></span>';
  }

  function mountNav(activePath) {
    const user = currentUser();
    const nav = document.getElementById('sideNav');
    if (!nav) return;

    const path = String(location.pathname || '');
    let activeRole = user && user.activeRole ? user.activeRole : 'teacher';
    if (path.indexOf('/admin/') === 0) {
      activeRole = 'admin';
    } else if (path.indexOf('/student/') === 0 || path.endsWith('/student.html')) {
      activeRole = 'student';
    } else if (
      path.indexOf('/teacher/') === 0
      || path.endsWith('/workspace.html')
      || path.endsWith('/projects.html')
      || path.endsWith('/classes.html')
      || path.endsWith('/teacher-insight.html')
      || path.endsWith('/history.html')
    ) {
      activeRole = 'teacher';
    }
    const links = getNavLinks(activeRole, user && user.adminLevel);
    const username = user ? escapeHtml(user.username || '未命名用户') : '未登录';
    const homeHref = activeRole === 'admin'
      ? '/admin/home.html'
      : (activeRole === 'student' ? '/student/home' : '/teacher/home.html');
    const subtitle = activeRole === 'admin'
      ? '管理控制台'
      : (activeRole === 'student' ? '学生端' : '教师工作台');
    const roleTextFixed = user
      ? escapeHtml(activeRole === 'admin' ? adminLevelLabel(user.adminLevel) : roleLabel(activeRole))
      : '未登录';
    if (nav.tagName === 'ASIDE') {
      const header = document.createElement('header');
      header.id = 'sideNav';
      header.className = nav.className || 'nav';
      header.setAttribute('role', 'banner');
      nav.replaceWith(header);
      return mountNav(activePath);
    }
    nav.classList.add('nav');
    nav.setAttribute('role', 'banner');
    nav.innerHTML = `
      <a class="nav-brand" href="${homeHref}">
        <img class="nav-logo" src="/brand-icon.jpg" alt="" width="36" height="36" />
        <div class="nav-brand-text">
          <h1>智课共生</h1>
          <div class="nav-subtitle">${subtitle}</div>
        </div>
      </a>
      <nav class="menu" aria-label="主导航">
        ${links.map(function (item) {
          const active = activePath === item.key;
          const iconName = item.icon || item.key;
          return '<a href="' + item.path + '" class="' + (active ? 'active' : '') + '"' + (active ? ' aria-current="page"' : '') + '>'
            + navIconSvg(iconName)
            + '<span>' + escapeHtml(item.label) + '</span>'
            + '</a>';
        }).join('')}
      </nav>
      <div class="meta">
        <span class="nav-meta-label">当前用户</span>
        <div class="nav-user">${username}</div>
        <div class="nav-role">${roleTextFixed}</div>
        <div class="nav-actions">
          <a href="#" class="link" data-help>帮助中心</a>
          <a href="/login.html" class="link">切换身份</a>
          <button id="logoutBtn" class="btn ghost" style="padding:6px 12px;font-size:12px;border-radius:999px;${user ? '' : 'display:none;'}">退出</button>
        </div>
      </div>
    `;
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', async function () {
        const current = currentUser();
        const loginPath = current ? roleLoginPath(current.activeRole) : '/login.html';
        await logout();
        location.href = loginPath;
      });
    }
  }

  async function changePassword(oldPassword, newPassword) {
    const payload = await requestJson('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({
        oldPassword: oldPassword || '',
        newPassword: newPassword || ''
      })
    });
    return payload;
  }

  function toast(message, tone) {
    const text = String(message || '').trim();
    if (!text) return;
    let root = document.getElementById('appToastRoot');
    if (!root) {
      root = document.createElement('div');
      root.id = 'appToastRoot';
      root.style.cssText = 'position:fixed;right:18px;top:18px;z-index:9999;display:grid;gap:10px;max-width:min(360px,calc(100vw - 36px));pointer-events:none;';
      root.setAttribute('aria-live', 'polite');
      root.setAttribute('aria-atomic', 'true');
      document.body.appendChild(root);
    }
    const isError = tone === 'err' || tone === 'error';
    const isOk = tone === 'ok' || tone === 'success';
    const item = document.createElement('div');
    item.style.cssText = [
      'pointer-events:auto',
      'border-radius:12px',
      'border:1px solid ' + (isError ? '#fecaca' : isOk ? '#bbf7d0' : '#dbe6f6'),
      'background:' + (isError ? '#fff7f7' : isOk ? '#f0fdf4' : '#ffffff'),
      'color:' + (isError ? '#991b1b' : isOk ? '#166534' : '#29415f'),
      'box-shadow:0 16px 36px rgba(20,32,55,.14)',
      'padding:12px 14px',
      'font-size:13px',
      'line-height:1.6',
      'transform:translateY(-6px)',
      'opacity:0',
      'transition:opacity var(--dur-base) var(--ease-out), transform var(--dur-base) var(--ease-out)'
    ].join(';');
    item.textContent = text;
    item.setAttribute('role', isError ? 'alert' : 'status');
    item.setAttribute('tabindex', '0');
    item.title = '点击关闭';
    item.addEventListener('click', function () {
      item.style.opacity = '0';
      item.style.transform = 'translateY(-6px)';
      setTimeout(function () {
        if (item.parentNode) item.parentNode.removeChild(item);
      }, 240);
    });
    root.appendChild(item);
    requestAnimationFrame(function () {
      item.style.opacity = '1';
      item.style.transform = 'translateY(0)';
    });
    setTimeout(function () {
      item.style.opacity = '0';
      item.style.transform = 'translateY(-6px)';
      setTimeout(function () {
        if (item.parentNode) item.parentNode.removeChild(item);
      }, 220);
    }, 2600);
  }

  window.AppStore = {
    now: now,
    addHistory: addHistory,
    addProject: addProject,
    register: register,
    login: login,
    logout: logout,
    changePassword: changePassword,
    requireLogin: requireLogin,
    requireRole: requireRole,
    refreshCurrentUser: refreshCurrentUser,
    redirectToLogin: redirectToLogin,
    redirectToHome: redirectToHome,
    currentUser: currentUser,
    getHistory: getHistory,
    clearHistory: clearHistory,
    getProjects: getProjects,
    getProject: getProject,
    updateProject: updateProject,
    uploadProjectResource: uploadProjectResource,
    deleteProjectResource: deleteProjectResource,
    generateLabTask: generateLabTask,
    deleteLabTask: deleteLabTask,
    submitLabTask: submitLabTask,
    publishProject: publishProject,
    listTeacherClasses: listTeacherClasses,
    createClassRoom: createClassRoom,
    publishLessonToClass: publishLessonToClass,
    buildStudentJoinLink: buildStudentJoinLink,
    getPublishedLessons: getPublishedLessons,
    getPublishedLesson: getPublishedLesson,
    trackLesson: trackLesson,
    removeProject: removeProject,
    mountNav: mountNav,
    normalizeRole: normalizeRole,
    roleLabel: roleLabel,
    roleLoginPath: roleLoginPath,
    roleRegisterPath: roleRegisterPath,
    roleHomePath: roleHomePath,
    toast: toast
  };
})();

(function () {
  if (window.ZkHelp || document.querySelector('script[data-help-modal]')) return;
  var script = document.createElement('script');
  script.src = '/help-modal.js?v=20260925a';
  script.dataset.helpModal = '1';
  document.body.appendChild(script);
})();

(function () {
  if (window.ZkMotion || document.body.classList.contains('auth-body')) return;
  var motion = document.createElement('script');
  motion.src = '/page-motion.js?v=20260919m';
  document.body.appendChild(motion);
})();


/* ===================== 按钮涟漪：鸿蒙 / Huawei 风格 Ripple ===================== */
;(function () {
  if (typeof window === 'undefined' || typeof document === 'undefined') return
  if (window.__buttonRippleInstalled) return
  window.__buttonRippleInstalled = true

  var HOST_SELECTOR = 'button, .btn, .el-button, [role="button"]'
  var RIPPLE_CLASS = 'z-ripple'
  var HOST_CLASS = 'z-ripple-host'
  var STYLE_ID = 'z-ripple-style'
  var MAX_PER_HOST = 6
  var DURATION_MS = 420

  var reduceMq = null
  try {
    if (window.matchMedia) reduceMq = window.matchMedia('(prefers-reduced-motion: reduce)')
  } catch (e) { /* 老浏览器：不做降级判断 */ }

  var STYLE_TEXT =
    '.' + HOST_CLASS + ' { position: relative; overflow: hidden; }\n' +
    '.' + RIPPLE_CLASS + ' { position: absolute; display: block; border-radius: 50%;' +
    ' pointer-events: none; z-index: 0; transform: scale(0); will-change: transform, opacity;' +
    ' animation: z-ripple-expand ' + DURATION_MS + 'ms linear forwards; }\n' +
    '@keyframes z-ripple-expand { 0% { transform: scale(0); opacity: 1; } 100% { transform: scale(1); opacity: 0; } }\n' +
    '@media (prefers-reduced-motion: reduce) { .' + RIPPLE_CLASS + ' { display: none; animation: none; } }'

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return
    var style = document.createElement('style')
    style.id = STYLE_ID
    style.textContent = STYLE_TEXT
    document.head.appendChild(style)
  }

  function parseColor(raw) {
    if (!raw) return null
    var m = String(raw).match(/rgba?\(([^)]+)\)/i)
    if (!m) return null
    var parts = m[1].split(/[,\s\/]+/).filter(Boolean).map(function (v) { return parseFloat(v) })
    if (parts.length < 3 || parts.some(function (v) { return isNaN(v) })) return null
    return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 }
  }

  function ensureHost(host) {
    if (host.classList.contains(HOST_CLASS)) return
    var cs = getComputedStyle(host)
    if (cs.position === 'static') host.style.position = 'relative'
    if (cs.overflow === 'visible') host.style.overflow = 'hidden'
    host.classList.add(HOST_CLASS)
  }

  function resolveRipple(host) {
    var cs = getComputedStyle(host)
    var bg = parseColor(cs.backgroundColor)
    var brand =
      parseColor(cs.getPropertyValue('--el-color-primary').trim()) ||
      parseColor(cs.getPropertyValue('--brand').trim()) ||
      { r: 31, g: 102, b: 255, a: 1 }
    if (!bg || bg.a < 0.15) return { r: brand.r, g: brand.g, b: brand.b, a: 0.2 }
    var luminance = (0.2126 * bg.r + 0.7152 * bg.g + 0.0722 * bg.b) / 255
    if (luminance < 0.45) return { r: 255, g: 255, b: 255, a: 0.26 }
    var fg = parseColor(cs.color)
    var chroma = fg ? Math.max(fg.r, fg.g, fg.b) - Math.min(fg.r, fg.g, fg.b) : 0
    if (fg && chroma >= 24) return { r: fg.r, g: fg.g, b: fg.b, a: 0.18 }
    return { r: 15, g: 23, b: 42, a: 0.1 }
  }

  function rippleBackground(c) {
    var solid = 'rgba(' + c.r + ', ' + c.g + ', ' + c.b + ', ' + c.a + ')'
    var clear = 'rgba(' + c.r + ', ' + c.g + ', ' + c.b + ', 0)'
    return 'radial-gradient(circle closest-side, ' + solid + ' 0%, ' + solid + ' 86%, ' + clear + ' 100%)'
  }

  function isDisabled(host) {
    if (host.hasAttribute('disabled')) return true
    if (host.getAttribute('aria-disabled') === 'true') return true
    return host.classList.contains('is-disabled')
  }

  ensureStyle()

  document.addEventListener('pointerdown', function (e) {
    if (e.pointerType === 'mouse' && e.button !== 0) return
    if (reduceMq && reduceMq.matches) return

    var target = e.target
    if (!target || typeof target.closest !== 'function') return
    var host = target.closest(HOST_SELECTOR)
    if (!host || isDisabled(host)) return

    var rect = host.getBoundingClientRect()
    if (rect.width < 2 || rect.height < 2) return

    ensureHost(host)

    var x = e.clientX - rect.left
    var y = e.clientY - rect.top
    var radius = Math.max(
      Math.hypot(x, y),
      Math.hypot(rect.width - x, y),
      Math.hypot(x, rect.height - y),
      Math.hypot(rect.width - x, rect.height - y)
    )
    if (!isFinite(radius) || radius <= 0) return

    var wave = document.createElement('span')
    wave.className = RIPPLE_CLASS
    wave.setAttribute('aria-hidden', 'true')
    wave.style.left = (x - radius) + 'px'
    wave.style.top = (y - radius) + 'px'
    wave.style.width = (radius * 2) + 'px'
    wave.style.height = (radius * 2) + 'px'
    wave.style.background = rippleBackground(resolveRipple(host))
    host.appendChild(wave)

    var waves = host.querySelectorAll('.' + RIPPLE_CLASS)
    if (waves.length > MAX_PER_HOST) waves[0].remove()

    wave.addEventListener('animationend', function () { wave.remove() }, { once: true })
  }, { passive: true })
})()
