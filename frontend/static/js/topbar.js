// 🌍 GLOBAL CONFIG
window.CONFIG_API = "https://inventory-python.onrender.com";
// window.CONFIG_API = "http://localhost:8000"; // Uncomment for local dev

document.addEventListener("DOMContentLoaded", () => {

  // 🔐 AUTH CHECK (protect pages)
  const token = localStorage.getItem("token");
  const user = JSON.parse(localStorage.getItem("user") || "{}");

  const isLoginPage = window.location.pathname.endsWith("login.html") || 
                       window.location.pathname.endsWith("register.html") || 
                       window.location.pathname.endsWith("verify.html");

  if (!isLoginPage && (!token || !user.username)) {
    window.location.href = "login.html";
    return;
  }

  // 🔝 CREATE TOPBAR (if not already on login/register)
  if (!isLoginPage) {
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

        <a href="messages.html" id="nav-messages">
          💬 Messages
          <span id="global-unread-badge" style="display:none; background:#fa3e3e; color:white; font-size:10px; padding:2px 6px; border-radius:10px; margin-left:5px; font-weight:bold;">0</span>
        </a>

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

    // --- GLOBAL UNREAD POLLING & PING ---
    const updateUnreadBadge = async () => {
      try {
        // Ping to update last_activity
        fetch(`${window.CONFIG_API}/user/${user.id}/ping`, { method: "POST" });

        // Get contacts to sum unread
        const res = await fetch(`${window.CONFIG_API}/messages/contacts/${user.id}`);
        if (res.ok) {
          const contacts = await res.json();
          const totalUnread = contacts.reduce((sum, c) => sum + (c.unread_count || 0), 0);
          const badge = document.getElementById("global-unread-badge");
          if (badge) {
            if (totalUnread > 0) {
              badge.innerText = totalUnread;
              badge.style.display = "inline-block";
            } else {
              badge.style.display = "none";
            }
          }
        }
      } catch (e) {
        console.error("Global poll error:", e);
      }
    };

    updateUnreadBadge();
    setInterval(updateUnreadBadge, 10000); // Every 10s
  }

  // --- USER PROFILE MODAL INJECTION ---
  const profileModalHtml = `
    <div class="profile-modal" id="profile-modal">
      <div class="profile-modal-box" style="width: 400px; max-height: 90vh; overflow-y: auto;">
        <h3>User Profile</h3>
        <div id="prof-static-details" style="background:#f5f6fa; padding:10px; border-radius:6px; margin-bottom:15px; font-size:14px; line-height:1.6;">
          Loading details...
        </div>
        <h4 style="margin-bottom: 10px; margin-top: 0; color: #1f3a5f;">Edit Information</h4>
        <label>Address</label><input type="text" id="prof-address" />
        <label>Store Name</label><input type="text" id="prof-storename" />
        <label>Store Location</label><input type="text" id="prof-storelocation" />
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

  const profileModal = document.getElementById("profile-modal");
  const usernameBtn = document.querySelector(".dropdown-user");
  if (usernameBtn) {
    usernameBtn.style.cursor = "pointer";
    usernameBtn.title = "Edit Profile";
    usernameBtn.addEventListener("click", async () => {
      try {
        const res = await fetch(`${window.CONFIG_API}/user/${user.id}`);
        if (res.ok) {
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
          if (hamburger) hamburger.classList.remove("active");
          if (dropdown) dropdown.classList.remove("show");
        }
      } catch (e) {
        console.error(e);
      }
    });
  }

  const cancelBtn = document.getElementById("prof-cancel-btn");
  if (cancelBtn) {
    cancelBtn.addEventListener("click", () => {
      profileModal.classList.remove("show");
    });
  }

  const saveBtn = document.getElementById("prof-save-btn");
  if (saveBtn) {
    saveBtn.addEventListener("click", async () => {
      const payload = {};
      const addr = document.getElementById("prof-address").value;
      const store = document.getElementById("prof-storename").value;
      const loc = document.getElementById("prof-storelocation").value;
      const pwd = document.getElementById("prof-password").value;
      
      if (addr) payload.address = addr;
      if (store) payload.storename = store;
      if (loc) payload.storelocation = loc;
      if (pwd) payload.password = pwd;

      try {
        saveBtn.innerText = "Saving...";
        saveBtn.disabled = true;
        const res = await fetch(`${window.CONFIG_API}/user/${user.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          alert("Profile updated successfully!");
          profileModal.classList.remove("show");
          user.storename = store;
          localStorage.setItem("user", JSON.stringify(user));
        } else {
          alert("Failed to update profile");
        }
        saveBtn.innerText = "Save";
        saveBtn.disabled = false;
      } catch (e) {
        console.error(e);
        saveBtn.innerText = "Save";
        saveBtn.disabled = false;
      }
    });
  }
});
