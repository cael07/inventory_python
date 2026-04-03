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

        <a href="#" id="nav-suki">
          👨‍👩‍👧‍👦 SUKI
          <span id="suki-unread-badge" style="display:none; background:#fa3e3e; color:white; font-size:10px; padding:2px 6px; border-radius:10px; margin-left:5px; font-weight:bold;">0</span>
        </a>
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

        // 1. Get messages to sum unread
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

        // 2. Get pending Suki requests
        const sukiRes = await fetch(`${window.CONFIG_API}/suki/pending/${user.id}`);
        if (sukiRes.ok) {
          const requests = await sukiRes.json();
          const sukiBadge = document.getElementById("suki-unread-badge");
          if (sukiBadge) {
            if (requests.length > 0) {
              sukiBadge.innerText = requests.length;
              sukiBadge.style.display = "inline-block";
            } else {
              sukiBadge.style.display = "none";
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

  // --- SUKI MODAL INJECTION ---
  const sukiModalHtml = `
    <div class="profile-modal" id="suki-modal">
      <div class="profile-modal-box" style="width: 95%; max-width: 420px; max-height: 85vh; overflow-y: auto; margin: 10px;">
        <h3 style="display:flex; align-items:center; justify-content:space-between;">
          Suki List
          <button id="suki-close-btn" style="background:none; border:none; font-size:20px; cursor:pointer; color:#888;">&times;</button>
        </h3>
        
        <div style="margin-bottom:15px;">
           <label style="margin-bottom:8px; display:block;">Add New Suki</label>
           <div style="display:flex; gap:8px;">
              <input type="text" id="suki-search-input" placeholder="Search username or store..." style="margin-bottom:0; flex:1;" />
           </div>
           <div id="suki-search-results" style="margin-top:8px; max-height:150px; overflow-y:auto; border:1px solid #eee; border-radius:4px; display:none;">
              <!-- Search results here -->
           </div>
        </div>

        <div id="suki-pending-section" style="display:none; background:#fffcf0; padding:10px; border-radius:6px; border:1px solid #ffeeba; margin-bottom:15px;">
           <h4 style="margin:0 0 10px 0; font-size:14px; color:#856404;">📥 Requests Received</h4>
           <div id="suki-pending-list"></div>
        </div>

        <hr style="border:0; border-top:1px solid #eee; margin:20px 0;">
        
        <h4 style="margin-bottom:10px; color:#1f3a5f;">Your Suki List</h4>
        <div id="suki-list-container" style="min-height:100px;">
           <p style="color:#888; font-size:14px; text-align:center; padding:20px 0;">Loading your suki list...</p>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", sukiModalHtml);

  const sukiModal = document.getElementById("suki-modal");
  const sukiLink = document.getElementById("nav-suki");
  const sukiListContainer = document.getElementById("suki-list-container");
  const sukiPendingSection = document.getElementById("suki-pending-section");
  const sukiPendingList = document.getElementById("suki-pending-list");
  const sukiSearchInput = document.getElementById("suki-search-input");
  const sukiSearchResults = document.getElementById("suki-search-results");

  // Load Suki List & Requests
  const loadSukiData = async () => {
    try {
      // 1. Load Requests
      const reqRes = await fetch(`${window.CONFIG_API}/suki/pending/${user.id}`);
      if (reqRes.ok) {
        const reqs = await reqRes.json();
        if (reqs.length > 0) {
          sukiPendingSection.style.display = "block";
          sukiPendingList.innerHTML = reqs.map(r => `
            <div style="display:flex; align-items:center; justify-content:space-between; padding:8px 0; border-bottom:1px solid #eee;">
               <div style="font-size:13px;">
                  <strong>${r.storename || r.username}</strong> wishes to be your suki
               </div>
               <div style="display:flex; gap:5px;">
                  <button onclick="window.handleSukiRequest(${r.id}, 'accept')" style="background:#27ae60; color:white; border:none; padding:3px 8px; border-radius:4px; font-size:11px; cursor:pointer;">Accept</button>
                  <button onclick="window.handleSukiRequest(${r.id}, 'decline')" style="background:#e74c3c; color:white; border:none; padding:3px 8px; border-radius:4px; font-size:11px; cursor:pointer;">&times;</button>
               </div>
            </div>
          `).join("");
        } else {
          sukiPendingSection.style.display = "none";
        }
      }

      // 2. Load Friends
      const res = await fetch(`${window.CONFIG_API}/suki/${user.id}`);
      if (res.ok) {
        const data = await res.json();
        if (data.length === 0) {
          sukiListContainer.innerHTML = `<p style="color:#888; font-size:14px; text-align:center; padding:20px 0;">No mutual suki yet. Add stores or users to start chatting!</p>`;
          return;
        }
        sukiListContainer.innerHTML = data.map(s => `
          <div style="display:flex; align-items:center; justify-content:space-between; padding:10px; border-bottom:1px solid #f9f9f9;">
            <div style="line-height:1.4;">
               <div style="font-weight:bold; font-size:15px;">${s.storename || s.username}</div>
               <div style="font-size:12px; color:#65676b;">${s.firstname} ${s.lastname} · ${s.storelocation || 'No location'}</div>
            </div>
            <button onclick="window.removeSuki(${s.id})" style="background:#f2f3f5; color:#444; border:none; padding:5px 10px; border-radius:4px; font-size:12px; cursor:pointer;">Remove</button>
          </div>
        `).join("");
      }
    } catch (e) { console.error(e); }
  };

  window.handleSukiRequest = async (requesterId, action) => {
    try {
      let res;
      if (action === 'accept') {
        res = await fetch(`${window.CONFIG_API}/suki/accept/${requesterId}/${user.id}`, { method: "PUT" });
      } else {
        res = await fetch(`${window.CONFIG_API}/suki/${requesterId}/${user.id}`, { method: "DELETE" });
      }
      if (res.ok) loadSukiData();
    } catch (e) { console.error(e); }
  };

  window.removeSuki = async (sukiId) => {
    if (!confirm("Remove this suki? Connection will be lost for both of you.")) return;
    try {
      const res = await fetch(`${window.CONFIG_API}/suki/${user.id}/${sukiId}`, { method: "DELETE" });
      if (res.ok) loadSukiData();
    } catch (e) { console.error(e); }
  };

  window.addSuki = async (sukiId) => {
    try {
      const res = await fetch(`${window.CONFIG_API}/suki?owner_id=${user.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ suki_id: sukiId })
      });
      if (res.ok) {
        const d = await res.json();
        alert(d.message);
        sukiSearchInput.value = "";
        sukiSearchResults.style.display = "none";
        loadSukiData();
      }
    } catch (e) { console.error(e); }
  };

  // Search Logic
  let searchTimeout;
  sukiSearchInput.addEventListener("input", (e) => {
    clearTimeout(searchTimeout);
    const q = e.target.value.trim();
    if (q.length < 2) {
      sukiSearchResults.style.display = "none";
      return;
    }
    searchTimeout = setTimeout(async () => {
      try {
        const res = await fetch(`${window.CONFIG_API}/users`); 
        if (res.ok) {
          const allUsers = (await res.json()).items;
          const filtered = allUsers.filter(u => u.id !== user.id && (u.username.toLowerCase().includes(q.toLowerCase()) || (u.storename && u.storename.toLowerCase().includes(q.toLowerCase())))).slice(0, 5);

          if (filtered.length > 0) {
            sukiSearchResults.innerHTML = filtered.map(u => `
              <div style="display:flex; align-items:center; justify-content:space-between; padding:8px 12px; border-bottom:1px solid #f0f0f0;">
                <div style="font-size:13px;">
                   <strong>${u.storename || u.username}</strong><br>
                   <small style="color:#888;">${u.firstname} ${u.lastname}</small>
                </div>
                <button onclick="window.addSuki(${u.id})" style="background:var(--messenger-blue, #0084ff); color:white; border:none; padding:4px 8px; border-radius:4px; font-size:12px; cursor:pointer;">Add</button>
              </div>
            `).join("");
            sukiSearchResults.style.display = "block";
          } else {
            sukiSearchResults.style.display = "none";
          }
        }
      } catch (e) { console.error(e); }
    }, 400);
  });

  if (sukiLink) {
    sukiLink.addEventListener("click", (e) => {
      e.preventDefault();
      loadSukiData();
      sukiModal.classList.add("show");
      if (hamburger) hamburger.classList.remove("active");
      if (dropdown) dropdown.classList.remove("show");
    });
  }

  const sukiCloseBtn = document.getElementById("suki-close-btn");
  if (sukiCloseBtn) {
    sukiCloseBtn.addEventListener("click", () => {
      sukiModal.classList.remove("show");
    });
  }

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
