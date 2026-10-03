// Mobile Sidebar Drawer Toggle Logic
function initSidebar() {
  const toggleBtn = document.getElementById("sidebar-toggle");
  const closeBtn = document.getElementById("sidebar-close");
  const overlay = document.getElementById("sidebar-overlay");
  const menu = document.getElementById("sidebar-menu");

  if (!toggleBtn || !closeBtn || !overlay || !menu) return;

  function openSidebar() {
    overlay.classList.remove("pointer-events-none", "opacity-0");
    overlay.classList.add("opacity-100");
    menu.classList.remove("translate-x-full");
    document.body.classList.add("sidebar-open");
  }

  function closeSidebar() {
    overlay.classList.add("pointer-events-none", "opacity-0");
    overlay.classList.remove("opacity-100");
    menu.classList.add("translate-x-full");
    document.body.classList.remove("sidebar-open");
  }

  toggleBtn.addEventListener("click", openSidebar);
  closeBtn.addEventListener("click", closeSidebar);
  overlay.addEventListener("click", closeSidebar);

  // Close sidebar when clicking any navigation link inside it
  const sidebarLinks = menu.querySelectorAll("nav a");
  sidebarLinks.forEach(link => {
    link.addEventListener("click", closeSidebar);
  });
}

// Hydrate icons and initialize event listeners on load
function initApp() {
  if (typeof lucide !== "undefined") {
    lucide.createIcons();
  }
  initSidebar();
}

window.addEventListener("DOMContentLoaded", initApp);

// Header Scroll Behavior (Glassmorphism Effect)
let isScrolled = false;

function checkHeaderScroll() {
  const scrollPos = window.scrollY;
  const headers = document.querySelectorAll('.header-glass');
  if (scrollPos > 50) {
    headers.forEach(header => header.classList.add('scrolled'));
    isScrolled = true;
  } else {
    headers.forEach(header => header.classList.remove('scrolled'));
    isScrolled = false;
  }
}

// Single passive scroll event listener for optimal performance
window.addEventListener('scroll', function() {
  const scrollPos = window.scrollY;
  if (scrollPos > 10 && !isScrolled) {
    document.querySelectorAll('.header-glass').forEach(header => header.classList.add('scrolled'));
    isScrolled = true;
  } else if (scrollPos <= 50 && isScrolled) {
    document.querySelectorAll('.header-glass').forEach(header => header.classList.remove('scrolled'));
    isScrolled = false;
  }
}, { passive: true });

// Check scroll state on DOM ready to handle page refreshes at scrolled positions
window.addEventListener('DOMContentLoaded', checkHeaderScroll);
