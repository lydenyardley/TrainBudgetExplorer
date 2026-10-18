// The day the table reports, and the week of answers the build walked for
// each row.

// The table's count line and its empty state are read in payload.js with the
// rest of the page's elements, because table.js is what writes them.
const serviceDayBar = document.getElementById("serviceDayBar");
const serviceDaySelect = document.getElementById("serviceDay");
const serviceDayHelp = document.getElementById("serviceDayHelp");

// The day the Time and Changes columns are reporting, as an index into
// DATA.serviceDays. Zero is the build's own day, which is what every one of
// these surfaces said before the reader could choose, so the page opens on the
// day it has always opened on.
// Put a day on the control and in the state the table reads. One function for
// every caller, because the reader can ask for a day two ways -- the control,
// or Back -- and a page where only one of them moves the table is a page whose
// address and its table disagree. It only records the day: rendering and the
// address are the caller's, so this is safe to call from applyState, which
// reads the address before the control has written its options, and safe to
// call again afterwards without rendering twice.
function setServiceDay(index) {
  const days = DATA.serviceDays || [];
  const wanted = Math.min(Math.max(Number(index) || 0, 0), Math.max(days.length - 1, 0));
  STATE.day = wanted;
  // The control has no options until the block below writes them, which is
  // after the address is read, so a link's day is recorded first and the
  // control is pointed at it once it exists.
  if (serviceDaySelect && serviceDaySelect.options.length) {
    serviceDaySelect.value = String(wanted);
  }
  return wanted;
}
// A day the reader chose on this page, which moves the table, the dock and the
// address together. A result set that changed under the reader starts again at
// its first page, and the dock is redrawn because a shortlisted row showing the
// build's day beside a table showing the chosen one is the page contradicting
// itself.
function chooseServiceDay(index) {
  setServiceDay(index);
  STATE.page = 1;
  render();
  renderShortlist();
  writeUrl();
}
// Every absence a row can carry, in one table, because three surfaces print
// one -- the Time cell, the dock's row and the copied text -- and because an
// absence with no day on it reads as a claim about the station rather than
// about the date. The build sends a key, the day it asked about and the day
// the row next runs; nothing here can be worded without them.
//
// A cell is narrow and a copied line is not, so each entry says both: the
// short form goes in the column, where the table's own day is the day it means,
// and the long form in the record, which names the date because that text
// travels away from the page. They are two lengths of one sentence rather than
// two sentences.
const JOURNEY_ABSENCE = {
  no_timetable: (day, later) => ({
    brief: day.short ? "No timetable " + day.short : "No timetable",
    full: day.long ? "no timetable in this build for " + day.long : "no timetable in this build",
  }),
  no_service: (day, later) => ({
    // The cell holds a short state and the day it means is in the row's own
    // details: a clause in a column of durations reads as a duration, and this
    // one was ungrammatical on top of that (audit item 22).
    brief: "No service that day",
    full: later
      ? "no service on " + day.long + ", and it runs on " + humanDate(later)
      : "no service on " + (day.long || "the day this build asked about") +
        ", nor on the " + (DATA.serviceHorizon || 7) + " days after it",
  }),
};
// The absence a row is carrying, worded from the three facts it holds. A state
// this build does not recognise is worded as an absence, because an
// unrecognised state is not a journey.
function absenceText(destination, brief) {
  const iso = DATA.serviceDate;
  const day = { short: shortDay(iso), long: iso ? humanDate(iso) : "" };
  const build = JOURNEY_ABSENCE[destination.journeyState] || JOURNEY_ABSENCE.no_service;
  return build(day, destination.nextService)[brief ? "brief" : "full"];
}

// What this row's station is on the day now chosen, as [minutes, changes], or
// null when it runs on no day the reader can pick. Null is the honest answer
// for a day the network does not serve, and for a row this build holds no week
// for, and the two are worded differently by the caller rather than collapsed
// into one "unknown".
function serviceAnswer(destination) {
  const days = DATA.serviceWeek;
  if (!days || !days.length) return undefined;
  const index = destination.serviceWeekIndex;
  // Null as well as undefined, because the build sends null for a row it
  // holds no week for rather than -1: a pool reference is a negative number,
  // so -1 would have decoded into pool entry zero and named a railcard.
  if (index === undefined || index === null || index < 0) return undefined;
  const perDay = days[index];
  if (!perDay) return undefined;
  // The day's table is keyed by station, so the row's own station is looked
  // up in it. Handing back the day's whole table instead is a row that
  // prints a dash for every station on the page, because the object has no
  // index 0 in it to read a duration from.
  const day = perDay[STATE.day];
  if (!day) return undefined;
  // The build keeps only the stations a walk reached, so a station this
  // day's table does not name is one it did not run to on that day. The row
  // is known to this table -- the build asked about every station a row
  // names -- so its absence is an answer, not a gap in what was asked.
  return Object.prototype.hasOwnProperty.call(day, destination.crs)
    ? day[destination.crs]
    : null;
}
// The minutes and changes to print, which are the chosen day's rather than the
// build's whenever the build carried a week. Day zero is the build's own answer
// and is asserted equal to it, so choosing the first day changes nothing.
function journeyFor(destination) {
  const answer = serviceAnswer(destination);
  if (answer === undefined) {
    return destination.journeyState === "found"
      ? { minutes: destination.minutes, changes: destination.changes, found: true }
      : { minutes: null, changes: null, found: false };
  }
  return answer === null
    ? { minutes: null, changes: null, found: false }
    : { minutes: answer[0], changes: answer[1], found: true };
}
// The absence, worded for the day being shown rather than the day the build
// asked about. S23's point, kept when the reader chooses the day: "No service"
// beside a station the network serves on the other six days reads as a claim
// about the station unless the sentence names the day it is about. When the
// chosen day has no service and another day in the week does, the sentence
// names both, which is what tells a reader the row is worth reading.
function dayAbsenceText(destination, brief) {
  const days = DATA.serviceDays || [];
  const iso = days[STATE.day];
  const day = { short: shortDay(iso), long: iso ? humanDate(iso) : "" };
  let later = null;
  const answer = serviceAnswer(destination);
  const perDay = DATA.serviceWeek && DATA.serviceWeek[destination.serviceWeekIndex];
  if (perDay) {
    // The next day this station does run on, looked up in that day's table
    // the same way the chosen day is. A day whose table does not name the
    // station is not a day it runs on, so it is passed over.
    for (let index = STATE.day + 1; index < perDay.length; index++) {
      const table = perDay[index];
      if (table && Object.prototype.hasOwnProperty.call(table, destination.crs)) {
        later = days[index];
        break;
      }
    }
  }
  // A row with no week of its own keeps the build's own wording, because there
  // is no chosen day for it to be worded about.
  if (answer === undefined) return absenceText(destination, brief);
  const state = answer === null ? JOURNEY_ABSENCE.no_service : null;
  if (!state) return "";
  const built = state(day, later);
  return built[brief ? "brief" : "full"];
}
