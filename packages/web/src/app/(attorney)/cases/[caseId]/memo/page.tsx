export default function CaseMemoPage({
  params,
}: {
  params: { caseId: string };
}) {
  return (
    <div>
      <h1>Case Preparation Memo</h1>
      <p>Case: {params.caseId}</p>
      <p>Attorney review interface with annotation, edit tracking, and comprehension checks will appear here.</p>
    </div>
  );
}
