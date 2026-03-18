"use client";

interface MotionEditorProps {
  motionId: string;
  title: string;
  draft: string;
}

export function MotionEditor({ motionId, title, draft }: MotionEditorProps) {
  return (
    <div>
      <h3>{title}</h3>
      <p style={{ fontSize: "0.8rem", color: "#ef4444", fontWeight: 600 }}>
        DRAFT — ATTORNEY REVIEW REQUIRED
      </p>
      <textarea
        defaultValue={draft}
        style={{
          width: "100%",
          minHeight: 400,
          padding: "1rem",
          fontFamily: "monospace",
          fontSize: "0.9rem",
          border: "1px solid #e5e7eb",
          borderRadius: 8,
        }}
      />
      <button style={{ marginTop: "0.5rem" }}>
        Mark as Reviewed
      </button>
    </div>
  );
}
