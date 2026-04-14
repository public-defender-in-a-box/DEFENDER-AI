interface IntakeProgressProps {
  completionPercentage: number;
  questionsAnswered: number;
  totalQuestions: number;
  phaseName?: string;
}

export function IntakeProgress({
  completionPercentage,
  questionsAnswered,
  totalQuestions,
  phaseName,
}: IntakeProgressProps) {
  return (
    <div style={{ marginBottom: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
        <span>
          {phaseName ? <strong>{phaseName}</strong> : null}
          {phaseName ? " — " : ""}
          {questionsAnswered} of {totalQuestions} topics covered
        </span>
        <span>{completionPercentage}%</span>
      </div>
      <div style={{
        height: 6,
        background: "#e5e7eb",
        borderRadius: 3,
        marginTop: "0.25rem",
      }}>
        <div style={{
          height: "100%",
          width: `${completionPercentage}%`,
          background: "#3b82f6",
          borderRadius: 3,
          transition: "width 0.3s ease",
        }} />
      </div>
    </div>
  );
}
