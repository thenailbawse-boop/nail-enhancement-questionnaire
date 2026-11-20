(function () {
  var $ = function (id) { return document.getElementById(id); };
  var events = [], current = null, timer = null, last = {};
  var mine = "";
  try { mine = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; $("tz").value = mine; } catch (e) {}
  var params = new URLSearchParams(location.search);
  $("ref").value = (params.get("src") || params.get("utm_source") || "").slice(0, 60);
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  function fmtParts(iso, tz, o) { return new Intl.DateTimeFormat("en-US", Object.assign({ timeZone: tz }, o)).format(new Date(iso)); }
  function fmt(iso, tz, withZone) {
    return fmtParts(iso, tz, { weekday: "long", month: "long", day: "numeric" }) + " at " +
      fmtParts(iso, tz, { hour: "numeric", minute: "2-digit", timeZoneName: withZone ? "short" : undefined });
  }
  function time(iso, tz) { return fmtParts(iso, tz, { hour: "numeric", minute: "2-digit", timeZoneName: "short" }).replace(":00", ""); }

  // ---------- Ticker ----------
  function setTicker(items) {
    var t = $("ticker"); t.textContent = "";
    for (var r = 0; r < 2; r++) {
      var s = document.createElement("span");
      for (var rep = 0; rep < 2; rep++) items.forEach(function (x, i) { var b = document.createElement(i % 2 ? "b" : "span"); b.textContent = x + " · "; s.appendChild(b); });
      t.appendChild(s);
    }
  }

  // ---------- Flip countdown ----------
  function buildFlip(box) {
    box.textContent = "";
    ["Days", "Hrs", "Min", "Sec"].forEach(function (u, i) {
      if (i) { var c = document.createElement("span"); c.className = "colon"; c.textContent = ":"; box.appendChild(c); }
      var unit = document.createElement("div"); unit.className = "unit";
      var pair = document.createElement("div"); pair.className = "pair";
      for (var k = 0; k < 2; k++) { var d = document.createElement("span"); d.className = "d"; d.textContent = "0"; pair.appendChild(d); }
      var lab = document.createElement("span"); lab.className = "u"; lab.textContent = u;
      unit.appendChild(pair); unit.appendChild(lab); box.appendChild(unit);
    });
  }
  function tick() {
    if (!current) return;
    var ms = new Date(current.startUtc).getTime() - Date.now();
    ["flip1", "flip2"].forEach(function (id) {
      var box = $(id);
      if (ms <= 0) { box.innerHTML = '<p class="livenow">We\'re live now</p>'; return; }
      if (!box.querySelector(".d")) buildFlip(box);
      var s = Math.floor(ms / 1000);
      var str = [Math.min(99, Math.floor(s / 86400)), Math.floor(s % 86400 / 3600), Math.floor(s % 3600 / 60), s % 60]
        .map(function (n) { return String(n).padStart(2, "0"); }).join("");
      var ds = box.querySelectorAll(".d");
      for (var i = 0; i < ds.length; i++) {
        if (ds[i].textContent !== str[i]) {
          ds[i].textContent = str[i];
          if (!reduce && last[id]) { ds[i].classList.remove("flip-in"); void ds[i].offsetWidth; ds[i].classList.add("flip-in"); }
        }
      }
      last[id] = true;
    });
  }

  // ---------- Show a session ----------
  function show(ev) {
    current = ev;
    $("eventId").value = ev.id;
    $("title").textContent = ev.title;
    var zone = mine || ev.tz;
    $("calMonth").textContent = fmtParts(ev.startUtc, zone, { month: "short" });
    $("calDay").textContent = fmtParts(ev.startUtc, zone, { day: "numeric" });
    $("calWeekday").textContent = fmtParts(ev.startUtc, zone, { weekday: "long" });
    $("calTime").textContent = time(ev.startUtc, zone);
    $("when").textContent = fmt(ev.startUtc, ev.tz, true) + " · " + (ev.durationMin || 45) + " min on Zoom";
    $("localwhen").textContent = mine && mine !== ev.tz ? "That's " + fmt(ev.startUtc, mine, true) + " where you are" : "";
    $("whenline").hidden = false;
    $("finalWhen").textContent = fmt(ev.startUtc, zone, true);
    $("menuFoot").textContent = (ev.durationMin || 45) + " min · live on Zoom · bring your phone";
    $("desc").textContent = ev.description || "";
    var zones = $("zones"); zones.textContent = "";
    [["America/Los_Angeles", "PT"], ["America/Denver", "MT"], ["America/Chicago", "CT"], ["America/New_York", "ET"]].forEach(function (z) {
      var s = document.createElement("span"); var b = document.createElement("b");
      b.textContent = fmtParts(ev.startUtc, z[0], { hour: "numeric", minute: "2-digit" }).replace(":00", "");
      s.appendChild(b); s.appendChild(document.createTextNode(" " + z[1]));
      if (fmtParts(ev.startUtc, z[0], { timeZoneName: "short" }) === fmtParts(ev.startUtc, zone, { timeZoneName: "short" })) s.className = "you";
      zones.appendChild(s);
    });
    $("final").hidden = false; $("clockbar").hidden = false;
    setTicker(["Free live class", ev.title, fmtParts(ev.startUtc, ev.tz, { weekday: "short", month: "short", day: "numeric" }), time(ev.startUtc, ev.tz), "Live on Zoom", "Bring your DMs"]);
    document.title = ev.title + " | Free Live Class with The Nail Bawse";
    Array.prototype.forEach.call($("picker").children, function (b) { b.setAttribute("aria-pressed", String(b.dataset.id === ev.id)); });
    tick(); if (!timer) timer = setInterval(tick, 1000);
  }

  setTicker(["Free live class", "Build Your AI Agent", "For beauty pros", "Live on Zoom", "Bring your DMs"]);

  fetch("/api/events").then(function (r) { return r.json(); }).then(function (data) {
    events = (data && data.events) || [];
    var wanted = params.get("s");
    if (!events.length) {
      $("waitlist").hidden = false; $("formtitle").textContent = "Get the next date"; $("submitText").textContent = "Notify me";
      document.querySelectorAll("[data-cta] span, .float-cta").forEach(function (a) { if (!a.children.length) a.textContent = "Notify me"; });
      return;
    }
    $("session").hidden = false;
    if (events.length > 1) {
      events.forEach(function (ev) {
        var b = document.createElement("button");
        b.type = "button"; b.dataset.id = ev.id;
        b.textContent = fmtParts(ev.startUtc, ev.tz, { weekday: "short", month: "short", day: "numeric" });
        b.addEventListener("click", function () { show(ev); });
        $("picker").appendChild(b);
      });
    }
    show(events.find(function (e) { return e.id === wanted; }) || events[0]);
  }).catch(function () { $("waitlist").hidden = false; });

  // ---------- CTAs scroll to form ----------
  document.querySelectorAll("[data-cta]").forEach(function (a) {
    a.addEventListener("click", function (e) { e.preventDefault(); $("reg").scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" }); setTimeout(function () { $("firstName").focus({ preventScroll: true }); }, 450); });
  });

  // ---------- Floating CTA when the form is off screen ----------
  if ("IntersectionObserver" in window) {
    var formSeen = true, heroGone = false;
    var upd = function () { $("floatCta").hidden = formSeen || !heroGone; };
    new IntersectionObserver(function (es) { formSeen = es[0].isIntersecting; upd(); }).observe($("reg"));
    new IntersectionObserver(function (es) { heroGone = !es[0].isIntersecting; upd(); }).observe(document.querySelector(".hero"));
  }

  // ---------- Reveal on scroll + DM demo ----------
  var chatPlayed = false;
  function playChat() {
    if (chatPlayed) return; chatPlayed = true;
    var steps = document.querySelectorAll("#chat [data-step]");
    var at = [200, 1100, 2000, 3600, 4400];
    steps.forEach(function (el, i) {
      setTimeout(function () {
        el.classList.add("show");
        if (el.classList.contains("typing")) setTimeout(function () { el.style.display = "none"; }, 1500);
      }, reduce ? 0 : at[i]);
    });
  }
  document.querySelectorAll(".win").forEach(function (w) { w.classList.add("reveal"); });
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (!e.isIntersecting) return;
        if (e.target.id === "dmPhone") playChat(); else e.target.classList.add("show");
        io.unobserve(e.target);
      });
    }, { threshold: 0.3 });
    io.observe($("dmPhone")); document.querySelectorAll(".reveal").forEach(function (el) { io.observe(el); });
  } else { playChat(); document.querySelectorAll(".reveal").forEach(function (el) { el.classList.add("show"); }); }
  $("approveBtn").addEventListener("click", function () { this.textContent = "Sent ✓"; this.classList.add("sent"); this.previousElementSibling.textContent = "Approved by you"; });

  // ---------- Sticky notes ----------
  var notes = document.querySelectorAll(".note-card");
  notes.forEach(function (n) {
    n.addEventListener("click", function () {
      n.setAttribute("aria-pressed", String(n.getAttribute("aria-pressed") !== "true"));
      var c = document.querySelectorAll('.note-card[aria-pressed="true"]').length;
      $("tally").textContent = c === 0 ? "" : c >= 3 ? "Okay, this class was made for you. Save your seat ↑" : c + " of 5. Sounds like you need an agent.";
    });
  });

  // ---------- Submit ----------
  $("reg").addEventListener("submit", function (e) {
    e.preventDefault();
    document.querySelectorAll(".err").forEach(function (el) { el.textContent = ""; });
    var f = new FormData($("reg"));
    var body = {}; f.forEach(function (v, k) { body[k] = v; });
    body.optIn = $("optIn").checked;
    $("submit").disabled = true; $("submitText").textContent = "Saving…";
    fetch("/api/register", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (res.ok) {
          location.href = (document.documentElement.getAttribute("data-thanks") || "/thanks.html") + "?e=" + encodeURIComponent(res.j.eventId) + (res.j.emailed ? "" : "&m=0") + "&n=" + encodeURIComponent((body.firstName || "").slice(0, 30));
          return;
        }
        var fields = res.j.fields || {};
        if (fields.phone) $("reg").querySelector("details").open = true;
        Object.keys(fields).forEach(function (k) { var el = document.querySelector('.err[data-for="' + k + '"]'); if (el) el.textContent = fields[k]; });
        document.querySelector('.err[data-for="form"]').textContent = res.j.error || "Something went wrong. Please try again.";
      })
      .catch(function () { document.querySelector('.err[data-for="form"]').textContent = "Couldn't reach the server. Check your connection and try again."; })
      .finally(function () { $("submit").disabled = false; $("submitText").textContent = current ? "Save my seat" : "Notify me"; });
  });
})();
