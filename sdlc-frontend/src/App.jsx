import { useState } from "react";
import "./App.css";

function App() {
  const [requirement, setRequirement] = useState("");
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleGenerate = async () => {
    if (!requirement.trim()) return;

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const res = await fetch("http://127.0.0.1:8000/expand", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ requirement })
      });

      if (!res.ok) {
        throw new Error("Backend error");
      }

      const data = await res.json();
      setResponse(data);
    } catch (err) {
      setError("Failed to connect to backend.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: "40px", fontFamily: "Arial" }}>
      <h1>AI SDLC Generator</h1>

      <textarea
        rows="4"
        style={{ width: "100%", marginBottom: "20px" }}
        placeholder="Enter one-line requirement..."
        value={requirement}
        onChange={(e) => setRequirement(e.target.value)}
      />

      <button onClick={handleGenerate} disabled={loading}>
        {loading ? "Generating..." : "Generate"}
      </button>

      {error && (
        <div style={{ color: "red", marginTop: "20px" }}>
          {error}
        </div>
      )}

      {response && (
        <div style={{ marginTop: "30px" }}>
          <h2>Final Output</h2>
          <pre
            style={{
              background: "#f4f4f4",
              padding: "20px",
              overflowX: "auto"
            }}
          >
            {JSON.stringify(response.final, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export default App;