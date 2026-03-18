"use client";

import type { IntakeMessage } from "@/types/agents";

interface ChatInterfaceProps {
  messages: IntakeMessage[];
  onSend: (message: string) => void;
}

export function ChatInterface({ messages, onSend }: ChatInterfaceProps) {
  return (
    <div>
      <div style={{
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        height: 400,
        overflowY: "auto",
        padding: "1rem",
        marginBottom: "1rem",
      }}>
        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              marginBottom: "0.75rem",
              textAlign: msg.sender === "CLIENT" ? "right" : "left",
            }}
          >
            <div style={{
              display: "inline-block",
              padding: "0.5rem 0.75rem",
              borderRadius: 8,
              background: msg.sender === "CLIENT" ? "#3b82f6" : "#f3f4f6",
              color: msg.sender === "CLIENT" ? "#fff" : "#111",
              maxWidth: "80%",
            }}>
              {msg.content}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
