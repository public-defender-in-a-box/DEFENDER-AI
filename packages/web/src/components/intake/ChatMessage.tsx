interface ChatMessageProps {
  content: string;
  sender: "SYSTEM" | "CLIENT";
  timestamp: string;
}

export function ChatMessage({ content, sender, timestamp }: ChatMessageProps) {
  return (
    <div style={{
      marginBottom: "0.75rem",
      textAlign: sender === "CLIENT" ? "right" : "left",
    }}>
      <div style={{
        display: "inline-block",
        padding: "0.5rem 0.75rem",
        borderRadius: 8,
        background: sender === "CLIENT" ? "#3b82f6" : "#f3f4f6",
        color: sender === "CLIENT" ? "#fff" : "#111",
        maxWidth: "80%",
        fontSize: "0.9rem",
      }}>
        {content}
      </div>
      <div style={{ fontSize: "0.7rem", color: "#9ca3af", marginTop: "0.15rem" }}>
        {new Date(timestamp).toLocaleTimeString()}
      </div>
    </div>
  );
}
