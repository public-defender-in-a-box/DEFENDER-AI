export default function ClientLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div style={{ maxWidth: 600, margin: "0 auto", padding: "1rem" }}>
      <header style={{ borderBottom: "1px solid #e5e7eb", paddingBottom: "0.5rem", marginBottom: "1rem" }}>
        <h2 style={{ fontSize: "1rem" }}>DEFENDER AI — Client Portal</h2>
        <p style={{ fontSize: "0.85rem", color: "#6b7280" }}>
          This system helps your attorney prepare your case. It does not provide legal advice.
        </p>
      </header>
      {children}
    </div>
  );
}
