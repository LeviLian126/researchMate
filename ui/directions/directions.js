// Switches between isolated visual-direction prototypes without changing their internal markup.
const buttons = Array.from(document.querySelectorAll("[data-direction]"));
const concepts = Array.from(document.querySelectorAll("[data-concept]"));

/** Displays one concept and updates the review controls and URL hash. */
function selectDirection(direction) {
  concepts.forEach((concept) => {
    const active = concept.dataset.concept === direction;
    concept.hidden = !active;
    concept.classList.toggle("is-active", active);
  });
  buttons.forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.direction === direction)));
  window.history.replaceState(null, "", `#${direction}`);
}

buttons.forEach((button) => button.addEventListener("click", () => selectDirection(button.dataset.direction)));

/** Selects the direction encoded in the URL when it points to a known concept. */
function selectDirectionFromLocation() {
  const requestedDirection = window.location.hash.slice(1);
  if (concepts.some((concept) => concept.dataset.concept === requestedDirection)) {
    selectDirection(requestedDirection);
  }
}

window.addEventListener("hashchange", selectDirectionFromLocation);
selectDirectionFromLocation();
