document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const errorEl = document.getElementById("login-error");
  errorEl.hidden = true;

  const payload = {
    username: form.username.value.trim(),
    password: form.password.value,
  };

  function formatErrorDetail(detail) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || String(item)).join("; ");
    }
    return "Login failed";
  }

  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(formatErrorDetail(data.detail));
    }
    window.location.href = "/";
  } catch (error) {
    errorEl.textContent = error.message;
    errorEl.hidden = false;
  }
});
