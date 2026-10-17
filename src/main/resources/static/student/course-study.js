(function () {
  'use strict';

  const PROGRESS_KEY = 'ai_teacher_course_study_progress_v1';

  function escapeHtml(text) {
    return String(text == null ? '' : text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function loadProgressMap() {
    try {
      const raw = localStorage.getItem(PROGRESS_KEY);
      const parsed = raw ? JSON.parse(raw) : {};
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch (e) {
      return {};
    }
  }

  function saveProgressMap(map) {
    localStorage.setItem(PROGRESS_KEY, JSON.stringify(map || {}));
  }

  function getLocalProgress(projectId) {
    const map = loadProgressMap();
    const item = map[projectId];
    if (!item) return { index: 0, percent: 0 };
    return {
      index: Number(item.index) || 0,
      percent: Math.min(100, Math.max(0, Number(item.percent) || 0))
    };
  }

  function setLocalProgress(projectId, index, total) {
    const map = loadProgressMap();
    const safeTotal = Math.max(total || 1, 1);
    const safeIndex = Math.max(0, Math.min(index, safeTotal - 1));
    const percent = ((safeIndex + 1) / safeTotal) * 100;
    map[projectId] = { index: safeIndex, percent: percent, updatedAt: new Date().toISOString() };
    saveProgressMap(map);
    return map[projectId];
  }

  function clearLocalProgress(projectId) {
    const map = loadProgressMap();
    delete map[projectId];
    saveProgressMap(map);
  }

  function extractSlides(rawText) {
    const rows = String(rawText || '').split(/\r?\n/);
    const result = [];
    let current = null;
    rows.forEach(function (row) {
      const line = (row || '').trim();
      const matched = line.match(/^===\s*第(\d+)页\s*===$/);
      if (matched) {
        if (current) result.push(current);
        current = { page: Number(matched[1]), lines: [] };
      } else if (current && line) {
        current.lines.push(line);
      }
    });
    if (current) result.push(current);
    if (!result.length && String(rawText || '').trim()) {
      return [{ page: 1, lines: String(rawText).trim().split(/\r?\n/).filter(Boolean) }];
    }
    return result;
  }

  function resourceTypeLabel(type) {
    const map = {
      code: '代码资料',
      sql: 'SQL 资料',
      error_log: '错误日志',
      document: '讲义文档',
      reading: '拓展阅读',
      question: '练习题',
      mindmap: '思维导图',
      video: '视频讲解'
    };
    return map[type] || (type || '学习资源');
  }

  async function boot() {
    const ok = await window.StudentShell.ensureStudentAuth();
    if (!ok) return;

    const main = window.StudentShell.mount('course-study');
    if (!main) return;

    main.innerHTML = `
      <div class="page-hero">
        <div>
          <h2>课程中心</h2>
          <p>浏览教师已发布智课，加载 AI 课件解析资源，查看详情与学习进度，并预览配套实践资料。师生统一端口 8082。</p>
        </div>
        <div class="view-tabs" role="tablist" aria-label="课程视图切换">
          <button id="tabCatalog" type="button" class="active">课程列表</button>
          <button id="tabDetail" type="button" disabled>课程详情</button>
        </div>
      </div>
      <section id="catalogView">
        <div class="toolbar">
          <input id="searchInput" type="search" placeholder="搜索课程名称、简介…" autocomplete="off" />
          <select id="modeFilter">
            <option value="all">全部课程</option>
            <option value="computer">计算机专项</option>
            <option value="general">通用课程</option>
          </select>
          <button id="refreshBtn" class="btn ghost" type="button">刷新</button>
        </div>
        <div id="catalogLoading" class="loading-state">正在加载已发布智课…</div>
        <div id="catalogEmpty" class="empty-state-box hidden">当前还没有已发布智课，请先在教师工作台完成发布。</div>
        <div id="courseGrid" class="course-grid"></div>
      </section>
      <section id="detailView" class="hidden">
        <div class="detail-actions" style="margin-bottom:12px;">
          <button id="backToCatalogBtn" class="btn ghost" type="button">返回列表</button>
          <a id="openWorkbenchLink" class="btn" href="/student.html">进入沉浸学习工作台</a>
          <a id="digitalLink" class="btn ghost" href="#" target="_blank" style="display:none;text-decoration:none;">打开讲解视频</a>
        </div>
        <div id="detailLoading" class="loading-state">正在加载课程详情…</div>
        <div id="detailError" class="empty-state-box hidden">课程加载失败，请稍后重试。</div>
        <div id="detailContent" class="detail-layout hidden">
          <div class="panel">
            <div class="tag-row">
              <span id="lessonTag" class="tag">已发布智课</span>
              <span id="modeTag" class="tag">通用</span>
            </div>
            <h3 id="detailTitle">未命名智课</h3>
            <p id="detailIntro" class="course-meta">暂无课程简介</p>
            <div>
              <div style="display:flex;justify-content:space-between;gap:8px;margin-bottom:6px;">
                <strong id="progressLabel">学习进度 0%</strong>
                <span id="sectionHint" class="course-meta">当前节点：未开始</span>
              </div>
              <div class="progress-track"><span id="progressBar" style="width:0%"></span></div>
            </div>
            <div>
              <h3 style="margin:14px 0 8px;">讲解节点</h3>
              <div id="sectionList" class="section-list"></div>
            </div>
            <div>
              <h3 style="margin:14px 0 8px;">讲稿预览</h3>
              <div id="scriptBox" class="script-box">选择节点后，讲稿内容将显示在这里。</div>
            </div>
            <div class="detail-actions">
              <button id="prevSectionBtn" class="btn ghost" type="button">上一节点</button>
              <button id="nextSectionBtn" class="btn" type="button">下一节点并记录进度</button>
              <button id="resetProgressBtn" class="btn ghost" type="button">重置本课进度</button>
            </div>
          </div>
          <div class="panel">
            <h3>配套学习资源</h3>
            <p class="course-meta">来自教师工作台课件解析与专项资料上传，可在线查阅预览。</p>
            <div id="resourceEmpty" class="empty-state-box hidden" style="padding:24px 12px;">本课暂无配套资源。</div>
            <div id="resourceGrid" class="resource-grid"></div>
            <h3 style="margin-top:16px;">实践实验</h3>
            <div id="labEmpty" class="empty-state-box hidden" style="padding:24px 12px;">教师尚未发布实验任务。</div>
            <div id="labGrid" class="resource-grid"></div>
          </div>
        </div>
      </section>
    `;

    const searchInput = document.getElementById('searchInput');
    const modeFilter = document.getElementById('modeFilter');
    const refreshBtn = document.getElementById('refreshBtn');
    const catalogLoading = document.getElementById('catalogLoading');
    const catalogEmpty = document.getElementById('catalogEmpty');
    const courseGrid = document.getElementById('courseGrid');
    const catalogView = document.getElementById('catalogView');
    const detailView = document.getElementById('detailView');
    const tabCatalog = document.getElementById('tabCatalog');
    const tabDetail = document.getElementById('tabDetail');
    const backToCatalogBtn = document.getElementById('backToCatalogBtn');
    const openWorkbenchLink = document.getElementById('openWorkbenchLink');
    const digitalLink = document.getElementById('digitalLink');
    const detailLoading = document.getElementById('detailLoading');
    const detailError = document.getElementById('detailError');
    const detailContent = document.getElementById('detailContent');
    const detailTitle = document.getElementById('detailTitle');
    const detailIntro = document.getElementById('detailIntro');
    const lessonTag = document.getElementById('lessonTag');
    const modeTag = document.getElementById('modeTag');
    const progressLabel = document.getElementById('progressLabel');
    const sectionHint = document.getElementById('sectionHint');
    const progressBar = document.getElementById('progressBar');
    const sectionList = document.getElementById('sectionList');
    const scriptBox = document.getElementById('scriptBox');
    const prevSectionBtn = document.getElementById('prevSectionBtn');
    const nextSectionBtn = document.getElementById('nextSectionBtn');
    const resetProgressBtn = document.getElementById('resetProgressBtn');
    const resourceEmpty = document.getElementById('resourceEmpty');
    const resourceGrid = document.getElementById('resourceGrid');
    const labEmpty = document.getElementById('labEmpty');
    const labGrid = document.getElementById('labGrid');
    const resourceModal = document.getElementById('resourceModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalMeta = document.getElementById('modalMeta');
    const modalBody = document.getElementById('modalBody');
    const closeModalBtn = document.getElementById('closeModalBtn');

    let lessons = [];
    let currentLesson = null;
    let slides = [];
    let selectedIdx = 0;

    function showCatalog() {
      catalogView.classList.remove('hidden');
      detailView.classList.add('hidden');
      tabCatalog.classList.add('active');
      tabDetail.classList.remove('active');
      tabDetail.disabled = !currentLesson;
    }

    function showDetailShell() {
      catalogView.classList.add('hidden');
      detailView.classList.remove('hidden');
      tabCatalog.classList.remove('active');
      tabDetail.classList.add('active');
      tabDetail.disabled = false;
    }

    function getFilteredLessons() {
      const query = (searchInput.value || '').trim().toLowerCase();
      const mode = modeFilter.value || 'all';
      return lessons.filter(function (item) {
        const title = String(item.lessonTitle || item.name || '').toLowerCase();
        const intro = String(item.lessonIntro || item.summary || item.meta || '').toLowerCase();
        if (query && title.indexOf(query) < 0 && intro.indexOf(query) < 0) return false;
        if (mode === 'computer' && item.subjectMode !== 'computer') return false;
        if (mode === 'general' && item.subjectMode === 'computer') return false;
        return true;
      });
    }

    function renderCatalog() {
      const items = getFilteredLessons();
      catalogLoading.classList.add('hidden');
      if (!lessons.length) {
        catalogEmpty.classList.remove('hidden');
        catalogEmpty.textContent = '当前还没有已发布智课，请先在教师工作台完成发布。';
        courseGrid.innerHTML = '';
        return;
      }
      if (!items.length) {
        catalogEmpty.classList.remove('hidden');
        catalogEmpty.textContent = '没有匹配的课程，请调整搜索或筛选条件。';
        courseGrid.innerHTML = '';
        return;
      }
      catalogEmpty.classList.add('hidden');
      courseGrid.innerHTML = items.map(function (item) {
        const local = getLocalProgress(item.id);
        const isActive = currentLesson && currentLesson.id === item.id;
        const modeText = item.subjectMode === 'computer' ? '计算机专项' : '通用课程';
        return (
          '<article class="course-card' + (isActive ? ' active' : '') + '" data-id="' + escapeHtml(item.id) + '">' +
            '<div class="course-card-head">' +
              '<div class="course-title">' + escapeHtml(item.lessonTitle || item.name || '未命名智课') + '</div>' +
              '<span class="status-pill ' + (local.percent > 0 ? 'ok' : 'idle') + '">' +
                (local.percent > 0 ? '学习中' : '可学习') +
              '</span>' +
            '</div>' +
            '<div class="course-meta">' + escapeHtml((item.lessonIntro || item.summary || item.meta || '暂无简介').slice(0, 90)) + '</div>' +
            '<div class="course-meta">' + modeText +
              ' · ' + (item.publishedAt ? new Date(item.publishedAt).toLocaleDateString('zh-CN') : '未标注时间') +
            '</div>' +
            '<div class="mini-progress"><span style="width:' + local.percent.toFixed(0) + '%"></span></div>' +
          '</article>'
        );
      }).join('');

      Array.from(courseGrid.querySelectorAll('[data-id]')).forEach(function (node) {
        node.addEventListener('click', function () {
          const id = node.getAttribute('data-id');
          if (id) openLesson(id);
        });
      });
    }

    async function loadCatalog() {
      catalogLoading.classList.remove('hidden');
      catalogEmpty.classList.add('hidden');
      courseGrid.innerHTML = '';
      try {
        lessons = await window.AppStore.getPublishedLessons();
        renderCatalog();
      } catch (e) {
        catalogLoading.classList.add('hidden');
        catalogEmpty.classList.remove('hidden');
        catalogEmpty.textContent = '已发布智课加载失败，请稍后重试。';
        window.AppStore.toast('课程列表加载失败', 'err');
      }
    }

    function renderSections() {
      if (!slides.length) {
        sectionList.innerHTML = '<span class="course-meta">当前课程暂无可视化讲解节点。</span>';
        scriptBox.textContent = currentLesson && currentLesson.script
          ? currentLesson.script
          : '暂无讲稿内容。';
        return;
      }
      sectionList.innerHTML = slides.map(function (slide, idx) {
        return '<button type="button" class="section-chip' + (idx === selectedIdx ? ' active' : '') + '" data-idx="' + idx + '">第 ' + slide.page + ' 页</button>';
      }).join('');
      Array.from(sectionList.querySelectorAll('[data-idx]')).forEach(function (btn) {
        btn.addEventListener('click', function () {
          goToSection(Number(btn.getAttribute('data-idx')));
        });
      });
      const slide = slides[selectedIdx];
      scriptBox.textContent = (slide.lines || []).join('\n') || '该节点暂无讲稿内容。';
      sectionHint.textContent = '当前节点：第 ' + slide.page + ' 页 / 共 ' + slides.length + ' 页';
    }

    function updateProgressUi() {
      const total = Math.max(slides.length, 1);
      const local = currentLesson ? getLocalProgress(currentLesson.id) : { percent: 0, index: 0 };
      const percent = slides.length ? ((selectedIdx + 1) / total) * 100 : local.percent;
      progressLabel.textContent = '学习进度 ' + percent.toFixed(0) + '%';
      progressBar.style.width = percent.toFixed(0) + '%';
    }

    function renderResources() {
      const resources = Array.isArray(currentLesson && currentLesson.resources) ? currentLesson.resources : [];
      if (!resources.length) {
        resourceEmpty.classList.remove('hidden');
        resourceGrid.innerHTML = '';
        return;
      }
      resourceEmpty.classList.add('hidden');
      resourceGrid.innerHTML = resources.map(function (item) {
        return (
          '<div class="resource-item" data-resource-id="' + escapeHtml(item.id) + '">' +
            '<strong>' + escapeHtml(item.fileName || resourceTypeLabel(item.resourceType)) + '</strong>' +
            '<span>' + escapeHtml(resourceTypeLabel(item.resourceType)) +
              (item.language ? ' · ' + escapeHtml(item.language) : '') +
            '</span>' +
          '</div>'
        );
      }).join('');
      Array.from(resourceGrid.querySelectorAll('[data-resource-id]')).forEach(function (node) {
        node.addEventListener('click', function () {
          const id = node.getAttribute('data-resource-id');
          const resource = resources.find(function (r) { return r.id === id; });
          if (resource) openResourceModal(resource);
        });
      });
    }

    function renderLabs() {
      const labs = Array.isArray(currentLesson && currentLesson.labTasks) ? currentLesson.labTasks : [];
      if (!labs.length) {
        labEmpty.classList.remove('hidden');
        labGrid.innerHTML = '';
        return;
      }
      labEmpty.classList.add('hidden');
      labGrid.innerHTML = labs.map(function (task) {
        return (
          '<div class="resource-item" data-lab-id="' + escapeHtml(task.id) + '">' +
            '<strong>' + escapeHtml(task.title || '实验任务') + '</strong>' +
            '<span>' + escapeHtml(task.language || '未指定语言') +
              ' · 用例 ' + (task.testCaseCount || 0) +
              ' · 限时 ' + (task.timeLimitMs || 0) + 'ms</span>' +
            '<span>' + escapeHtml((task.description || '暂无描述').slice(0, 100)) + '</span>' +
          '</div>'
        );
      }).join('');
      Array.from(labGrid.querySelectorAll('[data-lab-id]')).forEach(function (node) {
        node.addEventListener('click', function () {
          const id = node.getAttribute('data-lab-id');
          const task = labs.find(function (r) { return r.id === id; });
          if (!task) return;
          modalTitle.textContent = task.title || '实验任务';
          modalMeta.textContent = (task.language || '未指定语言') + ' · 限时 ' + (task.timeLimitMs || 0) + 'ms';
          modalBody.textContent =
            (task.description || '暂无描述') +
            '\n\n--- 起始代码 ---\n' +
            (task.starterCode || '// 暂无起始代码') +
            '\n\n--- 样例输入 ---\n' +
            (task.sampleInput || '无') +
            '\n\n--- 样例输出 ---\n' +
            (task.sampleOutput || '无');
          resourceModal.classList.add('show');
        });
      });
    }

    function openResourceModal(resource) {
      modalTitle.textContent = resource.fileName || resourceTypeLabel(resource.resourceType);
      modalMeta.textContent = resourceTypeLabel(resource.resourceType) +
        (resource.language ? ' · ' + resource.language : '');
      const content = resource.structuredContent || resource.rawContent || '暂无预览内容。';
      modalBody.textContent = content;
      resourceModal.classList.add('show');
    }

    function closeModal() {
      resourceModal.classList.remove('show');
    }

    async function trackCurrent(action) {
      if (!currentLesson) return;
      const total = Math.max(slides.length, 1);
      const sectionId = slides.length ? ('page_' + slides[selectedIdx].page) : 'start';
      const percent = slides.length ? ((selectedIdx + 1) / total) * 100 : 0;
      setLocalProgress(currentLesson.id, selectedIdx, total);
      try {
        await window.AppStore.trackLesson(currentLesson.id, {
          currentSectionId: sectionId,
          progressPercent: percent,
          action: action || 'progress',
          question: '',
          answer: '',
          understandingLevel: '',
          resolved: false
        });
      } catch (e) {
        /* 本地进度已保存，服务端失败不阻断浏览 */
      }
      updateProgressUi();
      renderCatalog();
    }

    function goToSection(idx) {
      if (!slides.length) return;
      selectedIdx = Math.max(0, Math.min(idx, slides.length - 1));
      renderSections();
      updateProgressUi();
      trackCurrent('view_section');
    }

    async function openLesson(projectId) {
      showDetailShell();
      detailLoading.classList.remove('hidden');
      detailError.classList.add('hidden');
      detailContent.classList.add('hidden');
      try {
        currentLesson = await window.AppStore.getPublishedLesson(projectId);
        if (!currentLesson) throw new Error('empty');
        slides = extractSlides(currentLesson.pptRawText || currentLesson.script || '');
        const local = getLocalProgress(projectId);
        selectedIdx = slides.length ? Math.min(local.index, slides.length - 1) : 0;

        detailTitle.textContent = currentLesson.lessonTitle || currentLesson.name || '未命名智课';
        detailIntro.textContent = currentLesson.lessonIntro || currentLesson.summary || currentLesson.meta || '暂无课程简介';
        lessonTag.textContent = currentLesson.published ? '已发布智课' : '未发布';
        modeTag.textContent = currentLesson.subjectMode === 'computer' ? '计算机专项' : '通用课程';
        openWorkbenchLink.href = '/student.html?projectId=' + encodeURIComponent(currentLesson.id);
        if (currentLesson.digitalUrl) {
          digitalLink.href = currentLesson.digitalUrl;
          digitalLink.style.display = '';
        } else {
          digitalLink.style.display = 'none';
        }

        renderSections();
        updateProgressUi();
        renderResources();
        renderLabs();
        detailLoading.classList.add('hidden');
        detailContent.classList.remove('hidden');
        await trackCurrent('open_lesson');
        renderCatalog();
      } catch (e) {
        detailLoading.classList.add('hidden');
        detailError.classList.remove('hidden');
        detailError.textContent = '课程加载失败，请返回列表后重试。';
        window.AppStore.toast('课程详情加载失败', 'err');
      }
    }

    tabCatalog.addEventListener('click', showCatalog);
    tabDetail.addEventListener('click', function () {
      if (currentLesson) showDetailShell();
    });
    backToCatalogBtn.addEventListener('click', showCatalog);
    refreshBtn.addEventListener('click', loadCatalog);
    searchInput.addEventListener('input', renderCatalog);
    modeFilter.addEventListener('change', renderCatalog);
    prevSectionBtn.addEventListener('click', function () {
      goToSection(selectedIdx - 1);
    });
    nextSectionBtn.addEventListener('click', function () {
      if (slides.length && selectedIdx < slides.length - 1) {
        goToSection(selectedIdx + 1);
      } else {
        trackCurrent('complete_section');
        window.AppStore.toast('已记录当前进度', 'ok');
      }
    });
    resetProgressBtn.addEventListener('click', function () {
      if (!currentLesson) return;
      clearLocalProgress(currentLesson.id);
      selectedIdx = 0;
      renderSections();
      updateProgressUi();
      trackCurrent('reset_progress');
      window.AppStore.toast('已重置本课本地进度', 'ok');
    });
    closeModalBtn.addEventListener('click', closeModal);
    resourceModal.addEventListener('click', function (e) {
      if (e.target === resourceModal) closeModal();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeModal();
    });

    const params = new URLSearchParams(location.search);
    const initialId = params.get('projectId');
    await loadCatalog();
    if (initialId) {
      await openLesson(initialId);
    } else {
      showCatalog();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
