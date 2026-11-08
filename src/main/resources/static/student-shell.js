(function () {
  const STUDENT_MENUS = [
    { key: 'home', path: '/student/home', label: '首页', icon: 'home' },
    { key: 'course-center', path: '/student/course-center', label: '课程中心', icon: 'book' },
    { key: 'profile-build', path: '/student/profile-dialogue', label: '画像构建', icon: 'user' },
    { key: 'resources', path: '/student/resources', label: '资源中心', icon: 'box' },
    { key: 'path', path: '/student/path', label: '学习路径', icon: 'path' },
    { key: 'tutor', path: '/student/tutor', label: '智能答疑', icon: 'chat' },
    { key: 'dashboard', path: '/student/dashboard', label: '学习数据', icon: 'chart' },
    { key: 'center', path: '/student/center', label: '个人中心', icon: 'setting' }
  ];

  function iconSvg(name) {
    const common = 'class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"';
    const map = {
      home: '<path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-9.5Z"/>',
      book: '<path d="M5 5.5A2.5 2.5 0 0 1 7.5 3H19v16H7.5A2.5 2.5 0 0 0 5 21.5V5.5Z"/><path d="M9 8h6M9 12h6"/>',
      user: '<path d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 0Z"/><path d="M4 20a8 8 0 0 1 16 0"/>',
      box: '<path d="M3 8.5 12 3l9 5.5v7L12 21l-9-5.5v-7Z"/><path d="M12 12v9M3 8.5l9 3.5 9-3.5"/>',
      path: '<path d="M5 19h4a2 2 0 0 0 2-2V7a2 2 0 0 1 2-2h6"/><path d="m15 3 4 2-4 2"/>',
      chat: '<path d="M5 6a3 3 0 0 1 3-3h8a3 3 0 0 1 3 3v7a3 3 0 0 1-3 3H11l-4 4v-4H8a3 3 0 0 1-3-3V6Z"/>',
      chart: '<path d="M4 19h16M7 16V10M12 16V7M17 16v-4"/>',
      setting: '<circle cx="12" cy="12" r="3"/><path d="M12 3v2M12 19v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M3 12h2M19 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'
    };
    return '<svg ' + common + '>' + (map[name] || map.home) + '</svg>';
  }

  function escapeHtml(value) {
    return String(value || '').replace(/[&<>"']/g, function (ch) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch];
    });
  }

  function mount(activeKey) {
    const main = document.createElement('div');
    main.className = 'student-shell';
    main.innerHTML =
      '<header class="shell-top">' +
        '<a class="shell-brand" href="/student/home">智课共生</a>' +
        '<nav class="shell-nav">' +
          STUDENT_MENUS.map(function (item) {
            const active = item.key === activeKey ? ' is-active' : '';
            return '<a class="shell-link' + active + '" href="' + item.path + '">' +
              iconSvg(item.icon) + '<span>' + escapeHtml(item.label) + '</span></a>';
          }).join('') +
        '</nav>' +
      '</header>' +
      '<div class="shell-body" id="student-shell-main"></div>';
    document.body.prepend(main);
    return document.getElementById('student-shell-main');
  }

  window.StudentShell = { mount: mount, menus: STUDENT_MENUS };
})();
