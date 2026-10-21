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
    img.src      = _thumbUrl(item.filename);
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
      openLightbox(_posterUrl(item.filename), targetImg || img);
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
      if (img) img.src = _thumbUrl(data.new_filename);
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
    if (_theater.active) _thRemoveItem(item);
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

function _itemMatches(item, term, filter) {
  const titleMatch  = !term || (item.dataset.title || '').toLowerCase().includes(term);
  const watchStatus = item.dataset.watched || '';
  const filterMatch =
    filter === 'all' ||
    (filter === 'watched'       && watchStatus === 'watched') ||
    (filter === 'want_to_watch' && watchStatus === 'want_to_watch') ||
    (filter === 'unwatched'     && watchStatus === '');
  return titleMatch && filterMatch;
}

function _applySearchAndFilter(term, filter) {
  const allItems = document.querySelectorAll('.grid-item');
  let visible = 0;
  allItems.forEach(function (item) {
    const show = _itemMatches(item, term, filter);
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
            _setLightboxSrc(_posterUrl(renData.new_filename));
            if (_lightboxGridItem) {
              _lightboxGridItem.dataset.filename = renData.new_filename;
              const img = _lightboxGridItem.querySelector('img');
              if (img) img.src = _thumbUrl(renData.new_filename);
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

/** Full-size poster (lightbox) vs. ~400px grid thumbnail. */
function _posterUrl(filename) { return '/posters/' + encodeURIComponent(filename); }
function _thumbUrl(filename)  { return '/thumbs/'  + encodeURIComponent(filename); }

const _reducedMotionMQ = window.matchMedia('(prefers-reduced-motion: reduce)');
const _mobileMQ        = window.matchMedia('(max-width: 700px)');
function _reducedMotion() { return _reducedMotionMQ.matches; }

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
      // Stacked bottom-sheet layout: flex-basis would set height, so leave it to CSS
      if (_mobileMQ.matches) { wrap.style.flex = ''; return; }
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
  if (parent?.dataset.filename) imageSrc = _posterUrl(parent.dataset.filename);
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
    '<div class="lb-delete-row" id="lb-delete-row">' + _LB_DELETE_BTN + '</div>' +
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
  if (_theater.active) _thRenderHero();
}

const _LB_DELETE_BTN = '<button class="lb-delete-btn" onclick="_lbConfirmDelete()">\uD83D\uDDD1 Delete poster</button>';

/** Inline confirm for the lightbox delete button. */
function _lbConfirmDelete() {
  const row = document.getElementById('lb-delete-row');
  if (!row || !_lightboxGridItem) return;
  const item = _lightboxGridItem;
  row.innerHTML =
    '<span class="lb-delete-q">Delete this poster?</span>' +
    '<button class="del-yes">Delete</button>' +
    '<button class="del-no">Cancel</button>';
  row.querySelector('.del-yes').addEventListener('click', function () { _doDelete(item); });
  row.querySelector('.del-no').addEventListener('click', function () { row.innerHTML = _LB_DELETE_BTN; });
}

// ── Lightbox prev / next (arrow keys, buttons, swipe) ─────────────────────────

/** Ordered list of grid items the lightbox can step through. */
function _lightboxSequence() {
  const cur = _lightboxGridItem;
  if (_theater.active) {
    const row = _theater.rows[_theater.row];
    if (row && row.items.includes(cur)) return row.items;
  }
  const all = Array.from(document.querySelectorAll('.grid-item'));
  if (_groupViewActive && cur && cur.dataset.collection) {
    return all.filter(function (i) { return i.dataset.collection === cur.dataset.collection; });
  }
  const term = (document.getElementById('searchBar')?.value || '').toLowerCase().trim();
  return all.filter(function (i) { return _itemMatches(i, term, currentFilter); });
}

function lightboxStep(dir) {
  if (!_lightboxGridItem) return;
  const seq = _lightboxSequence();
  if (seq.length < 2) return;
  let idx = seq.indexOf(_lightboxGridItem);
  idx = (idx + dir + seq.length) % seq.length;
  const img = seq[idx].querySelector('img');
  if (img) openLightbox(img.src, img);
  if (_theater.active) _thSyncToItem(seq[idx]);
  // Warm the cache for the next poster in the same direction
  const ahead = seq[(idx + dir + seq.length) % seq.length];
  if (ahead?.dataset.filename) { const pre = new Image(); pre.src = _posterUrl(ahead.dataset.filename); }
}

/** Swipe left/right on the poster to step; swipe down (mobile sheet) to close. */
function _initLightboxSwipe() {
  const dialog = document.querySelector('#lightbox .lb-dialog');
  if (!dialog) return;
  let x0 = null, y0 = null, t0 = 0;
  dialog.addEventListener('touchstart', function (e) {
    // Only the image area + handle are swipe surfaces; the sidebar scrolls normally
    if (!e.target.closest('.lb-image-wrap, .lb-handle') || e.target.closest('.lb-zoom-bar') ||
        e.touches.length !== 1) { x0 = null; return; }
    x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; t0 = Date.now();
  }, { passive: true });
  dialog.addEventListener('touchend', function (e) {
    if (x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0;
    const dy = e.changedTouches[0].clientY - y0;
    x0 = null;
    if (Date.now() - t0 > 800) return;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.3) {
      lightboxStep(dx < 0 ? 1 : -1);
    } else if (dy > 80 && Math.abs(dy) > Math.abs(dx) * 1.3 && _mobileMQ.matches) {
      closeLightbox();
    }
  }, { passive: true });
}

// ── Mobile nav menu ───────────────────────────────────────────────────────────

function toggleNavMenu(force) {
  const menu = document.getElementById('nav-menu');
  const btn  = document.getElementById('nav-menu-toggle');
  if (!menu || !btn) return;
  const open = typeof force === 'boolean' ? force : !menu.classList.contains('open');
  menu.classList.toggle('open', open);
  btn.classList.toggle('active', open);
  btn.setAttribute('aria-expanded', open ? 'true' : 'false');
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
            _setLightboxSrc(_posterUrl(renData.new_filename));
            if (_lightboxGridItem) {
              _lightboxGridItem.dataset.filename = renData.new_filename;
              const img = _lightboxGridItem.querySelector('img');
              if (img) img.src = _thumbUrl(renData.new_filename);
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
    _setLightboxSrc(_posterUrl(data.new_filename));

    // Update the grid item
    if (_lightboxGridItem) {
      _lightboxGridItem.dataset.title    = data.new_title;
      _lightboxGridItem.dataset.filename = data.new_filename;
      const img = _lightboxGridItem.querySelector('img');
      if (img) img.src = _thumbUrl(data.new_filename);
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
  img.width    = 400;
  img.height   = 600;
  img.src      = _thumbUrl(filename);
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

// ── Theater mode (Steam Big Picture style) ────────────────────────────────────
//
// Rows are built from the grid's data-* attributes plus /recently_added.
// Keyboard / mouse / gamepad move rows with transform (GPU, no layout);
// touch switches the rows to native overflow scrolling with scroll-snap.

const _coarseMQ = window.matchMedia('(pointer: coarse)');

const _theater = {
  active:   false,
  busy:     false,     // entering / exiting in progress
  rows:     [],        // [{ title, items, el, viewport, track, col }]
  row:      0,
  touch:    false,     // native-scroll mode
  scrollY:  0,
  bgFront:  'a',
  bgTimer:  0,
  preloaded: new Set(),
  lastMouse: 0,
  wheelAt:  0,
  ignoreScrollUntil: 0,
  touchRow: -1,        // row under the most recent touch
};

function toggleTheater() { _theater.active ? exitTheater() : enterTheater(); }

function _withViewTransition(update) {
  if (!document.startViewTransition || _reducedMotion()) {
    update();
    return Promise.resolve(false);
  }
  return document.startViewTransition(update).finished.then(function () { return true; }, function () { return true; });
}

function _requestFullscreen() {
  const el = document.documentElement;
  if (!el.requestFullscreen || document.fullscreenElement) return Promise.resolve();
  return el.requestFullscreen({ navigationUI: 'hide' })
    .then(function () {
      // Keyboard Lock lets Esc reach the page (close lightbox → exit theater)
      // instead of the browser silently leaving fullscreen.
      if (navigator.keyboard && navigator.keyboard.lock) {
        return navigator.keyboard.lock(['Escape']).catch(function () {});
      }
    })
    .catch(function () {});
}

function _exitFullscreen() {
  if (navigator.keyboard && navigator.keyboard.unlock) navigator.keyboard.unlock();
  if (!document.fullscreenElement || !document.exitFullscreen) return Promise.resolve();
  return document.exitFullscreen().catch(function () {});
}

/** The grid <img> for an item, if it's currently rendered inside the viewport. */
function _visibleGridImg(item) {
  if (!item || !item.offsetParent) return null;
  const r = item.getBoundingClientRect();
  if (r.bottom < 0 || r.top > window.innerHeight || r.right < 0 || r.left > window.innerWidth) return null;
  return item.querySelector('img');
}

function _thCollectRows(recent) {
  const items  = Array.from(document.querySelectorAll('.grid-item'));
  const byFile = new Map(items.map(function (i) { return [i.dataset.filename, i]; }));
  const pr     = function (i) { return parseInt(i.dataset.personalRating || '0', 10); };
  const rows   = [];
  function add(title, list, kind) { if (list.length) rows.push({ title: title, items: list, kind: kind || '' }); }

  add('Recently Added', (recent || []).map(function (r) { return byFile.get(r.filename); }).filter(Boolean));
  add('Want to Watch',  items.filter(function (i) { return i.dataset.watched === 'want_to_watch'; }));
  add('Watched',        items.filter(function (i) { return i.dataset.watched === 'watched'; }));
  add('Top Rated',      items.filter(function (i) { return pr(i) > 0; }).sort(function (a, b) {
    return pr(b) - pr(a) || (a.dataset.title || '').localeCompare(b.dataset.title || '');
  }));

  const groups = {};
  items.forEach(function (i) {
    const g = (i.dataset.collection || '').trim();
    if (g) (groups[g] = groups[g] || []).push(i);
  });
  Object.keys(groups).sort(function (a, b) { return a.toLowerCase().localeCompare(b.toLowerCase()); })
    .forEach(function (g) { add(g, groups[g], 'collection'); });

  if (!rows.length) add('Library', items);
  return rows;
}

function _thBuild() {
  const track = document.getElementById('th-rows-track');
  track.innerHTML = '';
  track.style.transform = '';
  document.getElementById('th-rows').scrollTop = 0;
  _theater.rows.forEach(function (row, r) {
    const sec = document.createElement('section');
    sec.className   = 'th-row';
    sec.dataset.row = r;
    sec.innerHTML =
      '<h2 class="th-row-title">' +
        (row.kind === 'collection' ? '<span class="th-row-kind">Collection</span>' : '') +
        escHtml(row.title) + '<span class="th-row-count">' + row.items.length + '</span>' +
      '</h2>';
    const vp = document.createElement('div');
    vp.className = 'th-row-viewport';
    const tr = document.createElement('div');
    tr.className = 'th-row-track';
    row.items.forEach(function (item, c) {
      const card = document.createElement('button');
      card.type        = 'button';
      card.className   = 'th-card';
      card.tabIndex    = -1;
      card.dataset.col = c;
      card.setAttribute('aria-label', item.dataset.title || '');
      if (item.dataset.color) card.style.setProperty('--th-glow', _hexToRgba(item.dataset.color, 0.7));
      const img = document.createElement('img');
      img.src       = _thumbUrl(item.dataset.filename);
      img.alt       = '';
      img.width     = 400;
      img.height    = 600;
      img.loading   = c < 10 ? 'eager' : 'lazy';
      img.decoding  = 'async';
      img.draggable = false;
      card.appendChild(img);
      tr.appendChild(card);
    });
    vp.appendChild(tr);
    sec.appendChild(vp);
    track.appendChild(sec);
    row.el = sec; row.viewport = vp; row.track = tr; row.col = 0;
    vp.addEventListener('scroll', function () { _thOnRowScroll(r); }, { passive: true });
  });
}

function _thCurItem() {
  const row = _theater.rows[_theater.row];
  return row ? row.items[row.col] : null;
}

function _thCardEl(r, c) {
  const row = _theater.rows[r];
  return row && row.track ? row.track.children[c] : null;
}

/** Move focus to row r / column c. opts: { reveal: true|false|'ifneeded', instant } */
function _thFocus(r, c, opts) {
  opts = opts || {};
  const rows = _theater.rows;
  if (!rows.length) return;
  r = Math.max(0, Math.min(rows.length - 1, r));
  const row = rows[r];
  c = Math.max(0, Math.min(row.items.length - 1, c));

  const prevRow = rows[_theater.row];
  if (prevRow) {
    _thCardEl(_theater.row, prevRow.col)?.classList.remove('th-focus');
    prevRow.el?.classList.remove('th-active');
  }
  _theater.row = r;
  row.col = c;
  row.el.classList.add('th-active');
  _thCardEl(r, c)?.classList.add('th-focus');

  if (opts.reveal !== false) _thReveal(r, !!opts.instant, opts.reveal === 'ifneeded');
  _thRenderHero();
  clearTimeout(_theater.bgTimer);
  _theater.bgTimer = setTimeout(_thSettled, 110);
}

/** Bring row r's focused card into view — transform in pointer mode, scroll in touch mode. */
function _thReveal(r, instant, onlyIfNeeded) {
  const row = _theater.rows[r];
  const card = _thCardEl(r, row.col);
  if (!row || !card) return;
  const rowsEl    = document.getElementById('th-rows');
  const rowsTrack = document.getElementById('th-rows-track');
  const pad   = parseFloat(getComputedStyle(row.track).paddingLeft) || 0;
  const vpW   = row.viewport.clientWidth;
  const maxX  = Math.max(0, row.track.scrollWidth - vpW);
  const peek  = row.col > 0 ? card.offsetWidth * 0.35 : 0;
  let x = Math.round(Math.min(Math.max(0, card.offsetLeft - pad - peek), maxX));
  const viewH = rowsEl.clientHeight - (parseFloat(getComputedStyle(rowsEl).paddingTop) || 0);
  const maxY  = Math.max(0, rowsTrack.scrollHeight - viewH);
  let y = Math.min(row.el.offsetTop, maxY);

  if (_theater.touch) {
    const behavior = (instant || _reducedMotion()) ? 'auto' : 'smooth';
    _theater.ignoreScrollUntil = performance.now() + 700;
    if (onlyIfNeeded) {
      const l = card.offsetLeft - row.viewport.scrollLeft;
      if (l >= 0 && l + card.offsetWidth <= vpW) x = row.viewport.scrollLeft;
    }
    row.viewport.scrollTo({ left: x, behavior: behavior });
    rowsEl.scrollTo({ top: y, behavior: behavior });
    return;
  }

  if (onlyIfNeeded) {
    const curX = row.x || 0;
    const l = card.offsetLeft - curX;
    if (l >= pad * 0.5 && l + card.offsetWidth <= vpW - pad * 0.5) x = curX;
    const curY = _theater.y || 0;
    const top = row.el.offsetTop - curY;
    if (top >= 0 && top + row.el.offsetHeight <= rowsEl.clientHeight) y = curY;
  }
  _thSetTransform(row.track, 'translate3d(' + (-x) + 'px,0,0)', instant);
  _thSetTransform(rowsTrack, 'translate3d(0,' + (-y) + 'px,0)', instant);
  row.x = x;
  _theater.y = y;
}

function _thSetTransform(el, value, instant) {
  if (instant) {
    el.classList.add('th-no-anim');
    el.style.transform = value;
    void el.offsetWidth;
    el.classList.remove('th-no-anim');
  } else {
    el.style.transform = value;
  }
}

function _thRevealAll(instant) {
  _theater.rows.forEach(function (row, r) { if (r !== _theater.row) _thReveal(r, true); });
  _thReveal(_theater.row, instant);
}

/** Switch between transform-driven (keys/mouse/pad) and native-scroll (touch) rows. */
function _thSetTouch(on) {
  if (_theater.touch === on) return;
  _theater.touch = on;
  const theater = document.getElementById('theater');
  theater.classList.toggle('th-touch', on);
  document.getElementById('th-rows-track').style.transform = '';
  _theater.y = 0;
  _theater.rows.forEach(function (row) { row.track.style.transform = ''; row.x = 0; row.viewport.scrollLeft = 0; });
  document.getElementById('th-rows').scrollTop = 0;
  _thRevealAll(true);
}

function _thRenderHero() {
  const item = _thCurItem();
  const hero = document.getElementById('th-hero');
  if (!item || !hero) return;
  const year   = item.dataset.year && item.dataset.year !== 'N/A' ? item.dataset.year : '';
  const imdb   = item.dataset.rating && item.dataset.rating !== 'N/A' ? item.dataset.rating : '';
  const pr     = parseInt(item.dataset.personalRating || '0', 10);
  const plot   = item.dataset.plot && item.dataset.plot !== 'No plot available' ? item.dataset.plot : '';
  const status = item.dataset.watched === 'watched' ? '\u2713 Watched'
               : item.dataset.watched === 'want_to_watch' ? '\u2665 Want to Watch' : '';
  const parts = [];
  if (year)   parts.push('<span>' + escHtml(year) + '</span>');
  if (imdb)   parts.push('<span class="th-imdb">IMDb</span><span>' + escHtml(imdb) + '</span>');
  if (pr > 0) parts.push('<span class="th-stars" aria-label="My rating ' + pr + ' of 5">' + '\u2605'.repeat(pr) + '<span class="th-stars-off">' + '\u2605'.repeat(5 - pr) + '</span></span>');
  if (status) parts.push('<span class="th-status">' + status + '</span>');

  document.getElementById('th-title').textContent = item.dataset.title || '';
  document.getElementById('th-meta').innerHTML    = parts.join('<span class="th-dot">\u00b7</span>');
  document.getElementById('th-plot').textContent  = plot;
  hero.classList.remove('th-in');
  void hero.offsetWidth;          // restart the fade-in
  hero.classList.add('th-in');
}

/** Runs once focus has been still for ~100ms: background crossfade + preloading. */
function _thSettled() {
  const item = _thCurItem();
  if (!item || !_theater.active) return;
  _thSetBackground(item);
  // Preload full-size posters for the focused card and its neighbours only
  const row = _theater.rows[_theater.row];
  [row.col, row.col + 1, row.col - 1].forEach(function (i) {
    const it = row.items[i];
    if (!it || _theater.preloaded.has(it.dataset.filename)) return;
    _theater.preloaded.add(it.dataset.filename);
    const im = new Image();
    im.decoding = 'async';
    im.src = _posterUrl(it.dataset.filename);
  });
}

function _thSetBackground(item) {
  const url   = _thumbUrl(item.dataset.filename);
  const front = document.getElementById('th-bg-' + _theater.bgFront);
  if (front.dataset.url === url) return;   // (colour is per poster, so url is enough)
  const backKey = _theater.bgFront === 'a' ? 'b' : 'a';
  const back    = document.getElementById('th-bg-' + backKey);
  const probe   = new Image();
  probe.onload = probe.onerror = function () {
    if (_thCurItem() !== item) return;          // focus moved on meanwhile
    // Tint layered over the poster, so the crossfade is still opacity-only
    const tint = item.dataset.color ? _hexToRgba(item.dataset.color, 0.38) : 'rgba(0,0,0,0)';
    back.style.backgroundImage =
      'linear-gradient(' + tint + ',' + tint + '), url("' + url.replace(/"/g, '%22') + '")';
    back.dataset.url = url;
    back.classList.add('th-bg-on');
    front.classList.remove('th-bg-on');
    _theater.bgFront = backKey;
  };
  probe.src = url;
}

function _thMove(dx, dy) {
  if (!_theater.rows.length) return;
  if (dy) {
    const r = _theater.row + dy;
    if (r < 0 || r >= _theater.rows.length) return;
    _thFocus(r, _theater.rows[r].col);
  } else {
    _thFocus(_theater.row, _theater.rows[_theater.row].col + dx);
  }
}

function _thOpen() {
  const item = _thCurItem();
  const img  = item?.querySelector('img');
  if (img) openLightbox(img.src, img);
}

/** Keep theater focus on the poster the lightbox stepped to. */
function _thSyncToItem(item) {
  const row = _theater.rows[_theater.row];
  const c = row ? row.items.indexOf(item) : -1;
  if (c >= 0) _thFocus(_theater.row, c);
}

/** Drop a deleted poster from every row, keeping focus as close as possible. */
function _thRemoveItem(item) {
  const cur = { r: _theater.row, c: _theater.rows[_theater.row]?.col || 0 };
  _theater.rows = _theater.rows
    .map(function (row) { return Object.assign({}, row, { items: row.items.filter(function (i) { return i !== item; }) }); })
    .filter(function (row) { return row.items.length; });
  if (!_theater.rows.length) { exitTheater(); return; }
  _thBuild();
  _theater.row = Math.min(cur.r, _theater.rows.length - 1);
  _thFocus(_theater.row, cur.c, { instant: true });
}

function _thOnRowScroll(r) {
  if (!_theater.touch || performance.now() < _theater.ignoreScrollUntil) return;
  const row = _theater.rows[r];
  clearTimeout(row.scrollTimer);
  row.scrollTimer = setTimeout(function () {
    if (performance.now() < _theater.ignoreScrollUntil) return;
    const pad  = parseFloat(getComputedStyle(row.track).paddingLeft) || 0;
    const left = row.viewport.scrollLeft;
    const cards = row.track.children;
    let c = 0;
    for (let i = 0; i < cards.length; i++) {
      if (cards[i].offsetLeft + cards[i].offsetWidth / 2 >= left + pad) { c = i; break; }
    }
    if (r === _theater.row) {
      if (c !== row.col) _thFocus(r, c, { reveal: false });
    } else if (r === _theater.touchRow) {
      _thFocus(r, c, { reveal: false });
    } else {
      row.col = c;   // e.g. a scroll-snap settle on another row — remember, don't steal focus
    }
  }, 140);
}

function _thOnRowsScroll() {
  if (!_theater.touch || performance.now() < _theater.ignoreScrollUntil) return;
  clearTimeout(_theater.vScrollTimer);
  _theater.vScrollTimer = setTimeout(function () {
    if (performance.now() < _theater.ignoreScrollUntil) return;
    const top = document.getElementById('th-rows').scrollTop;
    let best = 0, bestD = Infinity;
    _theater.rows.forEach(function (row, r) {
      const d = Math.abs(row.el.offsetTop - top);
      if (d < bestD) { bestD = d; best = r; }
    });
    if (best !== _theater.row) _thFocus(best, _theater.rows[best].col, { reveal: false });
  }, 140);
}

async function enterTheater() {
  if (_theater.active || _theater.busy) return;
  _theater.busy = true;
  const theater = document.getElementById('theater');
  closeLightbox();
  toggleNavMenu(false);
  document.getElementById('recent-dropdown')?.classList.remove('open');
  document.getElementById('recent-toggle-btn')?.classList.remove('active');

  // Fullscreen must be requested inside the click / key gesture, so start it first
  const recentReq = fetch('/recently_added?limit=30')
    .then(function (r) { return r.ok ? r.json() : []; })
    .catch(function () { return []; });
  const [, recent] = await Promise.all([_requestFullscreen(), recentReq]);

  await _refreshPosterColors();
  _theater.rows    = _thCollectRows(recent);
  _theater.row     = 0;
  _theater.scrollY = window.scrollY;
  _theater.touch   = _coarseMQ.matches;
  theater.classList.toggle('th-touch', _theater.touch);

  // Morph: the grid container becomes the rows area; the first poster morphs too if visible
  const grid   = document.querySelector('.grid-container');
  const rowsEl = document.getElementById('th-rows');
  const srcImg = _visibleGridImg(_theater.rows[0]?.items[0]);
  if (grid)   grid.style.viewTransitionName   = 'th-grid';
  if (srcImg) srcImg.style.viewTransitionName = 'th-poster';
  let dstImg = null;

  const usedVT = await _withViewTransition(function () {
    if (grid)   grid.style.viewTransitionName   = '';
    if (srcImg) srcImg.style.viewTransitionName = '';
    _thBuild();
    theater.hidden = false;
    document.body.classList.add('theater-open');
    document.getElementById('theater-btn')?.classList.add('active');
    _theater.active = true;
    _thFocus(0, 0, { instant: true });
    rowsEl.style.viewTransitionName = 'th-grid';
    if (srcImg) {
      dstImg = _thCardEl(0, 0)?.querySelector('img');
      if (dstImg) dstImg.style.viewTransitionName = 'th-poster';
    }
  });
  rowsEl.style.viewTransitionName = '';
  if (dstImg) dstImg.style.viewTransitionName = '';
  if (!usedVT && !_reducedMotion()) {
    theater.classList.add('th-fade-in');
    setTimeout(function () { theater.classList.remove('th-fade-in'); }, 400);
  }
  _padStart();
  _theater.busy = false;
}

async function exitTheater(opts) {
  if (!_theater.active || _theater.busy) return;
  _theater.busy = true;
  const theater = document.getElementById('theater');
  closeLightbox();
  if (!(opts && opts.fromFullscreenChange)) await _exitFullscreen();

  const item   = _thCurItem();
  const grid   = document.querySelector('.grid-container');
  const rowsEl = document.getElementById('th-rows');
  const card   = _thCardEl(_theater.row, _theater.rows[_theater.row]?.col)?.querySelector('img');
  rowsEl.style.viewTransitionName = 'th-grid';
  if (card) card.style.viewTransitionName = 'th-poster';
  let dstImg = null;

  await _withViewTransition(function () {
    rowsEl.style.viewTransitionName = '';
    if (card) card.style.viewTransitionName = '';
    theater.hidden = true;
    document.body.classList.remove('theater-open');
    document.getElementById('theater-btn')?.classList.remove('active');
    _theater.active = false;
    window.scrollTo({ top: _theater.scrollY, behavior: 'instant' });
    if (grid) grid.style.viewTransitionName = 'th-grid';
    dstImg = _visibleGridImg(item);
    if (dstImg) dstImg.style.viewTransitionName = 'th-poster';
  });
  if (grid) grid.style.viewTransitionName = '';
  if (dstImg) dstImg.style.viewTransitionName = '';
  document.getElementById('th-rows-track').innerHTML = '';
  _theater.rows = [];
  _theater.busy = false;
}

/** Arrow keys / WASD / Enter inside theater. Returns true if the key was used. */
function _thHandleKey(e) {
  const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  const moves = {
    ArrowLeft: [-1, 0], a: [-1, 0], ArrowRight: [1, 0], d: [1, 0],
    ArrowUp:   [0, -1], w: [0, -1], ArrowDown:  [0, 1], s: [0, 1],
  };
  if (moves[k]) {
    _thSetTouch(false);
    _thMove(moves[k][0], moves[k][1]);
    return true;
  }
  if (k === 'Enter' || k === ' ') { _thOpen(); return true; }
  if (k === 'Home') { _thFocus(_theater.row, 0); return true; }
  if (k === 'End')  { _thFocus(_theater.row, Infinity); return true; }
  return false;
}

function _thInit() {
  const theater = document.getElementById('theater');
  const rowsEl  = document.getElementById('th-rows');
  if (!theater || !rowsEl) return;

  // Click / tap a card. Touch: first tap focuses, second opens. Mouse: opens.
  rowsEl.addEventListener('click', function (e) {
    const card = e.target.closest('.th-card');
    if (!card) return;
    const r = parseInt(card.closest('.th-row').dataset.row, 10);
    const c = parseInt(card.dataset.col, 10);
    const already = r === _theater.row && c === _theater.rows[r].col;
    _theater.rows.forEach(function (row) { clearTimeout(row.scrollTimer); });
    clearTimeout(_theater.vScrollTimer);
    _theater.ignoreScrollUntil = performance.now() + 700;
    if (!already) _thFocus(r, c, { reveal: 'ifneeded' });
    if (already || !_theater.touch) _thOpen();
  });

  // Mouse hover focuses — but only after real pointer movement, so the row
  // sliding under a stationary cursor doesn't steal focus back.
  theater.addEventListener('pointermove', function (e) {
    if (e.pointerType !== 'mouse' || (!e.movementX && !e.movementY)) return;
    _theater.lastMouse = performance.now();
    if (_theater.touch) _thSetTouch(false);
  });
  rowsEl.addEventListener('pointerover', function (e) {
    if (e.pointerType !== 'mouse' || _theater.touch || performance.now() - _theater.lastMouse > 150) return;
    const card = e.target.closest('.th-card');
    if (!card) return;
    const r = parseInt(card.closest('.th-row').dataset.row, 10);
    const c = parseInt(card.dataset.col, 10);
    if (r !== _theater.row || c !== _theater.rows[r].col) _thFocus(r, c, { reveal: 'ifneeded' });
  });

  theater.addEventListener('touchstart', function (e) {
    const rowEl = e.target.closest && e.target.closest('.th-row');
    _theater.touchRow = rowEl ? parseInt(rowEl.dataset.row, 10) : -1;
    _thSetTouch(true);
  }, { passive: true });
  rowsEl.addEventListener('scroll', _thOnRowsScroll, { passive: true });

  // Wheel: vertical → change row, horizontal / shift → change column
  rowsEl.addEventListener('wheel', function (e) {
    if (_theater.touch) return;
    e.preventDefault();
    const horiz = e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY);
    const d = horiz ? (e.deltaX || e.deltaY) : e.deltaY;
    const now = performance.now();
    if (Math.abs(d) < 4 || now - _theater.wheelAt < (horiz ? 90 : 220)) return;
    _theater.wheelAt = now;
    if (horiz) _thMove(d > 0 ? 1 : -1, 0); else _thMove(0, d > 0 ? 1 : -1);
  }, { passive: false });

  let resizeT = 0;
  window.addEventListener('resize', function () {
    if (!_theater.active) return;
    clearTimeout(resizeT);
    resizeT = setTimeout(function () { _thRevealAll(true); }, 120);
  });

  // Leaving fullscreen by other means (browser UI, F11, Esc without keyboard lock) exits theater
  document.addEventListener('fullscreenchange', function () {
    if (!document.fullscreenElement && _theater.active && !_theater.busy) {
      exitTheater({ fromFullscreenChange: true });
    }
  });

  window.addEventListener('gamepadconnected', function () {
    _padStart();
    if (_theater.active) showToast('\uD83C\uDFAE Gamepad connected');
  });
}

// ── Gamepad (standard mapping) ────────────────────────────────────────────────
// D-pad 12–15 / left stick → move · A (0) → open · B (1) → back · Start (9) → theater

const _pad = { raf: 0, dir: '', since: 0, last: 0, btn: {} };

function _padStart() {
  if (!_pad.raf && navigator.getGamepads) _pad.raf = requestAnimationFrame(_padTick);
}

function _padTick(t) {
  const gp = Array.from(navigator.getGamepads ? navigator.getGamepads() : []).find(Boolean);
  if (!gp && !_theater.active) { _pad.raf = 0; return; }   // idle: stop polling
  _pad.raf = requestAnimationFrame(_padTick);
  if (!gp) return;

  const b  = function (i) { return !!(gp.buttons[i] && gp.buttons[i].pressed); };
  const ax = gp.axes[0] || 0, ay = gp.axes[1] || 0;
  let dir = '';
  if      (b(12)) dir = 'up';
  else if (b(13)) dir = 'down';
  else if (b(14)) dir = 'left';
  else if (b(15)) dir = 'right';
  else if (Math.max(Math.abs(ax), Math.abs(ay)) > 0.5) {
    dir = Math.abs(ax) > Math.abs(ay) ? (ax < 0 ? 'left' : 'right') : (ay < 0 ? 'up' : 'down');
  }
  // Fire once on press, then auto-repeat after 380ms every 110ms
  if (dir !== _pad.dir) {
    _pad.dir = dir; _pad.since = _pad.last = t;
    if (dir) _padAction(dir);
  } else if (dir && t - _pad.since > 380 && t - _pad.last > 110) {
    _pad.last = t;
    _padAction(dir);
  }
  [[0, 'open'], [1, 'back'], [9, 'start']].forEach(function (pair) {
    const pressed = b(pair[0]);
    if (pressed && !_pad.btn[pair[0]]) _padAction(pair[1]);
    _pad.btn[pair[0]] = pressed;
  });
}

function _padAction(act) {
  if (!document.getElementById('spin-overlay')?.hidden) {
    if (act === 'back') closeSpin();
    return;
  }
  const lbOpen = document.getElementById('lightbox')?.classList.contains('show');
  if (lbOpen) {
    if (act === 'left')  lightboxStep(-1);
    if (act === 'right') lightboxStep(1);
    if (act === 'back')  closeLightbox();
    return;
  }
  if (!_theater.active) { if (act === 'start') enterTheater(); return; }
  _thSetTouch(false);
  if (act === 'left')  _thMove(-1, 0);
  if (act === 'right') _thMove(1, 0);
  if (act === 'up')    _thMove(0, -1);
  if (act === 'down')  _thMove(0, 1);
  if (act === 'open')  _thOpen();
  if (act === 'back' || act === 'start') exitTheater();
}

// ── Poster colours (dominant colour per poster, from /poster_colors) ─────────

function _hexToRgba(hex, a) {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || '');
  if (!m) return '';
  return 'rgba(' + parseInt(m[1], 16) + ',' + parseInt(m[2], 16) + ',' + parseInt(m[3], 16) + ',' + a + ')';
}

function _setItemColor(item, color) {
  if (!color) return;
  item.dataset.color = color;
  item.style.setProperty('--pc', color);
}

/** Fill in colours the server computed after this page was rendered. */
async function _refreshPosterColors() {
  const missing = Array.from(document.querySelectorAll('.grid-item')).filter(function (i) { return !i.dataset.color; });
  if (!missing.length) return;
  try {
    const resp = await fetch('/poster_colors');
    if (!resp.ok) return;
    const colors = await resp.json();
    missing.forEach(function (i) { _setItemColor(i, colors[i.dataset.filename]); });
  } catch (_) { /* colours are decorative */ }
}

// ── 3D tilt on hover (mouse / trackpad only) ──────────────────────────────────

function _initTilt() {
  const grid = document.querySelector('.grid-container');
  if (!grid) return;
  const fineMQ = window.matchMedia('(hover: hover) and (pointer: fine)');
  let raf = 0, pending = null;

  function apply() {
    raf = 0;
    if (!pending) return;
    const item = pending.item;
    const r  = item.getBoundingClientRect();
    const px = (pending.x - r.left) / r.width  - 0.5;   // -0.5 … 0.5
    const py = (pending.y - r.top)  / r.height - 0.5;
    item.style.setProperty('--ry', (px * 14).toFixed(2) + 'deg');
    item.style.setProperty('--rx', (-py * 14).toFixed(2) + 'deg');
  }
  grid.addEventListener('pointermove', function (e) {
    if (e.pointerType !== 'mouse' || !fineMQ.matches || _reducedMotion()) return;
    const item = e.target.closest('.grid-item');
    if (!item || item.dataset.editing === 'true') return;
    pending = { item: item, x: e.clientX, y: e.clientY };
    if (!raf) raf = requestAnimationFrame(apply);
  });
  grid.addEventListener('pointerout', function (e) {
    const item = e.target.closest('.grid-item');
    if (!item || item.contains(e.relatedTarget)) return;
    item.style.removeProperty('--rx');
    item.style.removeProperty('--ry');
    if (pending && pending.item === item) pending = null;
  });
}

// ── "What should I watch?" slot machine ───────────────────────────────────────

const _spin = { anim: null, timer: 0 };

function openSpin() {
  const items  = Array.from(document.querySelectorAll('.grid-item'));
  let pool     = items.filter(function (i) { return i.dataset.watched === 'want_to_watch'; });
  let sub      = pool.length + ' poster' + (pool.length === 1 ? '' : 's') + ' in Want to Watch';
  if (!pool.length) {
    pool = items.filter(function (i) { return !i.dataset.watched; });
    sub  = 'Want to Watch is empty \u2014 picking from your unwatched posters';
  }
  if (!pool.length) { showToast('Nothing left to pick from \u2014 everything is watched!'); return; }

  closeLightbox();
  toggleNavMenu(false);
  const overlay = document.getElementById('spin-overlay');
  const reel    = document.getElementById('spin-reel');
  const win     = document.getElementById('spin-window');
  const frame   = document.getElementById('spin-frame');
  const result  = document.getElementById('spin-result');
  document.getElementById('spin-sub').textContent = sub;
  result.textContent = '';
  frame.classList.remove('spin-landed');
  overlay.hidden = false;

  // Reel: a shuffled run of posters ending on the pick, plus two after it to peek below
  const pick  = pool[Math.floor(Math.random() * pool.length)];
  const cells = [];
  const run   = Math.max(28, Math.min(44, pool.length * 3));
  for (let i = 0; i < run; i++) cells.push(pool[Math.floor(Math.random() * pool.length)]);
  cells.push(pick);
  const pickIdx = cells.length - 1;
  cells.push(pool[Math.floor(Math.random() * pool.length)], pool[Math.floor(Math.random() * pool.length)]);

  reel.innerHTML = '';
  cells.forEach(function (item) {
    const cell = document.createElement('div');
    cell.className = 'spin-cell';
    const img = document.createElement('img');
    img.src = _thumbUrl(item.dataset.filename);
    img.alt = '';
    img.width = 400; img.height = 600;
    img.decoding = 'async';
    cell.appendChild(img);
    reel.appendChild(cell);
  });
  const pre = new Image();
  pre.src = _posterUrl(pick.dataset.filename);       // full-size ready for the lightbox

  const cell  = reel.firstElementChild;
  const step  = cell.offsetHeight + parseFloat(getComputedStyle(reel).rowGap || 0);
  const offset = (win.clientHeight - cell.offsetHeight) / 2;
  const endY  = -(pickIdx * step) + offset;
  const color = pick.dataset.color;
  frame.style.setProperty('--spin-glow', color ? _hexToRgba(color, 0.75) : 'rgba(245,200,66,0.7)');

  function land() {
    _spin.anim = null;
    reel.style.transform = 'translate3d(0,' + endY + 'px,0)';
    frame.classList.add('spin-landed');
    const yr = pick.dataset.year && pick.dataset.year !== 'N/A' ? ' (' + pick.dataset.year + ')' : '';
    result.textContent = (pick.dataset.title || '') + yr;
    _spin.timer = setTimeout(function () {
      closeSpin();
      const img = pick.querySelector('img');
      if (img) openLightbox(img.src, img);
    }, _reducedMotion() ? 500 : 1100);
  }

  if (_reducedMotion() || !reel.animate) { land(); return; }
  _spin.anim = reel.animate(
    [{ transform: 'translate3d(0,' + offset + 'px,0)' }, { transform: 'translate3d(0,' + endY + 'px,0)' }],
    { duration: 3800, easing: 'cubic-bezier(0.08, 0.72, 0.14, 1)', fill: 'forwards' }
  );
  _spin.anim.onfinish = land;
}

function closeSpin() {
  clearTimeout(_spin.timer);
  if (_spin.anim) { _spin.anim.onfinish = null; _spin.anim.cancel(); _spin.anim = null; }
  const overlay = document.getElementById('spin-overlay');
  if (overlay) overlay.hidden = true;
  const reel = document.getElementById('spin-reel');
  if (reel) { reel.innerHTML = ''; reel.style.transform = ''; }
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

    const spinOpen = !document.getElementById('spin-overlay')?.hidden;
    if (spinOpen) {
      if (e.key === 'Escape') closeSpin();
      return;
    }

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
      } else if (document.getElementById('nav-menu')?.classList.contains('open')) {
        toggleNavMenu(false);
      } else if (document.getElementById('lightbox')?.classList.contains('show')) {
        closeLightbox();
      } else if (_theater.active) {
        exitTheater();
      }
      return;
    }

    if (typing) return;
    const lbOpen = document.getElementById('lightbox')?.classList.contains('show');
    const modalOpen = document.querySelector('.modal-overlay.show');
    if (modalOpen) return;

    if ((e.key === 'b' || e.key === 'B') && !e.ctrlKey && !e.metaKey && !e.altKey && !lbOpen) {
      e.preventDefault();
      toggleTheater();
      return;
    }
    if (_theater.active && !lbOpen) {
      if (_thHandleKey(e)) e.preventDefault();
      return;
    }
    if (e.key === 'ArrowRight') { if (lbOpen) lightboxStep(1);  else changePage(1); }
    if (e.key === 'ArrowLeft')  { if (lbOpen) lightboxStep(-1); else changePage(-1); }
  });

  document.getElementById('closeLightbox')?.addEventListener('click', closeLightbox);
  _initLightboxSwipe();
  _thInit();
  _initTilt();
  _refreshPosterColors();

  // Click outside the reel card closes the spin
  document.getElementById('spin-overlay')?.addEventListener('click', function (e) {
    if (e.target === this) closeSpin();
  });

  // Mobile nav menu: close after picking an action, or on outside tap
  document.getElementById('nav-menu')?.addEventListener('click', function (e) {
    if (e.target.closest('.nav-filter-btn, .nav-group-view-btn, .nav-recent-btn, .nav-upload-btn, .nav-link, .nav-feature-group > *')) {
      toggleNavMenu(false);
    }
  });
  document.addEventListener('click', function (e) {
    const menu = document.getElementById('nav-menu');
    if (!menu || !menu.classList.contains('open')) return;
    if (menu.contains(e.target) || e.target.closest('#nav-menu-toggle')) return;
    toggleNavMenu(false);
  });

  // PWA: service worker caches /static/* only (needs https or localhost)
  if ('serviceWorker' in navigator && window.isSecureContext) {
    navigator.serviceWorker.register('/sw.js').catch(function (err) {
      console.warn('Service worker registration failed', err);
    });
  }

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
