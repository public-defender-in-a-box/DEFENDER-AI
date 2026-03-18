export default function Home() {
  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui, sans-serif" }}>
      <h1>DEFENDER AI</h1>
      <p>Public Defender AI Assistant — 19-agent case preparation system.</p>
      <nav style={{ marginTop: "1rem" }}>
        <a href="/login" style={{ marginRight: "1rem" }}>Attorney Login</a>
        <a href="/intake">Client Intake</a>
      </nav>
    </main>
  );
}
