// ── State ─────────────────────────────────────────────────────────────────────
let currentPage = 1;
const itemsPerPage = 50;

// Lightbox state — set each time a poster is opened
let _lightboxFilename     = '';   // decoded filename, e.g. "Alien (1979).webp"
let _lightboxFilenameYear = '';   // 4-digit year parsed from filename, e.g. "1979"
let _lightboxGridItem     = null; // reference to the .grid-item DOM node

// ── Helpers ───────────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Dark mode ─────────────────────────────────────────────────────────────────
function toggleDarkMode() {
  document.body.classList.toggle('light-mode');
  const mode = document.body.classList.contains('light-mode') ? 'light' : 'dark';
  localStorage.setItem('theme', mode);
  document.getElementById('darkModeLabel').textContent = mode === 'dark' ? 'Dark Mode' : 'Light Mode';
}

// ── Lightbox ──────────────────────────────────────────────────────────────────
function openLightbox(imageSrc, element) {
  const lightbox      = document.getElementById('lightbox');
  const lightboxImage = document.getElementById('lightboxImage');
  const parent        = element.closest('.grid-item');
  const title       = parent?.dataset.title  || 'N/A';
  const displayYear = parent?.dataset.year   || 'N/A';
  const rating      = parent?.dataset.rating || 'N/A';
  const plot        = parent?.dataset.plot   || 'No plot available';

  // Decode the filename from the absolute URL the browser stores in img.src
  try {
    const url = new URL(imageSrc, window.location.origin);
    _lightboxFilename = decodeURIComponent(url.pathname.split('/posters/')[1] || '');
  } catch (_) {
    _lightboxFilename = decodeURIComponent(imageSrc.split('/posters/').pop());
  }
  const yrMatch         = _lightboxFilename.match(/\((\d{4})\)/);
  _lightboxFilenameYear = yrMatch ? yrMatch[1] : '';
  _lightboxGridItem     = parent;

  document.getElementById('metadata')?.remove();
  lightboxImage.src = imageSrc;
  lightbox.classList.add('show');

  const meta = document.createElement('div');
  meta.id = 'metadata';
  meta.innerHTML = `
    <h2>
      <span id="lb-title" class="editable-title">${escHtml(title)}</span>${displayYear !== 'N/A' ? `<span id="lb-year"> (${escHtml(displayYear)})</span>` : ''}
      <button class="lb-icon-btn" title="Edit title" onclick="startEditTitle()">✏</button>
    </h2>
    <p><strong>IMDb Rating:</strong> ${escHtml(rating)}</p>
    <p><strong>Plot:</strong> ${escHtml(plot)}</p>
  `;
  document.getElementById('closeLightbox').insertAdjacentElement('afterend', meta);
}

function closeLightbox() {
  const lightbox = document.getElementById('lightbox');
  lightbox.classList.remove('show');
  document.getElementById('lightboxImage').src = '';
  document.getElementById('metadata')?.remove();
}

// ── Title editing ─────────────────────────────────────────────────────────────
function startEditTitle() {
  const h2           = document.querySelector('#metadata h2');
  const currentTitle = document.getElementById('lb-title')?.textContent || '';
  h2.dataset.origTitle = currentTitle;

  h2.innerHTML = `
    <input id="title-edit-input" class="title-edit-input" type="text" value="${escHtml(currentTitle)}" />
    <button class="lb-icon-btn save-btn"   onclick="saveTitle()">✓ Save</button>
    <button class="lb-icon-btn cancel-btn" onclick="cancelEditTitle()">✕</button>
  `;

  const input = document.getElementById('title-edit-input');
  input.focus();
  input.select();
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter')  saveTitle();
    if (e.key === 'Escape') cancelEditTitle();
  });
}

function cancelEditTitle() {
  const h2    = document.querySelector('#metadata h2');
  const title = h2?.dataset.origTitle || '';
  const yr    = _lightboxFilenameYear;
  h2.innerHTML = `
    <span id="lb-title" class="editable-title">${escHtml(title)}</span>${yr ? `<span id="lb-year"> (${escHtml(yr)})</span>` : ''}
    <button class="lb-icon-btn" title="Edit title" onclick="startEditTitle()">✏</button>
  `;
}

async function saveTitle() {
  const input = document.getElementById('title-edit-input');
  if (!input) return;
  const newTitle = input.value.trim();
  if (!newTitle) { input.focus(); return; }

  const btn = document.querySelector('#metadata .save-btn');
  if (btn) { btn.disabled = true; btn.textContent = '…'; }

  try {
    const resp = await fetch('/rename', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        old_filename: _lightboxFilename,
        new_title:    newTitle,
        year:         _lightboxFilenameYear,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      alert(data.error || 'Rename failed');
      if (btn) { btn.disabled = false; btn.textContent = '✓ Save'; }
      return;
    }

    // Update module state
    _lightboxFilename     = data.new_filename;
    const yrMatch         = _lightboxFilename.match(/\((\d{4})\)/);
    _lightboxFilenameYear = yrMatch ? yrMatch[1] : _lightboxFilenameYear;

    // Update lightbox title display
    const h2 = document.querySelector('#metadata h2');
    const yr = _lightboxFilenameYear;
    h2.innerHTML = `
      <span id="lb-title" class="editable-title">${escHtml(data.new_title)}</span>${yr ? `<span id="lb-year"> (${escHtml(yr)})</span>` : ''}
      <button class="lb-icon-btn" title="Edit title" onclick="startEditTitle()">✏</button>
    `;

    // Update lightbox image src
    document.getElementById('lightboxImage').src = '/posters/' + data.new_filename;

    // Update the grid item
    if (_lightboxGridItem) {
      _lightboxGridItem.dataset.title = data.new_title;
      const img = _lightboxGridItem.querySelector('img');
      if (img) img.src = '/posters/' + data.new_filename;
    }

  } catch (err) {
    alert('Network error: ' + err.message);
    if (btn) { btn.disabled = false; btn.textContent = '✓ Save'; }
  }
}

// ── Upload ────────────────────────────────────────────────────────────────────
function openUploadModal() {
  document.getElementById('upload-modal').classList.add('show');
}

function closeUploadModal() {
  document.getElementById('upload-modal').classList.remove('show');
  document.getElementById('upload-form').reset();
  const btn = document.querySelector('#upload-form [type="submit"]');
  if (btn) { btn.disabled = false; btn.textContent = 'Upload'; }
}

function addNewPosterToGrid(filename, title, year) {
  const container = document.querySelector('.grid-container');
  const div = document.createElement('div');
  div.className      = 'grid-item';
  div.dataset.title  = title;
  div.dataset.year   = year;
  div.dataset.rating = 'N/A';
  div.dataset.plot   = 'No plot available';
  div.style.display  = 'none';

  const img = document.createElement('img');
  img.loading  = 'lazy';
  img.decoding = 'async';
  img.src      = '/posters/' + filename;
  img.alt      = title;
  img.addEventListener('click', () => openLightbox(img.src, img));
  div.appendChild(img);
  container.appendChild(div);

  // Navigate to last page so the new poster is visible
  const total = document.querySelectorAll('.grid-item').length;
  currentPage = Math.ceil(total / itemsPerPage);
  changePage(0);
}

// ── Pagination ────────────────────────────────────────────────────────────────
function changePage(direction) {
  const allItems   = document.querySelectorAll('.grid-item');
  const totalPages = Math.ceil(allItems.length / itemsPerPage) || 1;

  currentPage += direction;
  if (currentPage < 1) currentPage = 1;
  if (currentPage > totalPages) currentPage = totalPages;

  allItems.forEach((item, index) => {
    item.style.display = (Math.floor(index / itemsPerPage) + 1 === currentPage) ? 'block' : 'none';
  });

  document.getElementById('page-number').textContent = currentPage;

  const prevBtn = document.getElementById('prevBtn');
  const nextBtn = document.getElementById('nextBtn');
  if (prevBtn && nextBtn) {
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages;
  }
}

// ── DOMContentLoaded ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  // Restore saved theme
  if (localStorage.getItem('theme') === 'light') {
    document.body.classList.add('light-mode');
    const label = document.getElementById('darkModeLabel');
    if (label) label.textContent = 'Light Mode';
  }

  // Search — uses live querySelectorAll so dynamically added items are included
  const searchBar = document.getElementById('searchBar');
  if (searchBar) {
    searchBar.addEventListener('input', function () {
      const term     = searchBar.value.toLowerCase().trim();
      const allItems = document.querySelectorAll('.grid-item');
      let visible    = 0;

      allItems.forEach(item => {
        const match = (item.dataset.title || '').toLowerCase().includes(term);
        item.style.display = match ? 'block' : 'none';
        if (match) visible++;
      });

      document.getElementById('page-number').textContent = 1;
      const prevBtn = document.getElementById('prevBtn');
      const nextBtn = document.getElementById('nextBtn');
      if (prevBtn && nextBtn) {
        prevBtn.disabled = true;
        nextBtn.disabled = term.length === 0 ? visible <= itemsPerPage : true;
      }
    });
  }

  // Keyboard shortcuts
  document.addEventListener('keydown', e => {
    const active = document.activeElement;
    const typing = active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA');

    if (e.key === 'Escape') {
      const modal = document.getElementById('upload-modal');
      if (modal && modal.classList.contains('show')) {
        closeUploadModal();
      } else {
        closeLightbox();
      }
      return;
    }

    if (typing) return;
    if (e.key === 'ArrowRight') changePage(1);
    if (e.key === 'ArrowLeft')  changePage(-1);
  });

  document.getElementById('closeLightbox')?.addEventListener('click', closeLightbox);

  // Upload: auto-fill title from selected filename
  document.getElementById('upload-file')?.addEventListener('change', function () {
    const file = this.files[0];
    if (!file) return;
    const stem    = file.name.replace(/\.[^.]+$/, '');
    const yrMatch = stem.match(/\((\d{4})\)/);
    const title   = stem.replace(/\(\d{4}\)/, '').replace(/[_\-]+/g, ' ').replace(/\s+/g, ' ').trim();
    document.getElementById('upload-title').value = title;
    if (yrMatch) document.getElementById('upload-year').value = yrMatch[1];
  });

  // Upload form submit
  document.getElementById('upload-form')?.addEventListener('submit', async function (e) {
    e.preventDefault();
    const file  = document.getElementById('upload-file').files[0];
    const title = document.getElementById('upload-title').value.trim();
    const year  = document.getElementById('upload-year').value.trim();

    if (!file || !title) { alert('Please select a file and enter a title.'); return; }

    const btn = this.querySelector('[type="submit"]');
    btn.disabled    = true;
    btn.textContent = 'Uploading…';

    const fd = new FormData();
    fd.append('file',  file);
    fd.append('title', title);
    fd.append('year',  year);

    try {
      const resp = await fetch('/upload', { method: 'POST', body: fd });
      const data = await resp.json();
      if (!resp.ok) {
        alert(data.error || 'Upload failed');
        btn.disabled    = false;
        btn.textContent = 'Upload';
        return;
      }
      addNewPosterToGrid(data.filename, data.title, data.year);
      closeUploadModal();
    } catch (err) {
      alert('Network error: ' + err.message);
      btn.disabled    = false;
      btn.textContent = 'Upload';
    }
  });

  // Initialize first page
  changePage(0);

  // Heartbeat — keeps the Flask watchdog from shutting down
  function sendHeartbeat() { fetch('/heartbeat', { method: 'POST' }).catch(() => {}); }
  sendHeartbeat();
  setInterval(sendHeartbeat, 3000);
});
