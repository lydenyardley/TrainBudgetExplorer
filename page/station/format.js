// The numbers and the dates the page prints.

// Prices are always two decimal places. The pound sign lines up down the
// column, which is the whole point of a price-first list, and £8.70 is easier
// to compare with £8.65 than £8.70 is with £9.
const money = (pence) => "£" + (pence / 100).toFixed(2);
const duration = (minutes) => {
  if (minutes === null || minutes === undefined) return "-";
  const hours = Math.floor(minutes / 60);
  return hours ? hours + "h " + String(minutes % 60).padStart(2, "0") + "m" : minutes + "m";
};
const clock = (minutes) => {
  const hour = Math.floor(minutes / 60) % 24;
  return String(hour).padStart(2, "0") + ":" + String(minutes % 60).padStart(2, "0");
};

const MONTHS = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];

// Formatted from the ISO string by hand rather than through Date: new
// Date("2026-10-05") is parsed as UTC midnight, which prints as the 4th for any
// reader behind UTC. A copied date that is off by a day is worse than none.
// A row with no service says which day the page is about. The reader
// cannot reach the day the build happened to pick, so a bare "No service"
// beside a station the network serves reads as a fact about the station rather
// than about the date. A station with no service in the coming week has no other
// day to be named, and keeps the bare words.
const SHORT_DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
function shortDay(iso) {
  const parts = String(iso || "").split("-");
  if (parts.length !== 3) return "";
  return SHORT_DAYS[new Date(Date.UTC(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]))).getUTCDay()] || "";
}
function humanDate(iso) {
  const parts = String(iso).split("-").map(Number);
  return parts[2] + " " + MONTHS[parts[1] - 1] + " " + parts[0];
}

// A date the build could not read is left out of the sentence, not printed as
// whatever the formatter makes of it. The reference feed's publication date
// arrives from an HTTP header, and the first version of this line sliced it as
// an ISO timestamp and shipped the words "published undefined undefined NaN" to
// a real reader -- a page making a freshness claim it could not actually make.
// A clause with no readable date is no clause.
function dayPhrase(value) {
  if (!value) return "";
  const text = String(value).slice(0, 10);
  const parts = text.split("-").map(Number);
  if (parts.length !== 3 || parts.some((n) => !Number.isFinite(n))) return "";
  const shown = humanDate(text);
  return shown.includes("undefined") || shown.includes("NaN") ? "" : " " + shown;
}
