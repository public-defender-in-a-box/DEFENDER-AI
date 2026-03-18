export default function AttorneyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <nav style={{ width: 220, padding: "1rem", borderRight: "1px solid #e5e7eb" }}>
        <h2 style={{ fontSize: "1rem", marginBottom: "1rem" }}>DEFENDER AI</h2>
        <ul style={{ listStyle: "none", padding: 0 }}>
          <li style={{ marginBottom: "0.5rem" }}><a href="/dashboard">Dashboard</a></li>
          <li style={{ marginBottom: "0.5rem" }}><a href="/cases">Cases</a></li>
          <li style={{ marginBottom: "0.5rem" }}><a href="/upload">Upload</a></li>
        </ul>
      </nav>
      <main style={{ flex: 1, padding: "1.5rem" }}>
        {children}
      </main>
    </div>
  );
}
