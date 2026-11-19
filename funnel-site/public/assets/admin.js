(function () {
  var $ = function (id) { return document.getElementById(id); };
  var KEY = ""; try { KEY = localStorage.getItem("tnbAdminKey") || ""; } catch (e) {}
  var events = [];
  function api(path, opts) {
    opts = opts || {}; opts.headers = Object.assign({ "x-admin-key": KEY, "content-type": "application/json" }, opts.headers || {});
    return fetch(path, opts);
  }
  function flash(t) { $("flash").textContent = t; }
  function when(ev) {
    return new Intl.DateTimeFormat("en-US", { timeZone: ev.tz, weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" }).format(new Date(ev.startUtc));
  }
  function local(ev) {
    var d = new Date(ev.startUtc), p = {};
    new Intl.DateTimeFormat("en-CA", { timeZone: ev.tz, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })
      .formatToParts(d).forEach(function (x) { p[x.type] = x.value; });
    return { date: p.year + "-" + p.month + "-" + p.day, time: p.hour + ":" + p.minute };
  }
  function download(path, name) {
    api(path).then(function (r) { if (!r.ok) throw new Error(); return r.blob(); }).then(function (b) {
      var a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = name; document.body.appendChild(a); a.click(); a.remove();
    }).catch(function () { flash("Download failed. Try again."); });
  }
  function render() {
    var list = $("list"); list.textContent = "";
    if (!events.length) { list.innerHTML = '<p class="muted">No sessions yet. Add your first one above.</p>'; return; }
    events.forEach(function (ev) {
      var c = document.createElement("div"); c.className = "card";
      var h = document.createElement("strong"); h.textContent = ev.title;
      var m = document.createElement("div"); m.className = "meta";
      m.textContent = when(ev) + " · " + ev.registrations + " registered" + (ev.past ? " · past" : "") + (ev.announcedAt ? " · announced" : "") + (ev.zoomUrl ? "" : " · NO ZOOM LINK YET");
      var b = document.createElement("div"); b.className = "btns";
      function btn(label, fn, cls) { var x = document.createElement("button"); x.type = "button"; x.className = "btn" + (cls ? " " + cls : ""); x.textContent = label; x.addEventListener("click", fn); b.appendChild(x); return x; }
      btn("Edit", function () { edit(ev); });
      btn("Copy share link", function () {
        var link = location.origin + "/?s=" + encodeURIComponent(ev.id);
        (navigator.clipboard ? navigator.clipboard.writeText(link) : Promise.reject()).then(function () { flash("Copied: " + link); }, function () { flash(link); });
      });
      btn("Registrants CSV", function () { download("/api/registrants?id=" + encodeURIComponent(ev.id), "registrants-" + ev.id + ".csv"); });
      if (!ev.past && !ev.announcedAt) {
        var an = btn("Email my list about it", function () {
          if (an.dataset.armed !== "1") { an.dataset.armed = "1"; an.textContent = "Tap again to send"; return; }
          an.disabled = true;
          api("/api/announce", { method: "POST", body: JSON.stringify({ id: ev.id }) }).then(function (r) { return r.json(); }).then(function (j) {
            flash(j.error || ("Sent to " + j.sent + " people." + (j.capped ? " Daily limit reached; the rest go out if you send again tomorrow." : ""))); load();
          });
        });
      }
      var del = btn("Delete", function () {
        if (del.dataset.armed !== "1") { del.dataset.armed = "1"; del.textContent = "Tap again to delete"; return; }
        api("/api/events", { method: "DELETE", body: JSON.stringify({ id: ev.id }) }).then(function () { flash("Deleted."); load(); });
      }, "danger");
      c.append(h, m, b); list.appendChild(c);
    });
  }
  function load() {
    return api("/api/events?admin=1").then(function (r) {
      if (r.status === 401) { $("app").hidden = true; $("login").hidden = false; $("loginErr").textContent = KEY ? "That key didn't work." : ""; return; }
      return r.json().then(function (j) {
        events = j.events; $("login").hidden = true; $("app").hidden = false;
        $("stats").textContent = j.subscribers + " people on your list · " + events.filter(function (e) { return !e.past; }).length + " upcoming";
        render();
      });
    }).catch(function () { flash("Couldn't reach the server."); });
  }
  function reset() {
    $("ev").reset(); $("evId").value = ""; $("time").value = "19:00"; $("durationMin").value = "40";
    $("formHead").textContent = "Add a session"; $("save").textContent = "Post this session"; $("cancel").hidden = true;
  }
  function edit(ev) {
    var l = local(ev);
    $("evId").value = ev.id; $("title").value = ev.title; $("description").value = ev.description || ""; $("date").value = l.date; $("time").value = l.time;
    $("tz").value = ev.tz; $("durationMin").value = ev.durationMin; $("zoomUrl").value = ev.zoomUrl || ""; $("replayUrl").value = ev.replayUrl || "";
    $("formHead").textContent = "Edit session"; $("save").textContent = "Save changes"; $("cancel").hidden = false; window.scrollTo(0, 0);
  }
  $("cancel").addEventListener("click", reset);
  $("login").addEventListener("submit", function (e) {
    e.preventDefault(); KEY = $("key").value.trim();
    try { localStorage.setItem("tnbAdminKey", KEY); } catch (x) {}
    load();
  });
  $("ev").addEventListener("submit", function (e) {
    e.preventDefault();
    document.querySelectorAll("#ev .err").forEach(function (x) { x.textContent = ""; });
    var body = { id: $("evId").value || undefined };
    ["title", "description", "date", "time", "tz", "durationMin", "zoomUrl", "replayUrl"].forEach(function (k) { body[k] = $(k).value; });
    api("/api/events", { method: body.id ? "PUT" : "POST", body: JSON.stringify(body) }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) {
          Object.keys(res.j.fields || {}).forEach(function (k) { var x = document.querySelector('#ev .err[data-f="' + k + '"]'); if (x) x.textContent = res.j.fields[k]; });
          $("evErr").textContent = res.j.error || "Couldn't save."; return;
        }
        flash(body.id ? "Saved." : "Posted. It's live on your page now."); reset(); load();
      });
  });
  $("dlSubs").addEventListener("click", function () { download("/api/registrants", "email-list.csv"); });
  if (KEY) load();
})();
