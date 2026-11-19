(function () {
  var $ = function (id) { return document.getElementById(id); };
  var events = [], current = null, timer = null;
  var mine = "";
  try { mine = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; $("tz").value = mine; } catch (e) {}
  var params = new URLSearchParams(location.search);
  $("ref").value = (params.get("src") || params.get("utm_source") || "").slice(0, 60);

  function fmt(iso, tz, withZone) {
    var d = new Date(iso);
    var day = new Intl.DateTimeFormat("en-US", { timeZone: tz, weekday: "long", month: "long", day: "numeric" }).format(d);
    var time = new Intl.DateTimeFormat("en-US", { timeZone: tz, hour: "numeric", minute: "2-digit", timeZoneName: withZone ? "short" : undefined }).format(d);
    return day + " at " + time;
  }
  function part(iso, tz, opts) { return new Intl.DateTimeFormat("en-US", Object.assign({ timeZone: tz }, opts)).format(new Date(iso)); }

  // Description: lines that start with "1." / "-" / "•" become the numbered "What you'll learn" list; the rest stays as text.
  function renderLearn(text) {
    var list = $("learnList"), points = [], rest = [];
    list.textContent = "";
    String(text || "").split(/\n+/).forEach(function (line) {
      var m = line.match(/^\s*(?:\d+[.)]|[-•*])\s+(.*)$/);
      if (m && m[1].trim()) points.push(m[1].trim()); else if (line.trim()) rest.push(line.trim());
    });
    points.forEach(function (p) { var li = document.createElement("li"); li.textContent = p; list.appendChild(li); });
    list.hidden = !points.length;
    $("desc").textContent = rest.join("\n");
    $("learn").hidden = !points.length && !rest.length;
  }

  function cell(n, label) {
    var d = document.createElement("div");
    var b = document.createElement("strong"); b.textContent = String(n).padStart(2, "0");
    var s = document.createElement("span"); s.textContent = label;
    d.appendChild(b); d.appendChild(s); return d;
  }
  function tick() {
    if (!current) return;
    var ms = new Date(current.startUtc).getTime() - Date.now();
    ["countdown", "countdown2"].forEach(function (id) {
      var box = $(id); box.textContent = "";
      if (ms <= 0) { var live = document.createElement("p"); live.className = "livenow"; live.textContent = "We're live now"; box.appendChild(live); return; }
      var s = Math.floor(ms / 1000);
      box.appendChild(cell(Math.floor(s / 86400), "Days"));
      box.appendChild(cell(Math.floor(s % 86400 / 3600), "Hrs"));
      box.appendChild(cell(Math.floor(s % 3600 / 60), "Min"));
      box.appendChild(cell(s % 60, "Sec"));
    });
  }

  function show(ev) {
    current = ev;
    $("eventId").value = ev.id;
    $("title").textContent = ev.title;
    $("sub").textContent = "A free live class on Zoom with Anisia Burroughs, licensed cosmetologist and founder of The Nail Bawse.";
    var zone = mine || ev.tz;
    $("calMonth").textContent = part(ev.startUtc, zone, { month: "short" });
    $("calDay").textContent = part(ev.startUtc, zone, { day: "numeric" });
    $("when").textContent = fmt(ev.startUtc, ev.tz, true) + " · " + (ev.durationMin || 45) + " min";
    $("localwhen").textContent = mine && mine !== ev.tz ? "That's " + fmt(ev.startUtc, mine, true) + " where you are" : "";
    $("finalWhen").textContent = fmt(ev.startUtc, zone, true);
    $("final").hidden = false;
    renderLearn(ev.description);
    document.title = ev.title + " | Free Live Class";
    Array.prototype.forEach.call($("picker").children, function (b) { b.setAttribute("aria-pressed", String(b.dataset.id === ev.id)); });
    tick(); if (!timer) timer = setInterval(tick, 1000);
  }

  document.querySelectorAll("[data-cta]").forEach(function (a) {
    a.addEventListener("click", function (e) { e.preventDefault(); $("reg").scrollIntoView({ behavior: "smooth", block: "start" }); setTimeout(function () { $("firstName").focus({ preventScroll: true }); }, 400); });
  });

  fetch("/api/events").then(function (r) { return r.json(); }).then(function (data) {
    events = (data && data.events) || [];
    var wanted = params.get("s");
    if (!events.length) {
      $("waitlist").hidden = false; $("formtitle").textContent = "Tell me when the next date drops"; $("submit").textContent = "Notify me";
      document.querySelectorAll("[data-cta]").forEach(function (a) { a.textContent = "Notify me"; });
      return;
    }
    $("session").hidden = false;
    if (events.length > 1) {
      events.forEach(function (ev) {
        var b = document.createElement("button");
        b.type = "button"; b.dataset.id = ev.id;
        b.textContent = new Intl.DateTimeFormat("en-US", { timeZone: ev.tz, weekday: "short", month: "short", day: "numeric" }).format(new Date(ev.startUtc));
        b.addEventListener("click", function () { show(ev); });
        $("picker").appendChild(b);
      });
    }
    show(events.find(function (e) { return e.id === wanted; }) || events[0]);
  }).catch(function () { $("waitlist").hidden = false; });

  $("reg").addEventListener("submit", function (e) {
    e.preventDefault();
    document.querySelectorAll(".err").forEach(function (el) { el.textContent = ""; });
    var f = new FormData($("reg"));
    var body = {}; f.forEach(function (v, k) { body[k] = v; });
    body.optIn = $("optIn").checked;
    $("submit").disabled = true; $("submit").textContent = "Saving…";
    fetch("/api/register", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (res.ok) {
          var q = "?e=" + encodeURIComponent(res.j.eventId) + (res.j.emailed ? "" : "&m=0") + "&n=" + encodeURIComponent((body.firstName || "").slice(0, 30));
          location.href = "/thanks.html" + q; return;
        }
        var fields = res.j.fields || {};
        if (fields.phone) $("reg").querySelector("details").open = true;
        Object.keys(fields).forEach(function (k) { var el = document.querySelector('.err[data-for="' + k + '"]'); if (el) el.textContent = fields[k]; });
        document.querySelector('.err[data-for="form"]').textContent = res.j.error || "Something went wrong. Please try again.";
      })
      .catch(function () { document.querySelector('.err[data-for="form"]').textContent = "Couldn't reach the server. Check your connection and try again."; })
      .finally(function () { $("submit").disabled = false; $("submit").textContent = current ? "Save my seat" : "Notify me"; });
  });
})();
