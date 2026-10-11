// The change-station picker (ADR-0019).

// The picker (ADR-0019): choosing a station is navigation to that station's
// page, not a filter on this one. The options are real anchors, so keyboard
// handling and accessible naming are the browser's own. The list is built from
// the written outputs, so nothing here can lead to a missing page.
const changeOrigin = document.getElementById("changeOrigin");
const originPicker = document.getElementById("originPicker");
if (changeOrigin && DATA.stations && DATA.stations.length) {
  // The field the page's own script created, read here rather than from the
  // document: it is moved into the heading when the picker opens, and the
  // markup no longer holds it.
  const originSearch = document.createElement("input");
  originSearch.id = "originSearch";
  originSearch.type = "search";
  originSearch.placeholder = "station";
  originSearch.autocomplete = "off";
  originSearch.setAttribute("aria-describedby", "originStatus");
  originSearch.setAttribute("aria-controls", "originPicks");
  originSearch.setAttribute("aria-label", "Start from a different station");
  const originSlot = changeOrigin.parentElement;
  const originPicks = document.getElementById("originPicks");
  const originNomatch = document.getElementById("originNomatch");
  const originStatus = document.getElementById("originStatus");
  // The same cap and the same sentence the chooser's field draws: station
  // search is one behaviour, and a list that quietly stops at forty tells a
  // reader nothing about the 2,663 stations it is not showing (route audit
  // items 10 and 22, 9 October 2026).
  const originCap = document.getElementById("originCap");

  function renderPicks() {
    const needle = originSearch.value.trim().toLowerCase();
    const wanted = DATA.stations.filter((station) => stationMatches(station, needle));
    originPicks.replaceChildren();
    for (const station of wanted.slice(0, STATION_LIST_CAP)) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      // The reader's budget, ticket type and facets travel with them: changing
      // station is a correction of where they are leaving from, not a reset of
      // the decision they have already made.
      link.href = station.href + "?" + stateQuery();
      const name = document.createElement("span");
      name.textContent = station.name;
      const code = document.createElement("span");
      code.className = "code";
      code.textContent = station.crs;
      link.append(name, code);
      item.append(link);
      originPicks.append(item);
    }
    if (wanted.length) {
      originNomatch.hidden = true;
    } else {
      originNomatch.textContent = "We don't have prices from '" + originSearch.value.trim() +
        "'. Try the station's name or its three-letter code.";
      originNomatch.hidden = false;
    }
    // Said on the page rather than in a screen-reader-only status, because the
    // rows a sighted reader cannot see are the rows they are missing.
    if (originCap) {
      originCap.textContent = wanted.length > STATION_LIST_CAP
        ? "Showing " + STATION_LIST_CAP + " of " + wanted.length + " stations. Type to narrow the list."
        : "";
      originCap.hidden = wanted.length <= STATION_LIST_CAP;
    }
    originStatus.textContent = wanted.length + " station" + (wanted.length === 1 ? "" : "s") + " listed";
  }

  // The field is moved into the slot rather than duplicated, so there is one
  // input in the document and the heading's own accessible name is the one
  // that gets typed into.
  function setPicker(open) {
    changeOrigin.setAttribute("aria-expanded", String(open));
    originPicker.hidden = !open;
    if (open) {
      if (originSearch.parentElement !== originSlot) originSlot.append(originSearch);
      changeOrigin.hidden = true;
      renderPicks();
      // The field is sized to its placeholder, so it is as wide as the word
      // "station" and no wider until something is typed into it.
      originSearch.focus();
      originSearch.select();
    } else {
      changeOrigin.hidden = false;
      originSearch.remove();
      // Escape is a keyboard exit, and focus returns to the control that
      // opened the picker rather than dropping to the top of the page.
      changeOrigin.focus();
    }
  }

  changeOrigin.addEventListener("click", () => {
    setPicker(changeOrigin.getAttribute("aria-expanded") !== "true");
  });
  // The budget slot beside this one is a real field, so a keyboard reader tabs
  // to it and types. This control is a button, and a button takes no keystroke:
  // a reader tabbed to the station's name and stopped there, and the field was
  // only reachable by pressing Enter or Space on the name first, which is two
  // gestures for one edit. Any printable key opens the picker and carries that
  // one character into it, which is what the budget slot does without saying so.
  changeOrigin.addEventListener("keydown", (event) => {
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    // Space is the button's own key, and it is what opens the picker on its own.
    if (event.key.length !== 1 || event.key === " ") return;
    event.preventDefault();
    setPicker(true);
    originSearch.value = event.key;
    originSearch.setSelectionRange(1, 1);
    originSearch.dispatchEvent(new Event("input", { bubbles: true }));
  });
  originPicker.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setPicker(false);
  });
  // The field's own behaviour -- the completion, Tab and Enter, Escape, and the
  // click on the page that puts the station name back -- is the shared block,
  // because the chooser asks for the same three things. Walking away is one
  // path and it only acts while the picker is open, or every click on a
  // closed page would pull focus back to the station name.
  attachStationField({
    field: originSearch,
    stations: DATA.stations,
    dropdown: originPicker,
    inside: [originPicker],
    onChange: () => renderPicks(),
    onChoose: (station) => {
      window.location.href = station.href + "?" + stateQuery();
    },
    onCancel: () => {
      if (changeOrigin.getAttribute("aria-expanded") === "true") setPicker(false);
    },
  });
  // The picker is the field's other half -- the same selector, reached from the
  // heading -- so it answers the same two keys through the same block. Escape
  // from an option goes back to the field; Escape from the field closes it.
  wireListKeys(originSearch, originPicks);
} else if (changeOrigin) {
  // The shared station list did not arrive, so this control can only open
  // an empty panel. Put the station's own name where the control was --
  // the heading must never be left saying "from" and nothing -- and say
  // what the page is instead of naming a control it does not have. This is
  // still one station's page, and the way to another one is the All
  // stations link in the footer. A build that ships the list inside the
  // page never reaches this branch: DATA.stations is filled before this
  // script runs, so there is no request that can fail.
  const stationName = document.createElement("span");
  stationName.className = "origin-name";
  stationName.textContent = DATA.origin ? DATA.origin.name : "";
  changeOrigin.replaceWith(stationName);
  originPicker.remove();
  const fallbackNote = document.getElementById("firstUse");
  if (fallbackNote) fallbackNote.textContent = FIRST_USE_FALLBACK;
}
