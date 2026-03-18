export default function IntakeLandingPage() {
  return (
    <div>
      <h1>Client Intake</h1>
      <p>Your attorney has requested that you complete an intake interview.</p>
      <p>Enter your session code to begin:</p>
      <form style={{ marginTop: "1rem" }}>
        <input type="text" placeholder="Session code" style={{ marginRight: "0.5rem" }} />
        <button type="submit">Begin Interview</button>
      </form>
    </div>
  );
}
