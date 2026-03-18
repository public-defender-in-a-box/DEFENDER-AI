"use client";

export default function LoginPage() {
  return (
    <main style={{ padding: "2rem", maxWidth: 400, margin: "0 auto" }}>
      <h1>Attorney Login</h1>
      <form>
        <div style={{ marginBottom: "1rem" }}>
          <label htmlFor="email">Email</label>
          <input id="email" type="email" style={{ display: "block", width: "100%" }} />
        </div>
        <div style={{ marginBottom: "1rem" }}>
          <label htmlFor="password">Password</label>
          <input id="password" type="password" style={{ display: "block", width: "100%" }} />
        </div>
        <button type="submit">Sign In</button>
      </form>
    </main>
  );
}
