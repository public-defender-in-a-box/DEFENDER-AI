"use client";

interface AnnotationInputProps {
  sectionId: string;
  onSubmit: (annotation: string) => void;
}

export function AnnotationInput({ sectionId, onSubmit }: AnnotationInputProps) {
  return (
    <div style={{ marginTop: "0.5rem" }}>
      <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>
        Attorney Annotation (required for high-stakes review)
      </label>
      <textarea
        placeholder="Explain why you agree or disagree with this assessment..."
        style={{
          width: "100%",
          minHeight: 100,
          padding: "0.5rem",
          border: "1px solid #e5e7eb",
          borderRadius: 6,
          marginTop: "0.25rem",
        }}
      />
      <button style={{ marginTop: "0.5rem" }}>Submit Annotation</button>
    </div>
  );
}
