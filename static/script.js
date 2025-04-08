let currentPage = 1;
const itemsPerPage = 50;

function toggleDarkMode() {
  const body = document.body;
  body.classList.toggle('light-mode');
  const mode = body.classList.contains('light-mode') ? 'light' : 'dark';
  localStorage.setItem('theme', mode);
  document.getElementById('darkModeLabel').textContent =
    mode === 'dark' ? 'Dark Mode' : 'Light Mode';
}

function openLightbox(imageSrc, element) {
  const lightbox = document.getElementById('lightbox');
  const lightboxImage = document.getElementById('lightboxImage');

  const parent = element.closest('.grid-item');
  const title = parent.dataset.title || 'N/A';
  const year = parent.dataset.year || 'N/A';
  const rating = parent.dataset.rating || 'N/A';
  const plot = parent.dataset.plot || 'No plot available';

  const metadata = `
    <div id="metadata">
      <h2>${title} (${year})</h2>
      <p><strong>IMDb Rating:</strong> ${rating}</p>
      <p><strong>Plot:</strong> ${plot}</p>
    </div>
  `;

  const existingMetadata = document.getElementById('metadata');
  if (existingMetadata) existingMetadata.remove();

  lightboxImage.src = imageSrc;
  lightbox.classList.remove('hidden');
  lightbox.classList.add('show');

  const closeButton = document.getElementById('closeLightbox');
  closeButton.insertAdjacentHTML('beforebegin', metadata);
}

function closeLightbox() {
  const lightbox = document.getElementById('lightbox');
  const lightboxImage = document.getElementById('lightboxImage');
  lightbox.classList.remove('show');
  lightbox.classList.add('hidden');
  lightboxImage.src = '';

  const existingMetadata = document.getElementById('metadata');
  if (existingMetadata) existingMetadata.remove();
}

function changePage(direction) {
  const allItems = document.querySelectorAll('.grid-item');
  const totalItems = allItems.length;
  const totalPages = Math.ceil(totalItems / itemsPerPage);

  currentPage += direction;
  if (currentPage < 1) currentPage = 1;
  if (currentPage > totalPages) currentPage = totalPages;

  allItems.forEach(item => (item.style.display = 'none'));

  allItems.forEach((item, index) => {
    const page = Math.floor(index / itemsPerPage) + 1;
    if (page === currentPage) {
      item.style.display = 'block';
    }
  });

  document.getElementById('page-number').textContent = currentPage;
}

document.addEventListener('DOMContentLoaded', function () {
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme === 'light') {
    document.body.classList.add('light-mode');
  }

  const searchBar = document.getElementById('searchBar');
  const gridItems = document.querySelectorAll('.grid-item');

  searchBar.addEventListener('input', function () {
    const searchTerm = searchBar.value.toLowerCase();
    gridItems.forEach(item => {
      const title = item.getAttribute('data-title');
      if (title.includes(searchTerm)) {
        item.style.display = 'block';
      } else {
        item.style.display = 'none';
      }
    });
  });

  document.getElementById('closeLightbox').addEventListener('click', closeLightbox);

  changePage(0);
});
