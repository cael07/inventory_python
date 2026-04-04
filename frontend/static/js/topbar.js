// 🌍 GLOBAL CONFIG
window.CONFIG_API = "https://inventory-python.onrender.com";

document.addEventListener("DOMContentLoaded", () => {
  // 🎨 INJECT MODAL CSS
  const style = document.createElement("style");
  style.textContent = `
    .profile-modal {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.7);
      backdrop-filter: blur(4px);
      z-index: 10000;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .profile-modal.show {
      display: flex;
    }
    .profile-modal-box {
      background: white;
      padding: 24px;
      border-radius: 12px;
      position: relative;
      box-shadow: 0 10px 25px rgba(0,0,0,0.2);
    }
    .profile-modal-box label { display: block; margin-top: 10px; font-weight: 600; font-size: 13px; color: #666; }
    .profile-modal-box input { width: 100%; padding: 10px; margin-top: 4px; border: 1px solid #ddd; border-radius: 6px; }
    
    /* Topbar Specifics */
    .top-bar { display: flex; justify-content: space-between; align-items: center; background: #1f3a5f; padding: 10px 20px; color: white; position: sticky; top: 0; z-index: 1000; box-shadow: 0 2px 10px rgba(0,0,0,0.2); }
    .dropdown-menu { 
      display: flex; 
      position: fixed; 
      top: 52px; 
      right: -260px; /* Hidden by default */
      background: #2c3e50; 
      width: 250px; 
      height: calc(100vh - 52px); 
      flex-direction: column; 
      padding: 20px; 
      z-index: 999; 
      box-shadow: -5px 0 15px rgba(0,0,0,0.1); 
      transition: right 0.4s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease;
      opacity: 0;
      pointer-events: none;
    }
    .dropdown-menu.show { 
      right: 0; 
      opacity: 1;
      pointer-events: auto;
    }
    .dropdown-menu a { color: white; text-decoration: none; padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.1); font-size: 14px; transition: background 0.2s; }
    .dropdown-menu a:hover { background: rgba(255,255,255,0.05); padding-left: 5px; }
    
    .dropdown-divider { border-top: 1px solid rgba(255,255,255,0.1); margin: 15px 0; }
    
    .hamburger { cursor: pointer; display: flex; flex-direction: column; gap: 5px; width: 30px; height: 18px; justify-content: center; position: relative; }
    .hamburger span { display: block; width: 24px; height: 2px; background: white; border-radius: 2px; transition: all 0.3s ease-in-out; }
    
    /* ❌ X Animation */
    .hamburger.active span:nth-child(1) { transform: translateY(7px) rotate(45deg); }
    .hamburger.active span:nth-child(2) { opacity: 0; transform: translateX(-10px); }
    .hamburger.active span:nth-child(3) { transform: translateY(-7px) rotate(-45deg); }
  `;
  document.head.appendChild(style);

  // 🔐 AUTH CHECK
  const token = localStorage.getItem("token");
  const user = JSON.parse(localStorage.getItem("user") || "{}");

  const isLoginPage = window.location.pathname.endsWith("login.html") || 
                       window.location.pathname.endsWith("register.html") || 
                       window.location.pathname.endsWith("verify.html");

  if (!isLoginPage && (!token || !user.username)) {
    window.location.href = "login.html";
    return;
  }

  // 🛡 ROLE-BASED ACCESS CONTROL (ROUTE GUARDS)
  const userRank = user.rank || "owner";
  const path = window.location.pathname;

  if (userRank === "cashier" && (path.endsWith("product.html") || path.endsWith("products.html") || path.endsWith("monitoring.html"))) {
    alert("Access Denied: Cashiers cannot access Inventory/Products.");
    window.location.href = "dashboard.html";
    return;
  }

  if (userRank === "bagger" && (path.endsWith("pos.html") || path.endsWith("report.html"))) {
    alert("Access Denied: Baggers cannot access POS Terminal.");
    window.location.href = "dashboard.html";
    return;
  }

  if (userRank !== "owner" && path.endsWith("employee.html")) {
    alert("Access Denied: Only store owners can manage employees.");
    window.location.href = "dashboard.html";
    return;
  }

  // 🔝 CREATE TOPBAR
  if (!isLoginPage) {
    const topbarHtml = `
      <div class="top-bar">
        <a href="dashboard.html" class="logo" style="text-decoration:none; display:flex; align-items:center;">
          <img src="/static/img/cael.ico" alt="Logo" style="height:32px; width:32px; border-radius:50%; object-fit:cover; border:1px solid rgba(255,255,255,0.2);">
        </a>
        <div class="hamburger" id="hamburger">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>

      <div class="dropdown-menu" id="dropdown-menu">
        <a href="dashboard.html">📊 Dashboard</a>
        
        <div class="dropdown-divider"></div>

        ${ userRank === "owner" || userRank === "cashier" ? `
        <a href="pos.html">🛒 POS Terminal</a>
        <a href="report.html">📈 POS Report</a>
        <div class="dropdown-divider"></div>
        ` : '' }

        ${ userRank === "owner" || userRank === "bagger" ? `
        <a href="product.html">➕ Add Product</a>
        <a href="products.html">📦 Inventory</a>
        <a href="monitoring.html">📑 Product Report</a>
        <div class="dropdown-divider"></div>
        ` : '' }

        <a href="messages.html" id="nav-messages">
          💬 Messages
          <span id="global-unread-badge" style="display:none; background:#fa3e3e; color:white; font-size:10px; padding:2px 6px; border-radius:10px; margin-left:5px; font-weight:bold;">0</span>
        </a>

        <a href="suki_list.html" id="nav-suki">
          🤝 Suki List
          <span id="suki-unread-badge" style="display:none; background:#f39c12; color:white; font-size:10px; padding:2px 6px; border-radius:10px; margin-left:5px; font-weight:bold;">0</span>
        </a>

        ${ userRank === "owner" ? `
        <a href="employee.html">
          💼 Employee Mgmt
          <span id="emp-unread-badge" style="display:none; background:#f39c12; color:white; font-size:10px; padding:2px 6px; border-radius:10px; margin-left:5px; font-weight:bold;">0</span>
        </a>
        ` : '' }

        <div class="dropdown-divider"></div>
        
        <div class="dropdown-user" id="user-profile-trigger" style="cursor:pointer; display:flex; align-items:center; padding:10px 0;">
           <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:10px; opacity:0.8;"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
           <div style="display:flex; flex-direction:column; align-items:flex-start;">
              <span id="topbar-username" style="font-weight:600; color:#fff; font-size:14px;">${user.username} <span style="font-size:10px; background:#4b6584; padding:2px 4px; border-radius:4px; margin-left:4px; text-transform:uppercase;">${userRank}</span></span>
              <span style="font-size:11px; opacity:0.7; color:#fff;">${user.storename || 'No Store Set'}</span>
           </div>
        </div>

        <div class="dropdown-divider"></div>

        <a href="#" id="logout-btn" style="color: #ff9999; display:flex; align-items:center;">
           <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:8px;"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
           Logout
        </a>
      </div>
    `;

    document.body.insertAdjacentHTML("afterbegin", topbarHtml);

    // 🍔 TOGGLE DROPDOWN
    const hamburger = document.getElementById("hamburger");
    const dropdown = document.getElementById("dropdown-menu");

    hamburger.addEventListener("click", () => {
      hamburger.classList.toggle("active");
      dropdown.classList.toggle("show");
    });

    // Close when clicking outside
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

    // --- GLOBAL UNREAD POLLING ---
    const updateUnreadBadge = async () => {
      try {
        fetch(`${window.CONFIG_API}/user/${user.id}/ping`, { method: "POST" });
        const res = await fetch(`${window.CONFIG_API}/messages/contacts/${user.id}`);
        if (res.ok) {
          const contacts = await res.json();
          const totalUnread = contacts.reduce((sum, c) => sum + (c.unread_count || 0), 0);
          const badge = document.getElementById("global-unread-badge");
          if (badge) {
            badge.innerText = totalUnread;
            badge.style.display = totalUnread > 0 ? "inline-block" : "none";
          }
        }
        const sukiRes = await fetch(`${window.CONFIG_API}/suki/pending/${user.id}`);
        if (sukiRes.ok) {
          const reqs = await sukiRes.json();
          const sBadge = document.getElementById("suki-unread-badge");
          if (sBadge) {
            sBadge.innerText = reqs.length;
            sBadge.style.display = reqs.length > 0 ? "inline-block" : "none";
          }
        }
        if (userRank === "owner") {
            const empRes = await fetch(`${window.CONFIG_API}/employee/pending/${user.id}`);
            if (empRes.ok) {
              const reqs = await empRes.json();
              const eBadge = document.getElementById("emp-unread-badge");
              if (eBadge) {
                eBadge.innerText = reqs.length;
                eBadge.style.display = reqs.length > 0 ? "inline-block" : "none";
              }
            }
        }
      } catch (e) { console.error(e); }
    };
    updateUnreadBadge();
    setInterval(updateUnreadBadge, 10000);

    // --- PROFILE MODAL ---
    const profileModalHtml = `
      <div class="profile-modal" id="profile-modal">
        <div class="profile-modal-box" style="width: 400px; max-height: 90vh; overflow-y: auto;">
          <h3>User Profile</h3>
          <div id="prof-static-details" style="background:#f5f6fa; padding:10px; border-radius:6px; margin-bottom:15px; font-size:14px; line-height:1.6;">
            Loading...
          </div>
          <h4 style="margin-bottom: 10px; color: #1f3a5f;">Edit Information</h4>
          <label>Address</label><input type="text" id="prof-address" />
          <label>Store Name</label><input type="text" id="prof-storename" />
          <label>Store Location</label><input type="text" id="prof-storelocation" />
          <label>New Password (Optional)</label>
          <input type="password" id="prof-password" placeholder="Leave blank to keep current" />
          <div style="display:flex; gap:10px; margin-top:20px;">
            <button id="prof-save-btn" style="flex:1; background:#1f3a5f; color:white; border:none; padding:10px; border-radius:6px; cursor:pointer;">Save</button>
            <button id="prof-cancel-btn" style="flex:1; background:#eee; border:none; padding:10px; border-radius:6px; cursor:pointer;">Close</button>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML("beforeend", profileModalHtml);

    document.getElementById("user-profile-trigger").addEventListener("click", async () => {
      try {
        const res = await fetch(`${window.CONFIG_API}/user/${user.id}`);
        if (res.ok) {
          const data = await res.json();
          document.getElementById("prof-static-details").innerHTML = `
            <strong>Username:</strong> ${data.username}<br>
            <strong>Email:</strong> ${data.email}<br>
            <strong>Name:</strong> ${data.firstname} ${data.lastname}
          `;
          document.getElementById("prof-address").value = data.address || "";
          document.getElementById("prof-storename").value = data.storename || "";
          document.getElementById("prof-storelocation").value = data.storelocation || "";
          document.getElementById("profile-modal").classList.add("show");
          dropdown.classList.remove("show");
        }
      } catch (e) { console.error(e); }
    });

    document.getElementById("prof-cancel-btn").addEventListener("click", () => {
      document.getElementById("profile-modal").classList.remove("show");
    });

    document.getElementById("prof-save-btn").addEventListener("click", async () => {
      const btn = document.getElementById("prof-save-btn");
      const payload = {
        address: document.getElementById("prof-address").value,
        storename: document.getElementById("prof-storename").value,
        storelocation: document.getElementById("prof-storelocation").value
      };
      const pwd = document.getElementById("prof-password").value;
      if (pwd) payload.password = pwd;

      try {
        btn.innerText = "Saving...";
        const res = await fetch(`${window.CONFIG_API}/user/${user.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          alert("Profile updated!");
          location.reload();
        }
      } catch (e) { console.error(e); }
      btn.innerText = "Save";
    });
  }
});
