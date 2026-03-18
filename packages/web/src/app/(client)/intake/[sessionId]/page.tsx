"use client";

export default function IntakeSessionPage({
  params,
}: {
  params: { sessionId: string };
}) {
  return (
    <div>
      <h1>Intake Interview</h1>
      <p style={{ fontSize: "0.85rem", color: "#6b7280" }}>
        Session: {params.sessionId} — This conversation is protected by attorney-client privilege.
      </p>
      <div style={{
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        height: 400,
        padding: "1rem",
        overflowY: "auto",
        marginBottom: "1rem",
      }}>
        {/* Chat messages will render here */}
        <p style={{ color: "#9ca3af" }}>Chat interface loading...</p>
      </div>
      <form style={{ display: "flex", gap: "0.5rem" }}>
        <input type="text" placeholder="Type your response..." style={{ flex: 1 }} />
        <button type="submit">Send</button>
      </form>
    </div>
  );
}
