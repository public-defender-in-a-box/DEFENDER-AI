export default function MotionsPage({
  params,
}: {
  params: { caseId: string };
}) {
  return (
    <div>
      <h1>Draft Motions</h1>
      <p>Case: {params.caseId}</p>
      <p>Draft motions with attorney editing interface will appear here.</p>
    </div>
  );
}
