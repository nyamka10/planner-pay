// ---------- Тема ----------
(function () {
  const saved = localStorage.getItem("theme");
  if (saved) document.documentElement.setAttribute("data-theme", saved);
  else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches)
    document.documentElement.setAttribute("data-theme", "dark");
})();

function toggleTheme() {
  const cur = document.documentElement.getAttribute("data-theme");
  const next = cur === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
}

// ---------- Меню пользователя ----------
function toggleUserMenu(e) {
  e.stopPropagation();
  document.getElementById("usermenu").classList.toggle("open");
}
document.addEventListener("click", (e) => {
  const menu = document.getElementById("usermenu");
  if (menu && !menu.contains(e.target)) menu.classList.remove("open");
});

// ---------- Модалки ----------
function openModal(id) { document.getElementById(id).hidden = false; }
function closeModal(id) { document.getElementById(id).hidden = true; }

document.addEventListener("click", (e) => {
  if (e.target.classList.contains("modal")) e.target.hidden = true;
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") document.querySelectorAll(".modal").forEach((m) => (m.hidden = true));
});

// Прибавляет один месяц к дате yyyy-mm-dd (корректно для концов месяцев).
function addOneMonth(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  const target = new Date(y, m, d); // m уже даёт следующий месяц (0-индексация)
  if (target.getDate() !== d) target.setDate(0); // переполнение -> последний день месяца
  const yy = target.getFullYear();
  const mm = String(target.getMonth() + 1).padStart(2, "0");
  const dd = String(target.getDate()).padStart(2, "0");
  return `${yy}-${mm}-${dd}`;
}

function openRenew(id, dueDate, amount, service) {
  document.getElementById("renew-form").action = "/payments/" + id + "/renew";
  document.getElementById("renew-service").textContent = service;
  const next = addOneMonth(dueDate);
  const dateInput = document.getElementById("renew-date");
  const today = new Date().toISOString().slice(0, 10);
  dateInput.value = next < today ? today : next; // подсказка не в прошлом
  document.getElementById("renew-amount").value = amount;
  openModal("renew-modal");
}

function openEdit(id, date, service, amount, description) {
  document.getElementById("edit-form").action = "/payments/" + id + "/edit";
  document.getElementById("edit-date").value = date;
  document.getElementById("edit-service").value = service;
  document.getElementById("edit-amount").value = amount;
  document.getElementById("edit-description").value = description || "";
  openModal("edit-modal");
}

// ---------- Тепловая карта: подсказки ----------
function initHeatmap(currency) {
  const tooltip = document.getElementById("tooltip");
  if (!tooltip) return;
  const cells = document.querySelectorAll(".day-cell.has-items");

  function fmt(n) {
    return Number(n).toLocaleString("ru-RU", { maximumFractionDigits: 0 });
  }

  cells.forEach((cell) => {
    cell.addEventListener("mouseenter", (e) => {
      let items = [];
      try { items = JSON.parse(cell.dataset.items || "[]"); } catch (_) {}
      const date = cell.dataset.date;
      const [y, m, d] = date.split("-");
      let html = `<div class="tt-date">${d}.${m}.${y}</div>`;
      items.forEach((it) => {
        const cls = it.is_paid ? "tt-item paid" : "tt-item";
        const check = it.is_paid ? "✓ " : "";
        html += `<div class="${cls}"><span>${check}${escapeHtml(it.service)}</span><span>${fmt(it.amount)} ${currency}</span></div>`;
      });
      html += `<div class="tt-total"><span>Итого</span> ${cell.dataset.total} ${currency}</div>`;
      tooltip.innerHTML = html;
      tooltip.hidden = false;
      positionTooltip(e);
    });
    cell.addEventListener("mousemove", positionTooltip);
    cell.addEventListener("mouseleave", () => (tooltip.hidden = true));
  });

  function positionTooltip(e) {
    const pad = 14;
    let x = e.clientX + pad;
    let y = e.clientY + pad;
    const rect = tooltip.getBoundingClientRect();
    if (x + rect.width > window.innerWidth) x = e.clientX - rect.width - pad;
    if (y + rect.height > window.innerHeight) y = e.clientY - rect.height - pad;
    tooltip.style.left = x + "px";
    tooltip.style.top = y + "px";
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }
}
