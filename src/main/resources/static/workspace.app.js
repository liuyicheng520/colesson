  (async function () {
  if (!window.AppStore || !window.AppStore.requireRole) {
    location.replace('/teacher/login.html');
    return;
  }
  const bootOk = await window.AppStore.requireRole(['teacher', 'admin'], { loginRole: 'teacher' });
  if (!bootOk) {
    return;
  }
  window.AppStore.mountNav('index');
  const bootUser = window.AppStore.currentUser();

  let pptRawText = '';
  let currentScript = '';
  let lectureAudio = null;
  let interruptedAt = 0;
  let wasInterrupted = false;
  const lectureInterruptState = {
    status: 'idle',
    interruptedAt: 0,
    interruptedSlideIdx: -1,
    interruptedQuestion: '',
    interruptedText: ''
  };
  let selectedVoice = 'gentle_female';
  let selectedMode = 'auto';
  let slides = [];
  let selectedSlideIdx = -1;
  let typingJobId = 0;
  let scriptAbortController = null;
  let isScriptGenerating = false;
  let dragDepth = 0;
  const workflow = {
    parsed: false,
    scriptReady: false,
    currentStep: 1
  };

  const REQUEST_TIMEOUT = 45000;
  const SCRIPT_TIMEOUT = 120000;
  const AUDIO_TIMEOUT = 180000;

  const uploadArea = document.getElementById('uploadArea');
  const pptFile = document.getElementById('pptFile');
  const fileName = document.getElementById('fileName');
  const parseBtn = document.getElementById('parseBtn');
  const parseLoading = document.getElementById('parseLoading');
  const parseMsg = document.getElementById('parseMsg');
  const outlinePanel = document.getElementById('outlinePanel');
  const expandAllBtn = document.getElementById('expandAllBtn');
  const collapseAllBtn = document.getElementById('collapseAllBtn');
  const computerResourcePanel = document.getElementById('computerResourcePanel');
  const computerResourceFile = document.getElementById('computerResourceFile');
  const computerResourceType = document.getElementById('computerResourceType');
  const chooseComputerResourceBtn = document.getElementById('chooseComputerResourceBtn');
  const uploadComputerResourceBtn = document.getElementById('uploadComputerResourceBtn');
  const computerResourceHint = document.getElementById('computerResourceHint');
  const computerResourceList = document.getElementById('computerResourceList');
  const resourceCountBadge = document.getElementById('resourceCountBadge');
  const labTaskPanel = document.getElementById('labTaskPanel');
  const labTaskCountBadge = document.getElementById('labTaskCountBadge');
  const generateLabTaskBtn = document.getElementById('generateLabTaskBtn');
  const labTaskHint = document.getElementById('labTaskHint');
  const labTaskList = document.getElementById('labTaskList');
  const currentSlideHint = document.getElementById('currentSlideHint');
  const slidePreview = document.getElementById('slidePreview');
  const prevSlideBtn = document.getElementById('prevSlideBtn');
  const nextSlideBtn = document.getElementById('nextSlideBtn');
  const tabLockHint = document.getElementById('tabLockHint');
  const workflowBadge = document.getElementById('workflowBadge');
  const workPanelZone = document.getElementById('workPanelZone');
  const panelLockOverlay = document.getElementById('panelLockOverlay');
  const uploadBigHint = document.getElementById('uploadBigHint');
  const uploadSmallHint = document.getElementById('uploadSmallHint');
  const mainLayout = document.getElementById('mainLayout');
  const collapseLeftBtn = document.getElementById('collapseLeftBtn');
  const expandFloatBtn = document.getElementById('expandFloatBtn');
  const accountTrigger = document.getElementById('accountTrigger');
  const accountMenu = document.getElementById('accountMenu');
  const accountName = document.getElementById('accountName');
  const accountLabel = document.getElementById('accountLabel');
  const accountAvatar = document.getElementById('accountAvatar');
  const switchAccountBtn = document.getElementById('switchAccountBtn');
  const logoutBtn = document.getElementById('logoutBtn');
  const projectNameEl = document.getElementById('projectName');
  const projectNameInput = document.getElementById('projectNameInput');
  const projectMetaEl = document.getElementById('projectMeta');
  const projectStatusEl = document.getElementById('projectStatus');
  const projectModeEl = document.getElementById('projectMode');
  let projectNameDraft = '';
  let renamingProject = false;
  const lessonTitleInput = document.getElementById('lessonTitleInput');
  const lessonAudioInput = document.getElementById('lessonAudioInput');
  const lessonIntroInput = document.getElementById('lessonIntroInput');
  const publishLinkBox = document.getElementById('publishLinkBox');
  const studentLinkInput = document.getElementById('studentLinkInput');
  const publishLessonBtn = document.getElementById('publishLessonBtn');
  const copyStudentLinkBtn = document.getElementById('copyStudentLinkBtn');
  const openStudentBtn = document.getElementById('openStudentBtn');
  const publishStatus = document.getElementById('publishStatus');
  const publishClassSelect = document.getElementById('publishClassSelect');
  const toggleCreateClassBtn = document.getElementById('toggleCreateClassBtn');
  const createClassInlineBox = document.getElementById('createClassInlineBox');
  const newClassNameInput = document.getElementById('newClassNameInput');
  const newClassSubjectInput = document.getElementById('newClassSubjectInput');
  const confirmCreateClassBtn = document.getElementById('confirmCreateClassBtn');
  let teacherClasses = [];
  let publishMeta = { classId: '', inviteCode: '', className: '' };

  function publishMetaKey(pid) {
    return 'ai_teacher_publish_meta_' + String(pid || '');
  }

  function loadPublishMeta(pid) {
    try {
      const raw = localStorage.getItem(publishMetaKey(pid));
      if (!raw) return { classId: '', inviteCode: '', className: '' };
      const parsed = JSON.parse(raw);
      return {
        classId: parsed.classId || '',
        inviteCode: parsed.inviteCode || '',
        className: parsed.className || ''
      };
    } catch (e) {
      return { classId: '', inviteCode: '', className: '' };
    }
  }

  function savePublishMeta(pid, meta) {
    publishMeta = {
      classId: (meta && meta.classId) || '',
      inviteCode: (meta && meta.inviteCode) || '',
      className: (meta && meta.className) || ''
    };
    try {
      localStorage.setItem(publishMetaKey(pid), JSON.stringify(publishMeta));
    } catch (e) { /* ignore */ }
  }

  function studentJoinLinkFor(project) {
    const pid = project && project.id ? project.id : projectId;
    const invite = publishMeta.inviteCode;
    const cid = publishMeta.classId;
    if (window.AppStore && window.AppStore.buildStudentJoinLink && invite) {
      return window.AppStore.buildStudentJoinLink(invite, cid, pid);
    }
    if (!invite) return '';
    const params = new URLSearchParams();
    params.set('invite', invite);
    if (cid) params.set('classId', cid);
    if (pid) params.set('projectId', pid);
    // 进班入口统一到学生端 SPA
    return location.origin + '/student/course-center?' + params.toString();
  }

  async function refreshTeacherClasses(preferredId) {
    if (!window.AppStore || !window.AppStore.listTeacherClasses) return;
    try {
      teacherClasses = await window.AppStore.listTeacherClasses();
    } catch (e) {
      teacherClasses = [];
    }
    const prefer = preferredId || publishMeta.classId || '';
    publishClassSelect.innerHTML = '<option value="">请选择班级（必选）</option>';
    teacherClasses.forEach(function (c) {
      if (!c || !c.id) return;
      const opt = document.createElement('option');
      opt.value = c.id;
      opt.textContent = (c.name || '未命名班级') + (c.inviteCode ? ' · 邀请码 ' + c.inviteCode : '');
      opt.dataset.invite = c.inviteCode || '';
      opt.dataset.name = c.name || '';
      publishClassSelect.appendChild(opt);
    });
    if (prefer && teacherClasses.some(function (c) { return c.id === prefer; })) {
      publishClassSelect.value = prefer;
    }
  }
  const stepEls = [
    document.getElementById('step1'),
    document.getElementById('step2'),
    document.getElementById('step3'),
    document.getElementById('step4')
  ];

  const tabs = Array.from(document.querySelectorAll('.tab'));
  const panels = Array.from(document.querySelectorAll('.panel'));

  const scriptBtn = document.getElementById('scriptBtn');
  const scriptLoading = document.getElementById('scriptLoading');
  const scriptResult = document.getElementById('scriptResult');
  const copyScriptBtn = document.getElementById('copyScriptBtn');
  const regenScriptBtn = document.getElementById('regenScriptBtn');
  const exportScriptBtn = document.getElementById('exportScriptBtn');

  const chatBox = document.getElementById('chatBox');
  const chatShell = document.getElementById('chatShell');
  const chatResizeHandle = document.getElementById('chatResizeHandle');
  const questionInput = document.getElementById('questionInput');
  const answerBtn = document.getElementById('answerBtn');
  const resumeBtn = document.getElementById('resumeBtn');
  const answerLoading = document.getElementById('answerLoading');
  const interruptPanel = document.getElementById('interruptPanel');
  const interruptState = document.getElementById('interruptState');
  const interruptPosition = document.getElementById('interruptPosition');
  const interruptDetail = document.getElementById('interruptDetail');
  const qaPromptTags = document.getElementById('qaPromptTags');
  const promptTags = Array.from(document.querySelectorAll('#qaPromptTags .prompt-tag'));
  const qaMsgCount = document.getElementById('qaMsgCount');
  const qaClearBtn = document.getElementById('qaClearBtn');
  const qaExportBtn = document.getElementById('qaExportBtn');
  const qaCopyLastBtn = document.getElementById('qaCopyLastBtn');
  const qaHeightBtns = Array.from(document.querySelectorAll('[data-qa-h]'));
  const computerQaModeBar = document.getElementById('computerQaModeBar');
  const computerQuestionType = document.getElementById('computerQuestionType');
  let selectedComputerResourceId = '';
  const QA_HEIGHT_KEY = 'workspace.qaChatHeight';
  const QA_HEIGHT_MIN = 220;
  const QA_HEIGHT_MAX = () => Math.max(QA_HEIGHT_MIN, Math.floor(window.innerHeight * 0.78));
  let chatHistory = [];
  let chatResizeState = null;

  const voiceCards = Array.from(document.querySelectorAll('.voice-card'));
  const modeSegButtons = Array.from(document.querySelectorAll('#modeSeg button'));
  const cloudAudioUrl = document.getElementById('cloudAudioUrl');
  if (cloudAudioUrl && cloudAudioUrl.value.includes('paddlespeech.cdn.bcebos.com')) {
    cloudAudioUrl.value = '';
  }
  const audioBtn = document.getElementById('audioBtn');
  const audioLoading = document.getElementById('audioLoading');
  const audioResult = document.getElementById('audioResult');
  const playerCard = document.getElementById('playerCard');
  const playPauseBtn = document.getElementById('playPauseBtn');
  const interruptBtn = document.getElementById('interruptBtn');
  const lectureStateText = document.getElementById('lectureStateText');
  const lecturePositionText = document.getElementById('lecturePositionText');
  const seekBar = document.getElementById('seekBar');
  const timeLabel = document.getElementById('timeLabel');
  const speedBtns = Array.from(document.querySelectorAll('.speed-btn'));
  // 下方自定义播放条已移除：保留原生 <audio controls>，打断继续仍走问答区「继续讲解」
  let projectId = new URLSearchParams(location.search).get('projectId') || '';
  let currentProject = null;
  let projectSaveSeq = 0;
  let projectRecovering = false;
  let currentUser = bootUser;

  function notify(message, tone) {
    if (window.AppStore && window.AppStore.toast) {
      window.AppStore.toast(message, tone);
    } else {
      window.alert(message);
    }
  }

  function getUserInitial(name) {
    const raw = (name || '').trim();
    if (!raw) return '智';
    return raw.slice(0, 1).toUpperCase();
  }

  function syncAccountEntry() {
    currentUser = window.AppStore.currentUser();
    const username = currentUser && currentUser.username ? currentUser.username : '未登录';
    accountName.textContent = username;
    accountLabel.textContent = username;
    accountAvatar.textContent = getUserInitial(username);
  }

  function setAccountMenu(open) {
    accountMenu.classList.toggle('open', open);
    accountTrigger.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  function setProjectStatus(text, tone) {
    projectStatusEl.textContent = text;
    projectStatusEl.classList.remove('ok', 'warn');
    if (tone) projectStatusEl.classList.add(tone);
  }

  function formatProjectMeta(project) {
    if (!project) {
      return '上传 PPT 后会按文件名自动创建项目并保存；名称不对可直接点上方改名。';
    }
    const extras = [];
    if (project.meta) extras.push(project.meta);
    if (project.updatedAt) extras.push(`最近更新 ${new Date(project.updatedAt).toLocaleString('zh-CN')}`);
    return extras.join(' · ') || '项目已自动创建，讲稿与解析结果会保存到当前项目。';
  }

  function suggestProjectNameFromFile(fileOrName) {
    const raw = typeof fileOrName === 'string'
      ? fileOrName
      : (fileOrName && fileOrName.name ? fileOrName.name : '');
    const base = String(raw || '')
      .replace(/^已选择：/, '')
      .replace(/\\/g, '/')
      .split('/')
      .pop()
      .replace(/\.(pptx?|PPTX?)$/, '')
      .trim();
    return base || `工作台课程_${new Date().toISOString().slice(0, 10)}`;
  }

  function setProjectNameDisplay(name, editable) {
    const label = name || '未命名项目';
    if (projectNameEl) projectNameEl.textContent = label;
    if (!projectNameInput) return;
    if (document.activeElement === projectNameInput && renamingProject) return;
    projectNameInput.value = label;
    projectNameDraft = label;
    projectNameInput.disabled = !editable;
  }

  function isComputerProject() {
    return Boolean(currentProject && currentProject.subjectMode === 'computer');
  }

  function resourceTypeLabel(type) {
    return {
      source_code: '源代码',
      sql: 'SQL脚本',
      error_log: '错误日志',
      lab_document: '实验资料'
    }[type] || '专项资料';
  }

  function renderComputerResources() {
    const enabled = isComputerProject();
    computerResourcePanel.classList.toggle('show', enabled);
    labTaskPanel.classList.toggle('show', enabled);
    computerQaModeBar.style.display = enabled ? 'flex' : 'none';
    if (!enabled) {
      selectedComputerResourceId = '';
      return;
    }
    const resources = Array.isArray(currentProject.resources) ? currentProject.resources : [];
    resourceCountBadge.textContent = `${resources.length} 份`;
    if (!resources.length) {
      computerResourceList.innerHTML = '<div class="muted">尚未加入代码或实验资料。上传后可用于专项讲稿与问答。</div>';
      selectedComputerResourceId = '';
      return;
    }
    if (!resources.some((item) => item.id === selectedComputerResourceId)) {
      selectedComputerResourceId = resources[0].id;
    }
    computerResourceList.innerHTML = resources.map(function (item) {
      return `
        <article class="computer-resource-item ${item.id === selectedComputerResourceId ? 'active' : ''}" data-resource-id="${escapeHtml(item.id)}">
          <div class="computer-resource-top">
            <div>
              <div class="resource-name">${escapeHtml(item.fileName || '未命名资料')}</div>
              <div class="muted">${resourceTypeLabel(item.resourceType)} · ${escapeHtml(item.language || 'Text')}</div>
            </div>
            <button class="resource-link" type="button" data-delete-resource="${escapeHtml(item.id)}">删除</button>
          </div>
          <div class="resource-summary">${escapeHtml(item.structuredContent || '已完成文本解析')}</div>
        </article>
      `;
    }).join('');

    Array.from(computerResourceList.querySelectorAll('[data-resource-id]')).forEach(function (node) {
      node.addEventListener('click', function (event) {
        if (event.target.closest('[data-delete-resource]')) return;
        selectedComputerResourceId = node.getAttribute('data-resource-id') || '';
        renderComputerResources();
      });
    });
    Array.from(computerResourceList.querySelectorAll('[data-delete-resource]')).forEach(function (button) {
      button.addEventListener('click', async function () {
        const resourceId = button.getAttribute('data-delete-resource');
        if (!resourceId || !projectId) return;
        button.disabled = true;
        try {
          currentProject = await window.AppStore.deleteProjectResource(projectId, resourceId);
          renderComputerResources();
          notify('专项资料已删除', 'ok');
        } catch (err) {
          notify(err.message || '删除专项资料失败', 'err');
          button.disabled = false;
        }
      });
    });
  }

  function renderLabTasks() {
    if (!isComputerProject()) return;
    const tasks = Array.isArray(currentProject.labTasks) ? currentProject.labTasks : [];
    labTaskCountBadge.textContent = `${tasks.length} 个`;
    if (!tasks.length) {
      labTaskList.innerHTML = '<div class="muted">尚未生成实验任务。生成后将随课程发布给学生。</div>';
      return;
    }
    labTaskList.innerHTML = tasks.map(function (task) {
      const testCount = Array.isArray(task.testCases) ? task.testCases.length : 0;
      return `
        <article class="lab-task-item">
          <div class="computer-resource-top">
            <div>
              <div class="resource-name">${escapeHtml(task.title || '未命名实验')}</div>
              <div class="muted">${escapeHtml(task.language || 'Java')} · ${testCount} 个测试用例 · ${Number(task.timeLimitMs || 2000)}ms</div>
            </div>
            <button class="resource-link" type="button" data-delete-lab-task="${escapeHtml(task.id)}">删除</button>
          </div>
          <div class="resource-summary">${escapeHtml(task.description || '')}</div>
          <div class="muted">样例：${escapeHtml(task.sampleInput || '无输入')} → ${escapeHtml(task.sampleOutput || '无输出')}</div>
        </article>
      `;
    }).join('');
    Array.from(labTaskList.querySelectorAll('[data-delete-lab-task]')).forEach(function (button) {
      button.addEventListener('click', async function () {
        const taskId = button.getAttribute('data-delete-lab-task');
        if (!taskId || !projectId) return;
        button.disabled = true;
        try {
          currentProject = await window.AppStore.deleteLabTask(projectId, taskId);
          renderLabTasks();
          notify('实验任务已删除', 'ok');
        } catch (err) {
          button.disabled = false;
          notify(err.message || '删除实验任务失败', 'err');
        }
      });
    });
  }

  function setPublishStatus(text, tone) {
    publishStatus.className = tone === 'err' ? 'msg-err' : tone === 'ok' ? 'msg-ok' : 'muted';
    publishStatus.textContent = text;
  }

  function syncPublishBox() {
    if (!currentProject) {
      publishLessonBtn.disabled = true;
      publishLinkBox.classList.remove('show');
      studentLinkInput.value = '';
      copyStudentLinkBtn.style.display = 'none';
      copyStudentLinkBtn.disabled = true;
      openStudentBtn.style.display = 'none';
      setPublishStatus('请先绑定项目，再生成讲稿后发布。');
      return;
    }
    publishMeta = loadPublishMeta(currentProject.id);
    if (!lessonTitleInput.value.trim()) {
      lessonTitleInput.value = currentProject.lessonTitle || currentProject.name || '';
    }
    if (!lessonIntroInput.value.trim()) {
      lessonIntroInput.value = currentProject.lessonIntro || currentProject.summary || currentProject.meta || '';
    }
    if (!lessonAudioInput.value.trim()) {
      lessonAudioInput.value = currentProject.audioUrl || '';
    }
    if (publishMeta.classId && publishClassSelect) {
      publishClassSelect.value = publishMeta.classId;
    }
    const hasClass = !!(publishClassSelect && publishClassSelect.value);
    publishLessonBtn.disabled = !(currentScript.trim() && hasClass);
    const joinLink = studentJoinLinkFor(currentProject);
    if (currentProject.published && joinLink) {
      publishLinkBox.classList.add('show');
      studentLinkInput.value = joinLink;
      copyStudentLinkBtn.style.display = 'inline-flex';
      copyStudentLinkBtn.disabled = false;
      openStudentBtn.style.display = 'inline-flex';
      openStudentBtn.href = `/teacher-insight.html?projectId=${encodeURIComponent(currentProject.id)}`;
      const classHint = publishMeta.className ? `（班级：${publishMeta.className}）` : '';
      setPublishStatus(`已发布到班级${classHint}。请把学生端链接发给学生：未注册先注册，再加入班级学习。`, 'ok');
    } else if (currentProject.published && !joinLink) {
      publishLinkBox.classList.remove('show');
      studentLinkInput.value = '';
      copyStudentLinkBtn.style.display = 'none';
      copyStudentLinkBtn.disabled = true;
      openStudentBtn.style.display = 'inline-flex';
      openStudentBtn.href = `/teacher-insight.html?projectId=${encodeURIComponent(currentProject.id)}`;
      setPublishStatus('已发布，但尚未绑定班级。请选择班级后重新点「发布智课」。', 'err');
    } else {
      publishLinkBox.classList.remove('show');
      studentLinkInput.value = '';
      copyStudentLinkBtn.style.display = 'none';
      copyStudentLinkBtn.disabled = true;
      openStudentBtn.style.display = 'none';
      if (!currentScript.trim()) {
        setPublishStatus('完成讲稿后，选择班级即可发布到学生端。');
      } else if (!hasClass) {
        setPublishStatus('请选择发布班级；若没有班级，请先新建。');
      } else {
        setPublishStatus('已选班级，可发布到学生端。');
      }
    }
  }

  function syncProjectHeader() {
    if (!projectId) {
      setProjectNameDisplay('上传课件后自动建项目', false);
      projectMetaEl.textContent = '上传 PPT 后会按文件名自动创建项目；名称可随时修改，无需先去「我的备课」绑定。';
      projectModeEl.textContent = '待上传课件';
      projectModeEl.classList.remove('project');
      setProjectStatus('等待上传');
      return;
    }
    if (!currentProject) {
      setProjectNameDisplay('项目加载中...', false);
      projectMetaEl.textContent = '正在同步项目内容和工作台状态。';
      projectModeEl.textContent = '项目模式';
      projectModeEl.classList.add('project');
      setProjectStatus('正在加载', 'warn');
      return;
    }
    setProjectNameDisplay(currentProject.name || '未命名项目', true);
    projectMetaEl.textContent = formatProjectMeta(currentProject);
    projectModeEl.textContent = '项目模式';
    projectModeEl.classList.add('project');
    if (isComputerProject()) {
      projectModeEl.textContent = '计算机专项模式';
    }
    if (workflow.scriptReady) {
      setProjectStatus('项目已保存', 'ok');
    } else if (workflow.parsed) {
      setProjectStatus('已解析待生成');
    } else {
      setProjectStatus('项目已就绪', 'ok');
    }
  }

  function setProgressStep(step) {
    workflow.currentStep = step;
    stepEls.forEach((el, idx) => {
      const no = idx + 1;
      el.classList.remove('active', 'done');
      if (no < step) el.classList.add('done');
      if (no === step) el.classList.add('active');
    });
    updateWorkflowBadge();
  }

  function updateWorkflowBadge() {
    if (!workflow.parsed) {
      workflowBadge.textContent = '待解析课件';
      return;
    }
    if (!workflow.scriptReady) {
      workflowBadge.textContent = '已解析，待生成讲稿';
      return;
    }
    if (workflow.currentStep <= 3) {
      workflowBadge.textContent = '讲稿完成，可进入问答';
      return;
    }
    workflowBadge.textContent = '全流程已就绪';
  }

  function buildProjectSummary() {
    if (currentScript.trim()) {
      return `已解析 ${slides.length || 0} 页，讲稿已生成，可继续问答和讲解视频`;
    }
    if (pptRawText.trim()) {
      return `已解析 ${slides.length || 0} 页课件，待生成讲稿`;
    }
    return currentProject && currentProject.summary ? currentProject.summary : '项目已创建，待上传课件';
  }

  function pulseUnlockTabs() {
    tabs.forEach((t) => {
      if (t.disabled) return;
      t.classList.remove('unlock-pulse');
      void t.offsetWidth;
      t.classList.add('unlock-pulse');
    });
  }

  function updateTabLocks() {
    tabs.forEach((tab) => {
      const panelId = tab.dataset.tab;
      const needScriptReady = panelId === 'qaPanel' || panelId === 'voicePanel';
      const locked = needScriptReady && !workflow.scriptReady;
      tab.disabled = locked;
      tab.classList.toggle('locked', locked);
      if (locked) {
        tab.title = '请先完成讲稿生成';
      } else {
        tab.removeAttribute('title');
      }
    });
    if (!workflow.parsed) {
      tabLockHint.textContent = '请先在左侧完成 PPT 解析，右侧操作将自动开放。';
      tabLockHint.style.display = 'block';
    } else if (!workflow.scriptReady) {
      tabLockHint.textContent = '已解析课件，请先生成讲稿，再解锁问答和讲解视频。';
      tabLockHint.style.display = 'block';
    } else {
      tabLockHint.style.display = 'none';
    }
    workPanelZone.classList.toggle('locked', !workflow.parsed);
    workPanelZone.classList.toggle('unlocked', workflow.parsed);
    panelLockOverlay.setAttribute('aria-hidden', workflow.parsed ? 'true' : 'false');
    updateWorkflowBadge();
  }

  function setScriptGeneratingState(on) {
    isScriptGenerating = on;
    scriptBtn.classList.toggle('pulse', on);
    scriptBtn.textContent = on ? '停止生成' : '生成讲稿';
    scriptBtn.disabled = !workflow.parsed;
  }

  function setUploadIntentState(active) {
    uploadArea.classList.toggle('drag-intent', active);
    uploadBigHint.textContent = active ? '松开鼠标，立即解析！' : '拖拽 PPT 到这里，或点击选择文件';
    uploadSmallHint.textContent = active ? '系统已准备接收 .ppt / .pptx' : '支持 .ppt / .pptx，建议不超过 100MB';
  }

  function setLeftCollapsed(collapsed) {
    mainLayout.classList.toggle('collapsed-left', !!collapsed);
    const on = mainLayout.classList.contains('collapsed-left');
    collapseLeftBtn.textContent = on ? '<' : '收起';
    collapseLeftBtn.title = on ? '展开资料区' : '收起资料区';
  }

  function switchTab(tabId) {
    const target = tabs.find((x) => x.dataset.tab === tabId);
    if (!target || target.disabled) return;
    tabs.forEach((x) => x.classList.remove('active'));
    panels.forEach((p) => p.classList.remove('active'));
    target.classList.add('active');
    document.getElementById(tabId).classList.add('active');
    // 问答 / 语音讲解：收起左侧资料区，主内容占满整宽（与讲稿编辑体验一致）
    if (tabId === 'qaPanel' || tabId === 'voicePanel') {
      setLeftCollapsed(true);
    }
    if (workflow.parsed) {
      if (tabId === 'scriptPanel') setProgressStep(2);
      if (tabId === 'qaPanel') setProgressStep(3);
      if (tabId === 'voicePanel') setProgressStep(4);
    } else {
      setProgressStep(1);
    }
  }

  function getSelectedSlide() {
    if (selectedSlideIdx < 0 || selectedSlideIdx >= slides.length) return null;
    return slides[selectedSlideIdx];
  }

  function getFocusedPptText() {
    const focus = getSelectedSlide();
    if (!focus) return pptRawText;
    const focusText = focus.lines.join('\n') || '（此页无文本）';
    return `=== 第${focus.page}页 ===\n${focusText}`;
  }

  function updateCurrentSlideHint() {
    const focus = getSelectedSlide();
    if (!focus) {
      currentSlideHint.textContent = '当前定位：未选中页（默认基于全量课件）';
      slidePreview.textContent = '尚未选中页面';
      return;
    }
    const preview = (focus.lines[0] || '（此页无文本）').slice(0, 30);
    currentSlideHint.textContent = `当前定位：第 ${focus.page} 页 · ${preview}`;
    slidePreview.textContent = focus.lines.join('\n') || '（此页无文本）';
  }

  function setSelectedSlide(idx, syncTab = true) {
    if (!Number.isInteger(idx) || idx < 0 || idx >= slides.length) return;
    selectedSlideIdx = idx;
    Array.from(outlinePanel.querySelectorAll('.outline-item')).forEach((item, i) => {
      item.classList.toggle('active', i === idx);
    });
    updateCurrentSlideHint();
    syncLectureInterruptUi();
    prevSlideBtn.disabled = idx <= 0;
    nextSlideBtn.disabled = idx >= slides.length - 1;
    if (syncTab) switchTab('scriptPanel');
  }

  function typewriteScript(text) {
    const ticket = ++typingJobId;
    return new Promise((resolve) => {
      const total = text.length;
      let i = 0;
      function tick() {
        if (ticket !== typingJobId) return resolve();
        i = Math.min(total, i + 36);
        scriptResult.textContent = text.slice(0, i);
        if (i >= total) {
          scriptResult.innerHTML = renderMarkdown(text);
          return resolve();
        }
        requestAnimationFrame(tick);
      }
      scriptResult.textContent = '';
      requestAnimationFrame(tick);
    });
  }

  const escapeHtml = (str) => (str || '').replace(/[&<>"']/g, (s) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[s]));

  const formatTime = (sec) => {
    if (!Number.isFinite(sec)) return '00:00';
    const s = Math.floor(sec);
    const m = Math.floor(s / 60);
    const r = s % 60;
    return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`;
  };

  function editorEmptyState(title, desc) {
    return `
      <div class="empty-state">
        <div class="empty-shell">
          <div class="empty-illustration"></div>
          <div class="empty-title">${escapeHtml(title)}</div>
          <div class="empty-copy">${escapeHtml(desc)}</div>
          <div class="empty-tips">
            <span class="empty-tip">讲稿草稿</span>
            <span class="empty-tip">页级联动</span>
            <span class="empty-tip">可继续编辑</span>
          </div>
        </div>
      </div>
    `;
  }

  function setEditorEmptyState(title, desc) {
    scriptResult.innerHTML = editorEmptyState(title, desc);
  }

  function createLoadingTicker(el, messages) {
    if (!el || !Array.isArray(messages) || !messages.length) return () => {};
    let idx = 0;
    el.textContent = messages[0];
    const timer = setInterval(() => {
      idx = (idx + 1) % messages.length;
      el.textContent = messages[idx];
    }, 950);
    return () => clearInterval(timer);
  }

  function renderMarkdown(text) {
    const safe = escapeHtml(text || '');
    let html = safe
      .replace(/^###\s(.+)$/gm, '<h3>$1</h3>')
      .replace(/^##\s(.+)$/gm, '<h3>$1</h3>')
      .replace(/^#\s(.+)$/gm, '<h3>$1</h3>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    const lines = html.split('\n');
    let out = '';
    let inList = false;
    lines.forEach((line) => {
      const trimmed = line.trim();
      // 分页标记展示为小节标题，去掉 === 等装饰符号
      const pageMark = trimmed.match(/^(?:=+\s*)?第\s*(\d+)\s*页(?:=\s*)?$/);
      if (pageMark) {
        if (inList) {
          out += '</ul>';
          inList = false;
        }
        out += `<h3 class="script-page-mark">第 ${pageMark[1]} 页</h3>`;
        return;
      }
      if (/^\s*[-*]\s+/.test(line)) {
        if (!inList) {
          out += '<ul>';
          inList = true;
        }
        out += `<li>${line.replace(/^\s*[-*]\s+/, '')}</li>`;
      } else {
        if (inList) {
          out += '</ul>';
          inList = false;
        }
        if (trimmed) {
          out += `<p>${line}</p>`;
        }
      }
    });
    if (inList) out += '</ul>';

    return out || '<p>暂无内容</p>';
  }

  function getLectureAudio() {
    if (lectureAudio && document.body.contains(lectureAudio)) return lectureAudio;
    lectureAudio = document.getElementById('lectureAudio');
    return lectureAudio;
  }

  function getSlideLabel(idx = selectedSlideIdx) {
    if (idx >= 0 && idx < slides.length) {
      return `第 ${slides[idx].page} 页`;
    }
    return '全量讲稿';
  }

  function getLecturePositionLabel(audio = getLectureAudio(), at = null) {
    if (!audio) return '未生成语音';
    const current = Number.isFinite(at) ? at : audio.currentTime;
    const duration = Number.isFinite(audio.duration) ? audio.duration : NaN;
    return `${formatTime(current || 0)} / ${formatTime(duration)}`;
  }

  function syncLectureInterruptUi(detail) {
    const audio = getLectureAudio();
    const hasAudio = !!audio;
    const isInterrupted = lectureInterruptState.status === 'interrupted';
    const isPlaying = hasAudio && !audio.paused && !audio.ended;
    const isEnded = hasAudio && audio.ended;
    const positionLabel = isInterrupted
      ? getLecturePositionLabel(audio, lectureInterruptState.interruptedAt)
      : getLecturePositionLabel(audio);
    const slideLabel = isInterrupted
      ? getSlideLabel(lectureInterruptState.interruptedSlideIdx)
      : getSlideLabel();

    let statusText = '讲解状态：待生成语音';
    if (isInterrupted) {
      statusText = '讲解状态：已打断';
    } else if (isPlaying) {
      statusText = '讲解状态：正在讲解';
    } else if (isEnded) {
      statusText = '讲解状态：讲解完成';
    } else if (hasAudio) {
      statusText = audio.currentTime > 0 ? '讲解状态：已暂停' : '讲解状态：待播放';
    }

    if (lectureStateText) lectureStateText.textContent = statusText;
    if (lecturePositionText) lecturePositionText.textContent = `${slideLabel} · ${positionLabel}`;
    if (interruptState) interruptState.textContent = statusText;
    if (interruptPosition) interruptPosition.textContent = `${slideLabel} · ${positionLabel}`;
    if (interruptPanel) interruptPanel.classList.toggle('interrupted', isInterrupted);
    if (interruptBtn) interruptBtn.disabled = !isPlaying;
    if (resumeBtn) resumeBtn.disabled = !isInterrupted;

    if (interruptDetail) {
      if (detail) {
        interruptDetail.textContent = detail;
      } else if (isInterrupted) {
        const question = lectureInterruptState.interruptedQuestion
          ? `问题：${lectureInterruptState.interruptedQuestion}`
          : '请在下方输入打断问题。';
        interruptDetail.textContent = `已在 ${slideLabel} 的 ${formatTime(lectureInterruptState.interruptedAt)} 暂停。${question}`;
      } else if (isPlaying) {
        interruptDetail.textContent = '当前正在讲解，发送问题或点击“打断提问”会自动暂停并记录当前位置。';
      } else if (hasAudio) {
        interruptDetail.textContent = '播放讲解后，可以在任意时刻打断提问，回答后从原位置继续。';
      } else {
        interruptDetail.textContent = '播放讲解时，发送问题会自动暂停讲解并记录当前位置。';
      }
    }
  }

  function interruptLectureIfPlaying(question = '') {
    const audio = getLectureAudio();
    if (!audio || audio.paused || audio.ended) return false;
    interruptedAt = audio.currentTime || 0;
    wasInterrupted = true;
    lectureInterruptState.status = 'interrupted';
    lectureInterruptState.interruptedAt = interruptedAt;
    lectureInterruptState.interruptedSlideIdx = selectedSlideIdx;
    lectureInterruptState.interruptedQuestion = question || '';
    lectureInterruptState.interruptedText = getFocusedPptText();
    audio.pause();
    syncLectureInterruptUi();
    return true;
  }

  async function requestApi(url, options = {}) {
    const timeoutMs = typeof options.timeoutMs === 'number' ? options.timeoutMs : REQUEST_TIMEOUT;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    const fetchOptions = { credentials: 'same-origin', ...options };
    delete fetchOptions.timeoutMs;
    let externalAbortHandler = null;
    if (fetchOptions.signal) {
      if (fetchOptions.signal.aborted) controller.abort();
      externalAbortHandler = () => controller.abort();
      fetchOptions.signal.addEventListener('abort', externalAbortHandler, { once: true });
    }
    try {
      const response = await fetch(url, { ...fetchOptions, signal: controller.signal });
      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        const text = await response.text();
        if (response.status === 401 || /login/i.test(text || '')) {
          throw new Error('登录已失效，请重新登录后再解析');
        }
        throw new Error(text || `请求失败（状态码：${response.status}）`);
      }
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.message || `请求失败（状态码：${response.status}）`);
      if (typeof payload.code !== 'number' || payload.code !== 0) throw new Error(payload.message || '请求失败，请稍后重试');
      return payload;
    } catch (err) {
      if (err.name === 'AbortError') {
        if (fetchOptions.signal && fetchOptions.signal.aborted) {
          throw new Error('请求已停止');
        }
        throw new Error(`请求超时（${Math.floor(timeoutMs / 1000)}秒），请稍后重试`);
      }
      const msg = String((err && err.message) || err || '');
      if (/Failed to fetch|NetworkError|Load failed|network/i.test(msg)) {
        throw new Error('网络中断或服务重启，请确认已登录后重试解析（大课件已改为秒级抽文字）');
      }
      throw err;
    } finally {
      if (fetchOptions.signal && externalAbortHandler) {
        fetchOptions.signal.removeEventListener('abort', externalAbortHandler);
      }
      clearTimeout(timeoutId);
    }
  }

  function replaceProjectIdInUrl(nextId) {
    const url = new URL(location.href);
    if (nextId) {
      url.searchParams.set('projectId', nextId);
    } else {
      url.searchParams.delete('projectId');
    }
    history.replaceState({}, '', url.pathname + url.search + url.hash);
    projectId = nextId || '';
  }

  async function createProjectFromSuggestedName(suggestedName, meta) {
    const name = (suggestedName || '').trim() || suggestProjectNameFromFile('');
    const created = await window.AppStore.addProject(name, meta || '上传课件后自动创建');
    if (!created || !created.id) {
      throw new Error('自动创建项目失败');
    }
    replaceProjectIdInUrl(created.id);
    applyProjectRecord(created);
    setProjectStatus('已自动创建项目', 'ok');
    return created;
  }

  async function ensureProjectForUpload(file) {
    const suggested = suggestProjectNameFromFile(file || (fileName && fileName.textContent) || '');
    if (projectId && currentProject && currentProject.id === projectId) {
      const currentName = String(currentProject.name || '').trim();
      const looksPlaceholder = !currentName
        || /^(临时工作台|上传课件后自动建项目|工作台课程|未命名项目)$/.test(currentName)
        || /^工作台课程_/.test(currentName);
      if (looksPlaceholder && suggested && suggested !== currentName) {
        try {
          const updated = await window.AppStore.updateProject(projectId, {
            name: suggested,
            meta: currentProject.meta || `来自课件 ${file && file.name ? file.name : suggested}`
          });
          if (updated) applyProjectRecord(updated);
        } catch (e) {
          // 改名失败不阻断上传解析
        }
      }
      return true;
    }
    if (projectId) {
      try {
        const project = await window.AppStore.getProject(projectId);
        if (project) {
          applyProjectRecord(project);
          return ensureProjectForUpload(file);
        }
      } catch (err) {
        // fall through to create
      }
    }
    await createProjectFromSuggestedName(
      suggested,
      file && file.name ? `来自课件 ${file.name}` : '上传课件后自动创建'
    );
    notify(`已按课件自动创建项目「${suggested}」`, 'ok');
    return true;
  }

  async function recoverProjectBinding(reason) {
    if (projectRecovering) return false;
    projectRecovering = true;
    try {
      const suggested = suggestProjectNameFromFile(
        (fileName && fileName.textContent) || (pptFile.files && pptFile.files[0]) || ''
      );
      await createProjectFromSuggestedName(suggested, reason ? `恢复：${reason}` : '原项目不可用后自动创建');
      notify(`原项目不可用，已自动新建「${suggested}」`, 'ok');
      if (parseMsg) parseMsg.innerHTML = '';
      return true;
    } catch (e) {
      replaceProjectIdInUrl('');
      currentProject = null;
      syncProjectHeader();
      setProjectStatus('自动建项失败', 'warn');
      if (projectMetaEl) {
        projectMetaEl.textContent = `${reason || '项目不可用'}。请重新选择课件，系统会再试自动创建项目。`;
      }
      if (parseMsg) {
        parseMsg.innerHTML = `<span class="muted">自动建项失败（${escapeHtml(e.message || reason || '项目不存在')}）。请重新上传课件重试。</span>`;
      }
      return false;
    } finally {
      projectRecovering = false;
    }
  }

  async function ensureProjectBound() {
    if (projectId && currentProject && currentProject.id === projectId) {
      return true;
    }
    if (projectId) {
      try {
        const project = await window.AppStore.getProject(projectId);
        if (project) {
          applyProjectRecord(project);
          return true;
        }
      } catch (err) {
        return recoverProjectBinding(err.message || '项目不存在');
      }
    }
    const file = pptFile.files && pptFile.files[0];
    return ensureProjectForUpload(file || null);
  }

  async function renameCurrentProject(nextName) {
    const name = String(nextName || '').trim();
    if (!projectId || !name) return false;
    if (currentProject && currentProject.name === name) return true;
    renamingProject = true;
    setProjectStatus('正在改名...', 'warn');
    try {
      const updated = await window.AppStore.updateProject(projectId, { name });
      if (updated) {
        applyProjectRecord(updated);
      } else if (currentProject) {
        currentProject.name = name;
        syncProjectHeader();
      }
      setProjectStatus('项目名称已更新', 'ok');
      notify(`项目已改名为「${name}」`, 'ok');
      return true;
    } catch (err) {
      setProjectStatus(err.message || '改名失败', 'warn');
      notify(err.message || '改名失败，请稍后重试', 'err');
      syncProjectHeader();
      return false;
    } finally {
      renamingProject = false;
    }
  }

  function extractSlides(rawText) {
    const rows = (rawText || '').split(/\r?\n/);
    const result = [];
    let current = null;
    rows.forEach((r) => {
      const line = (r || '').trim();
      const m = line.match(/^===\s*第(\d+)页\s*===$/);
      if (m) {
        if (current) result.push(current);
        current = { page: Number(m[1]), lines: [] };
      } else if (current && line) {
        current.lines.push(line);
      }
    });
    if (current) result.push(current);
    return result;
  }

  function formatOutlineLines(lines) {
    const rows = lines && lines.length ? lines : ['（此页无文本）'];
    return rows.map((line) => {
      const text = String(line || '');
      if (text.startsWith('【图片内容识别】')) {
        return `<div class="outline-vision">${escapeHtml(text)}</div>`;
      }
      if (text.startsWith('【图片/图形】') || text.startsWith('【图片/图形内容】')) {
        return `<div class="outline-media">${escapeHtml(text)}</div>`;
      }
      return `<div>${escapeHtml(text)}</div>`;
    }).join('');
  }

  function renderOutline() {
    if (!slides.length) {
      outlinePanel.style.display = 'none';
      return;
    }
    outlinePanel.style.display = 'block';
    const visionPages = slides.filter((s) => (s.lines || []).some((l) => String(l).startsWith('【图片内容识别】'))).length;
    outlinePanel.innerHTML = (visionPages
      ? `<div class="outline-vision-summary">已解析图片内容 ${visionPages} 页（写入大纲，可供讲稿使用）</div>`
      : '') + slides.map((s, idx) => {
      const visionLine = (s.lines || []).find((l) => String(l).startsWith('【图片内容识别】'));
      const preview = (visionLine || s.lines[0] || '（此页无文本）').replace(/^【图片内容识别】/, '图识：').slice(0, 40);
      return `
        <div class="outline-item ${idx === 0 ? 'open active' : ''}" data-idx="${idx}">
          <button class="outline-toggle">
            <span>第 ${s.page} 页 · ${escapeHtml(preview)}</span>
            <span>${idx === 0 ? '▾' : '▸'}</span>
          </button>
          <div class="outline-content">${formatOutlineLines(s.lines)}</div>
        </div>
      `;
    }).join('');

    Array.from(outlinePanel.querySelectorAll('.outline-toggle')).forEach((btn) => {
      btn.addEventListener('click', () => {
        const item = btn.closest('.outline-item');
        const idx = Number(item.dataset.idx || -1);
        item.classList.toggle('open');
        btn.querySelector('span:last-child').textContent = item.classList.contains('open') ? '▾' : '▸';
        setSelectedSlide(idx);
      });
    });
    if (selectedSlideIdx < 0 && slides.length > 0) {
      setSelectedSlide(0, false);
    }
  }

  async function persistProjectState(extra, allowRecover = true) {
    if (!projectId || !window.AppStore || !window.AppStore.updateProject) return null;
    const seq = ++projectSaveSeq;
    setProjectStatus('正在保存...', 'warn');
    try {
      const updated = await window.AppStore.updateProject(projectId, {
        pptRawText: pptRawText || '',
        script: currentScript || '',
        summary: buildProjectSummary(),
        ...(extra || {})
      });
      if (seq !== projectSaveSeq) return updated;
      currentProject = updated;
      syncProjectHeader();
      setProjectStatus('项目已保存', 'ok');
      return updated;
    } catch (err) {
      const msg = err && err.message ? String(err.message) : '';
      if (allowRecover && /项目不存在|无权访问/.test(msg)) {
        const recovered = await recoverProjectBinding(msg);
        if (recovered && projectId) {
          return persistProjectState(extra, false);
        }
      }
      if (seq === projectSaveSeq) {
        setProjectStatus(msg || '保存失败，请稍后重试', 'warn');
      }
      throw err;
    }
  }

  function applyProjectRecord(project) {
    currentProject = project;
    syncProjectHeader();
    syncPublishBox();
    renderComputerResources();
    renderLabTasks();
    if (!project) return;
    pptRawText = (project.pptRawText || '').trim();
    currentScript = project.script || '';
    slides = extractSlides(pptRawText);
    selectedSlideIdx = -1;
    renderOutline();

    if (pptRawText) {
      workflow.parsed = true;
      parseMsg.textContent = `已从项目恢复课件内容，共 ${slides.length || 0} 页。`;
      expandAllBtn.disabled = false;
      collapseAllBtn.disabled = false;
      setProgressStep(2);
    } else {
      workflow.parsed = false;
      parseMsg.textContent = '当前项目还没有解析课件，上传 PPT 后会自动保存。';
      expandAllBtn.disabled = true;
      collapseAllBtn.disabled = true;
    }

    if (currentScript.trim()) {
      workflow.scriptReady = true;
      scriptResult.innerHTML = renderMarkdown(currentScript);
      copyScriptBtn.disabled = false;
      regenScriptBtn.disabled = false;
      exportScriptBtn.disabled = false;
      answerBtn.disabled = false;
      audioBtn.disabled = false;
      setProgressStep(3);
    } else {
      workflow.scriptReady = false;
      setEditorEmptyState('等待生成讲稿', '完成左侧课件解析后，可生成结构化讲稿，并继续编辑、问答和讲解视频。');
      copyScriptBtn.disabled = true;
      regenScriptBtn.disabled = true;
      exportScriptBtn.disabled = true;
      answerBtn.disabled = true;
      audioBtn.disabled = true;
    }
    if (project.audioUrl) {
      lessonAudioInput.value = project.audioUrl;
    }
    if (project.lessonTitle) {
      lessonTitleInput.value = project.lessonTitle;
    }
    if (project.lessonIntro) {
      lessonIntroInput.value = project.lessonIntro;
    }
    updateCurrentSlideHint();
    updateTabLocks();
    syncPublishBox();
    setScriptGeneratingState(false);
  }

  chooseComputerResourceBtn.addEventListener('click', function () {
    computerResourceFile.click();
  });

  computerResourceFile.addEventListener('change', function () {
    const file = computerResourceFile.files && computerResourceFile.files[0];
    uploadComputerResourceBtn.disabled = !file;
    computerResourceHint.textContent = file
      ? `已选择：${file.name}`
      : '单个文件不超过 1MB，资料只绑定当前项目。';
  });

  uploadComputerResourceBtn.addEventListener('click', async function () {
    const file = computerResourceFile.files && computerResourceFile.files[0];
    if (!file || !projectId || !isComputerProject()) return;
    uploadComputerResourceBtn.disabled = true;
    computerResourceHint.textContent = '正在识别代码结构与错误线索...';
    try {
      const data = await window.AppStore.uploadProjectResource(projectId, file, {
        resourceType: computerResourceType.value,
        language: ''
      });
      currentProject = data.project || currentProject;
      selectedComputerResourceId = data.resource && data.resource.id ? data.resource.id : '';
      computerResourceFile.value = '';
      computerResourceHint.textContent = data.resource && data.resource.structuredContent
        ? data.resource.structuredContent
        : '专项资料解析成功';
      renderComputerResources();
      notify('专项资料已加入当前课程', 'ok');
    } catch (err) {
      computerResourceHint.textContent = err.message || '专项资料解析失败';
      notify(err.message || '专项资料解析失败', 'err');
    } finally {
      uploadComputerResourceBtn.disabled = !(computerResourceFile.files && computerResourceFile.files[0]);
    }
  });

  generateLabTaskBtn.addEventListener('click', async function () {
    if (!projectId || !isComputerProject()) return;
    generateLabTaskBtn.disabled = true;
    labTaskHint.textContent = '正在根据课程语言生成实验与测试用例...';
    try {
      const data = await window.AppStore.generateLabTask(projectId);
      currentProject = data.project || currentProject;
      labTaskHint.textContent = data.task
        ? `已生成：${data.task.title}（${data.task.language}）`
        : '实验任务生成成功';
      renderLabTasks();
      notify('实验任务已生成并绑定当前课程', 'ok');
    } catch (err) {
      labTaskHint.textContent = err.message || '实验任务生成失败';
      notify(err.message || '实验任务生成失败', 'err');
    } finally {
      generateLabTaskBtn.disabled = false;
    }
  });

  async function bootstrapProjectContext() {
    syncProjectHeader();
    if (!projectId) {
      // 带失效书签进工作台时 URL 可能无 projectId；有课件操作前会 ensure
      return;
    }
    try {
      const project = await window.AppStore.getProject(projectId);
      applyProjectRecord(project);
      if (parseMsg && /项目不存在|项目加载失败/.test(parseMsg.textContent || '')) {
        parseMsg.innerHTML = '';
      }
    } catch (err) {
      const msg = err.message || '项目加载失败';
      setProjectNameDisplay('正在自动重建项目...', false);
      projectMetaEl.textContent = msg;
      setProjectStatus('正在恢复', 'warn');
      const ok = await recoverProjectBinding(msg);
      if (!ok && parseMsg) {
        parseMsg.innerHTML = `<span class="muted">原项目不可用。请重新上传课件，系统会按文件名自动创建新项目。</span>`;
      }
    }
  }

  function clampQaHeight(px) {
    const max = QA_HEIGHT_MAX();
    const n = Number(px);
    if (!Number.isFinite(n)) return Math.min(420, max);
    return Math.max(QA_HEIGHT_MIN, Math.min(max, Math.round(n)));
  }

  function syncQaHeightButtons(activeHeight) {
    qaHeightBtns.forEach((btn) => {
      const target = Number(btn.dataset.qaH || '0');
      btn.classList.toggle('is-active', Math.abs(target - activeHeight) <= 8);
    });
  }

  function applyChatHeight(px, source = 'api') {
    if (!chatBox) return 0;
    const next = clampQaHeight(px);
    chatBox.style.height = `${next}px`;
    try {
      localStorage.setItem(QA_HEIGHT_KEY, String(next));
    } catch (e) {
      // ignore quota / private mode
    }
    syncQaHeightButtons(next);
    return next;
  }

  function restoreChatHeight() {
    let saved = null;
    try {
      saved = localStorage.getItem(QA_HEIGHT_KEY);
    } catch (e) {
      saved = null;
    }
    const fallback = Math.min(Math.floor(window.innerHeight * 0.48), 520);
    return applyChatHeight(saved || fallback, saved ? 'localStorage' : 'default');
  }

  function updateQaMsgCount() {
    if (qaMsgCount) qaMsgCount.textContent = `${chatHistory.length} 条`;
  }

  function renderEmptyChat() {
    chatBox.innerHTML = `<div class="muted" id="chatEmptyHint">问答记录会显示在这里。可拖动底部横条或点「矮/中/高」调整高度。</div>`;
    updateQaMsgCount();
  }

  function getPromptForTag(tag) {
    const template = tag.dataset.promptTemplate || '';
    if (template) {
      const page = selectedSlideIdx >= 0 ? selectedSlideIdx + 1 : 1;
      return template.replace(/\{page\}/g, String(page));
    }
    return tag.dataset.prompt || '';
  }

  function appendChat(role, text, meta = '') {
    const emptyHint = document.getElementById('chatEmptyHint');
    if (emptyHint) emptyHint.remove();
    const cls = role === 'user' ? 'user' : 'ai';
    const now = new Date();
    const timeLabel = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    const id = `qa-${Date.now()}-${chatHistory.length}`;
    chatHistory.push({ id, role, text, meta, time: timeLabel });
    const metaHtml = meta
      ? `<div class="muted" style="margin-top:4px;">${escapeHtml(meta)}</div>`
      : '';
    chatBox.insertAdjacentHTML('beforeend', `
      <div class="msg ${cls}" data-msg-id="${id}">
        <div class="bubble">
          <div>${escapeHtml(text)}</div>
          ${metaHtml}
          <div class="msg-meta-row">
            <span class="muted" style="font-size:12px;">${timeLabel}</span>
            <div class="msg-actions">
              <button type="button" class="msg-action" data-copy-msg="${id}">复制</button>
            </div>
          </div>
        </div>
      </div>
    `);
    chatBox.scrollTop = chatBox.scrollHeight;
    updateQaMsgCount();
  }

  async function copyTextToClipboard(text) {
    if (!text) return false;
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (e) {
      try {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        const ok = document.execCommand('copy');
        ta.remove();
        return ok;
      } catch (err) {
        return false;
      }
    }
  }

  function clearChatHistory() {
    chatHistory = [];
    renderEmptyChat();
    notify('已清空问答记录', 'ok');
  }

  function exportChatHistory() {
    if (!chatHistory.length) {
      notify('暂无问答记录可导出', 'err');
      return;
    }
    const lines = chatHistory.map((item) => {
      const who = item.role === 'user' ? '教师' : '助手';
      const meta = item.meta ? `\n[${item.meta}]` : '';
      return `[${item.time}] ${who}：\n${item.text}${meta}`;
    });
    const blob = new Blob([lines.join('\n\n')], { type: 'text/plain;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `课堂问答_${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
    notify('问答记录已导出', 'ok');
  }

  async function copyLastAiAnswer() {
    const last = [...chatHistory].reverse().find((item) => item.role === 'ai');
    if (!last) {
      notify('还没有可复制的回答', 'err');
      return;
    }
    const ok = await copyTextToClipboard(last.text);
    notify(ok ? '已复制最近一条回答' : '复制失败，请手动选择文本', ok ? 'ok' : 'err');
  }

  function bindChatResize() {
    if (!chatResizeHandle || !chatBox) return;
    const onMove = (clientY) => {
      if (!chatResizeState) return;
      const delta = clientY - chatResizeState.startY;
      applyChatHeight(chatResizeState.startH + delta, 'drag');
    };
    const onUp = () => {
      if (!chatResizeState) return;
      chatResizeHandle.classList.remove('is-dragging');
      chatResizeState = null;
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
    };
    const onPointerMove = (e) => onMove(e.clientY);
    const onPointerUp = () => onUp();

    chatResizeHandle.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      chatResizeState = {
        startY: e.clientY,
        startH: chatBox.offsetHeight || clampQaHeight(parseInt(chatBox.style.height, 10) || 420)
      };
      chatResizeHandle.classList.add('is-dragging');
      window.addEventListener('pointermove', onPointerMove);
      window.addEventListener('pointerup', onPointerUp);
    });
  }

  uploadArea.addEventListener('click', () => pptFile.click());
  uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
    setUploadIntentState(true);
  });
  uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
    setUploadIntentState(false);
  });
  uploadArea.addEventListener('drop', async (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    setUploadIntentState(false);
    dragDepth = 0;
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (!f) return;
    const dt = new DataTransfer();
    dt.items.add(f);
    pptFile.files = dt.files;
    fileName.textContent = `已选择：${f.name}`;
    try {
      await ensureProjectForUpload(f);
    } catch (err) {
      notify(err.message || '自动创建项目失败，解析时会再试', 'warn');
    }
  });
  pptFile.addEventListener('change', async () => {
    const f = pptFile.files && pptFile.files[0];
    fileName.textContent = f ? `已选择：${f.name}` : '';
    if (!f) return;
    try {
      await ensureProjectForUpload(f);
    } catch (err) {
      notify(err.message || '自动创建项目失败，解析时会再试', 'warn');
    }
  });

  window.addEventListener('dragenter', (e) => {
    e.preventDefault();
    const types = e.dataTransfer && e.dataTransfer.types ? Array.from(e.dataTransfer.types) : [];
    if (!types.includes('Files')) return;
    dragDepth += 1;
    setUploadIntentState(true);
  });

  window.addEventListener('dragleave', (e) => {
    e.preventDefault();
    const types = e.dataTransfer && e.dataTransfer.types ? Array.from(e.dataTransfer.types) : [];
    if (!types.includes('Files')) return;
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) setUploadIntentState(false);
  });

  window.addEventListener('drop', (e) => {
    e.preventDefault();
    dragDepth = 0;
    setUploadIntentState(false);
  });

  parseBtn.addEventListener('click', async () => {
    const f = pptFile.files && pptFile.files[0];
    if (!f) return notify('请先上传 PPT 文件', 'err');
    const lower = f.name.toLowerCase();
    if (!lower.endsWith('.ppt') && !lower.endsWith('.pptx')) {
      return notify('仅支持 .ppt / .pptx', 'err');
    }

    parseBtn.disabled = true;
    parseLoading.style.display = 'block';
    parseMsg.textContent = '正在解析...';
    const stopParseTicker = createLoadingTicker(parseLoading, [
      '正在快速提取各页文字…',
      '跳过页图渲染，争取秒级完成…'
    ]);

    try {
      const form = new FormData();
      form.append('file', f);
      const payload = await requestApi('/parse-ppt', { method: 'POST', body: form });
      const data = payload.data || {};
      pptRawText = data.rawText || '';
      slides = extractSlides(pptRawText);
      currentScript = '';
      workflow.scriptReady = false;
      copyScriptBtn.disabled = true;
      regenScriptBtn.disabled = true;
      exportScriptBtn.disabled = true;
      answerBtn.disabled = true;
      audioBtn.disabled = true;
      renderOutline();
      const visionHit = slides.filter((s) => (s.lines || []).some((l) => String(l).startsWith('【图片内容识别】') && !/未开启|未能|失败|缺少|上限/.test(String(l)))).length;
      const visionAny = slides.filter((s) => (s.lines || []).some((l) => String(l).startsWith('【图片内容识别】'))).length;
      parseMsg.textContent = `${payload.message || '解析成功'}，共 ${slides.length || 0} 页`
        + (visionHit ? `，其中 ${visionHit} 页已写入图片识别内容` : (visionAny ? `，图片识别已尝试 ${visionAny} 页（见大纲详情）` : ''));
      if (visionAny) {
        expandAllBtn.disabled = false;
        Array.from(outlinePanel.querySelectorAll('.outline-item')).forEach((item) => {
          item.classList.add('open');
          const icon = item.querySelector('.outline-toggle span:last-child');
          if (icon) icon.textContent = '▾';
        });
      }
      workflow.parsed = true;
      setScriptGeneratingState(false);
      expandAllBtn.disabled = false;
      collapseAllBtn.disabled = false;
      updateTabLocks();
      pulseUnlockTabs();
      switchTab('scriptPanel');
      setProgressStep(2);
      try {
        await ensureProjectForUpload(f);
        if (projectId) {
          await persistProjectState({
            name: (currentProject && currentProject.name) || suggestProjectNameFromFile(f),
            meta: `来自课件 ${f.name}`
          });
        }
      } catch (saveErr) {
        notify(saveErr.message || '课件已解析，但项目保存失败', 'warn');
        if (parseMsg && !/已解析|成功/.test(parseMsg.textContent || '')) {
          parseMsg.innerHTML = `<span class="msg-ok">PPT 已解析；项目保存稍后重试（${escapeHtml(saveErr.message || '保存失败')}）</span>`;
        }
      }
      syncPublishBox();
    } catch (err) {
      parseMsg.innerHTML = `<span class="msg-err">${escapeHtml(err.message)}</span>`;
    } finally {
      stopParseTicker();
      parseLoading.style.display = 'none';
      parseBtn.disabled = false;
    }
  });

  expandAllBtn.addEventListener('click', () => {
    Array.from(outlinePanel.querySelectorAll('.outline-item')).forEach((item) => {
      item.classList.add('open');
      const icon = item.querySelector('.outline-toggle span:last-child');
      if (icon) icon.textContent = '▾';
    });
  });

  collapseAllBtn.addEventListener('click', () => {
    Array.from(outlinePanel.querySelectorAll('.outline-item')).forEach((item) => {
      item.classList.remove('open');
      const icon = item.querySelector('.outline-toggle span:last-child');
      if (icon) icon.textContent = '▸';
    });
  });

  tabs.forEach((t) => {
    t.addEventListener('click', () => switchTab(t.dataset.tab));
  });

  async function generateScriptCore() {
    if (!pptRawText.trim()) return notify('请先解析 PPT', 'err');
    if (isScriptGenerating) {
      if (scriptAbortController) scriptAbortController.abort();
      typingJobId += 1;
      setScriptGeneratingState(false);
      scriptLoading.style.display = 'none';
      scriptResult.innerHTML = `<div class="muted">已停止生成，可重新发起。</div>`;
      return;
    }

    setScriptGeneratingState(true);
    regenScriptBtn.disabled = true;
    scriptLoading.style.display = 'block';
    scriptResult.innerHTML = `
      <div class="editor-skeleton">
        <div class="line"></div>
        <div class="line"></div>
        <div class="line"></div>
        <div class="line"></div>
      </div>
    `;
    const stopScriptTicker = createLoadingTicker(scriptLoading, [
      '正在梳理讲解顺序与知识逻辑...',
      '正在生成开场白、过渡语与重点提示...',
      '正在润色表达，让讲稿更适合课堂讲授...'
    ]);
    scriptAbortController = new AbortController();

    try {
      const sourceText = pptRawText.trim() || getFocusedPptText();
      const compact = sourceText.length > 12000 ? sourceText.slice(0, 12000) : sourceText;
      const payload = await requestApi('/generate-script', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pptText: compact,
          projectId: projectId,
          resourceId: selectedComputerResourceId
        }),
        signal: scriptAbortController.signal,
        timeoutMs: SCRIPT_TIMEOUT
      });
      const script = payload.data && payload.data.script ? payload.data.script : '';
      if (!script.trim()) throw new Error('讲稿生成结果为空');
      currentScript = script;
      await typewriteScript(script);
      workflow.scriptReady = true;
      updateTabLocks();
      pulseUnlockTabs();
      copyScriptBtn.disabled = false;
      regenScriptBtn.disabled = false;
      exportScriptBtn.disabled = false;
      answerBtn.disabled = false;
      audioBtn.disabled = false;
      setProgressStep(3);
      try {
        await ensureProjectBound();
        if (projectId) {
          await persistProjectState();
        }
      } catch (saveErr) {
        // 讲稿已生成：保存失败不得覆盖编辑区内容
        notify(saveErr.message || '讲稿已生成，但项目保存失败', 'warn');
      }
      syncPublishBox();
    } catch (err) {
      if (err.name === 'AbortError' || /aborted|终止|停止/.test(String(err.message || ''))) {
        scriptResult.innerHTML = `<div class="muted">已停止生成。</div>`;
      } else if (currentScript && currentScript.trim()) {
        notify(err.message || '操作失败', 'warn');
        scriptResult.innerHTML = renderMarkdown(currentScript);
      } else {
        scriptResult.innerHTML = `<div class="msg-err">${escapeHtml(err.message)}</div>`;
      }
    } finally {
      stopScriptTicker();
      scriptLoading.style.display = 'none';
      scriptAbortController = null;
      setScriptGeneratingState(false);
      regenScriptBtn.disabled = !currentScript.trim();
      copyScriptBtn.disabled = !currentScript.trim();
      exportScriptBtn.disabled = !currentScript.trim();
    }
  }

  scriptBtn.addEventListener('click', generateScriptCore);
  regenScriptBtn.addEventListener('click', generateScriptCore);

  copyScriptBtn.addEventListener('click', async () => {
    if (!currentScript) return;
    await navigator.clipboard.writeText(currentScript);
    copyScriptBtn.textContent = '已复制';
    setTimeout(() => { copyScriptBtn.textContent = '复制'; }, 1200);
  });

  exportScriptBtn.addEventListener('click', () => {
    if (!currentScript) return;
    const blob = new Blob([currentScript], { type: 'application/msword;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `讲稿_${Date.now()}.doc`;
    a.click();
    URL.revokeObjectURL(a.href);
  });

  promptTags.forEach((tag) => {
    tag.addEventListener('click', () => {
      const prompt = getPromptForTag(tag);
      questionInput.value = prompt;
      questionInput.focus();
    });
  });

  qaHeightBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      applyChatHeight(Number(btn.dataset.qaH || '420'), 'preset');
    });
  });

  if (qaClearBtn) qaClearBtn.addEventListener('click', clearChatHistory);
  if (qaExportBtn) qaExportBtn.addEventListener('click', exportChatHistory);
  if (qaCopyLastBtn) qaCopyLastBtn.addEventListener('click', copyLastAiAnswer);

  chatBox.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-copy-msg]');
    if (!btn) return;
    const id = btn.getAttribute('data-copy-msg');
    const item = chatHistory.find((m) => m.id === id);
    if (!item) return;
    const ok = await copyTextToClipboard(item.text);
    notify(ok ? '已复制该条消息' : '复制失败', ok ? 'ok' : 'err');
  });

  answerBtn.addEventListener('click', async () => {
    const q = questionInput.value.trim();
    if (!q) return notify('请输入问题', 'err');
    if (!pptRawText.trim()) return notify('请先解析 PPT', 'err');

    let interrupted = interruptLectureIfPlaying(q);
    if (!interrupted && lectureInterruptState.status === 'interrupted') {
      lectureInterruptState.interruptedQuestion = q;
      syncLectureInterruptUi();
      interrupted = true;
    }
    appendChat('user', q);
    questionInput.value = '';
    answerBtn.disabled = true;
    answerLoading.style.display = 'block';
    const stopAnswerTicker = createLoadingTicker(answerLoading, [
      '正在结合当前课件上下文作答...',
      '正在检索知识点并匹配最相关内容...',
      '正在组织更适合学生理解的回答方式...'
    ]);

    try {
      const payload = await requestApi('/answer-question', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectId: projectId,
          question: q,
          questionType: isComputerProject() ? computerQuestionType.value : '',
          resourceId: selectedComputerResourceId,
          pptText: getFocusedPptText() || pptRawText
        })
      });
      const data = payload.data || {};
      const source = data.source || 'unknown';
      const score = Number.isFinite(Number(data.hitScore)) ? Number(data.hitScore).toFixed(2) : '-';
      const knowledgeSources = Array.isArray(data.knowledgeSources) ? data.knowledgeSources : [];
      const citationText = knowledgeSources.length
        ? ` · 检索依据：${knowledgeSources.map((item) => {
            const title = `${item.title || '资料'}${item.section ? ` / ${item.section}` : ''}`;
            const rights = item.license ? ` [${item.license}]` : '';
            return `${title}${rights}${item.url ? ` ${item.url}` : ''}`;
          }).join('；')}`
        : '';
      const meta = source === 'dataset'
        ? `来源：知识库（score=${score}）`
        : source === 'computer_project'
          ? `来源：${data.sourceLabel || '当前计算机课程项目'} · 模式：${data.questionType || computerQuestionType.value}${citationText}`
          : `来源：${source}`;
      const tip = interrupted ? '已自动暂停讲解，可点击“继续讲解”恢复。' : '';
      appendChat('ai', (data.answer || '（空回答）') + (tip ? `\n\n${tip}` : ''), meta);
    } catch (err) {
      appendChat('ai', `问答失败：${err.message}`);
    } finally {
      stopAnswerTicker();
      answerLoading.style.display = 'none';
      answerBtn.disabled = false;
    }
  });

  questionInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!answerBtn.disabled) answerBtn.click();
    }
  });

  resumeBtn.addEventListener('click', async () => {
    const audio = getLectureAudio();
    if (!audio) return notify('请先生成讲课语音', 'err');
    try {
      if (wasInterrupted && interruptedAt > 0 && Number.isFinite(audio.duration) && interruptedAt < audio.duration) {
        audio.currentTime = interruptedAt;
      }
      await audio.play();
      wasInterrupted = false;
      lectureInterruptState.status = 'playing';
      lectureInterruptState.interruptedQuestion = '';
      resumeBtn.disabled = true;
      if (playPauseBtn) playPauseBtn.textContent = '暂停';
      syncLectureInterruptUi('已回到打断前位置继续讲解。');
    } catch (err) {
      notify(`继续讲解失败：${err.message || '请检查浏览器播放权限'}`, 'err');
    }
  });

  if (interruptBtn) {
    interruptBtn.addEventListener('click', () => {
      const interrupted = interruptLectureIfPlaying();
      if (!interrupted) return;
      switchTab('qaPanel');
      questionInput.focus();
      notify('已暂停讲解，请输入打断问题。', 'ok');
    });
  }

  voiceCards.forEach((card) => {
    card.addEventListener('click', () => {
      voiceCards.forEach((c) => c.classList.remove('active'));
      card.classList.add('active');
      selectedVoice = card.dataset.voice || 'gentle_female';
    });
  });

  modeSegButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      modeSegButtons.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      selectedMode = btn.dataset.mode || 'auto';
    });
  });

  function bindPlayerEvents(audioEl) {
    if (!audioEl) return;
    lectureAudio = audioEl;
    if (playerCard) playerCard.style.display = 'none';

    audioEl.addEventListener('timeupdate', () => {
      if (!Number.isFinite(audioEl.duration) || audioEl.duration <= 0) return;
      if (seekBar) seekBar.value = String((audioEl.currentTime / audioEl.duration) * 100);
      if (timeLabel) timeLabel.textContent = `${formatTime(audioEl.currentTime)} / ${formatTime(audioEl.duration)}`;
      syncLectureInterruptUi();
    });

    audioEl.addEventListener('play', () => {
      if (playPauseBtn) playPauseBtn.textContent = '暂停';
      if (lectureInterruptState.status !== 'interrupted') {
        lectureInterruptState.status = 'playing';
      }
      syncLectureInterruptUi();
    });

    audioEl.addEventListener('pause', () => {
      if (playPauseBtn) playPauseBtn.textContent = '播放';
      if (lectureInterruptState.status !== 'interrupted' && !audioEl.ended) {
        lectureInterruptState.status = 'paused';
      }
      syncLectureInterruptUi();
    });

    audioEl.addEventListener('ended', () => {
      lectureInterruptState.status = 'ended';
      wasInterrupted = false;
      interruptedAt = 0;
      syncLectureInterruptUi('本轮讲解已完成。');
    });

    audioEl.addEventListener('loadedmetadata', () => syncLectureInterruptUi());
    audioEl.addEventListener('error', () => {
      notify('音频无法播放：请检查 /audio 资源是否可访问', 'err');
    });
    syncLectureInterruptUi();
  }

  function resolveAudioMime(url) {
    const lower = String(url || '').toLowerCase();
    if (lower.includes('.wav')) return 'audio/wav';
    if (lower.includes('.ogg')) return 'audio/ogg';
    if (lower.includes('.m4a')) return 'audio/mp4';
    return 'audio/mpeg';
  }

  audioBtn.addEventListener('click', async () => {
    if (!currentScript.trim()) return notify('请先生成讲稿', 'err');

    audioBtn.disabled = true;
    audioLoading.style.display = 'block';
    audioResult.innerHTML = '';
    const stopAudioTicker = createLoadingTicker(audioLoading, [
      '正在合成讲解音频...',
      '正在生成学生端同款讲解视频...',
      '正在准备可发布学习资源...'
    ]);

    try {
      const payload = await requestApi('/generate-audio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script: currentScript,
          mode: selectedMode,
          audioUrl: cloudAudioUrl.value.trim(),
          voiceStyle: selectedVoice,
          projectId: projectId || '',
          pptRawText: pptRawText || '',
          lessonTitle: (currentProject && (currentProject.lessonTitle || currentProject.name)) || '课程讲解'
        }),
        timeoutMs: AUDIO_TIMEOUT
      });

      const data = payload.data || {};
      const lectureUrl = data.lectureUrl || data.digitalUrl || '';
      const okMsg = `<div class="msg-ok">✅ ${escapeHtml(payload.message || '语音合成成功，已生成讲解视频')}</div>`;

      const extra = lectureUrl
        ? `<div style="margin-top:8px;"><a href="${lectureUrl}" target="_blank" class="btn" style="display:inline-block;text-decoration:none;">查看讲解视频</a></div>
           <div class="muted" style="margin-top:6px;">该资源与学生端「AI视频讲解」为同一播放器，发布后学生即可学习。</div>`
        : '';

      const audioUrl = data.audioUrl || '';
      const audioMime = resolveAudioMime(audioUrl);
      audioResult.innerHTML = `
        ${okMsg}
        <div class="muted" style="margin-bottom:8px;">产物：讲解视频（沉浸式幻灯 + 旁白）。请用下方播放条收听旁白。</div>
        <audio id="lectureAudio" controls preload="metadata" style="width:100%;" src="${escapeHtml(audioUrl)}">
          <source src="${escapeHtml(audioUrl)}" type="${audioMime}" />
        </audio>
        ${extra}
      `;

      const audioEl = document.getElementById('lectureAudio');
      if (audioEl && audioUrl) {
        audioEl.src = audioUrl;
        audioEl.load();
      }
      if (data.audioUrl) {
        lessonAudioInput.value = data.audioUrl;
      }
      if (projectId) {
        try {
          currentProject = await window.AppStore.updateProject(projectId, {
            audioUrl: data.audioUrl || '',
            digitalUrl: lectureUrl || ''
          });
          syncProjectHeader();
        } catch (e) {
          // keep audio result even if project sync fails
        }
      }
      interruptedAt = 0;
      wasInterrupted = false;
      lectureInterruptState.status = 'idle';
      lectureInterruptState.interruptedAt = 0;
      lectureInterruptState.interruptedSlideIdx = -1;
      lectureInterruptState.interruptedQuestion = '';
      lectureInterruptState.interruptedText = '';
      resumeBtn.disabled = true;
      bindPlayerEvents(audioEl);
      setProgressStep(4);
      syncPublishBox();
    } catch (err) {
      audioResult.innerHTML = `<div class="msg-err">❌ ${escapeHtml(err.message)}</div>`;
    } finally {
      stopAudioTicker();
      audioLoading.style.display = 'none';
      audioBtn.disabled = false;
    }
  });

  renderEmptyChat();
  restoreChatHeight();
  bindChatResize();
  window.addEventListener('resize', () => {
    if (!chatBox) return;
    const current = parseInt(chatBox.style.height, 10) || chatBox.offsetHeight;
    applyChatHeight(current, 'window-resize');
  });
  syncLectureInterruptUi();
  syncAccountEntry();
  updateTabLocks();
  setScriptGeneratingState(false);
  setProgressStep(1);
  if (projectNameInput) {
    projectNameInput.addEventListener('focus', () => {
      renamingProject = true;
      projectNameDraft = projectNameInput.value;
    });
    projectNameInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        projectNameInput.blur();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        projectNameInput.value = projectNameDraft || (currentProject && currentProject.name) || '';
        renamingProject = false;
        projectNameInput.blur();
      }
    });
    projectNameInput.addEventListener('blur', async () => {
      const next = String(projectNameInput.value || '').trim();
      renamingProject = false;
      if (!projectId) {
        syncProjectHeader();
        return;
      }
      if (!next) {
        syncProjectHeader();
        return;
      }
      await renameCurrentProject(next);
    });
  }

  await bootstrapProjectContext();

  collapseLeftBtn.addEventListener('click', () => {
    setLeftCollapsed(!mainLayout.classList.contains('collapsed-left'));
  });

  expandFloatBtn.addEventListener('click', () => {
    setLeftCollapsed(false);
  });

  prevSlideBtn.addEventListener('click', () => {
    if (selectedSlideIdx > 0) setSelectedSlide(selectedSlideIdx - 1);
  });

  nextSlideBtn.addEventListener('click', () => {
    if (selectedSlideIdx < slides.length - 1) setSelectedSlide(selectedSlideIdx + 1);
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      setAccountMenu(false);
    }
    if (e.altKey && e.key === 'ArrowUp') {
      e.preventDefault();
      if (selectedSlideIdx > 0) setSelectedSlide(selectedSlideIdx - 1);
    }
    if (e.altKey && e.key === 'ArrowDown') {
      e.preventDefault();
      if (selectedSlideIdx < slides.length - 1) setSelectedSlide(selectedSlideIdx + 1);
    }
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      if (!scriptBtn.disabled || isScriptGenerating) {
        e.preventDefault();
        generateScriptCore();
      }
    }
  });

  accountTrigger.addEventListener('click', () => {
    setAccountMenu(!accountMenu.classList.contains('open'));
  });

  document.addEventListener('click', (e) => {
    if (!accountTrigger.contains(e.target) && !accountMenu.contains(e.target)) {
      setAccountMenu(false);
    }
  });

  switchAccountBtn.addEventListener('click', async () => {
    if (window.AppStore && window.AppStore.logout) {
      await window.AppStore.logout();
    }
    location.href = '/login.html';
  });

  logoutBtn.addEventListener('click', async () => {
    const currentRole = window.AppStore && window.AppStore.currentUser
      ? (window.AppStore.currentUser() || {}).activeRole
      : '';
    if (window.AppStore && window.AppStore.logout) {
      await window.AppStore.logout();
    }
    location.href = window.AppStore && window.AppStore.roleLoginPath
      ? window.AppStore.roleLoginPath(currentRole || 'teacher')
      : '/teacher/login.html';
  });

  publishClassSelect.addEventListener('change', () => {
    const opt = publishClassSelect.selectedOptions[0];
    if (opt && opt.value) {
      savePublishMeta(projectId || (currentProject && currentProject.id), {
        classId: opt.value,
        inviteCode: opt.dataset.invite || '',
        className: opt.dataset.name || opt.textContent || ''
      });
    }
    syncPublishBox();
  });

  toggleCreateClassBtn.addEventListener('click', () => {
    const show = createClassInlineBox.style.display === 'none' || !createClassInlineBox.style.display;
    createClassInlineBox.style.display = show ? 'flex' : 'none';
  });

  confirmCreateClassBtn.addEventListener('click', async () => {
    const name = (newClassNameInput.value || '').trim();
    if (!name) {
      notify('请填写班级名称。', 'err');
      return;
    }
    confirmCreateClassBtn.disabled = true;
    try {
      const room = await window.AppStore.createClassRoom({
        name: name,
        subject: (newClassSubjectInput.value || '').trim(),
        description: ''
      });
      if (!room || !room.id) throw new Error('班级创建失败');
      savePublishMeta(projectId || (currentProject && currentProject.id), {
        classId: room.id,
        inviteCode: room.inviteCode || '',
        className: room.name || name
      });
      await refreshTeacherClasses(room.id);
      createClassInlineBox.style.display = 'none';
      newClassNameInput.value = '';
      newClassSubjectInput.value = '';
      notify('班级已创建并选用', 'ok');
      syncPublishBox();
    } catch (err) {
      notify((err && err.message) || '创建班级失败', 'err');
    } finally {
      confirmCreateClassBtn.disabled = false;
    }
  });

  publishLessonBtn.addEventListener('click', async () => {
    if (!projectId) {
      notify('请先从「我的备课」进入备课台，再进行智课发布。', 'err');
      return;
    }
    if (!currentScript.trim()) {
      notify('请先生成讲稿后再发布。', 'err');
      return;
    }
    const classId = (publishClassSelect.value || '').trim();
    if (!classId) {
      notify('请先选择要发布到的班级；没有班级请先新建。', 'err');
      return;
    }
    publishLessonBtn.disabled = true;
    setPublishStatus('正在发布智课到班级...');
    try {
      const project = await window.AppStore.publishProject(projectId, {
        lessonTitle: lessonTitleInput.value.trim(),
        lessonIntro: lessonIntroInput.value.trim(),
        audioUrl: lessonAudioInput.value.trim(),
        digitalUrl: currentProject && currentProject.digitalUrl ? currentProject.digitalUrl : ''
      });
      const room = await window.AppStore.publishLessonToClass(classId, projectId);
      const opt = publishClassSelect.selectedOptions[0];
      savePublishMeta(projectId, {
        classId: classId,
        inviteCode: (room && room.inviteCode) || (opt && opt.dataset.invite) || publishMeta.inviteCode || '',
        className: (room && room.name) || (opt && opt.dataset.name) || publishMeta.className || ''
      });
      currentProject = project || currentProject;
      if (currentProject) currentProject.published = true;
      syncProjectHeader();
      syncPublishBox();
      notify('已发布到班级，请复制学生端链接发给学生。', 'ok');
    } catch (err) {
      setPublishStatus(err.message || '智课发布失败', 'err');
    } finally {
      publishLessonBtn.disabled = !(currentScript.trim() && publishClassSelect.value);
    }
  });

  copyStudentLinkBtn.addEventListener('click', async () => {
    if (!currentProject || !currentProject.published) return;
    const link = studentJoinLinkFor(currentProject);
    if (!link) {
      notify('请先选择班级并重新发布，再复制学生端链接。', 'err');
      return;
    }
    try {
      await navigator.clipboard.writeText(link);
      const rawText = copyStudentLinkBtn.textContent;
      copyStudentLinkBtn.textContent = '已复制学生端链接';
      setTimeout(() => {
        copyStudentLinkBtn.textContent = rawText;
      }, 1400);
    } catch (err) {
      notify('复制失败，请手动复制学生端链接。', 'err');
    }
  });

  refreshTeacherClasses(publishMeta.classId).then(function () {
    syncPublishBox();
  });
  })();
