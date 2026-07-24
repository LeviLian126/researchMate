// Provides the prototype interactions for record tabs, evidence inspection, and simulated follow-up research.
const inspector = document.querySelector("#evidence-inspector");
const sourceCard = document.querySelector("#source-card");
const scrim = document.querySelector("#scrim");
const closeInspectorButton = document.querySelector("#close-inspector");
const recordTabs = Array.from(document.querySelectorAll("[data-record-tab]"));
const recordPanels = Array.from(document.querySelectorAll("[data-record-panel]"));
const promptInput = document.querySelector("#prompt");
const composer = document.querySelector("#composer");
const composerStatus = document.querySelector("#composer-status");
const followupButtons = Array.from(document.querySelectorAll("[data-prompt]"));
const themeButtons = Array.from(document.querySelectorAll("[data-theme-option]"));
const themeName = document.querySelector("#theme-name");
const themeLabels = { cobalt: "Cobalt studio", aubergine: "Aubergine signal", forest: "Forest research" };

/** Shows the evidence inspector and synchronizes its accessibility state. */
function openInspector() {
  inspector.classList.add("open");
  inspector.setAttribute("aria-hidden", "false");
  sourceCard.setAttribute("aria-expanded", "true");
  scrim.hidden = false;
  closeInspectorButton.focus();
}

/** Hides the evidence inspector and returns focus to the cited source. */
function closeInspector() {
  inspector.classList.remove("open");
  inspector.setAttribute("aria-hidden", "true");
  sourceCard.setAttribute("aria-expanded", "false");
  scrim.hidden = true;
  sourceCard.focus();
}

/** Displays the metadata panel associated with the chosen record section. */
function selectRecordTab(tabName) {
  recordTabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.recordTab === tabName));
  recordPanels.forEach((panel) => { panel.hidden = panel.dataset.recordPanel !== tabName; });
}

/** Simulates a source-bound research request without calling the production API. */
function runInquiry(event) {
  event.preventDefault();
  const submitButton = composer.querySelector("button[type='submit']");
  submitButton.disabled = true;
  composerStatus.textContent = "Reading 12 local sources…";
  window.setTimeout(() => {
    composerStatus.textContent = "Demo complete · production version will append a cited record.";
    submitButton.disabled = false;
  }, 900);
}

/** Applies one semantic color system and keeps the review choice across reloads. */
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  themeName.textContent = themeLabels[theme];
  themeButtons.forEach((button) => {
    const active = button.dataset.themeOption === theme;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  window.localStorage.setItem("researchmate-demo-theme", theme);
}

sourceCard.addEventListener("click", openInspector);
closeInspectorButton.addEventListener("click", closeInspector);
scrim.addEventListener("click", closeInspector);
recordTabs.forEach((tab) => tab.addEventListener("click", () => selectRecordTab(tab.dataset.recordTab)));
followupButtons.forEach((button) => button.addEventListener("click", () => { promptInput.value = button.dataset.prompt; promptInput.focus(); }));
composer.addEventListener("submit", runInquiry);
document.addEventListener("keydown", (event) => { if (event.key === "Escape" && inspector.classList.contains("open")) closeInspector(); });
themeButtons.forEach((button) => button.addEventListener("click", () => applyTheme(button.dataset.themeOption)));
applyTheme(window.localStorage.getItem("researchmate-demo-theme") || "cobalt");
