import { useState } from "react";

import { useStore } from "./store";

export const AuthScreen = () => {
  const config = useStore((s) => s.config);
  const login = useStore((s) => s.login);
  const register = useStore((s) => s.register);

  const canRegister = config ? config.allow_registration : true;
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const setField = (field) => (event) => setForm((f) => ({ ...f, [field]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    if (busy) return;
    setError("");
    setBusy(true);
    try {
      if (mode === "register") await register(form.name.trim() || "User", form.email.trim(), form.password);
      else await login(form.email.trim(), form.password);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <div className="nf-auth">
      <form className="nf-auth-card" onSubmit={submit} noValidate>
        <div className="nf-brand is-large">NexFlow</div>
        <p className="nf-muted">Build, run and save visual automation workflows.</p>

        {canRegister && (
          <div className="nf-tabs" role="tablist">
            {["login", "register"].map((value) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={mode === value}
                className={`nf-tab${mode === value ? " is-active" : ""}`}
                onClick={() => {
                  setMode(value);
                  setError("");
                }}
              >
                {value === "login" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>
        )}

        {mode === "register" && (
          <label className="nf-field">
            <span className="nf-label">Name</span>
            <input className="nf-input" value={form.name} onChange={setField("name")} autoComplete="name" maxLength={80} />
          </label>
        )}
        <label className="nf-field">
          <span className="nf-label">Email</span>
          <input className="nf-input" type="email" value={form.email} onChange={setField("email")} autoComplete="email" required />
        </label>
        <label className="nf-field">
          <span className="nf-label">Password</span>
          <input
            className="nf-input"
            type="password"
            value={form.password}
            onChange={setField("password")}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            minLength={mode === "register" ? 8 : undefined}
            required
          />
          {mode === "register" && <span className="nf-hint">At least 8 characters.</span>}
        </label>

        {error && (
          <div className="nf-alert is-error" role="alert">
            {error}
          </div>
        )}

        <button type="submit" className="nf-btn is-primary is-block" disabled={busy || !form.email || !form.password}>
          {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
        </button>

        {config?.demo_account && mode === "login" && (
          <button
            type="button"
            className="nf-btn is-ghost is-block"
            onClick={() => setForm({ name: "", email: "demo@nexflow.app", password: "demo1234" })}
          >
            Fill in demo account
          </button>
        )}
      </form>
    </div>
  );
};
