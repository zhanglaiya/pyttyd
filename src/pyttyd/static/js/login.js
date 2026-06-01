document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const errorEl = document.getElementById("login-error");
  errorEl.hidden = true;

  const payload = {
    username: form.username.value.trim(),
    password: form.password.value,
  };

  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || "Login failed");
    }
    window.location.href = "/";
  } catch (error) {
    errorEl.textContent = error.message;
    errorEl.hidden = false;
  }
});
