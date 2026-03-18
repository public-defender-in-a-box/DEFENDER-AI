"use client";

export default function UploadPage() {
  return (
    <div>
      <h1>Upload Charging Document</h1>
      <p>Upload a criminal complaint, indictment, or arrest report to begin case processing.</p>
      <form style={{ marginTop: "1rem" }}>
        <div style={{ marginBottom: "1rem" }}>
          <label htmlFor="docType">Document Type</label>
          <select id="docType" style={{ display: "block", width: "100%" }}>
            <option value="COMPLAINT">Criminal Complaint</option>
            <option value="INDICTMENT">Indictment</option>
            <option value="ARREST_REPORT">Arrest Report</option>
            <option value="OTHER">Other</option>
          </select>
        </div>
        <div style={{ marginBottom: "1rem" }}>
          <label htmlFor="file">File (PDF)</label>
          <input id="file" type="file" accept=".pdf,.png,.jpg,.jpeg" />
        </div>
        <button type="submit">Upload &amp; Process</button>
      </form>
    </div>
  );
}
