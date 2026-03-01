import { useState, useEffect, useRef } from "react";
import "./App.css";
import mermaid from "mermaid";

mermaid.initialize({
  startOnLoad: false,
  theme: "default",
  securityLevel: "loose"
});

function MermaidDiagram({ chart }) {
  const ref = useRef(null);

  useEffect(() => {
  if (!chart) return;

  const cleanChart = chart
    .replace(/```mermaid/g, "")
    .replace(/```/g, "")
    .trim();

  mermaid
    .render("diagram-" + Date.now(), cleanChart)
    .then(({ svg }) => {
      if (ref.current) {
        ref.current.innerHTML = svg;
      }
    })
    .catch((err) => {
      console.error("Mermaid render error:", err);
      console.log("Clean chart content:", cleanChart);
    });

}, [chart]);

  return <div ref={ref} />;
}

function App() {
  const [requirement, setRequirement] = useState("");
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("BRD");

  const handleGenerate = async () => {
    if (!requirement.trim()) return;

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const res = await fetch("http://127.0.0.1:8000/expand", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ requirement })
      });

      if (!res.ok) throw new Error("Backend error");

      const data = await res.json();
      setResponse(data);
    } catch (err) {
      console.error(err);
      setError("Failed to connect to backend.");
    } finally {
      setLoading(false);
    }
  };

  const renderTabContent = () => {
    if (!response?.artifacts) return null;

    const artifacts = response.artifacts;

    switch (activeTab) {
      case "BRD":
        return <pre>{JSON.stringify(artifacts.brd, null, 2)}</pre>;

      case "PRD":
        return <pre>{JSON.stringify(artifacts.prd, null, 2)}</pre>;

      case "Architecture":
        return (
          <>
            <pre>
              {JSON.stringify(artifacts.technical_architecture, null, 2)}
            </pre>

            {artifacts.mermaid_diagram && (
              <div style={{ marginTop: "30px" }}>
                <MermaidDiagram chart={artifacts.mermaid_diagram} />
              </div>
            )}
          </>
        );

      case "Sprints":
        return <pre>{JSON.stringify(artifacts.sprint_plan, null, 2)}</pre>;

      case "Deployment":
        return <pre>{JSON.stringify(artifacts.deployment_plan, null, 2)}</pre>;

      default:
        return null;
    }
  };

  const riskColor = (score) => {
    if (score >= 0.7) return "red";
    if (score >= 0.4) return "orange";
    return "green";
  };

  return (
    <div style={{ padding: "40px", fontFamily: "Arial" }}>
      <h1>AI SDLC Control Console</h1>

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
        <div style={{ color: "red", marginTop: "20px" }}>{error}</div>
      )}

      {response && (
        <div style={{ marginTop: "40px" }}>
          <h2>Project Risk Overview</h2>

          <div style={{ marginBottom: "10px" }}>
            <strong>Risk Score: </strong>
            <span style={{ color: riskColor(response.risk_score) }}>
              {response.risk_score}
            </span>
          </div>

          <div style={{ marginBottom: "10px" }}>
            <strong>Governance Level: </strong>
            {response.governance?.maturity_level}
          </div>

          <div style={{ marginBottom: "20px" }}>
            <strong>Deployment Approved: </strong>
            {response.enforcement?.approved_for_deployment
              ? "✅ Yes"
              : "❌ No"}
          </div>

          <h3>Required Actions</h3>
          <ul>
            {response.enforcement?.actions?.map((action, i) => (
              <li key={i}>{action}</li>
            ))}
          </ul>

          <div style={{ marginTop: "20px", marginBottom: "30px" }}>
            <button style={{ marginRight: "10px" }}>
              Create Jira Ticket
            </button>
            <button>Trigger Rundeck Deployment</button>
          </div>

          <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
            {["BRD", "PRD", "Architecture", "Sprints", "Deployment"].map(
              (tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  style={{
                    background: activeTab === tab ? "#333" : "#eee",
                    color: activeTab === tab ? "white" : "black",
                    padding: "6px 12px"
                  }}
                >
                  {tab}
                </button>
              )
            )}
          </div>

          <div
            style={{
              background: "#f4f4f4",
              padding: "20px",
              borderRadius: "8px",
              maxHeight: "500px",
              overflow: "auto"
            }}
          >
            {renderTabContent()}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;