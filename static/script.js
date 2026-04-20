// ── Steam UI helpers ──────────────────────────────────────────────────────────

/** Update the text content of an existing .card-overlay from its parent grid-item's data-* attrs. */
function _updateCardOverlayContent(overlay, item) {
  const title  = item.dataset.title  || '';
  const year   = item.dataset.year   || '';
  const rating = (item.dataset.rating && item.dataset.rating !== 'N/A')
    ? '\u2605 ' + item.dataset.rating : '';
  const meta = [year, rating].filter(Boolean).join(' \u00b7 ');
  const pr   = parseInt(item.dataset.personalRating || '0', 10);
  const stars = pr > 0
    ? '\u2605'.repeat(pr) + '\u2606'.repeat(5 - pr)
    : '';
  overlay.innerHTML =
    '<span class="card-overlay-title">' + escHtml(title) + '</span>' +
    (meta  ? '<span class="card-overlay-meta">'  + escHtml(meta)  + '</span>' : '') +
    (stars ? '<span class="card-overlay-stars">' + stars          + '</span>' : '');
}

/**
 * Append trash btn (top-left), button group (top-right: eye + pencil),
 * watched badge, and hover overlay to a .grid-item.
 */
function _addCardOverlay(item) {
  if (item.querySelector('.card-overlay')) return; // already added

  // Trash button — top-left
  const trashBtn = document.createElement('button');
  trashBtn.className = 'card-trash-btn';
  trashBtn.title = 'Delete poster';
  trashBtn.setAttribute('aria-label', 'Delete poster');
  trashBtn.textContent = '\uD83D\uDDD1';  // 🗑
  trashBtn.addEventListener('click', function (e) { e.stopPropagation(); _confirmDelete(item); });
  item.appendChild(trashBtn);

  // Right-side button group: eye + pencil
  const btnGroup = document.createElement('div');
  btnGroup.className = 'card-btn-group';

  const eyeBtn = document.createElement('button');
  eyeBtn.className = 'card-btn card-watch-btn';
  eyeBtn.title = 'Toggle watched';
  eyeBtn.setAttribute('aria-label', 'Toggle watched');
  eyeBtn.textContent = '\uD83D\uDC41';  // 👁
  eyeBtn.addEventListener('click', function (e) { e.stopPropagation(); _toggleWatched(item); });
  _syncWatchBtn(eyeBtn, item.dataset.watched || '');

  const editBtn = document.createElement('button');
  editBtn.className = 'card-btn card-edit-btn';
  editBtn.title = 'Rename poster';
  editBtn.setAttribute('aria-label', 'Rename poster');
  editBtn.textContent = '\u270f';
  editBtn.addEventListener('click', function (e) { e.stopPropagation(); _startCardEdit(item); });

  const linkBtn = document.createElement('button');
  linkBtn.className = 'card-btn card-link-btn';
  linkBtn.title = 'Link metadata';
  linkBtn.setAttribute('aria-label', 'Link metadata');
  linkBtn.innerHTML = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>';
  linkBtn.addEventListener('click', function (e) { e.stopPropagation(); openLinkModal(item); });

  btnGroup.appendChild(eyeBtn);
  btnGroup.appendChild(editBtn);
  btnGroup.appendChild(linkBtn);
  item.appendChild(btnGroup);

  // Watched badge — always visible when watched
  _updateWatchedBadge(item);

  // Hover overlay
  const overlay = document.createElement('div');
  overlay.className = 'card-overlay';
  _updateCardOverlayContent(overlay, item);
  item.appendChild(overlay);
}

/**
 * Fill #recent-strip by fetching /recently_added — always reads live filesystem
 * mtimes so newly uploaded or manually dropped-in posters appear immediately.
 */
async function populateRecentStrip() {
  const strip = document.getElementById('recent-strip');
  if (!strip) return;

  strip.innerHTML = '<p class="recent-empty">Loading\u2026</p>';

  let recent;
  try {
    const resp = await fetch('/recently_added');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    recent = await resp.json();
  } catch (err) {
    strip.innerHTML = '<p class="recent-empty">Could not load recent posters.</p>';
    return;
  }

  if (!recent.length) {
    strip.innerHTML = '<p class="recent-empty">No posters yet.</p>';
    return;
  }

  strip.innerHTML = '';

  recent.forEach(function (item) {
    const card = document.createElement('div');
    card.className = 'recent-card';

    const img    = document.createElement('img');
    img.src      = '/posters/' + encodeURIComponent(item.filename);
    img.alt      = item.title;
    img.loading  = 'lazy';
    img.decoding = 'async';

    const info = document.createElement('div');
    info.className = 'recent-info';
    info.innerHTML =
      '<span class="recent-title">' + escHtml(item.title) + '</span>' +
      '<span class="recent-year">'  + escHtml(item.year)  + '</span>';

    card.appendChild(img);
    card.appendChild(info);

    card.addEventListener('click', function () {
      // Prefer the live grid item so openLightbox gets all data-* attributes
      let targetImg = null;
      document.querySelectorAll('.grid-item').forEach(function (gi) {
        if (gi.dataset.filename === item.filename) {
          const gImg = gi.querySelector('img');
          if (gImg) targetImg = gImg;
        }
      });
      openLightbox('/posters/' + encodeURIComponent(item.filename), targetImg || img);
    });

    strip.appendChild(card);
  });
}

// ── Inline card rename ────────────────────────────────────────────────────────

/** Extract decoded filename (e.g. "Alien (1979).webp") from data-filename attr or img.src. */
function _getFilename(item) {
  if (item.dataset.filename) return item.dataset.filename;
  const img = item.querySelector('img');
  if (!img) return '';
  try {
    const url = new URL(img.src, window.location.origin);
    return decodeURIComponent(url.pathname.split('/posters/')[1] || '');
  } catch (_) {
    return decodeURIComponent(img.src.split('/posters/').pop());
  }
}

/** Enter inline edit mode on a card's overlay. */
function _startCardEdit(item) {
  if (item.dataset.editing === 'true') return;
  item.dataset.editing = 'true';
  const overlay = item.querySelector('.card-overlay');
  if (!overlay) { delete item.dataset.editing; return; }

  const currentTitle = item.dataset.title || '';
  const year = (item.dataset.year && item.dataset.year !== 'N/A') ? item.dataset.year : '';
  const filename = _getFilename(item);

  overlay.classList.add('editing');
  overlay.innerHTML = '<input class="card-title-input" type="text" value="' + escHtml(currentTitle) + '" placeholder="Movie title" />';

  const input = overlay.querySelector('.card-title-input');
  input.focus();
  input.select();

  let committed = false;
  function commit(save) {
    if (committed) return;
    committed = true;
    overlay.classList.remove('editing');
    if (save) {
      const newTitle = input.value.trim();
      if (newTitle && newTitle !== currentTitle) {
        _doRename(item, overlay, filename, newTitle, year);
        return;
      }
    }
    _updateCardOverlayContent(overlay, item);
    delete item.dataset.editing;
  }

  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter')  { e.preventDefault(); commit(true); }
    if (e.key === 'Escape') { e.preventDefault(); commit(false); }
  });
  input.addEventListener('blur', function () { setTimeout(function () { commit(false); }, 180); });
}

/** POST /rename for a grid card, then update DOM. */
async function _doRename(item, overlay, filename, newTitle, year) {
  overlay.classList.add('editing');
  overlay.innerHTML = '<span class="card-overlay-saving">Saving\u2026</span>';

  try {
    const resp = await fetch('/rename', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ old_filename: filename, new_title: newTitle, year: year }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      showToast(data.error || 'Rename failed', 'error');
    } else {
      item.dataset.title    = data.new_title;
      item.dataset.filename = data.new_filename;
      const img = item.querySelector('img');
      if (img) img.src = '/posters/' + data.new_filename;
      showToast('\u201c' + data.new_title + '\u201d renamed');
      // Sync open lightbox if it's showing this card
      if (_lightboxGridItem === item) {
        const lbTitle = document.getElementById('lb-title');
        if (lbTitle) lbTitle.textContent = data.new_title;
        _lightboxFilename = data.new_filename;
        const yrMatch = _lightboxFilename.match(/\((\d{4})\)/);
        _lightboxFilenameYear = yrMatch ? yrMatch[1] : _lightboxFilenameYear;
      }
      populateRecentStrip();
    }
  } catch (err) {
    showToast('Network error', 'error');
  }

  overlay.classList.remove('editing');
  _updateCardOverlayContent(overlay, item);
  delete item.dataset.editing;
}

/** Show a brief Steam-style toast in the bottom-right corner. */
function showToast(message, type) {
  const toast = document.createElement('div');
  toast.className = 'steam-toast' + (type ? ' toast-' + type : '');
  toast.textContent = message;
  document.body.appendChild(toast);
  requestAnimationFrame(function () {
    requestAnimationFrame(function () { toast.classList.add('show'); });
  });
  setTimeout(function () {
    toast.classList.remove('show');
    setTimeout(function () { toast.remove(); }, 300);
  }, 2500);
}

// ── Delete poster ─────────────────────────────────────────────────────────────

function _confirmDelete(item) {
  if (item.querySelector('.delete-confirm')) return; // already showing
  const confirm = document.createElement('div');
  confirm.className = 'delete-confirm';
  confirm.innerHTML =
    '<span class="delete-confirm-text">Delete this poster?</span>' +
    '<div class="delete-confirm-btns">' +
      '<button class="del-yes">Delete</button>' +
      '<button class="del-no">Cancel</button>' +
    '</div>';
  confirm.querySelector('.del-yes').addEventListener('click', function (e) {
    e.stopPropagation(); _doDelete(item);
  });
  confirm.querySelector('.del-no').addEventListener('click', function (e) {
    e.stopPropagation(); confirm.remove();
  });
  item.appendChild(confirm);
  setTimeout(function () { if (confirm.isConnected) confirm.remove(); }, 6000);
}

async function _doDelete(item) {
  const filename = _getFilename(item);
  if (!filename) return;
  try {
    const resp = await fetch('/delete_poster', {
      method:  'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ filename }),
    });
    const data = await resp.json();
    if (!resp.ok) { showToast(data.error || 'Delete failed', 'error'); return; }
    if (_lightboxGridItem === item) closeLightbox();
    item.remove();
    showToast('Poster deleted');
    populateRecentStrip();
    const countEl = document.getElementById('total-count');
    if (countEl) countEl.textContent = document.querySelectorAll('.grid-item').length + ' titles';
    // Re-run current filter so counts stay consistent
    _applySearchAndFilter((document.getElementById('searchBar')?.value || '').toLowerCase().trim(), currentFilter);
  } catch (err) {
    showToast('Network error', 'error');
  }
}

// ── Watched / Unwatched ───────────────────────────────────────────────────────

function _syncWatchBtn(btn, status) {
  btn.classList.toggle('watch-active',      status === 'watched');
  btn.classList.toggle('watch-want-active', status === 'want_to_watch');
  btn.title = status === 'watched'      ? 'Mark as Unwatched'
            : status === 'want_to_watch' ? 'Remove from Want to Watch'
            : 'Mark as Watched';
}

function _updateWatchedBadge(item) {
  item.querySelector('.watched-badge')?.remove();
  const status = item.dataset.watched || '';
  if (!status) return;
  const badge = document.createElement('div');
  if (status === 'watched') {
    badge.className = 'watched-badge watched-badge-done';
    badge.textContent = '\u2713';
    badge.setAttribute('aria-label', 'Watched');
  } else {
    badge.className = 'watched-badge watched-badge-want';
    badge.textContent = '\u2665';
    badge.setAttribute('aria-label', 'Want to Watch');
  }
  item.appendChild(badge);
}

async function _toggleWatched(item) {
  const filename = _getFilename(item);
  if (!filename) return;
  try {
    const resp = await fetch('/toggle_watched', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ filename }),
    });
    const data = await resp.json();
    if (!resp.ok) { showToast(data.error || 'Failed', 'error'); return; }
    item.dataset.watched = data.status || '';
    _updateWatchedBadge(item);
    const btn = item.querySelector('.card-watch-btn');
    if (btn) _syncWatchBtn(btn, data.status || '');
    showToast(data.status === 'watched' ? 'Marked as watched' : 'Marked as unwatched');
    // Sync open lightbox
    if (_lightboxGridItem === item) _syncLightboxWatchBtns(data.status || '');
  } catch (err) {
    showToast('Network error', 'error');
  }
}

async function _setWatchStatus(status) {
  const filename = _lightboxFilename;
  if (!filename) return;
  // Toggle: clicking the active status clears it
  const current = _lightboxGridItem ? (_lightboxGridItem.dataset.watched || '') : '';
  const newStatus = (current === status) ? '' : status;
  try {
    const resp = await fetch('/set_watched', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ filename, status: newStatus }),
    });
    const data = await resp.json();
    if (!resp.ok) { showToast(data.error || 'Failed', 'error'); return; }
    if (_lightboxGridItem) {
      _lightboxGridItem.dataset.watched = data.status || '';
      _updateWatchedBadge(_lightboxGridItem);
      const eyeBtn = _lightboxGridItem.querySelector('.card-watch-btn');
      if (eyeBtn) _syncWatchBtn(eyeBtn, data.status || '');
    }
    _syncLightboxWatchBtns(data.status || '');
    const label = data.status === 'watched'      ? 'Marked as watched'
                : data.status === 'want_to_watch' ? 'Added to Want to Watch'
                : 'Status cleared';
    showToast(label);
  } catch (err) {
    showToast('Network error', 'error');
  }
}

function _syncLightboxWatchBtns(status) {
  const btnW = document.getElementById('lb-btn-watched');
  const btnT = document.getElementById('lb-btn-want');
  if (btnW) btnW.classList.toggle('lb-watch-active', status === 'watched');
  if (btnT) btnT.classList.toggle('lb-watch-active', status === 'want_to_watch');
}

// ── Filter ────────────────────────────────────────────────────────────────────

let currentFilter = 'all';

function _applySearchAndFilter(term, filter) {
  const allItems = document.querySelectorAll('.grid-item');
  let visible = 0;
  allItems.forEach(function (item) {
    const titleMatch  = !term || (item.dataset.title || '').toLowerCase().includes(term);
    const watchStatus = item.dataset.watched || '';
    const filterMatch =
      filter === 'all' ||
      (filter === 'watched'       && watchStatus === 'watched') ||
      (filter === 'want_to_watch' && watchStatus === 'want_to_watch') ||
      (filter === 'unwatched'     && watchStatus === '');
    const show = titleMatch && filterMatch;
    item.style.display = show ? 'block' : 'none';
    if (show) visible++;
  });
  // When no active filter/search just hand back to pagination
  if (!term && filter === 'all') {
    changePage(0);
    return;
  }
  document.getElementById('page-number').textContent = 1;
  const prevBtn = document.getElementById('prevBtn');
  const nextBtn = document.getElementById('nextBtn');
  if (prevBtn) prevBtn.disabled = true;
  if (nextBtn) nextBtn.disabled = visible <= itemsPerPage;
  if (_groupViewActive) _applyGroupView();
}

function _applyFilter(filter) {
  currentFilter = filter;
  document.querySelectorAll('.nav-filter-btn').forEach(function (btn) {
    btn.classList.toggle('active', btn.dataset.filter === filter);
  });
  _applySearchAndFilter(
    (document.getElementById('searchBar')?.value || '').toLowerCase().trim(),
    filter
  );
}

// ── Personal star rating ──────────────────────────────────────────────────────

function _renderPersonalStars(currentRating) {
  const container = document.getElementById('lb-personal-stars');
  if (!container) return;
  container.innerHTML = '';
  for (let i = 1; i <= 5; i++) {
    const star = document.createElement('span');
    star.className = 'lb-star' + (i <= currentRating ? ' filled' : '');
    star.textContent = i <= currentRating ? '\u2605' : '\u2606';
    star.dataset.rating = i;
    star.addEventListener('mouseenter', function () {
      const val = parseInt(this.dataset.rating);
      container.querySelectorAll('.lb-star').forEach(function (s, idx) {
        s.textContent = idx < val ? '\u2605' : '\u2606';
      });
    });
    star.addEventListener('mouseleave', function () {
      const saved = parseInt(container.dataset.saved || '0');
      container.querySelectorAll('.lb-star').forEach(function (s, idx) {
        s.classList.toggle('filled', idx < saved);
        s.textContent = idx < saved ? '\u2605' : '\u2606';
      });
    });
    star.addEventListener('click', function () {
      const rating = parseInt(this.dataset.rating);
      _setPersonalRating(_lightboxFilename, rating);
    });
    container.appendChild(star);
  }
  container.dataset.saved = currentRating;
}

async function _setPersonalRating(filename, rating) {
  try {
    const resp = await fetch('/set_rating', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ filename, rating }),
    });
    const data = await resp.json();
    if (!resp.ok) { showToast(data.error || 'Failed', 'error'); return; }
    // Update container saved state
    const container = document.getElementById('lb-personal-stars');
    if (container) {
      container.dataset.saved = data.rating;
      container.querySelectorAll('.lb-star').forEach(function (s, idx) {
        s.classList.toggle('filled', idx < data.rating);
        s.textContent = idx < data.rating ? '\u2605' : '\u2606';
      });
    }
    // Update grid card
    if (_lightboxGridItem) {
      _lightboxGridItem.dataset.personalRating = data.rating;
      const overlay = _lightboxGridItem.querySelector('.card-overlay');
      if (overlay) _updateCardOverlayContent(overlay, _lightboxGridItem);
    }
    showToast(data.rating ? data.rating + '\u2605 saved' : 'Rating cleared');
  } catch (err) {
    showToast('Network error', 'error');
  }
}

// ── Inline metadata editing (year / plot) ────────────────────────────────────

function _startFieldEdit(field) {
  const row = document.getElementById('lb-field-' + field);
  if (!row || row.dataset.editing === 'true') return;
  row.dataset.editing = 'true';

  const valEl  = row.querySelector('.lb-field-val');
  const editBtn = row.querySelector('.lb-field-btn');
  const current = valEl ? valEl.textContent.trim() : '';

  const input = document.createElement(field === 'plot' ? 'textarea' : 'input');
  input.className = 'lb-field-input';
  input.value     = current;
  if (field !== 'plot') input.type = 'text';

  const saveBtn   = document.createElement('button');
  saveBtn.className = 'lb-field-save';
  saveBtn.textContent = 'Save';

  const cancelBtn = document.createElement('button');
  cancelBtn.className = 'lb-field-cancel';
  cancelBtn.textContent = 'Cancel';

  if (valEl)   valEl.style.display   = 'none';
  if (editBtn) editBtn.style.display = 'none';
  row.appendChild(input);
  row.appendChild(saveBtn);
  row.appendChild(cancelBtn);
  input.focus();

  function cancel() {
    input.remove(); saveBtn.remove(); cancelBtn.remove();
    if (valEl)   valEl.style.display   = '';
    if (editBtn) editBtn.style.display = '';
    delete row.dataset.editing;
  }

  saveBtn.addEventListener('click', function () { _saveFieldEdit(field, input.value.trim(), valEl, cancel); });
  cancelBtn.addEventListener('click', cancel);
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && field !== 'plot') { e.preventDefault(); _saveFieldEdit(field, input.value.trim(), valEl, cancel); }
    if (e.key === 'Escape') cancel();
  });
}

async function _saveFieldEdit(field, value, valEl, cancelFn) {
  if (!value) { cancelFn(); return; }
  const body = { filename: _lightboxFilename };
  body[field] = value;
  try {
    const resp = await fetch('/update_metadata', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
    });
    const data = await resp.json();
    if (!resp.ok) { showToast(data.error || 'Save failed', 'error'); return; }
    cancelFn();
    if (valEl) valEl.textContent = data[field] || value;
    // Update grid card data attrs
    if (_lightboxGridItem) {
      if (field === 'plot')  _lightboxGridItem.dataset.plot  = data.plot  || value;
      if (field === 'year')  _lightboxGridItem.dataset.year  = data.year  || value;
      if (field === 'title') _lightboxGridItem.dataset.title = data.title || value;
    }
    showToast(field.charAt(0).toUpperCase() + field.slice(1) + ' updated');

    // When year changes and the filename carries a year tag, also rename the file
    // so "Movie (oldYear).webp" becomes "Movie (newYear).webp" on disk.
    if (field === 'year' && _lightboxFilenameYear && _lightboxFilenameYear !== value) {
      const currentTitle = _lightboxGridItem?.dataset.title || '';
      if (currentTitle) {
        try {
          const renResp = await fetch('/rename', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ old_filename: _lightboxFilename, new_title: currentTitle, year: value }),
          });
          const renData = await renResp.json();
          if (renResp.ok) {
            _lightboxFilename     = renData.new_filename;
            _lightboxFilenameYear = value;
            _setLightboxSrc('/posters/' + renData.new_filename);
            if (_lightboxGridItem) {
              _lightboxGridItem.dataset.filename = renData.new_filename;
              const img = _lightboxGridItem.querySelector('img');
              if (img) img.src = '/posters/' + renData.new_filename;
            }
          }
        } catch (_) { /* rename failure is non-fatal — metadata was already saved */ }
      }
    }
  } catch (err) {
    showToast('Network error', 'error');
  }
}

// ── Add Poster card ───────────────────────────────────────────────────────────

/** Insert the special "Add Poster" card as the first item in the grid. */
function _insertAddPosterCard() {
  const container = document.querySelector('.grid-container');
  if (!container || container.querySelector('.add-poster-card')) return;
  const card = document.createElement('div');
  card.className = 'add-poster-card';
  card.setAttribute('role', 'button');
  card.setAttribute('tabindex', '0');
  card.innerHTML =
    '<div class="add-poster-inner">' +
      '<span class="add-poster-plus">+</span>' +
      '<span class="add-poster-label">Add Poster</span>' +
    '</div>';
  card.addEventListener('click', openUploadModal);
  card.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openUploadModal(); }
  });
  container.prepend(card);
}

// ── Drop zone ─────────────────────────────────────────────────────────────────

/** Wire up the drag-and-drop upload zone in the modal. */
function _initDropZone() {
  const zone      = document.getElementById('drop-zone');
  const fileInput = document.getElementById('upload-file');
  const filenameEl = document.getElementById('drop-filename');
  if (!zone || !fileInput) return;

  function highlight()   { zone.classList.add('drag-over'); }
  function unhighlight() { zone.classList.remove('drag-over'); }

  zone.addEventListener('dragover',  function (e) { e.preventDefault(); highlight(); });
  zone.addEventListener('dragenter', function (e) { e.preventDefault(); highlight(); });
  zone.addEventListener('dragleave', function (e) {
    if (!zone.contains(e.relatedTarget)) unhighlight();
  });
  zone.addEventListener('drop', function (e) {
    e.preventDefault();
    unhighlight();
    const file = e.dataTransfer && e.dataTransfer.files[0];
    if (file) _setDropFile(file, zone, fileInput, filenameEl);
  });
  fileInput.addEventListener('change', function () {
    const file = fileInput.files[0];
    if (file) _setDropFile(file, zone, fileInput, filenameEl);
  });
}

/** Apply a dropped/selected file: update visual state, auto-fill title/year. */
function _setDropFile(file, zone, fileInput, filenameEl) {
  if (filenameEl) filenameEl.textContent = file.name;
  zone.classList.add('has-file');
  zone.classList.remove('drag-over');

  const stem    = file.name.replace(/\.[^.]+$/, '');
  const yrMatch = stem.match(/\((\d{4})\)/);
  const title   = stem.replace(/\(\d{4}\)/g, '').replace(/[_\-]+/g, ' ').replace(/\s+/g, ' ').trim();

  const titleEl = document.getElementById('upload-title');
  const yearEl  = document.getElementById('upload-year');
  if (titleEl) titleEl.value = title;
  if (yrMatch && yearEl) yearEl.value = yrMatch[1];

  // Sync file input when file came from drag-drop
  if (fileInput.files[0] !== file) {
    try { const dt = new DataTransfer(); dt.items.add(file); fileInput.files = dt.files; } catch (_) {}
  }
}

// ── State ─────────────────────────────────────────────────────────────────────
let currentPage = 1;
const itemsPerPage = 50;

// Lightbox state — set each time a poster is opened
let _lightboxFilename     = '';   // decoded filename, e.g. "Alien (1979).webp"
let _lightboxFilenameYear = '';   // 4-digit year parsed from filename, e.g. "1979"
let _lightboxGridItem     = null; // reference to the .grid-item DOM node
let _lightboxZoom         = 1.0;  // current zoom level (0.7–1.3), saved per poster

// ── Helpers ───────────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Recently Added dropdown ───────────────────────────────────────────────────
function toggleRecentDropdown() {
  const dropdown = document.getElementById('recent-dropdown');
  const btn      = document.getElementById('recent-toggle-btn');
  if (!dropdown || !btn) return;
  const isOpen = dropdown.classList.contains('open');
  if (isOpen) {
    dropdown.classList.remove('open');
    btn.classList.remove('active');
  } else {
    populateRecentStrip(); // refresh before showing
    dropdown.classList.add('open');
    btn.classList.add('active');
  }
}

// ── Dark mode ─────────────────────────────────────────────────────────────────
function toggleDarkMode() {
  document.body.classList.toggle('light-mode');
  const mode = document.body.classList.contains('light-mode') ? 'light' : 'dark';
  localStorage.setItem('theme', mode);
  document.getElementById('darkModeLabel').textContent = mode === 'dark' ? 'Dark Mode' : 'Light Mode';
}

// ── Lightbox customization panel ─────────────────────────────────────────────

const _LB_FONTS = [
  { label: 'Inter (default)', value: "'Inter', sans-serif" },
  { label: 'Georgia',         value: 'Georgia, serif' },
  { label: 'Merriweather',    value: "'Merriweather', serif" },
  { label: 'Courier New',     value: "'Courier New', monospace" },
  { label: 'Raleway',         value: "'Raleway', sans-serif" },
  { label: 'Lato',            value: "'Lato', sans-serif" },
];
const _LB_SIZES = ['13px', '15px', '16px', '18px', '21px'];
const _LB_DEFAULTS = { fontFamily: "'Inter', sans-serif", fontSize: '16px', textColor: '#e0e0e0', bgTint: 36 };

function _loadCustomStyle() {
  try { return JSON.parse(localStorage.getItem('lb_custom') || 'null') || {}; } catch(_) { return {}; }
}
function _saveCustomStyle(prefs) {
  localStorage.setItem('lb_custom', JSON.stringify(prefs));
}

function _applyCustomStyle(prefs) {
  const sidebar = document.querySelector('.lb-sidebar');
  const meta    = document.getElementById('metadata');
  if (!sidebar || !meta) return;
  const ff   = prefs.fontFamily || _LB_DEFAULTS.fontFamily;
  const fs   = prefs.fontSize   || _LB_DEFAULTS.fontSize;
  const col  = prefs.textColor  || _LB_DEFAULTS.textColor;
  const tint = prefs.bgTint !== undefined ? prefs.bgTint : _LB_DEFAULTS.bgTint;
  meta.style.fontFamily = ff;
  meta.style.setProperty('--lb-fs', fs);  // drives all child font-sizes via CSS var
  meta.style.color      = col;
  sidebar.style.background = 'rgb(' + tint + ',' + tint + ',' + tint + ')';
}

function _toggleCustomPanel() {
  const existing = document.getElementById('lb-custom-panel');
  if (existing) { existing.remove(); return; }

  const prefs = _loadCustomStyle();
  const ff   = prefs.fontFamily || _LB_DEFAULTS.fontFamily;
  const fs   = prefs.fontSize   || _LB_DEFAULTS.fontSize;
  const col  = prefs.textColor  || _LB_DEFAULTS.textColor;
  const tint = prefs.bgTint !== undefined ? prefs.bgTint : _LB_DEFAULTS.bgTint;

  const panel = document.createElement('div');
  panel.id = 'lb-custom-panel';
  panel.className = 'lb-custom-panel';
  panel.style.display = 'block';

  const fontOpts = _LB_FONTS.map(function (f) {
    return '<option value="' + escHtml(f.value) + '"' + (f.value === ff ? ' selected' : '') + '>' + escHtml(f.label) + '</option>';
  }).join('');

  const sizeOpts = _LB_SIZES.map(function (s) {
    return '<option value="' + s + '"' + (s === fs ? ' selected' : '') + '>' + s + '</option>';
  }).join('');

  panel.innerHTML =
    '<div class="lbcp-header">' +
      '<span class="lbcp-title">Appearance</span>' +
      '<button class="lbcp-reset" onclick="_resetCustomPanel()">Reset</button>' +
    '</div>' +
    '<label class="lbcp-row">' +
      '<span class="lbcp-label">Font</span>' +
      '<select id="lbcp-font" class="lbcp-select">' + fontOpts + '</select>' +
    '</label>' +
    '<label class="lbcp-row">' +
      '<span class="lbcp-label">Size</span>' +
      '<select id="lbcp-size" class="lbcp-select">' + sizeOpts + '</select>' +
    '</label>' +
    '<label class="lbcp-row">' +
      '<span class="lbcp-label">Text color</span>' +
      '<input type="color" id="lbcp-color" class="lbcp-color" value="' + col + '" />' +
    '</label>' +
    '<label class="lbcp-row">' +
      '<span class="lbcp-label">Sidebar tint</span>' +
      '<input type="range" id="lbcp-tint" class="lbcp-range" min="18" max="72" value="' + tint + '" />' +
      '<span class="lbcp-tint-val" id="lbcp-tint-val">' + tint + '</span>' +
    '</label>';

  // Insert before #metadata (or after gear btn)
  const gearBtn = document.getElementById('lb-gear-btn');
  gearBtn.insertAdjacentElement('afterend', panel);

  function _save() {
    const newPrefs = {
      fontFamily: document.getElementById('lbcp-font').value,
      fontSize:   document.getElementById('lbcp-size').value,
      textColor:  document.getElementById('lbcp-color').value,
      bgTint:     parseInt(document.getElementById('lbcp-tint').value, 10),
    };
    _saveCustomStyle(newPrefs);
    _applyCustomStyle(newPrefs);
  }

  panel.querySelector('#lbcp-font').addEventListener('change', _save);
  panel.querySelector('#lbcp-size').addEventListener('change', _save);
  panel.querySelector('#lbcp-color').addEventListener('input', _save);
  panel.querySelector('#lbcp-tint').addEventListener('input', function () {
    document.getElementById('lbcp-tint-val').textContent = this.value;
    _save();
  });
}

function _resetCustomPanel() {
  _saveCustomStyle(_LB_DEFAULTS);
  _applyCustomStyle(_LB_DEFAULTS);
  // Rebuild panel with reset values
  document.getElementById('lb-custom-panel')?.remove();
  _toggleCustomPanel();
}

// ── Lightbox helpers ──────────────────────────────────────────────────────────

/**
 * Set the lightbox image, sync the blurred backdrop, and resize the left panel
 * to naturally fit the poster's aspect ratio (clamped to 38%–68% of dialog width).
 */
function _setLightboxSrc(url) {
  const img  = document.getElementById('lightboxImage');
  const wrap = document.getElementById('lb-image-wrap');

  if (!url) {
    if (img)  { img.src = ''; img.onload = null; img.style.transform = ''; }
    if (wrap) { wrap.style.backgroundImage = ''; wrap.style.flex = ''; }
    return;
  }

  if (wrap) wrap.style.backgroundImage = 'url("' + url.replace(/"/g, '%22') + '")';

  if (img) {
    img.onload = function () {
      if (!wrap || !img.naturalWidth) return;
      const ratio   = img.naturalWidth / img.naturalHeight;
      const wrapH   = wrap.clientHeight || (window.innerHeight * 0.88);
      const dialog  = wrap.parentElement;
      const dialogW = dialog ? dialog.clientWidth : window.innerWidth * 0.92;
      // Ideal width: the width the poster would occupy at full height with object-fit:contain
      const ideal   = ratio * wrapH;
      const minW    = 0.38 * dialogW;
      const maxW    = 0.68 * dialogW;
      const targetW = Math.min(Math.max(ideal, minW), maxW);
      wrap.style.flex = '0 0 ' + targetW + 'px';
    };
    img.src = url;
  }
}

// ── Lightbox ──────────────────────────────────────────────────────────────────
function openLightbox(imageSrc, element) {
  const lightbox = document.getElementById('lightbox');
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
  document.getElementById('lb-custom-panel')?.remove();
  _setLightboxSrc(imageSrc);
  lightbox.classList.add('show');

  // ── Zoom bar ───────────────────────────────────────────────────────────────
  const wrap = document.getElementById('lb-image-wrap');
  wrap?.querySelector('.lb-zoom-bar')?.remove();   // clear previous
  _lightboxZoom = parseFloat(parent?.dataset.zoom || '1.0');
  if (wrap) {
    const zoomPct = Math.round(_lightboxZoom * 100);
    const zbar = document.createElement('div');
    zbar.className = 'lb-zoom-bar';
    zbar.innerHTML =
      '<input type="range" class="lb-zoom-slider" min="70" max="130" step="1" value="' + zoomPct + '" />' +
      '<span class="lb-zoom-label">' + zoomPct + '%</span>' +
      '<button class="lb-zoom-save-btn" title="Save zoom for this poster">\uD83D\uDCBE</button>';
    wrap.appendChild(zbar);

    const img      = document.getElementById('lightboxImage');
    const slider   = zbar.querySelector('.lb-zoom-slider');
    const label    = zbar.querySelector('.lb-zoom-label');
    const saveBtn  = zbar.querySelector('.lb-zoom-save-btn');

    // Apply saved zoom immediately (after onload sets src so the image exists)
    if (img && _lightboxZoom !== 1.0) img.style.transform = 'scale(' + _lightboxZoom + ')';

    slider.addEventListener('input', function () {
      _lightboxZoom = parseInt(this.value, 10) / 100;
      if (img) img.style.transform = _lightboxZoom !== 1.0 ? 'scale(' + _lightboxZoom + ')' : '';
      label.textContent = this.value + '%';
    });
    saveBtn.addEventListener('click', _saveLightboxZoom);
  }

  const personalRating = parseInt(parent?.dataset.personalRating || '0', 10);

  const watchStatus = parent?.dataset.watched    || '';
  const collection  = parent?.dataset.collection || '';

  const meta = document.createElement('div');
  meta.id = 'metadata';
  meta.innerHTML =
    '<h2>' +
      '<span id="lb-title" class="editable-title">' + escHtml(title) + '</span>' +
      '<button class="lb-icon-btn" title="Rename file" onclick="startEditTitle()">\u270f</button>' +
    '</h2>' +
    '<div class="lb-field-row" id="lb-field-year">' +
      '<span class="lb-field-label">Year:</span>' +
      '<span class="lb-field-val">' + escHtml(displayYear) + '</span>' +
      '<button class="lb-field-btn" onclick="_startFieldEdit(\'year\')">\u270f</button>' +
    '</div>' +
    '<div class="lb-field-row" id="lb-field-imdb">' +
      '<span class="lb-field-label">IMDb:</span>' +
      '<span class="lb-field-val">' + escHtml(rating) + '</span>' +
    '</div>' +
    '<div class="lb-link-row">' +
      '<button class="lb-link-meta-btn" onclick="openLinkModal(_lightboxGridItem, _applyLinkedMetadata)">' +
        '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="vertical-align:-1px;margin-right:4px"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>' +
        'Link Metadata' +
      '</button>' +
    '</div>' +
    '<div class="lb-watch-row">' +
      '<button id="lb-btn-watched" class="lb-watch-btn' + (watchStatus === 'watched' ? ' lb-watch-active' : '') + '" onclick="_setWatchStatus(\'watched\')">\u2713 Watched</button>' +
      '<button id="lb-btn-want"    class="lb-watch-btn' + (watchStatus === 'want_to_watch' ? ' lb-watch-active' : '') + '" onclick="_setWatchStatus(\'want_to_watch\')">\u2665 Want to Watch</button>' +
    '</div>' +
    '<div class="lb-stars-row">' +
      '<span class="lb-stars-label">My Rating:</span>' +
      '<span id="lb-personal-stars"></span>' +
    '</div>' +
    '<div class="lb-field-row" id="lb-field-plot">' +
      '<span class="lb-field-label">Plot:</span>' +
      '<span class="lb-field-val">' + escHtml(plot) + '</span>' +
      '<button class="lb-field-btn" onclick="_startFieldEdit(\'plot\')">\u270f</button>' +
    '</div>' +
    '<div class="lb-field-row lb-collection-row" id="lb-field-collection">' +
      '<span class="lb-field-label">Collection:</span>' +
      '<div class="lb-collection-combo" id="lb-collection-combo">' +
        '<input type="text" id="lb-collection-input" class="lb-collection-input"' +
               ' placeholder="Type or select a group\u2026" autocomplete="off" />' +
        '<div id="lb-collection-list" class="lb-collection-list"></div>' +
      '</div>' +
    '</div>' +
    '<div class="lb-save-bar">' +
      '<button class="lb-save-btn" id="lb-save-btn" onclick="lbSaveAll()">Save Changes</button>' +
    '</div>';
  document.getElementById('closeLightbox').insertAdjacentElement('afterend', meta);
  _renderPersonalStars(personalRating);
  _loadCollectionCombo(collection);
  // Apply saved custom styles
  _applyCustomStyle(_loadCustomStyle());
}

function closeLightbox() {
  const lightbox = document.getElementById('lightbox');
  lightbox.classList.remove('show');
  _setLightboxSrc('');   // clears src, bg-image, and flex width
  document.getElementById('metadata')?.remove();
  document.getElementById('lb-custom-panel')?.remove();
  _lightboxZoom = 1.0;
  // Reset sidebar bg so it doesn't bleed if custom tint was set
  const sidebar = document.querySelector('.lb-sidebar');
  if (sidebar) sidebar.style.background = '';
}

// ── Poster zoom ───────────────────────────────────────────────────────────────

async function _saveLightboxZoom() {
  const saveBtn = document.querySelector('.lb-zoom-save-btn');
  if (saveBtn) { saveBtn.textContent = '\u2026'; saveBtn.disabled = true; }
  try {
    const resp = await fetch('/save_zoom', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ filename: _lightboxFilename, zoom: _lightboxZoom }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      showToast(data.error || 'Failed to save zoom', 'error');
    } else {
      // Keep the grid item's data-zoom in sync so re-opens use the new value
      if (_lightboxGridItem) _lightboxGridItem.dataset.zoom = String(_lightboxZoom);
      if (saveBtn) {
        saveBtn.textContent = '\u2713';
        saveBtn.classList.add('saved');
        setTimeout(function () {
          saveBtn.textContent = '\uD83D\uDCBE';
          saveBtn.classList.remove('saved');
          saveBtn.disabled = false;
        }, 1500);
        return;  // skip the re-enable below
      }
      showToast('Zoom saved');
    }
  } catch (_) {
    showToast('Network error', 'error');
  }
  if (saveBtn) { saveBtn.textContent = '\uD83D\uDCBE'; saveBtn.disabled = false; }
}

// ── Save All button ───────────────────────────────────────────────────────────
async function lbSaveAll() {
  const btn = document.getElementById('lb-save-btn');
  if (!btn || btn.classList.contains('saving')) return;
  btn.classList.add('saving');
  btn.textContent = 'Saving\u2026';

  const errors = [];

  // 1. Metadata: collect current displayed values and any in-progress edits
  const titleEl  = document.getElementById('lb-title');
  const titleIn  = document.getElementById('title-edit-input');
  const newTitle = (titleIn ? titleIn.value.trim() : titleEl?.textContent.trim()) || '';

  const yearRow  = document.getElementById('lb-field-year');
  const yearIn   = yearRow?.querySelector('.lb-field-input');
  const yearVal  = yearRow?.querySelector('.lb-field-val');
  const newYear  = (yearIn ? yearIn.value.trim() : yearVal?.textContent.trim()) || '';

  const plotRow  = document.getElementById('lb-field-plot');
  const plotIn   = plotRow?.querySelector('.lb-field-input');
  const plotVal  = plotRow?.querySelector('.lb-field-val');
  const newPlot  = (plotIn ? plotIn.value.trim() : plotVal?.textContent.trim()) || '';

  // Fire metadata update (title change also triggers a rename via update_metadata
  // which handles plot/year; the rename endpoint handles file rename separately)
  try {
    const mdResp = await fetch('/update_metadata', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ filename: _lightboxFilename, title: newTitle, year: newYear, plot: newPlot }),
    });
    const mdData = await mdResp.json();
    if (!mdResp.ok) {
      errors.push(mdData.error || 'Metadata save failed');
    } else {
      // Sync grid item data attrs
      if (_lightboxGridItem) {
        if (newTitle) _lightboxGridItem.dataset.title = mdData.title || newTitle;
        if (newYear)  _lightboxGridItem.dataset.year  = mdData.year  || newYear;
        if (newPlot)  _lightboxGridItem.dataset.plot  = mdData.plot  || newPlot;
      }
      // If title changed, also rename file so it matches on disk
      const displayedTitle = titleEl?.textContent.trim() || '';
      const titleChanged   = newTitle && newTitle !== displayedTitle;
      const yearChanged    = newYear && newYear !== _lightboxFilenameYear;
      if ((titleChanged || yearChanged) && _lightboxFilenameYear) {
        try {
          const renResp = await fetch('/rename', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ old_filename: _lightboxFilename, new_title: newTitle || displayedTitle, year: newYear || _lightboxFilenameYear }),
          });
          const renData = await renResp.json();
          if (renResp.ok) {
            _lightboxFilename     = renData.new_filename;
            _lightboxFilenameYear = newYear || _lightboxFilenameYear;
            _setLightboxSrc('/posters/' + renData.new_filename);
            if (_lightboxGridItem) {
              _lightboxGridItem.dataset.filename = renData.new_filename;
              const img = _lightboxGridItem.querySelector('img');
              if (img) img.src = '/posters/' + renData.new_filename;
            }
          }
        } catch (_) { /* rename failure is non-fatal */ }
      }
      // Commit any open text fields back to display mode
      if (titleIn) cancelEditTitle();
      if (yearIn)  { yearVal.textContent = mdData.year || newYear; yearIn.closest('.lb-field-row') && _commitFieldEdit(yearRow); }
      if (plotIn)  { plotVal.textContent = mdData.plot || newPlot; plotIn.closest('.lb-field-row') && _commitFieldEdit(plotRow); }
      // Refresh title display
      const h2 = document.querySelector('#metadata h2');
      if (h2 && !document.getElementById('title-edit-input')) {
        const span = document.getElementById('lb-title');
        if (span) span.textContent = mdData.title || newTitle;
      }
    }
  } catch (err) {
    errors.push('Network error');
  }

  // 2. Collection — read the combo input value and save if changed
  const collInput   = document.getElementById('lb-collection-input');
  const collCurrent = _lightboxGridItem?.dataset.collection || '';
  const collNew     = (collInput?.value || '').trim();
  if (collNew !== collCurrent) {
    try {
      const cResp = await fetch('/set_collection', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ filename: _lightboxFilename, group: collNew }),
      });
      if (!cResp.ok) errors.push('Collection save failed');
      else if (_lightboxGridItem) _lightboxGridItem.dataset.collection = collNew;
    } catch (_) { errors.push('Collection network error'); }
  }

  // 3. Show result
  btn.classList.remove('saving');
  if (errors.length) {
    btn.textContent = 'Save failed';
    btn.style.background = '#c0392b';
    setTimeout(function () {
      btn.textContent = 'Save Changes';
      btn.style.background = '';
    }, 2500);
  } else {
    btn.classList.add('saved');
    btn.textContent = '\u2713 Saved!';
    setTimeout(function () {
      btn.classList.remove('saved');
      btn.textContent = 'Save Changes';
    }, 2000);
  }
}

/** Close the inline edit UI on a field row without re-fetching (used by lbSaveAll). */
function _commitFieldEdit(row) {
  if (!row) return;
  const input     = row.querySelector('.lb-field-input');
  const saveBtn   = row.querySelector('.lb-field-save');
  const cancelBtn = row.querySelector('.lb-field-cancel');
  const valEl     = row.querySelector('.lb-field-val');
  const editBtn   = row.querySelector('.lb-field-btn');
  if (input)     input.remove();
  if (saveBtn)   saveBtn.remove();
  if (cancelBtn) cancelBtn.remove();
  if (valEl)     valEl.style.display   = '';
  if (editBtn)   editBtn.style.display = '';
  delete row.dataset.editing;
}

// ── Title editing ─────────────────────────────────────────────────────────────
function startEditTitle() {
  const h2           = document.querySelector('#metadata h2');
  const currentTitle = document.getElementById('lb-title')?.textContent || '';
  h2.dataset.origTitle = currentTitle;

  h2.innerHTML =
    '<input id="title-edit-input" class="title-edit-input" type="text" value="' + escHtml(currentTitle) + '" />' +
    '<button class="lb-icon-btn save-btn"   onclick="saveTitle()">\u2713 Save</button>' +
    '<button class="lb-icon-btn cancel-btn" onclick="cancelEditTitle()">\u2715</button>';

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
  h2.innerHTML =
    '<span id="lb-title" class="editable-title">' + escHtml(title) + '</span>' +
    '<button class="lb-icon-btn" title="Rename file" onclick="startEditTitle()">\u270f</button>';
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
    h2.innerHTML =
      '<span id="lb-title" class="editable-title">' + escHtml(data.new_title) + '</span>' +
      '<button class="lb-icon-btn" title="Rename file" onclick="startEditTitle()">\u270f</button>';

    // Update lightbox image src
    _setLightboxSrc('/posters/' + data.new_filename);

    // Update the grid item
    if (_lightboxGridItem) {
      _lightboxGridItem.dataset.title    = data.new_title;
      _lightboxGridItem.dataset.filename = data.new_filename;
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
  const zone = document.getElementById('drop-zone');
  if (zone) zone.classList.remove('drag-over', 'has-file');
  const fn = document.getElementById('drop-filename');
  if (fn) fn.textContent = '';
}

function addNewPosterToGrid(filename, title, year) {
  const container = document.querySelector('.grid-container');
  const div = document.createElement('div');
  div.className              = 'grid-item';
  div.dataset.title          = title;
  div.dataset.year           = year;
  div.dataset.rating         = 'N/A';
  div.dataset.plot           = 'No plot available';
  div.dataset.filename       = filename;
  div.dataset.watched        = '';
  div.dataset.personalRating = '0';
  div.style.display          = 'none';

  const img = document.createElement('img');
  img.loading  = 'lazy';
  img.decoding = 'async';
  img.src      = '/posters/' + filename;
  img.alt      = title;
  img.addEventListener('click', () => openLightbox(img.src, img));
  div.appendChild(img);

  // Add Steam hover overlay to the new card
  _addCardOverlay(div);

  container.appendChild(div);

  // Refresh recent strip and total count to include the new poster
  populateRecentStrip();
  const countEl = document.getElementById('total-count');
  if (countEl) {
    countEl.textContent = document.querySelectorAll('.grid-item').length + ' titles';
  }

  // Navigate to last page so the new poster is visible
  const total = document.querySelectorAll('.grid-item').length;
  currentPage = Math.ceil(total / itemsPerPage);
  changePage(0);
}

// ── Card size slider ──────────────────────────────────────────────────────────

function setCardSize(px) {
  px = Math.min(300, Math.max(100, parseInt(px, 10)));
  document.documentElement.style.setProperty('--card-width', px + 'px');
  const slider = document.getElementById('card-size-slider');
  if (slider) slider.value = px;
  localStorage.setItem('card_size', px);
}

function adjustCardSize(delta) {
  const slider = document.getElementById('card-size-slider');
  const current = parseInt(slider ? slider.value : localStorage.getItem('card_size') || '160', 10);
  setCardSize(current + delta);
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
  if (_groupViewActive) _applyGroupView();
}

// ── Group View ────────────────────────────────────────────────────────────────

let _groupViewActive = false;

function toggleGroupView() {
  _groupViewActive = !_groupViewActive;
  const btn   = document.getElementById('group-view-btn');
  const pgBar = document.getElementById('pagination-controls');
  if (btn) btn.classList.toggle('active', _groupViewActive);
  if (_groupViewActive) {
    if (pgBar) pgBar.style.display = 'none';
    _applyGroupView();
  } else {
    if (pgBar) pgBar.style.display = '';
    _clearGroupView();
    changePage(0); // restore normal page view
  }
}

/**
 * Group View: hide all individual grid items, show one proxy card per group.
 * Ungrouped posters are hidden completely.
 */
function _applyGroupView() {
  _clearGroupView(); // always start clean

  const container = document.querySelector('.grid-container');
  if (!container) return;

  // Collect ALL grid items and build group map (order = DOM order)
  const allItems = Array.from(document.querySelectorAll('.grid-item'));
  const groups   = {};
  allItems.forEach(function (item) {
    const col = (item.dataset.collection || '').trim();
    if (!col) return;
    if (!groups[col]) groups[col] = [];
    groups[col].push(item);
  });

  // Hide every individual grid item (ungrouped ones stay hidden; grouped ones
  // are represented by proxy cards)
  allItems.forEach(function (item) { item.classList.add('group-view-hidden'); });

  if (Object.keys(groups).length === 0) {
    showToast('No posters are assigned to a group yet', '');
    // Restore items and turn off group view
    allItems.forEach(function (item) { item.classList.remove('group-view-hidden'); });
    _groupViewActive = false;
    const btn   = document.getElementById('group-view-btn');
    const pgBar = document.getElementById('pagination-controls');
    if (btn) btn.classList.remove('active');
    if (pgBar) pgBar.style.display = '';
    return;
  }

  // Create one proxy card per group (sorted alphabetically)
  Object.keys(groups).sort(function (a, b) {
    return a.toLowerCase().localeCompare(b.toLowerCase());
  }).forEach(function (groupName) {
    const items    = groups[groupName];
    const repImg   = items[0] ? items[0].querySelector('img') : null;

    const proxy = document.createElement('div');
    proxy.className = 'group-proxy-card';
    proxy.dataset.groupName = groupName;

    // Blurred background from the first poster image
    if (repImg) {
      const bg = document.createElement('img');
      bg.src       = repImg.src;
      bg.alt       = '';
      bg.className = 'group-proxy-bg';
      bg.setAttribute('aria-hidden', 'true');
      proxy.appendChild(bg);
    }

    // Overlay: group name + count
    const overlay = document.createElement('div');
    overlay.className = 'group-proxy-overlay';
    overlay.innerHTML =
      '<span class="group-proxy-name">' + escHtml(groupName) + '</span>' +
      '<span class="group-proxy-count">' + items.length + '\u00a0poster' +
        (items.length !== 1 ? 's' : '') + '</span>';
    proxy.appendChild(overlay);

    // Count badge (bottom-right corner)
    const badge = document.createElement('div');
    badge.className = 'group-count-badge';
    badge.textContent = items.length;
    proxy.appendChild(badge);

    proxy.addEventListener('click', function () {
      _toggleGroupExpand(groupName, proxy, items);
    });

    container.appendChild(proxy);
  });
}

function _clearGroupView() {
  // Remove all proxy cards and expand rows
  document.querySelectorAll('.group-proxy-card').forEach(function (c) { c.remove(); });
  document.querySelectorAll('.group-expand-row').forEach(function (r) { r.remove(); });
  // Un-hide all grid items
  document.querySelectorAll('.grid-item.group-view-hidden').forEach(function (item) {
    item.classList.remove('group-view-hidden');
  });
}

/**
 * Toggle the inline expand row below a group proxy card.
 * Shows all group members at a comfortable large size (min 200px).
 */
function _toggleGroupExpand(groupName, proxyCard, items) {
  const rowId   = 'gex-' + groupName.replace(/[^a-z0-9]/gi, '_');
  const existing = document.getElementById(rowId);
  if (existing) {
    existing.remove();
    proxyCard.classList.remove('group-expanded');
    return;
  }

  const row = document.createElement('div');
  row.className = 'group-expand-row';
  row.id        = rowId;

  items.forEach(function (item) {
    const img = item.querySelector('img');
    if (!img) return;

    const card = document.createElement('div');
    card.className = 'group-expand-card';

    const thumb = document.createElement('img');
    thumb.src      = img.src;
    thumb.alt      = item.dataset.title || '';
    thumb.loading  = 'lazy';
    thumb.decoding = 'async';

    const label = document.createElement('div');
    label.className = 'group-expand-label';
    label.textContent = item.dataset.title || '';

    card.appendChild(thumb);
    card.appendChild(label);
    // Open lightbox using the original grid-item img so data-* attrs resolve
    card.addEventListener('click', function (e) {
      e.stopPropagation();
      openLightbox(img.src, img);
    });
    row.appendChild(card);
  });

  // Insert after the proxy card; grid-column:1/-1 places it on its own full row
  proxyCard.insertAdjacentElement('afterend', row);
  proxyCard.classList.add('group-expanded');
}

// ── Collection combo-box (lightbox) ───────────────────────────────────────────

let _collectionGroups = [];   // cached after first fetch

async function _loadCollectionCombo(currentGroup) {
  const input = document.getElementById('lb-collection-input');
  const list  = document.getElementById('lb-collection-list');
  if (!input || !list) return;

  // Show the currently assigned group immediately
  input.value = currentGroup || '';

  try {
    const resp = await fetch('/collection_groups');
    _collectionGroups = await resp.json();
  } catch (err) {
    console.error('Failed to load collection groups', err);
    _collectionGroups = [];
  }

  function _renderList(query) {
    const q        = (query || '').trim().toLowerCase();
    const filtered = q
      ? _collectionGroups.filter(function (g) { return g.toLowerCase().includes(q); })
      : _collectionGroups.slice();

    list.innerHTML = '';

    // "— None —" always at the top to clear the group
    const noneItem = document.createElement('div');
    noneItem.className = 'lb-collection-list-item lb-collection-list-none';
    noneItem.textContent = '\u2014 None \u2014';
    noneItem.addEventListener('mousedown', function (e) {
      e.preventDefault();
      _selectGroup('');
    });
    list.appendChild(noneItem);

    filtered.forEach(function (g) {
      const item = document.createElement('div');
      item.className = 'lb-collection-list-item';
      if (g === currentGroup) item.classList.add('lb-collection-list-current');
      item.textContent = g;
      item.addEventListener('mousedown', function (e) {
        e.preventDefault();
        _selectGroup(g);
      });
      list.appendChild(item);
    });

    // "Create new group: …" at the bottom when typed name is new
    const typed      = (query || '').trim();
    const exactMatch = _collectionGroups.some(function (g) {
      return g.toLowerCase() === typed.toLowerCase();
    });
    if (typed && !exactMatch) {
      const createItem = document.createElement('div');
      createItem.className = 'lb-collection-list-item lb-collection-list-create';
      createItem.textContent = 'Create new group: \u201c' + typed + '\u201d';
      createItem.addEventListener('mousedown', function (e) {
        e.preventDefault();
        _selectGroup(typed);
      });
      list.appendChild(createItem);
    }

    list.style.display = '';
  }

  async function _selectGroup(name) {
    currentGroup = name;
    input.value  = name;
    list.style.display = 'none';
    await _saveCollection(name);
    if (_lightboxGridItem) _lightboxGridItem.dataset.collection = name;
    // Add new group to local cache so it appears on next open/filter
    if (name && !_collectionGroups.includes(name)) {
      _collectionGroups.push(name);
      _collectionGroups.sort(function (a, b) {
        return a.toLowerCase().localeCompare(b.toLowerCase());
      });
    }
  }

  function _getKbItems() {
    return Array.from(list.querySelectorAll('.lb-collection-list-item'));
  }

  input.addEventListener('focus', function () { _renderList(input.value); });
  input.addEventListener('input', function () { _renderList(input.value); });

  input.addEventListener('keydown', function (e) {
    if (list.style.display === 'none') { _renderList(input.value); return; }

    const items = _getKbItems();
    const kb    = list.querySelector('.lb-collection-list-item.lb-collection-list-kb');
    const idx   = kb ? items.indexOf(kb) : -1;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const next = items[idx + 1] || items[0];
      items.forEach(function (i) { i.classList.remove('lb-collection-list-kb'); });
      if (next) next.classList.add('lb-collection-list-kb');
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prev = items[idx - 1] || items[items.length - 1];
      items.forEach(function (i) { i.classList.remove('lb-collection-list-kb'); });
      if (prev) prev.classList.add('lb-collection-list-kb');
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const kbItem = list.querySelector('.lb-collection-list-item.lb-collection-list-kb');
      if (kbItem) {
        kbItem.dispatchEvent(new MouseEvent('mousedown'));
      } else {
        // No keyboard selection — commit the typed value directly
        const typed = input.value.trim();
        if (typed) _selectGroup(typed);
        else list.style.display = 'none';
      }
    } else if (e.key === 'Escape') {
      input.value = currentGroup || '';
      list.style.display = 'none';
    }
  });

  // Delay on blur so mousedown handlers on list items fire first
  input.addEventListener('blur', function () {
    setTimeout(function () { list.style.display = 'none'; }, 160);
  });
}

async function _saveCollection(group) {
  try {
    const resp = await fetch('/set_collection', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ filename: _lightboxFilename, group }),
    });
    const data = await resp.json();
    if (!resp.ok) { showToast(data.error || 'Failed', 'error'); return; }
    showToast(data.group ? 'Added to \u201c' + data.group + '\u201d' : 'Removed from collection');
  } catch (err) {
    showToast('Network error', 'error');
  }
}

// ── Link Metadata ─────────────────────────────────────────────────────────────

let _linkModalGridItem  = null;
let _linkModalOnSuccess = null;

/**
 * Open the Link Metadata modal.
 *   gridItem  — the .grid-item whose metadata we're updating
 *   onSuccess — optional callback(data) called after a successful apply
 *               (used by the lightbox to update its display fields)
 */
function openLinkModal(gridItem, onSuccess) {
  const item     = (gridItem && gridItem.closest) ? gridItem.closest('.grid-item') : gridItem;
  const filename = item?.dataset.filename || '';
  if (!filename) { showToast('No poster selected', 'error'); return; }

  _linkModalGridItem  = item;
  _linkModalOnSuccess = onSuccess || null;

  const modal = document.getElementById('link-modal');
  const body  = document.getElementById('link-modal-body');
  if (!modal || !body) return;

  body.innerHTML = '';
  _buildLinkUI(body, filename);
  modal.classList.add('show');
}

function closeLinkModal() {
  const modal = document.getElementById('link-modal');
  if (modal) modal.classList.remove('show');
  _linkModalGridItem  = null;
  _linkModalOnSuccess = null;
}

/**
 * Build the full link UI inside container:
 *   search input → scrollable list (all entries loaded immediately) →
 *   preview panel → Apply / Cancel buttons
 */
function _buildLinkUI(container, filename) {
  container.innerHTML =
    '<div class="lls-search-row">' +
      '<svg class="lls-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>' +
      '<input class="lls-input" type="text" placeholder="Filter by title\u2026" autocomplete="off" />' +
    '</div>' +
    '<div class="lls-list-wrap">' +
      '<div class="lls-list"><div class="lls-status">Loading\u2026</div></div>' +
    '</div>' +
    '<div class="lls-preview lls-preview-hint">Select an entry above to preview</div>' +
    '<div class="lls-footer">' +
      '<button class="lls-cancel btn-ghost" onclick="closeLinkModal()">Cancel</button>' +
      '<button class="lls-apply btn-steam-primary" disabled>Apply</button>' +
    '</div>';

  const input    = container.querySelector('.lls-input');
  const list     = container.querySelector('.lls-list');
  const preview  = container.querySelector('.lls-preview');
  const applyBtn = container.querySelector('.lls-apply');

  let _entries  = [];
  let _selected = null;

  function _renderList(q) {
    const lq     = q.toLowerCase();
    const shown  = q
      ? _entries.filter(function (e) { return e.title.toLowerCase().includes(lq); })
      : _entries;

    list.innerHTML = '';

    if (!shown.length) {
      list.innerHTML = '<div class="lls-status">No matches</div>';
      return;
    }

    shown.forEach(function (entry) {
      const row = document.createElement('div');
      row.className = 'lls-item';
      if (_selected && _selected.key === entry.key) row.classList.add('lls-selected');
      row.innerHTML =
        '<span class="lls-item-title">' + escHtml(entry.title) + '</span>' +
        '<span class="lls-item-meta">' + escHtml(entry.year) +
          (entry.rating && entry.rating !== 'N/A' ? ' \u00b7 \u2605' + escHtml(entry.rating) : '') +
        '</span>';
      row.addEventListener('click', function () {
        _selected = entry;
        list.querySelectorAll('.lls-item').forEach(function (r) { r.classList.remove('lls-selected'); });
        row.classList.add('lls-selected');
        row.scrollIntoView({ block: 'nearest' });
        preview.classList.remove('lls-preview-hint');
        preview.innerHTML =
          '<div class="lls-pv-title">' + escHtml(entry.title) + '</div>' +
          '<div class="lls-pv-meta">' + escHtml(entry.year) +
            (entry.rating && entry.rating !== 'N/A' ? ' \u00b7 \u2605 ' + escHtml(entry.rating) : '') +
          '</div>' +
          (entry.plot ? '<div class="lls-pv-plot">' + escHtml(entry.plot) + '</div>' : '');
        applyBtn.disabled = false;
      });
      list.appendChild(row);
    });
  }

  // Load all cache entries as soon as the UI opens
  (async function loadEntries() {
    try {
      const resp = await fetch('/cache_entries');
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      _entries = await resp.json();
      _renderList('');
    } catch (err) {
      list.innerHTML = '<div class="lls-status lls-status-error">Failed to load entries: ' + escHtml(err.message) + '</div>';
    }
  })();

  input.addEventListener('input', function () {
    _renderList(this.value.trim());
  });

  applyBtn.addEventListener('click', async function () {
    if (!_selected) return;
    applyBtn.textContent = 'Applying\u2026';
    applyBtn.disabled    = true;
    try {
      const resp = await fetch('/link_metadata', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          filename: filename,
          title:    _selected.title,
          year:     _selected.year,
          rating:   _selected.rating,
          plot:     _selected.plot,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        showToast(data.error || 'Link failed', 'error');
        applyBtn.textContent = 'Apply';
        applyBtn.disabled    = false;
        return;
      }
      // Notify the caller (lightbox path) to update its display fields
      if (_linkModalOnSuccess) _linkModalOnSuccess(data);
      // Always sync the grid item's data-* attrs and overlay
      if (_linkModalGridItem) {
        if (data.title)  _linkModalGridItem.dataset.title  = data.title;
        if (data.year)   _linkModalGridItem.dataset.year   = data.year;
        if (data.rating) _linkModalGridItem.dataset.rating = data.rating;
        if (data.plot)   _linkModalGridItem.dataset.plot   = data.plot;
        const ov = _linkModalGridItem.querySelector('.card-overlay');
        if (ov) _updateCardOverlayContent(ov, _linkModalGridItem);
      }
      showToast('\u2713 Metadata linked');
      closeLinkModal();
    } catch (_) {
      showToast('Network error', 'error');
      applyBtn.textContent = 'Apply';
      applyBtn.disabled    = false;
    }
  });

  setTimeout(function () { input.focus(); }, 0);
}

/**
 * Update the open lightbox display after a successful link.
 * Called as the onSuccess callback from the lightbox "Link Metadata" button.
 */
function _applyLinkedMetadata(data) {
  const titleSpan = document.getElementById('lb-title');
  if (titleSpan && data.title) titleSpan.textContent = data.title;

  const yearRow = document.getElementById('lb-field-year');
  if (yearRow && data.year) {
    const v = yearRow.querySelector('.lb-field-val');
    if (v) v.textContent = data.year;
  }
  const imdbRow = document.getElementById('lb-field-imdb');
  if (imdbRow && data.rating) {
    const v = imdbRow.querySelector('.lb-field-val');
    if (v) v.textContent = data.rating;
  }
  const plotRow = document.getElementById('lb-field-plot');
  if (plotRow && data.plot) {
    const v = plotRow.querySelector('.lb-field-val');
    if (v) v.textContent = data.plot;
  }
}

// ── DOMContentLoaded ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  // Restore saved card size
  const savedSize = parseInt(localStorage.getItem('card_size') || '160', 10);
  setCardSize(savedSize);

  // Restore saved theme
  if (localStorage.getItem('theme') === 'light') {
    document.body.classList.add('light-mode');
    const label = document.getElementById('darkModeLabel');
    if (label) label.textContent = 'Light Mode';
  }

  // Add card overlay + pencil btn to every server-rendered grid item
  document.querySelectorAll('.grid-item').forEach(_addCardOverlay);

  // Insert the "Add Poster" placeholder card at position 0
  _insertAddPosterCard();

  // Show total poster count in the nav
  const countEl = document.getElementById('total-count');
  if (countEl) {
    countEl.textContent = document.querySelectorAll('.grid-item').length + ' titles';
  }

  // Close link modal by clicking outside the card
  document.getElementById('link-modal')?.addEventListener('click', function (e) {
    if (e.target === this) closeLinkModal();
  });

  // Close lightbox by clicking the dark backdrop (outside .lb-dialog)
  const lightboxEl = document.getElementById('lightbox');
  if (lightboxEl) {
    lightboxEl.addEventListener('click', function (e) {
      if (e.target === lightboxEl) closeLightbox();
    });
  }

  // Close Recently Added dropdown when clicking outside it
  document.addEventListener('click', function (e) {
    const dropdown = document.getElementById('recent-dropdown');
    const btn      = document.getElementById('recent-toggle-btn');
    if (!dropdown || !dropdown.classList.contains('open')) return;
    if (dropdown.contains(e.target) || btn.contains(e.target)) return;
    dropdown.classList.remove('open');
    btn.classList.remove('active');
  }, true); // capture phase so it fires before card click handlers

  // Search
  const searchBar = document.getElementById('searchBar');
  if (searchBar) {
    searchBar.addEventListener('input', function () {
      _applySearchAndFilter(searchBar.value.toLowerCase().trim(), currentFilter);
    });
  }

  // Filter buttons
  document.querySelectorAll('.nav-filter-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { _applyFilter(btn.dataset.filter); });
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', e => {
    const active = document.activeElement;
    const typing = active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA');

    if (e.key === 'Escape') {
      const modal    = document.getElementById('upload-modal');
      const dropdown = document.getElementById('recent-dropdown');
      const linkModal = document.getElementById('link-modal');
      if (modal && modal.classList.contains('show')) {
        closeUploadModal();
      } else if (linkModal && linkModal.classList.contains('show')) {
        closeLinkModal();
      } else if (dropdown && dropdown.classList.contains('open')) {
        dropdown.classList.remove('open');
        document.getElementById('recent-toggle-btn')?.classList.remove('active');
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

  // Wire drag-and-drop upload zone
  _initDropZone();

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
});
