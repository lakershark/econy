// ── Section name translations ────────────────────────────────────────────────
const SECTION_NAMES = {
  'The world this week': '本周要闻',
  'Leaders': '社论',
  'Letters': '读者来信',
  'By Invitation': '特邀评论',
  'Briefing': '深度报道',
  'United States': '美国',
  'The Americas': '美洲',
  'Asia': '亚洲',
  'China': '中国',
  'Middle East & Africa': '中东与非洲',
  'Europe': '欧洲',
  'Britain': '英国',
  'International': '国际',
  'Business': '商业',
  'Finance & economics': '金融与经济',
  'Science & technology': '科学与技术',
  'Culture': '文化',
  'Economic & financial indicators': '经济与金融指标',
  'Obituary': '讣告',
  // New Yorker sections
  'Fiction': '小说',
  'Poetry': '诗歌',
  'Annals of': '纪实：',
  'Comment': '评论',
  'Profiles': '人物特写',
  'Reporting': '新闻报道',
  'The Talk of the Town': '城中话题',
};

function sectionLabel(name) {
  return SECTION_NAMES[name] || name;
}

// ── Magazine index ──────────────────────────────────────────────────────────
// Add new issues here as they are processed
const ISSUES = {
  economist: [
    { date: '2026-04-25', label: '2026-04-25', file: 'data/economist/2026-04-25.json' },
    { date: '2026-04-18', label: '2026-04-18', file: 'data/economist/2026-04-18.json' },
    { date: '2026-04-11', label: '2026-04-11', file: 'data/economist/2026-04-11.json' },
    { date: '2026-04-04', label: '2026-04-04', file: 'data/economist/2026-04-04.json' },
    { date: '2026-03-28', label: '2026-03-28', file: 'data/economist/2026-03-28.json' },
  ],
  new_yorker: [
    { date: '2026-04-20', label: '2026-04-20', file: 'data/new_yorker/2026-04-20.json' },
    { date: '2026-04-13', label: '2026-04-13', file: 'data/new_yorker/2026-04-13.json' },
    { date: '2026-04-06', label: '2026-04-06', file: 'data/new_yorker/2026-04-06.json' },
    { date: '2026-03-30', label: '2026-03-30', file: 'data/new_yorker/2026-03-30.json' },
  ],
};

// ── State ───────────────────────────────────────────────────────────────────
let currentIssue = null;
let focusedIdx = -1;
let allArticles = []; // flat list of article elements for keyboard nav

// ── Mobile sidebar toggle ─────────────────────────────────────────────────────
const menuBtn  = document.getElementById('menu-btn');
const sidebar  = document.getElementById('sidebar');
const overlay  = document.getElementById('overlay');

function openSidebar() {
  sidebar.classList.add('open');
  overlay.classList.add('visible');
}

function closeSidebar() {
  sidebar.classList.remove('open');
  overlay.classList.remove('visible');
}

menuBtn.addEventListener('click', () => {
  sidebar.classList.contains('open') ? closeSidebar() : openSidebar();
});

overlay.addEventListener('click', closeSidebar);

function updatePlaceholder() {
  const el = document.getElementById('placeholder-text');
  if (el) el.textContent = window.innerWidth <= 640 ? '☰ 请点击左上角选择一期杂志' : '← 请从左侧选择一期杂志';
}
window.addEventListener('resize', updatePlaceholder);
updatePlaceholder();

// ── Sidebar setup ────────────────────────────────────────────────────────────
function buildSidebar() {
  for (const [mag, issues] of Object.entries(ISSUES)) {
    const list = document.getElementById(`list-${mag}`);
    const title = document.querySelector(`.mag-title[data-mag="${mag}"]`);

    if (issues.length === 0) {
      list.innerHTML = '<li style="color:#bbb;cursor:default">暂无数据</li>';
    }

    issues.forEach(issue => {
      const li = document.createElement('li');
      li.textContent = issue.label;
      li.dataset.file = issue.file;
      li.dataset.mag = mag;
      // Use touchend for iOS Safari (click often doesn't fire on <li>)
      let tapped = false;
      li.addEventListener('touchend', (e) => {
        e.preventDefault();
        tapped = true;
        loadIssue(issue.file, li);
      });
      li.addEventListener('click', () => { if (!tapped) loadIssue(issue.file, li); tapped = false; });
      list.appendChild(li);
    });

    title.addEventListener('click', () => {
      title.classList.toggle('open');
      list.classList.toggle('open');
    });

    // Auto-open if there are issues
    if (issues.length > 0) {
      title.classList.add('open');
      list.classList.add('open');
    }
  }
}

// ── Load & render issue ───────────────────────────────────────────────────────
async function loadIssue(file, li) {
  // Update active state
  document.querySelectorAll('.issue-list li').forEach(el => el.classList.remove('active'));
  li.classList.add('active');
  closeSidebar();

  // Show loading state
  document.getElementById('placeholder').hidden = false;
  document.getElementById('placeholder-text').textContent = '加载中...';
  document.getElementById('issue-view').hidden = true;

  try {
    const resp = await fetch(file + '?v=' + encodeURIComponent(file));
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const issue = await resp.json();
    currentIssue = issue;
    renderIssue(issue);
  } catch (e) {
    document.getElementById('placeholder').hidden = false;
    document.getElementById('placeholder-text').textContent = '加载失败: ' + e.message;
  }
}

function renderIssue(issue) {
  document.getElementById('placeholder').hidden = true;
  const view = document.getElementById('issue-view');
  view.hidden = false;

  const magName = issue.magazine === 'The Economist' ? 'The Economist' : 'The New Yorker';
  document.getElementById('issue-title').textContent = `${magName} · ${issue.issue_date}`;

  const totalArticles = issue.toc.reduce((n, s) => n + s.articles.length, 0);
  const withSummary = issue.toc.reduce((n, s) => n + s.articles.filter(a => a.summary).length, 0);
  document.getElementById('issue-meta').textContent =
    `共 ${totalArticles} 篇文章 · ${withSummary} 篇有摘要`;

  const toc = document.getElementById('toc');
  toc.innerHTML = '';
  allArticles = [];
  focusedIdx = -1;

  issue.toc.forEach(section => {
    const block = document.createElement('div');
    block.className = 'section-block';

    const heading = document.createElement('div');
    heading.className = 'section-name';
    heading.textContent = sectionLabel(section.section);
    block.appendChild(heading);

    section.articles.forEach(art => {
      const el = buildArticleEl(art);
      block.appendChild(el);
      allArticles.push(el);
    });

    toc.appendChild(block);
  });

  // Wire expand/collapse all
  document.getElementById('btn-expand-all').onclick = () => {
    allArticles.forEach(el => el.classList.add('open'));
  };
  document.getElementById('btn-collapse-all').onclick = () => {
    allArticles.forEach(el => el.classList.remove('open'));
  };
}

function buildArticleEl(art) {
  const el = document.createElement('div');
  el.className = 'article';

  const header = document.createElement('div');
  header.className = 'article-header';

  const toggle = document.createElement('span');
  toggle.className = 'article-toggle';
  toggle.textContent = art.summary ? '▶' : '·';

  const textCol = document.createElement('div');
  textCol.style.flex = '1';

  const title = document.createElement('div');
  title.className = 'article-title';
  title.textContent = art.title_zh || art.title;

  textCol.appendChild(title);

  const subText = art.subtitle_zh || art.subtitle;
  if (subText) {
    const sub = document.createElement('div');
    sub.className = 'article-subtitle';
    sub.textContent = subText;
    textCol.appendChild(sub);
  }

  header.appendChild(toggle);
  header.appendChild(textCol);
  el.appendChild(header);

  const body = document.createElement('div');
  body.className = 'article-body';
  if (art.summary) {
    body.textContent = art.summary;
  } else {
    body.innerHTML = '<span class="no-summary">暂无摘要</span>';
  }
  el.appendChild(body);

  if (art.summary) {
    header.addEventListener('click', () => {
      el.classList.toggle('open');
    });
  }

  return el;
}

// ── Search ───────────────────────────────────────────────────────────────────
document.getElementById('search').addEventListener('input', e => {
  const q = e.target.value.trim().toLowerCase();

  if (!q) {
    allArticles.forEach(el => {
      el.classList.remove('search-hidden');
      // Restore original text
      const titleEl = el.querySelector('.article-title');
      titleEl.textContent = titleEl.textContent; // rerender without marks
    });
    // Restore section visibility
    document.querySelectorAll('.section-block').forEach(s => s.hidden = false);
    return;
  }

  allArticles.forEach(el => {
    const titleEl = el.querySelector('.article-title');
    const subtitleEl = el.querySelector('.article-subtitle');
    const bodyEl = el.querySelector('.article-body');

    const title = titleEl.textContent.toLowerCase();
    const subtitle = subtitleEl ? subtitleEl.textContent.toLowerCase() : '';
    const body = bodyEl ? bodyEl.textContent.toLowerCase() : '';

    const match = title.includes(q) || subtitle.includes(q) || body.includes(q);
    el.classList.toggle('search-hidden', !match);
    if (match) el.classList.add('open');
  });

  // Hide sections with no visible articles
  document.querySelectorAll('.section-block').forEach(block => {
    const anyVisible = [...block.querySelectorAll('.article')].some(
      a => !a.classList.contains('search-hidden')
    );
    block.hidden = !anyVisible;
  });
});

// ── Keyboard navigation ───────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  const tag = document.activeElement.tagName;
  if (tag === 'INPUT') return;

  const visible = allArticles.filter(el => !el.classList.contains('search-hidden'));
  if (!visible.length) return;

  if (e.key === 'j' || e.key === 'ArrowDown') {
    e.preventDefault();
    if (focusedIdx >= 0) visible[focusedIdx]?.classList.remove('focused');
    focusedIdx = Math.min(focusedIdx + 1, visible.length - 1);
    const el = visible[focusedIdx];
    el.classList.add('focused');
    el.scrollIntoView({ block: 'nearest' });
  } else if (e.key === 'k' || e.key === 'ArrowUp') {
    e.preventDefault();
    if (focusedIdx >= 0) visible[focusedIdx]?.classList.remove('focused');
    focusedIdx = Math.max(focusedIdx - 1, 0);
    const el = visible[focusedIdx];
    el.classList.add('focused');
    el.scrollIntoView({ block: 'nearest' });
  } else if (e.key === ' ' || e.key === 'Enter') {
    e.preventDefault();
    if (focusedIdx >= 0) visible[focusedIdx]?.classList.toggle('open');
  } else if (e.key === '/') {
    e.preventDefault();
    document.getElementById('search').focus();
  } else if (e.key === 'Escape') {
    document.getElementById('search').value = '';
    document.getElementById('search').dispatchEvent(new Event('input'));
    if (focusedIdx >= 0) visible[focusedIdx]?.classList.remove('focused');
    focusedIdx = -1;
  }
});

// ── Init ─────────────────────────────────────────────────────────────────────
buildSidebar();

// Auto-load the first available issue
const firstEconomist = ISSUES.economist[0];
if (firstEconomist) {
  const li = document.querySelector(`.issue-list li[data-file="${firstEconomist.file}"]`);
  if (li) loadIssue(firstEconomist.file, li);
}
