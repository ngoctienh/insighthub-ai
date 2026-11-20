(function () {
  window.getCsrfToken = function () {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  };

  window.showToast = function (message, type) {
    const container = document.getElementById("toast-container");
    if (!container || !message) return;
    const tone =
      type === "error"
        ? "bg-rose-600 text-white border-rose-700"
        : type === "info" || type === "warning"
        ? "bg-slate-900 text-white border-slate-800"
        : "bg-emerald-600 text-white border-emerald-700";

    const toast = document.createElement("div");
    toast.className =
      "pointer-events-auto px-4 py-3 rounded-xl border shadow-lg text-sm font-medium flex items-center gap-2 transition-all duration-200 " +
      tone;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(function () {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(8px)";
      setTimeout(function () {
        toast.remove();
      }, 220);
    }, 3600);
  };

  window.copyText = function (text, successMsg) {
    if (!navigator.clipboard) {
      window.showToast("Trình duyệt không hỗ trợ clipboard.", "error");
      return;
    }
    navigator.clipboard
      .writeText(text || "")
      .then(function () {
        window.showToast(successMsg || "Đã sao chép!", "success");
      })
      .catch(function () {
        window.showToast("Không thể sao chép vào clipboard.", "error");
      });
  };

  window.toggleModal = function (id, open) {
    const el = document.getElementById(id);
    if (!el) return;
    if (open) {
      el.classList.remove("hidden");
      el.classList.add("flex");
    } else {
      el.classList.add("hidden");
      el.classList.remove("flex");
    }
  };

  document.addEventListener("DOMContentLoaded", function () {
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons();
    }
    const mobileBtn = document.getElementById("mobile-menu-open");
    const mobileClose = document.getElementById("mobile-menu-close");
    const mobileBackdrop = document.getElementById("mobile-sidebar-backdrop");
    const mobileDrawer = document.getElementById("mobile-sidebar-drawer");

    function setDrawer(open) {
      if (!mobileDrawer) return;
      if (open) {
        mobileDrawer.classList.remove("hidden");
        mobileDrawer.classList.add("flex");
      } else {
        mobileDrawer.classList.add("hidden");
        mobileDrawer.classList.remove("flex");
      }
    }
    if (mobileBtn) mobileBtn.addEventListener("click", function () { setDrawer(true); });
    if (mobileClose) mobileClose.addEventListener("click", function () { setDrawer(false); });
    if (mobileBackdrop) mobileBackdrop.addEventListener("click", function () { setDrawer(false); });
  });
})();
