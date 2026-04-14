"use client";

import { useEffect, useRef, useState } from "react";
import { Mic, MicOff } from "lucide-react";
import type { IntakeMessage } from "@/types/agents";

interface ChatInterfaceProps {
  messages: IntakeMessage[];
  onSend: (message: string) => void;
  disabled?: boolean;
  voiceMode?: boolean;
  isListening?: boolean;
  isSpeaking?: boolean;
  onMicStart?: () => void;
  onMicStop?: () => void;
  transcript?: string;
}

export function ChatInterface({
  messages,
  onSend,
  disabled,
  voiceMode,
  isListening,
  isSpeaking,
  onMicStart,
  onMicStop,
  transcript,
}: ChatInterfaceProps) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Show live transcript in input while listening
  const displayValue = isListening && transcript ? transcript : input;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setInput("");
  };

  const handleMicClick = () => {
    if (isListening) {
      onMicStop?.();
    } else {
      onMicStart?.();
    }
  };

  const micDisabled = disabled || isSpeaking;

  return (
    <div>
      <div style={{
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        height: 400,
        overflowY: "auto",
        padding: "1rem",
        marginBottom: "0.75rem",
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
              whiteSpace: "pre-wrap",
              textAlign: "left",
            }}>
              {msg.content}
            </div>
            {msg.timestamp && (
              <div style={{ fontSize: "0.7rem", color: "#9ca3af", marginTop: "0.15rem" }}>
                {new Date(msg.timestamp).toLocaleTimeString()}
              </div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <form onSubmit={handleSubmit} style={{ display: "flex", gap: "0.5rem" }}>
        <input
          type="text"
          value={displayValue}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            disabled
              ? "Interview complete"
              : isListening
                ? "Listening..."
                : "Type your response..."
          }
          disabled={disabled || isListening}
          style={{
            flex: 1,
            padding: "0.5rem 0.75rem",
            borderRadius: 6,
            border: `1px solid ${isListening ? "#22c55e" : "#d1d5db"}`,
            fontSize: "0.9rem",
            opacity: disabled ? 0.5 : 1,
          }}
        />
        {voiceMode && (
          <button
            type="button"
            onClick={handleMicClick}
            disabled={micDisabled}
            title={
              isSpeaking
                ? "Wait for AI to finish speaking"
                : isListening
                  ? "Stop listening"
                  : "Start listening"
            }
            style={{
              padding: "0.5rem 0.75rem",
              borderRadius: 6,
              border: "none",
              background: micDisabled
                ? "#9ca3af"
                : isListening
                  ? "#ef4444"
                  : "#22c55e",
              color: "#fff",
              cursor: micDisabled ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {isListening ? <MicOff size={18} /> : <Mic size={18} />}
          </button>
        )}
        <button
          type="submit"
          disabled={disabled || !input.trim() || isListening}
          style={{
            padding: "0.5rem 1rem",
            borderRadius: 6,
            border: "none",
            background: disabled || !input.trim() || isListening ? "#9ca3af" : "#3b82f6",
            color: "#fff",
            cursor: disabled || !input.trim() || isListening ? "not-allowed" : "pointer",
            fontSize: "0.9rem",
          }}
        >
          Send
        </button>
      </form>
    </div>
  );
}
