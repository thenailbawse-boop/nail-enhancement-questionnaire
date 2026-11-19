(function () {
  var $ = function (id) { return document.getElementById(id); };
  var events = [], current = null;
  try { $("tz").value = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (e) {}
  var params = new URLSearchParams(location.search);
  $("ref").value = (params.get("src") || params.get("utm_source") || "").slice(0, 60);

  function fmt(iso, tz, withZone) {
    var d = new Date(iso);
    var day = new Intl.DateTimeFormat("en-US", { timeZone: tz, weekday: "long", month: "long", day: "numeric" }).format(d);
    var time = new Intl.DateTimeFormat("en-US", { timeZone: tz, hour: "numeric", minute: "2-digit", timeZoneName: withZone ? "short" : undefined }).format(d);
    return day + " at " + time;
  }
  function show(ev) {
    current = ev;
    $("eventId").value = ev.id;
    $("title").textContent = ev.title;
    $("sub").textContent = "A free live session on Zoom with Anisia Burroughs, licensed cosmetologist and founder of The Nail Bawse.";
    $("when").textContent = fmt(ev.startUtc, ev.tz, true) + " · " + (ev.durationMin || 45) + " min on Zoom";
    var mine = Intl.DateTimeFormat().resolvedOptions().timeZone;
    $("localwhen").textContent = mine && mine !== ev.tz ? "Your time: " + fmt(ev.startUtc, mine, true) : "";
    $("desc").textContent = ev.description || "";
    document.title = ev.title + " | Free Live Session";
    Array.prototype.forEach.call($("picker").children, function (b) { b.setAttribute("aria-pressed", String(b.dataset.id === ev.id)); });
  }
  fetch("/api/events").then(function (r) { return r.json(); }).then(function (data) {
    events = (data && data.events) || [];
    var wanted = params.get("s");
    if (!events.length) { $("waitlist").hidden = false; $("formtitle").textContent = "Tell me when the next date drops"; $("submit").textContent = "Notify me"; return; }
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
        if (res.ok) { location.href = "/thanks.html?e=" + encodeURIComponent(res.j.eventId) + (res.j.emailed ? "" : "&m=0"); return; }
        var fields = res.j.fields || {};
        Object.keys(fields).forEach(function (k) { var el = document.querySelector('.err[data-for="' + k + '"]'); if (el) el.textContent = fields[k]; });
        document.querySelector('.err[data-for="form"]').textContent = res.j.error || "Something went wrong. Please try again.";
      })
      .catch(function () { document.querySelector('.err[data-for="form"]').textContent = "Couldn't reach the server. Check your connection and try again."; })
      .finally(function () { $("submit").disabled = false; $("submit").textContent = current ? "Save my seat" : "Notify me"; });
  });
})();
