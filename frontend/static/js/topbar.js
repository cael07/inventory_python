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

      <a href="messages.html">💬 Messages</a>

      <div class="dropdown-divider"></div>

      <div class="dropdown-user">
        👤 <strong id="topbar-username"></strong>
      </div>

      <a href="#" id="logout-btn">🚪 Log Out</a>
    </div>
  `;

  document.body.prepend(topbar);

  // --- USER PROFILE MODAL INJECTION ---
  const profileModalHtml = `
    <div class="profile-modal" id="profile-modal">
      <div class="profile-modal-box" style="width: 400px; max-height: 90vh; overflow-y: auto;">
        <h3>User Profile</h3>

        <!-- STATIC DETAILS -->
        <div id="prof-static-details" style="background:#f5f6fa; padding:10px; border-radius:6px; margin-bottom:15px; font-size:14px; line-height:1.6;">
          Loading details...
        </div>

        <h4 style="margin-bottom: 10px; margin-top: 0; color: #1f3a5f;">Edit Information</h4>
        <label>Address</label>
        <input type="text" id="prof-address" />
        <label>Store Name</label>
        <input type="text" id="prof-storename" />
        <label>Store Location</label>
        <input type="text" id="prof-storelocation" />
        <label>New Password (Optional)</label>
        <input type="password" id="prof-password" placeholder="Leave blank to keep current" />
        <div class="btn-row">
          <button id="prof-save-btn">Save</button>
          <button id="prof-cancel-btn" class="btn-cancel">Close</button>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", profileModalHtml);

  // 👤 SET USERNAME
  document.getElementById("topbar-username").innerText = user.username;

  // 👤 PROFILE MODAL LOGIC
  const profileModal = document.getElementById("profile-modal");
  const usernameBtn = document.querySelector(".dropdown-user");
  usernameBtn.style.cursor = "pointer";
  
  usernameBtn.title = "Edit Profile";
  
  usernameBtn.addEventListener("click", async () => {
    try {
      const res = await fetch(`https://inventory-python.onrender.com/user/${user.id}`);
      if(res.ok) {
        const data = await res.json();
        
        const staticHtml = `
          <strong>Username:</strong> ${data.username}<br>
          <strong>Email:</strong> ${data.email}<br>
          <strong>Name:</strong> ${data.firstname} ${data.middlename ? data.middlename + ' ' : ''}${data.lastname}<br>
          <strong>Registered:</strong> ${data.date || 'unknown'}<br>
          <strong>Status:</strong> ${data.verified ? '<span style="color:#27ae60;">Verified</span>' : '<span style="color:#e74c3c;">Unverified</span>'}
        `;
        document.getElementById("prof-static-details").innerHTML = staticHtml;

        document.getElementById("prof-address").value = data.address || "";
        document.getElementById("prof-storename").value = data.storename || "";
        document.getElementById("prof-storelocation").value = data.storelocation || "";
        document.getElementById("prof-password").value = "";
        profileModal.classList.add("show");
        
        // Hide dropdown
        document.getElementById("hamburger").classList.remove("active");
        document.getElementById("dropdown-menu").classList.remove("show");
      } else {
        alert("Could not load user profile");
      }
    } catch(e) {
      console.error(e);
      alert("Error loading profile");
    }
  });

  document.getElementById("prof-cancel-btn").addEventListener("click", () => {
    profileModal.classList.remove("show");
  });

  document.getElementById("prof-save-btn").addEventListener("click", async () => {
    const payload = {};
    const addr = document.getElementById("prof-address").value;
    const store = document.getElementById("prof-storename").value;
    const loc = document.getElementById("prof-storelocation").value;
    const pwd = document.getElementById("prof-password").value;
    
    if(addr) payload.address = addr;
    if(store) payload.storename = store;
    if(loc) payload.storelocation = loc;
    if(pwd) payload.password = pwd;

    try {
      const btn = document.getElementById("prof-save-btn");
      btn.innerText = "Saving...";
      btn.disabled = true;
      
      const res = await fetch(`https://inventory-python.onrender.com/user/${user.id}`, {
        method: "PUT",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });
      if(res.ok) {
        alert("Profile updated successfully!");
        profileModal.classList.remove("show");
        user.storename = store;
        localStorage.setItem("user", JSON.stringify(user));
      } else {
        alert("Failed to update profile");
      }
      btn.innerText = "Save";
      btn.disabled = false;
    } catch(e) {
      console.error(e);
      alert("Error updating profile");
      document.getElementById("prof-save-btn").innerText = "Save";
      document.getElementById("prof-save-btn").disabled = false;
    }
  });

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
