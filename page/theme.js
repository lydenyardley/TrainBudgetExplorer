  // The one thing this page does before it renders anything: say which palette
  // it is, so there is no flash of the other one. Dark unless the reader has
  // chosen otherwise, on this device, in this browser.
  (function () {
    var dark = true;
    try {
      var stored = localStorage.getItem("tbe-theme");
      if (stored) dark = stored === "dark";
    } catch (e) { /* storage blocked: the default stands */ }
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  })();
  // The control, wired once the body exists. It ships hidden and is revealed
  // here: a button that cannot do anything without this script is a control
  // that lies, which is the same defect as the Change button this replaced.
  //
  // It is revealed only if the stylesheet is here to be changed. A route that
  // fetches its stylesheet (ADR-0047) may not get it, and a switch that
  // rewrites an attribute no rule reads is the picker's "a control that opens
  // nothing" in a different dress: so the switch is taken away and the page
  // says what state it is in, which is the picker's failure mode one route
  // down. The marker is a token the stylesheet sets, so the answer is the
  // browser's own rather than a guess about whether a request is still in
  // flight -- and it is read again on load, because a stylesheet still
  // arriving when the body exists has not failed yet.
  function stylesheetArrived() {
    return getComputedStyle(document.documentElement)
      .getPropertyValue("--tbe-stylesheet").trim() !== "";
  }
  function wireTheme() {
    var root = document.documentElement;
    var toggle = document.getElementById("themeToggle");
    if (!toggle) return;
    var glyph = toggle.querySelector(".glyph");
    function paint(dark) {
      root.dataset.theme = dark ? "dark" : "light";
      toggle.setAttribute("aria-checked", String(dark));
      if (glyph) glyph.textContent = dark ? "☾" : "☀";
    }
    if (!stylesheetArrived()) {
      // Gone rather than inert, and the page says why it is plain text.
      toggle.remove();
      var note = document.getElementById("styleNote");
      if (note) {
        note.textContent = "This page’s styling did not load, so it is plain"
          + " text. Every price, time and restriction on it is still here.";
        note.hidden = false;
      }
      return;
    }
    paint(root.dataset.theme === "dark");
    toggle.hidden = false;
    toggle.addEventListener("click", function () {
      var dark = root.dataset.theme !== "dark";
      paint(dark);
      try { localStorage.setItem("tbe-theme", dark ? "dark" : "light"); } catch (e) { /* remembered for this page only */ }
    });
  }
  document.addEventListener("DOMContentLoaded", wireTheme);
  window.addEventListener("load", function () {
    // A page that was styled all along is left exactly as it is, so this
    // only speaks when the switch is still hidden and the note still is.
    var toggle = document.getElementById("themeToggle");
    if (toggle && !toggle.hidden) return;
    var note = document.getElementById("styleNote");
    if (note && note.hidden) wireTheme();
  });
