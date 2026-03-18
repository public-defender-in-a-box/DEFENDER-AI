"use client";

interface ComprehensionCheckProps {
  question: string;
  onAnswer: (answer: string) => void;
}

export function ComprehensionCheck({ question, onAnswer }: ComprehensionCheckProps) {
  return (
    <div style={{
      background: "#fef3c7",
      border: "1px solid #f59e0b",
      borderRadius: 8,
      padding: "1rem",
      marginTop: "0.5rem",
    }}>
      <p style={{ fontWeight: 600, fontSize: "0.85rem" }}>Comprehension Check</p>
      <p style={{ fontSize: "0.85rem" }}>{question}</p>
      <input
        type="text"
        placeholder="Your answer..."
        style={{
          width: "100%",
          padding: "0.5rem",
          border: "1px solid #d1d5db",
          borderRadius: 6,
          marginTop: "0.5rem",
        }}
      />
      <button style={{ marginTop: "0.5rem" }}>Verify</button>
    </div>
  );
}
