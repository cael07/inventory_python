document.addEventListener("DOMContentLoaded", () => {
  const bar = document.createElement("div");
  bar.innerHTML = `
    <div class="topbar">
      <a href="index.html">
        <img src="/static/img/cael.ico" alt="Logo">
      </a>
    </div>
  `;
  document.body.prepend(bar);
});
