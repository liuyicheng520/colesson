(function () {
  if (window.ZkHelp) return;

  var style = document.createElement('style');
  style.textContent = [
    '.zk-help{position:fixed;inset:0;z-index:1000;display:grid;place-items:center;padding:20px;}',
    '.zk-help[hidden]{display:none !important;}',
    '.zk-help-backdrop{position:absolute;inset:0;background:rgba(10,22,44,.5);backdrop-filter:blur(10px);}',
    '.zk-help-window{position:relative;width:min(640px,100%);max-height:min(820px,calc(100vh - 40px));display:flex;flex-direction:column;border-radius:24px;background:linear-gradient(180deg,#ffffff 0%,#f7fafc 100%);box-shadow:0 30px 80px rgba(12,28,58,.3);overflow:hidden;animation:zkHelpIn .28s cubic-bezier(.22,.7,.18,1);}',
    '.zk-help-window::before{content:"";height:3px;background:linear-gradient(90deg,#1f66ff,#5aa8ff 55%,#6fd3bf);}',
    '.zk-help-head{display:flex;justify-content:space-between;gap:16px;align-items:center;padding:22px 26px 8px;}',
    '.zk-help-kicker{margin:0;color:#1f66ff;font-size:11px;letter-spacing:.18em;font-weight:600;}',
    '.zk-help-head h2{margin:4px 0 0;color:#142033;font-size:26px;line-height:1.25;letter-spacing:-.02em;font-family:"ZK Display","PingFang SC","Microsoft YaHei",sans-serif;font-weight:600;}',
    '.zk-help-close{flex:0 0 auto;width:34px;height:34px;border:0;border-radius:999px;background:#eef3f9;color:#314158;font-size:18px;line-height:1;cursor:pointer;}',
    '.zk-help-close:hover{background:#e2eaf4;}',
    '.zk-help-body{overflow:auto;padding:8px 26px 24px;}',
    '.zk-help-lead{margin:0 0 16px;color:#5a6d86;font-size:14px;line-height:1.7;}',
    '.zk-help-stack{display:flex;flex-direction:column;gap:12px;}',
    '.zk-help-card{padding:16px 18px;border-radius:16px;background:#fff;border:1px solid #e6eef8;box-shadow:0 1px 0 rgba(20,40,80,.03);}',
    '.zk-help-card h3{margin:0 0 10px;display:inline-flex;align-items:center;gap:8px;color:#142033;font-size:15px;font-weight:650;}',
    '.zk-help-tag{display:inline-flex;align-items:center;justify-content:center;min-width:42px;height:22px;padding:0 8px;border-radius:999px;background:#ebf2ff;color:#1f66ff;font-size:12px;font-weight:650;letter-spacing:.02em;}',
    '.zk-help-card p{margin:0;color:#45586f;font-size:14px;line-height:1.8;}',
    '.zk-help-card .zk-name{color:#1a2b44;font-weight:600;}',
    '.zk-help-block{margin-top:18px;padding:16px 18px;border-radius:16px;background:#fff;border:1px solid #e6eef8;}',
    '.zk-help-block h3{margin:0 0 12px;color:#1f66ff;font-size:13px;letter-spacing:.08em;font-weight:650;}',
    '.zk-help-steps{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:10px;}',
    '.zk-help-steps li{display:grid;grid-template-columns:28px 1fr;gap:10px;align-items:start;color:#314158;font-size:14px;line-height:1.75;}',
    '.zk-help-num{width:28px;height:28px;border-radius:999px;display:grid;place-items:center;background:#eef4ff;color:#1f66ff;font-size:12px;font-weight:700;}',
    '.zk-help-block p{margin:0;color:#314158;font-size:14px;line-height:1.8;}',
    '.zk-help-foot{margin:16px 0 0;padding:12px 14px;border-radius:12px;background:#f4f7fb;color:#6b7c93;font-size:12px;line-height:1.7;}',
    '@media (max-width:640px){.zk-help{padding:10px;}.zk-help-head,.zk-help-body{padding-left:16px;padding-right:16px;}.zk-help-head h2{font-size:22px;}}',
    '@media (prefers-reduced-motion:reduce){.zk-help-window{animation:none;}}',
    '@keyframes zkHelpIn{from{opacity:0;transform:translateY(10px) scale(.985);}}'
  ].join('');
  document.head.appendChild(style);

  var root = document.createElement('div');
  root.className = 'zk-help';
  root.hidden = true;
  root.innerHTML = [
    '<div class="zk-help-backdrop" data-zk-close></div>',
    '<div class="zk-help-window" role="dialog" aria-modal="true" aria-labelledby="zkHelpTitle">',
    '<div class="zk-help-head">',
    '<div><p class="zk-help-kicker">智课共生</p><h2 id="zkHelpTitle">帮助中心</h2></div>',
    '<button class="zk-help-close" type="button" data-zk-close aria-label="关闭">×</button>',
    '</div>',
    '<div class="zk-help-body">',
    '<p class="zk-help-lead">老师和学生可以按身份查看用法。</p>',
    '<div class="zk-help-stack">',
    '<section class="zk-help-card"><h3><span class="zk-help-tag">老师</span></h3>',
    '<p>从教师入口登录，打开 <span class="zk-name">备课台</span>。先上传课件，再生成讲稿。讲稿是草稿，请改完再用。课上可以提问，也可以让数字人朗读讲稿。备课与学情在顶部菜单，改密码在个人中心。</p></section>',
    '<section class="zk-help-card"><h3><span class="zk-help-tag">学生</span></h3>',
    '<p>从学生入口进入学习首页，打开 <span class="zk-name">课程中心</span>。没听懂就去 <span class="zk-name">智能答疑</span>，问题尽量写具体。关掉页面也没关系，下次登录会尽量回到正在做的任务。</p></section>',
    '</div>',
    '<section class="zk-help-block"><h3>账号和密码</h3>',
    '<ol class="zk-help-steps">',
    '<li><span class="zk-help-num">1</span><span>没有账号，去开通中心。密码至少 6 位，要输入两次。</span></li>',
    '<li><span class="zk-help-num">2</span><span>还记得旧密码：登录后在个人中心修改。</span></li>',
    '<li><span class="zk-help-num">3</span><span>完全忘了：老师提交重置申请，等管理员处理。学生告诉任课老师。不要把密码发给同学。</span></li>',
    '</ol></section>',
    '<section class="zk-help-block"><h3>还是解决不了</h3>',
    '<p>上课内容、作业、进不了某一课，找任课老师。账号开不了，或密码等了很久，找平台管理员。</p>',
    '</section>',
    '<p class="zk-help-foot">生成的讲稿和回答请自己再看一遍。公式、史实和实验步骤，请按课本核对。</p>',
    '</div></div>'
  ].join('');
  document.body.appendChild(root);

  var lastFocus = null;

  function open() {
    lastFocus = document.activeElement;
    root.hidden = false;
    document.body.style.overflow = 'hidden';
    var closeBtn = root.querySelector('.zk-help-close');
    if (closeBtn) closeBtn.focus();
  }

  function close() {
    root.hidden = true;
    document.body.style.overflow = '';
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  root.addEventListener('click', function (e) {
    if (e.target && e.target.hasAttribute('data-zk-close')) close();
  });

  document.addEventListener('keydown', function (e) {
    if (!root.hidden && e.key === 'Escape') close();
  });

  document.addEventListener('click', function (e) {
    var trigger = e.target && e.target.closest ? e.target.closest('[data-help]') : null;
    if (!trigger) return;
    e.preventDefault();
    open();
  });

  window.ZkHelp = { open: open, close: close };
})();
