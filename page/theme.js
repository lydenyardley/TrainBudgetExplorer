  // The one thing this page does before it renders anything: name a stored
  // palette, so a return visit does not flash the system one. Nothing stored
  // leaves the meta at "light dark", which is follow-the-system, and the
  // stylesheet already says the same, so there is no second guess to flash.
  (function () {
    try {
      var stored = localStorage.getItem("tbe-theme");
      if (stored === "dark" || stored === "light") {
        var meta = document.querySelector('meta[name="color-scheme"]');
        if (meta) meta.setAttribute("content", stored);
      }
    } catch (e) { /* storage blocked: the meta stays "light dark" */ }
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
    var toggle = document.getElementById("themeToggle");
    if (!toggle) return;
    var glyph = toggle.querySelector(".glyph");
    function systemDark() {
      return window.matchMedia("(prefers-color-scheme: dark)").matches;
    }
    // "light dark" follows the system. "light" or "dark" pins one scheme, and
    // the stylesheet reads this same meta, so the two cannot disagree.
    function apply(content) {
      var meta = document.querySelector('meta[name="color-scheme"]');
      if (meta) meta.setAttribute("content", content);
      var dark = content === "dark" || (content !== "light" && systemDark());
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
    var meta = document.querySelector('meta[name="color-scheme"]');
    apply(meta ? meta.getAttribute("content") : "light dark");
    toggle.hidden = false;
    // While nothing is stored the colours already follow the system. The
    // switch does not, unless something tells it the system moved.
    var media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", function () {
      var current = document.querySelector('meta[name="color-scheme"]');
      if (current && current.getAttribute("content") === "light dark") apply("light dark");
    });
    // Another tab can pin or drop the choice. This tab did not write it, so
    // the storage event is the only way it hears.
    window.addEventListener("storage", function (event) {
      if (event.key !== "tbe-theme") return;
      if (event.newValue === "dark" || event.newValue === "light") apply(event.newValue);
      else apply("light dark");
    });
    toggle.addEventListener("click", function () {
      var metaNow = document.querySelector('meta[name="color-scheme"]');
      var content = metaNow ? metaNow.getAttribute("content") : "light dark";
      var darkNow = content === "dark" || (content !== "light" && systemDark());
      var wantDark = !darkNow;
      var theme = wantDark ? "dark" : "light";
      // Pressing the switch onto the scheme the system is already using puts
      // the pin down. Storing that scheme would freeze it against the next
      // system change, which is the opposite of what the press undoes. A
      // stored value that the system later matches is left in place: dropping
      // it then would make a night-time OS switch unpin a choice.
      if (wantDark === systemDark()) {
        try { localStorage.removeItem("tbe-theme"); } catch (e) { /* this page follows anyway */ }
        apply("light dark");
      } else {
        try { localStorage.setItem("tbe-theme", theme); } catch (e) { /* remembered for this page only */ }
        apply(theme);
      }
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
