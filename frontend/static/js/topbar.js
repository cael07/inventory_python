document.addEventListener("DOMContentLoaded", () => {

  // 🔐 AUTH CHECK (protect pages)
  const token = localStorage.getItem("token");
  const user = JSON.parse(localStorage.getItem("user") || "{}");

  if (!token || !user.username) {
    window.location.href = "login.html";
    return;
  }

  // 🔝 CREATE TOPBAR
  const topbar = document.createElement("div");
  topbar.className = "topbar";

  topbar.innerHTML = `
    <a href="dashboard.html" class="topbar-logo">
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
      <a href="product_management.html">📦 Products</a>
      <a href="report.html">📊 Reports</a>
      <a href="#">⚙️ Settings</a>

      <div class="dropdown-divider"></div>

      <a href="#">👨‍👩‍👧‍👦 SUKI</a>
      <a href="#">🧑‍🤝‍🧑 Employees</a>

      <div class="dropdown-divider"></div>

      <a href="#">💬 Messages</a>

      <div class="dropdown-divider"></div>

      <div class="dropdown-user">
        👤 <strong id="topbar-username"></strong>
      </div>

      <a href="#" id="logout-btn">🚪 Log Out</a>
    </div>
  `;

  document.body.prepend(topbar);

  // 👤 SET USERNAME
  document.getElementById("topbar-username").innerText = user.username;

  // 🍔 TOGGLE DROPDOWN
  const hamburger = document.getElementById("hamburger");
  const dropdown = document.getElementById("dropdown-menu");

  hamburger.addEventListener("click", () => {
    hamburger.classList.toggle("active");
    dropdown.classList.toggle("show");
  });

  // ❌ CLOSE DROPDOWN WHEN CLICKING OUTSIDE
  document.addEventListener("click", (e) => {
    if (!hamburger.contains(e.target) && !dropdown.contains(e.target)) {
      hamburger.classList.remove("active");
      dropdown.classList.remove("show");
    }
  });

  // 🚪 LOGOUT
  document.getElementById("logout-btn").addEventListener("click", (e) => {
    e.preventDefault();

    localStorage.removeItem("token");
    localStorage.removeItem("user");

    window.location.href = "login.html";
  });

});
