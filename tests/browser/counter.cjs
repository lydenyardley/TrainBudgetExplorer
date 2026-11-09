/**
 * The visit counter is a request the page does not need.
 *
 * A published page loads GoatCounter's script from this site and sends one
 * count. Two failures are the ones worth proving, because both are how a
 * reader actually meets the counter: the script does not arrive, and the
 * count is refused. Either way the page is the same page. The count that
 * does leave carries `ref` and not the search, which is the venue tag the
 * launch checklist asks for and not the budget the privacy page says stays.
 *
 * One page per run. The snippet is the same on every route, and a sweep that
 * repeated the two loads would be timing the counter rather than the page.
 */
async function checkTheCounter({ page, context, url, check }) {
  if (checkTheCounter.done) return;
  const present = await page.evaluate(
    () => !!document.querySelector("script[data-goatcounter]")
  );
  if (!present) return;
  checkTheCounter.done = true;

  const blocked = await context.newPage();
  try {
    await blocked.route("**/goatcounter-count.js", (route) => route.abort());
    await blocked.goto(url);
    const heading = await blocked.locator("h1").textContent();
    check(
      "the page still shows its heading when the counter script is blocked",
      Boolean(heading && heading.trim()),
      String(heading)
    );
    if (await blocked.locator("#budgetNumber").count()) {
      await blocked.locator("#budgetNumber").fill("30");
      const value = await blocked.locator("#budgetNumber").inputValue();
      check(
        "the budget still changes when the counter script is blocked",
        value === "30",
        value
      );
    }
  } finally {
    await blocked.close();
  }

  const counting = await context.newPage();
  try {
    await counting.route("**://trainbudgetexplorer.goatcounter.com/**", (route) => route.abort());
    const joined = url + (url.includes("?") ? "&" : "?") + "ref=venue&budget=25&card=YNG";
    await counting.goto(joined);
    const carried = await counting.evaluate(() =>
      Array.from(document.querySelectorAll("a[href]"))
        .filter((link) => {
          try { return new URL(link.href).origin === location.origin; }
          catch (error) { return false; }
        })
        .every((link) => new URL(link.href).searchParams.get("ref") === "venue")
    );
    check(
      "a link on this page keeps ref for the next page's count",
      carried,
      "an internal link dropped ref"
    );
    let sent = "";
    let ok = false;
    try {
      const seen = counting.waitForRequest(
        (request) => request.url().includes("trainbudgetexplorer.goatcounter.com/count"),
        { timeout: 5000 }
      );
      await counting.evaluate(() => {
        if (!window.goatcounter || typeof window.goatcounter.count !== "function") return;
        // The suite serves the page from 127.0.0.1, which the script refuses
        // to count. The published host is not a local address.
        window.goatcounter.allow_local = true;
        window.goatcounter.count();
      });
      const countUrl = new URL((await seen).url());
      // `q` is the campaign query GoatCounter reads. The host name contains
      // the word budget, so the check is the parameter, not a substring.
      sent = "q=" + countUrl.searchParams.get("q") + " p=" + countUrl.searchParams.get("p");
      ok = countUrl.searchParams.get("q") === "?ref=venue"
        && !(countUrl.searchParams.get("p") || "").includes("?")
        && !countUrl.searchParams.has("budget")
        && !countUrl.searchParams.has("card");
    } catch (error) {
      sent = "no count request (" + error.message + ")";
    }
    check(
      "the count sends ref and not the search",
      ok,
      sent
    );
    const still = await counting.locator("h1").textContent();
    check(
      "the page still shows its heading when the count is blocked",
      Boolean(still && still.trim()),
      String(still)
    );
    if (await counting.locator("#budgetNumber").count()) {
      await counting.locator("#budgetNumber").fill("40");
      const value = await counting.locator("#budgetNumber").inputValue();
      check(
        "the budget still changes when the count is blocked",
        value === "40",
        value
      );
    }
  } finally {
    await counting.close();
  }
}

module.exports = { checkTheCounter };
