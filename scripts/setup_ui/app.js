"use strict";
const $ = (id) => document.getElementById(id);
const token = location.pathname.split("/")[1];
let file = null, later = false, existing = false;
async function api(route, body) {
  const response = await fetch("api/" + route, body === undefined ? {} : {
    method: "POST", headers: {"Content-Type": "application/json", "X-Setup-Token": token}, body: JSON.stringify(body)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "La demande a échoué.");
  return result;
}
function fail(error) { $("error").textContent = error.message || "Impossible de joindre la configuration. Rouvrez Configurer.command."; $("error").hidden = false; $("error").scrollIntoView({block: "center", behavior: "smooth"}); }
function updateAuthors(preferred) {
  const selected = preferred || $("default-author").value;
  const names = [...new Set($("authors").value.split(",").map(s => s.trim()).filter(Boolean))];
  $("default-author").replaceChildren(...names.map(n => { const option = document.createElement("option"); option.value = n; option.textContent = n; return option; }));
  $("default-author").value = names.includes(selected) ? selected : names[0] || "";
}
function choose(chosen) {
  if (!chosen) return;
  if (!chosen.name.toLowerCase().endsWith(".csv") || chosen.size > 20 * 1024 * 1024 || !chosen.size) { fail(new Error("Choisissez un fichier CSV non vide, de 20 Mo maximum.")); return; }
  file = chosen; later = false;
  $("filename").textContent = chosen.name + " · " + Math.max(1, Math.round(chosen.size / 1024)) + " Ko";
  $("chosen").hidden = false; $("later").setAttribute("aria-pressed", "false"); $("later-note").hidden = true; $("error").hidden = true;
}
function aiVisibility() { $("ai-settings").hidden = !$("ai").checked; $("key-field").hidden = $("key-action").value !== "replace"; }
async function load() {
  try {
    const data = await api("settings"), v = data.values;
    $("authors").value = v.HANDCODING_AUTHORS; updateAuthors(v.HANDCODING_AUTHOR);
    $("ai").checked = v.HANDCODING_AI_ENABLED === "1"; $("model").value = v.HANDCODING_AI_MODEL;
    $("coding-port").value = v.HANDCODING_CODING_PORT; $("harmonization-port").value = v.HANDCODING_HARMONIZATION_PORT;
    $("key-status").textContent = data.local_key ? "Une clé privée est déjà enregistrée pour cette application." : data.key_available ? "Une clé est disponible dans l’environnement de ce Mac ; elle n’est pas copiée dans l’application." : "Aucune clé n’est actuellement disponible. Vous pouvez activer l’IA plus tard.";
    if (data.warning) { $("error").textContent = data.warning; $("error").hidden = false; }
    existing = data.input_present; $("existing").hidden = !existing; $("later").hidden = existing; $("input-path").textContent = data.input_folder;
    $("loading").hidden = true; $("settings").hidden = false; aiVisibility();
  } catch (error) { $("loading").textContent = error.message; }
}
$("authors").addEventListener("input", () => updateAuthors());
$("ai").addEventListener("change", aiVisibility); $("key-action").addEventListener("change", aiVisibility);
$("file").addEventListener("change", (e) => choose(e.target.files[0]));
$("drop").addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("file").click(); } });
for (const event of ["dragenter", "dragover"]) $("drop").addEventListener(event, e => { e.preventDefault(); $("drop").classList.add("dragging"); });
for (const event of ["dragleave", "drop"]) $("drop").addEventListener(event, e => { e.preventDefault(); $("drop").classList.remove("dragging"); });
$("drop").addEventListener("drop", e => { if (e.dataTransfer.files.length !== 1) fail(new Error("Déposez un seul fichier CSV.")); else choose(e.dataTransfer.files[0]); });
document.addEventListener("dragover", e => e.preventDefault()); document.addEventListener("drop", e => e.preventDefault());
$("remove-file").addEventListener("click", () => { file = null; $("file").value = ""; $("chosen").hidden = true; });
$("later").addEventListener("click", () => { later = true; file = null; $("file").value = ""; $("chosen").hidden = true; $("later").setAttribute("aria-pressed", "true"); $("later-note").hidden = false; });
$("settings").addEventListener("submit", async e => {
  e.preventDefault(); $("error").hidden = true;
  if (!file && !existing && !later) { fail(new Error("Ajoutez les interviews ou cliquez sur « Ajouter la base plus tard ».")); return; }
  $("save").disabled = true; $("save").textContent = "Enregistrement…";
  try {
    let upload = null;
    if (file) { const bytes = new Uint8Array(await file.arrayBuffer()); let binary = ""; for (let i = 0; i < bytes.length; i += 32768) binary += String.fromCharCode(...bytes.subarray(i, i + 32768)); upload = {name: file.name, content: btoa(binary)}; }
    const data = await api("save", {values: {
      HANDCODING_AUTHORS: $("authors").value, HANDCODING_AUTHOR: $("default-author").value,
      HANDCODING_AI_ENABLED: $("ai").checked ? "1" : "0", HANDCODING_AI_MODEL: $("model").value.trim(),
      HANDCODING_CODING_PORT: $("coding-port").value, HANDCODING_HARMONIZATION_PORT: $("harmonization-port").value
    }, key_action: $("key-action").value, new_key: $("key").value, file: upload, later});
    $("key").value = ""; $("key-action").value = "keep"; file = null; $("file").value = ""; $("chosen").hidden = true;
    $("settings").hidden = true; $("success").hidden = false;
    $("success-text").textContent = data.input_present ? "Les interviews sont en place. Vos réglages seront utilisés au prochain lancement." : "Le dossier des interviews est prêt : " + data.input_folder + ". Placez-y un fichier nommé interviews.csv avant de lancer le codage.";
    window.scrollTo({top: 0, behavior: "smooth"});
  } catch (error) { fail(error); }
  finally { $("save").disabled = false; $("save").textContent = "Enregistrer la configuration"; }
});
$("open-input").addEventListener("click", () => api("open-folder", {folder: "input"}).catch(fail));
$("open-outputs").addEventListener("click", () => api("open-folder", {folder: "outputs"}).catch(fail));
$("edit").addEventListener("click", () => { $("success").hidden = true; load(); });
$("close").addEventListener("click", async () => { try { await api("close", {}); } catch {} document.querySelector("main").replaceChildren(Object.assign(document.createElement("p"), {textContent: "La configuration est fermée. Vous pouvez fermer cet onglet."})); });
load();
