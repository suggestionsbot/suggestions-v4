/* Localise <t:...> timestamps to the viewer's time zone and handle spoilers
   (click, Enter or Space to reveal). Safe to include more than once. */
(function () {
  if (window.__dcComponentsLoaded) return;
  window.__dcComponentsLoaded = true;
  // With JS present, focus alone no longer reveals spoilers (see CSS).
  document.documentElement.classList.add("dc-js");

  // The viewer's own locale (what Discord uses), not the page's <html lang>,
  // which says what language the page is written in. Override with
  // <html data-dc-locale="en-NZ"> if needed.
  var lang = document.documentElement.getAttribute("data-dc-locale")
    || (navigator.languages && navigator.languages[0]) || navigator.language || "en-US";
  var formats = {
    t: { hour: "numeric", minute: "2-digit" },
    T: { hour: "numeric", minute: "2-digit", second: "2-digit" },
    d: { year: "numeric", month: "2-digit", day: "2-digit" },
    D: { year: "numeric", month: "long", day: "numeric" },
    f: { year: "numeric", month: "long", day: "numeric", hour: "numeric", minute: "2-digit" },
    F: { weekday: "long", year: "numeric", month: "long", day: "numeric", hour: "numeric", minute: "2-digit" },
    S: { dateStyle: "short", timeStyle: "short" }
  };
  // Discord's 12/24-hour clock is a user setting, not a locale default:
  // <html data-dc-hour-cycle="h23"> (24h) or "h12" overrides the locale.
  var hourCycle = document.documentElement.getAttribute("data-dc-hour-cycle");
  if (hourCycle === "h23" || hourCycle === "h12") {
    for (var k in formats) {
      if (k === "S") { formats[k] = { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: hourCycle }; }
      else if (formats[k].hour) { formats[k].hourCycle = hourCycle; }
    }
  }
  var units = [
    ["year", 31536000], ["month", 2592000], ["day", 86400],
    ["hour", 3600], ["minute", 60], ["second", 1]
  ];

  // Formatters are expensive to construct; build each once.
  var cache = {};
  function dateFormatter(style) {
    var key = formats[style] ? style : "f";
    if (!cache[key]) cache[key] = new Intl.DateTimeFormat(lang, formats[key]);
    return cache[key];
  }
  function relativeFormatter() {
    if (!cache.R) cache.R = new Intl.RelativeTimeFormat(lang, { numeric: "always" });
    return cache.R;
  }

  function relative(date) {
    var diff = (date.getTime() - Date.now()) / 1000;
    var abs = Math.abs(diff);
    for (var i = 0; i < units.length; i++) {
      if (abs >= units[i][1] || units[i][0] === "second") {
        return relativeFormatter().format(Math.round(diff / units[i][1]), units[i][0]);
      }
    }
  }

  function render(el) {
    var ts = parseInt(el.getAttribute("data-dc-ts"), 10);
    if (isNaN(ts)) return;
    var date = new Date(ts * 1000);
    if (isNaN(date.getTime())) return;
    var style = el.getAttribute("data-dc-style") || "f";
    try {
      el.textContent = style === "R" ? relative(date) : dateFormatter(style).format(date);
      el.title = dateFormatter("F").format(date);
    } catch (e) { /* keep server-rendered text */ }
  }

  function renderAll(selector) {
    var nodes = document.querySelectorAll(selector);
    for (var i = 0; i < nodes.length; i++) render(nodes[i]);
  }

  var SPOILER = ".dc-spoiler, .dc-spoiler-media, .dc-spoiler-block";
  function reveal(event) {
    var target = event.target && event.target.closest && event.target.closest(SPOILER);
    if (target && !target.classList.contains("dc-revealed")) {
      target.classList.add("dc-revealed");
      event.preventDefault();
      event.stopPropagation();
    }
  }
  document.addEventListener("click", reveal, true);
  document.addEventListener("keydown", function (event) {
    if (event.key === "Enter" || event.key === " ") reveal(event);
  }, true);

  function start() { renderAll("time.dc-timestamp[data-dc-ts]"); }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
  setInterval(function () {
    if (!document.hidden) renderAll('time.dc-timestamp[data-dc-style="R"]');
  }, 30000);
})();
