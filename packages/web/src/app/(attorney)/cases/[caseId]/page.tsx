export default function CaseDetailPage({
  params,
}: {
  params: { caseId: string };
}) {
  return (
    <div>
      <h1>Case: {params.caseId}</h1>
      <nav style={{ marginBottom: "1rem" }}>
        <a href={`/cases/${params.caseId}/memo`} style={{ marginRight: "1rem" }}>Case Memo</a>
        <a href={`/cases/${params.caseId}/motions`} style={{ marginRight: "1rem" }}>Motions</a>
        <a href={`/cases/${params.caseId}/timeline`}>Timeline</a>
      </nav>
      <p>Parsed charges and pipeline status will appear here.</p>
    </div>
  );
}
