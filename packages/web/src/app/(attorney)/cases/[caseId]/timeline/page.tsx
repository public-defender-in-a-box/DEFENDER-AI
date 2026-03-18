export default function TimelinePage({
  params,
}: {
  params: { caseId: string };
}) {
  return (
    <div>
      <h1>Case Timeline</h1>
      <p>Case: {params.caseId}</p>
      <p>Pipeline execution timeline and audit log will appear here.</p>
    </div>
  );
}
