const LEVEL_DESCRIPTIONS = {
  basic: "Nível básico — leitura rápida do caso: cada exame aparece com seu resultado agregado, sem detalhamento adicional. Pensado para o médico assistente que quer entender o caso do paciente de forma direta.",
  detailed: "Nível detalhado — grafo completo: valores, unidades e faixas de referência viram nós próprios, e todas as entidades relevantes são ligadas a vocabulários controlados. Pensado para quem estuda o caso em profundidade.",
};

let cy = null;
let currentCase = null;
let currentLevel = "basic";

function cytoscapeStyle() {
  return [
    {
      selector: "node",
      style: {
        "background-color": "data(color)",
        "border-width": 1,
        "border-color": "#94a3a8",
        label: "data(label)",
        "font-size": 10,
        "font-family": "-apple-system, Segoe UI, sans-serif",
        color: "#16211f",
        "text-wrap": "wrap",
        "text-max-width": "90px",
        width: "label",
        height: "label",
        padding: "8px",
        shape: "round-rectangle",
      },
    },
    {
      selector: "edge",
      style: {
        width: 1.4,
        "line-color": "#a9b3b0",
        "target-arrow-color": "#a9b3b0",
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
        label: "data(relation)",
        "font-size": 8,
        "font-family": "-apple-system, Segoe UI, sans-serif",
        color: "#4a5a57",
        "text-rotation": "autorotate",
        "text-background-color": "#f6f7f5",
        "text-background-opacity": 1,
        "text-background-padding": 2,
      },
    },
    {
      selector: "node:selected",
      style: { "border-width": 3, "border-color": "#0e6b64" },
    },
    {
      selector: "edge:selected",
      style: { "line-color": "#0e6b64", "target-arrow-color": "#0e6b64", width: 2.4 },
    },
  ];
}

async function loadGraph(caseId, level) {
  const res = await fetch(`/api/graph/${encodeURIComponent(caseId)}/${level}`);
  if (!res.ok) {
    document.getElementById("details-content").textContent =
      "Não foi possível carregar o grafo. Rode `python -m kg_extraction.pipeline` para gerar os dados processados.";
    return;
  }
  const data = await res.json();

  if (cy) cy.destroy();
  cy = cytoscape({
    container: document.getElementById("cy"),
    elements: [...data.nodes, ...data.edges],
    style: cytoscapeStyle(),
    layout: { name: "breadthfirst", directed: true, spacingFactor: 1.1, padding: 20 },
  });

  cy.on("tap", "node", (evt) => showDetails(evt.target.data(), "nó"));
  cy.on("tap", "edge", (evt) => showDetails(evt.target.data(), "aresta"));
}

function showDetails(data, kind) {
  const panel = document.getElementById("details-content");
  if (kind === "nó") {
    panel.textContent =
      `Tipo: ${data.type}\nRótulo: ${data.label}` +
      (data.attributes ? `\nAtributos: ${data.attributes}` : "");
  } else {
    panel.textContent = `Relação: ${data.relation}\nOrigem: ${data.source}\nDestino: ${data.target}`;
  }
}

async function loadCaseText(caseId) {
  const res = await fetch(`/api/case_text/${encodeURIComponent(caseId)}`);
  const el = document.getElementById("case-text");
  if (!res.ok) {
    el.textContent = "";
    return;
  }
  const data = await res.json();
  el.textContent = data.case_text;
}

function setLevel(level) {
  currentLevel = level;
  document.querySelectorAll(".level-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.level === level);
  });
  document.getElementById("level-description").textContent = LEVEL_DESCRIPTIONS[level];
  loadGraph(currentCase, currentLevel);
}

document.getElementById("level-toggle").addEventListener("click", (evt) => {
  const btn = evt.target.closest(".level-btn");
  if (btn) setLevel(btn.dataset.level);
});

document.getElementById("case-select").addEventListener("change", (evt) => {
  currentCase = evt.target.value;
  loadGraph(currentCase, currentLevel);
  loadCaseText(currentCase);
});

// Inicialização: primeiro caso da lista, nível básico
window.addEventListener("DOMContentLoaded", () => {
  const select = document.getElementById("case-select");
  currentCase = select.value;
  document.getElementById("level-description").textContent = LEVEL_DESCRIPTIONS.basic;
  loadGraph(currentCase, currentLevel);
  loadCaseText(currentCase);
});
