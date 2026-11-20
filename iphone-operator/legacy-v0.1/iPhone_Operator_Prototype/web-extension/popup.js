const output = document.getElementById("output");
const inspectButton = document.getElementById("inspect");
const copyButton = document.getElementById("copy");
const runButton = document.getElementById("run");
let lastInspection = null;

async function activeTab() {
  const tabs = await browser.tabs.query({ active: true, currentWindow: true });
  if (!tabs.length || tabs[0].id === undefined) throw new Error("No accessible active Safari tab");
  return tabs[0];
}
async function contact(message) {
  const tab = await activeTab();
  try {
    await browser.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
  } catch (err) {
    throw new Error(`Cannot access this page. Grant website permission in Safari. Details: ${String(err)}`);
  }
  return browser.tabs.sendMessage(tab.id, message);
}
function show(value) { output.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2); }

inspectButton.addEventListener("click", async () => {
  try {
    const response = await contact({ type: "inspect" });
    if (!response.ok) throw new Error(response.reason);
    lastInspection = response.result;
    show(response.result);
  } catch (e) { show(`Inspection error: ${e.message}`); }
});
copyButton.addEventListener("click", async () => {
  if (!lastInspection) return show("Inspect the page first.");
  try { await navigator.clipboard.writeText(JSON.stringify(lastInspection, null, 2)); show("Inspection copied. Never paste private page data into an untrusted AI."); }
  catch (e) { show(`Copy error: ${e.message}`); }
});
runButton.addEventListener("click", async () => {
  try {
    const plan = JSON.parse(document.getElementById("plan").value);
    if (!Array.isArray(plan.steps) || plan.steps.length > 20) throw new Error("JSON needs steps array (20 maximum)");
    const response = await contact({ type: "run", plan });
    show(response);
  } catch (e) { show(`Plan error: ${e.message}`); }
});
