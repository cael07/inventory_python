document.addEventListener("DOMContentLoaded", () => {
  const topbar = document.createElement("div");
  topbar.className = "topbar";
  topbar.innerHTML = `
    <a href="index.html" class="topbar-logo">
      <img src="/static/img/cael.ico" alt="Logo">
    </a>
  `;
  document.body.prepend(topbar);
});
