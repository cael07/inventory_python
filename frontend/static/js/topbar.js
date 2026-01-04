document.addEventListener("DOMContentLoaded", () => {
  const topbar = document.createElement("div");
  topbar.className = "topbar";

  topbar.innerHTML = `
    <a href="index.html" class="topbar-logo">
      <img src="/static/img/cael.ico" alt="Logo">
    </a>

    <!-- Hamburger -->
    <div class="topbar-hamburger" id="hamburger">
      <span></span>
      <span></span>
      <span></span>
    </div>

<!-- Dropdown Menu -->
<div class="topbar-dropdown" id="dropdown-menu">
  <a href="pos.html">🧾 POS</a>
  <a href="product_management.html">📦 Product Management</a>
  <a href="report.html">📊 Reports</a>
  <a href="#">👤 SUKI</a>
  <a href="#">⚙️ Settings</a>

  <div class="dropdown-divider"></div>

  <a href="#">💬 Messages</a>

  <div class="dropdown-divider"></div>

  <a href="#">👤 John P.</a>
  <a href="#">🚪 Log Out</a>
</div>

  `;

  document.body.prepend(topbar);

  // Toggle dropdown
  const hamburger = document.getElementById("hamburger");
  const dropdown = document.getElementById("dropdown-menu");

  hamburger.addEventListener("click", () => {
    hamburger.classList.toggle("active");
    dropdown.classList.toggle("show");
  });

  // Close dropdown when clicking outside
  document.addEventListener("click", (e) => {
    if (!hamburger.contains(e.target) && !dropdown.contains(e.target)) {
      hamburger.classList.remove("active");
      dropdown.classList.remove("show");
    }
  });
});
