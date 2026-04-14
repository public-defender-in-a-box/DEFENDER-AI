"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function IntakeLandingPage() {
  const [caseId, setCaseId] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = caseId.trim();
    if (!trimmed) return;

    setError("");
    setLoading(true);

    try {
      const res = await fetch(
        `http://localhost:8000/api/v1/intake/${encodeURIComponent(trimmed)}/validate`
      );
      const data = await res.json();

      if (!data.valid) {
        setError(data.error || "This session code is not valid.");
        return;
      }

      router.push(`/intake/${encodeURIComponent(trimmed)}`);
    } catch {
      setError("Could not connect to the server. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1 style={{ fontSize: "1.25rem", marginBottom: "0.5rem" }}>Client Intake Interview</h1>
      <p>Your attorney has requested that you complete an intake interview.</p>
      <p style={{ color: "#6b7280", fontSize: "0.85rem" }}>
        Enter the session code provided by your attorney to begin.
      </p>
      <form onSubmit={handleSubmit} style={{ marginTop: "1rem", display: "flex", gap: "0.5rem" }}>
        <input
          type="text"
          value={caseId}
          onChange={(e) => setCaseId(e.target.value)}
          placeholder="Session code (e.g. CASE-abc123)"
          disabled={loading}
          style={{
            flex: 1,
            padding: "0.5rem 0.75rem",
            borderRadius: 6,
            border: "1px solid #d1d5db",
            fontSize: "0.9rem",
          }}
        />
        <button
          type="submit"
          disabled={loading || !caseId.trim()}
          style={{
            padding: "0.5rem 1rem",
            borderRadius: 6,
            border: "none",
            background: loading || !caseId.trim() ? "#9ca3af" : "#3b82f6",
            color: "#fff",
            cursor: loading || !caseId.trim() ? "not-allowed" : "pointer",
            fontSize: "0.9rem",
          }}
        >
          {loading ? "Checking..." : "Begin Interview"}
        </button>
      </form>
      {error && (
        <p style={{ color: "#dc2626", marginTop: "0.75rem", fontSize: "0.9rem" }}>{error}</p>
      )}
    </div>
  );
}
