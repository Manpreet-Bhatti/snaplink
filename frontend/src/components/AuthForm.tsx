import { useState } from "react";
import { login, register, setToken } from "../api";

export default function AuthForm({ onAuth }: { onAuth: (token: string) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const auth = mode === "login" ? await login(email, password) : await register(email, password);
      setToken(auth.token);
      onAuth(auth.token);
    } catch (err) {
      const message = err instanceof Error ? err.message : "unknown error";
      setError(message);
    }
  }

  return (
    <main className="auth">
      <div className="auth-shell">
        <section className="auth-brand">
          <span className="auth-brand-mark">SnapLink</span>
          <h1>Short links, shared fast.</h1>
          <p>Create, track, and manage your links in one place.</p>
        </section>
        <section className="auth-panel">
          <form className="auth-form" onSubmit={handleSubmit}>
            <h2>{mode === "login" ? "Welcome back" : "Create an account"}</h2>
            <p className="auth-subtitle">
              {mode === "login" ? "Log in to continue" : "It takes less than a minute"}
            </p>

            <label className="field">
              <span>Email</span>
              <input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>

            <label className="field">
              <span>Password</span>
              <input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
              />
            </label>

            {error && <p className="error">{error}</p>}

            <button type="submit" className="auth-submit">
              {mode === "login" ? "Log in" : "Register"}
            </button>

            <button
              type="button"
              className="link-btn"
              onClick={() => setMode(mode === "login" ? "register" : "login")}
            >
              {mode === "login" ? "Don't have an account? Register" : "Have an account? Log in"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
