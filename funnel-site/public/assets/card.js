/* The Nail Bawse appointment card: a 1080x1920 story graphic drawn on a canvas.
   NBCard.draw({ title, when, name }) -> Promise<HTMLCanvasElement> */
(function () {
  var C = { espresso: "#3B2621", ink: "#2A1A15", cream: "#FFFDFB", pink: "#F4A6C4", pink2: "#F9C9DB", rose: "#A24D6E", muted: "#8A736B", line: "#E7D8CE" };
  var SERIF = "Fraunces, Georgia, serif", SANS = "Inter, Arial, sans-serif", HAND = "Caveat, 'Segoe Print', cursive";

  var POLISH = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 150"><defs>' +
    '<linearGradient id="p" x1="0" x2="1"><stop offset="0" stop-color="#F7BFD4"/><stop offset=".55" stop-color="#F4A6C4"/><stop offset="1" stop-color="#D9799F"/></linearGradient>' +
    '<linearGradient id="c" x1="0" x2="1"><stop offset="0" stop-color="#5A3A31"/><stop offset=".5" stop-color="#3B2621"/><stop offset="1" stop-color="#24150F"/></linearGradient></defs>' +
    '<rect x="27" y="4" width="26" height="58" rx="5" fill="url(#c)"/><rect x="31" y="8" width="4" height="48" rx="2" fill="#fff" opacity=".18"/>' +
    '<rect x="22" y="58" width="36" height="10" rx="3" fill="#2A1A15"/>' +
    '<path d="M14 76 Q14 66 26 66 H54 Q66 66 66 76 V132 Q66 146 52 146 H28 Q14 146 14 132 Z" fill="url(#p)"/>' +
    '<path d="M21 78 Q21 72 28 72 H33 V138 H28 Q21 138 21 130 Z" fill="#fff" opacity=".35"/>' +
    '<rect x="25" y="96" width="30" height="22" rx="3" fill="#FFF8F2" opacity=".85"/>' +
    '<text x="40" y="111" text-anchor="middle" font-family="Georgia,serif" font-style="italic" font-size="10" fill="#3B2621">NB</text></svg>';

  function img(src) { return new Promise(function (ok) { var i = new Image(); i.onload = function () { ok(i); }; i.onerror = function () { ok(null); }; i.src = src; }); }
  function fontsReady() {
    if (!document.fonts || !document.fonts.load) return Promise.resolve();
    return Promise.all(["600 100px Fraunces", "italic 600 100px Fraunces", "700 100px Caveat", "800 40px Inter", "600 40px Inter"]
      .map(function (f) { return document.fonts.load(f).catch(function () {}); })).then(function () { return document.fonts.ready; });
  }
  function rr(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
  function spaced(g, text, x, y, sp, align) {
    var w = 0, i; for (i = 0; i < text.length; i++) w += g.measureText(text[i]).width + (i < text.length - 1 ? sp : 0);
    var cx = align === "center" ? x - w / 2 : align === "right" ? x - w : x;
    var ta = g.textAlign; g.textAlign = "left";
    for (i = 0; i < text.length; i++) { g.fillText(text[i], cx, y); cx += g.measureText(text[i]).width + sp; }
    g.textAlign = ta;
  }
  function fit(g, text, font, size, max, min) { do { g.font = font.replace("{s}", size); if (g.measureText(text).width <= max) break; size -= 2; } while (size > min); return size; }
  function star(g, x, y, r, color) {
    g.save(); g.translate(x, y); g.fillStyle = color; g.beginPath();
    g.moveTo(0, -r); g.quadraticCurveTo(r * .12, -r * .12, r, 0); g.quadraticCurveTo(r * .12, r * .12, 0, r);
    g.quadraticCurveTo(-r * .12, r * .12, -r, 0); g.quadraticCurveTo(-r * .12, -r * .12, 0, -r); g.fill(); g.restore();
  }
  // Split a title into one or two balanced lines that fit
  function titleLines(g, t, max) {
    g.font = "600 112px " + SERIF;
    if (g.measureText(t.toUpperCase()).width <= max) return [t];
    var w = t.split(" "), best = [t], bestDiff = 1e9;
    for (var i = 1; i < w.length; i++) {
      var a = w.slice(0, i).join(" "), b = w.slice(i).join(" ");
      var d = Math.abs(g.measureText(a.toUpperCase()).width - g.measureText(b.toUpperCase()).width);
      if (d < bestDiff) { bestDiff = d; best = [a, b]; }
    }
    return best;
  }

  function draw(data) {
    return Promise.all([fontsReady(), img("data:image/svg+xml;charset=utf-8," + encodeURIComponent(POLISH))]).then(function (r) {
      var polish = r[1];
      var c = document.createElement("canvas"); c.width = 1080; c.height = 1920;
      var g = c.getContext("2d");

      // Background: blush gradient, ruled lines, sparkles
      var bg = g.createLinearGradient(0, 0, 0, 1920); bg.addColorStop(0, "#F8D7E3"); bg.addColorStop(1, "#FCEFF3");
      g.fillStyle = bg; g.fillRect(0, 0, 1080, 1920);
      g.strokeStyle = "rgba(162,77,110,.09)"; g.lineWidth = 2;
      for (var y = 70; y < 1920; y += 64) { g.beginPath(); g.moveTo(0, y); g.lineTo(1080, y); g.stroke(); }
      star(g, 150, 210, 26, C.pink); star(g, 930, 250, 18, C.rose); star(g, 980, 1630, 24, C.pink); star(g, 110, 1560, 14, C.rose);

      // Top line
      g.textAlign = "center"; g.fillStyle = C.rose; g.font = "700 92px " + HAND;
      g.fillText("tag @thenailbawse", 540, 300);

      // Ribbon + clip
      g.lineCap = "round";
      [[300, 380], [780, 380]].forEach(function (p) {
        g.strokeStyle = C.espresso; g.lineWidth = 50; g.beginPath(); g.moveTo(p[0], p[1]); g.quadraticCurveTo((p[0] + 540) / 2, 470, 540, 560); g.stroke();
        g.strokeStyle = C.pink; g.lineWidth = 36; g.beginPath(); g.moveTo(p[0], p[1]); g.quadraticCurveTo((p[0] + 540) / 2, 470, 540, 560); g.stroke();
      });
      g.fillStyle = C.espresso; rr(g, 490, 530, 100, 64, 18); g.fill();
      g.fillStyle = "rgba(255,255,255,.18)"; rr(g, 502, 540, 30, 44, 10); g.fill();

      // Card
      g.save(); g.translate(540, 580); g.rotate(-0.025);
      var W = 880, H = 1000, X = -W / 2;
      g.save(); g.shadowColor = "rgba(42,26,21,.28)"; g.shadowBlur = 60; g.shadowOffsetY = 34;
      g.fillStyle = C.cream; rr(g, X, 0, W, H, 46); g.fill(); g.restore();
      // header band
      g.save(); rr(g, X, 0, W, H, 46); g.clip();
      g.fillStyle = C.espresso; g.fillRect(X, 0, W, 250);
      g.fillStyle = C.pink; g.fillRect(X, 250, W, 10);
      g.restore();
      g.strokeStyle = C.espresso; g.lineWidth = 8; rr(g, X, 0, W, H, 46); g.stroke();
      // slot
      g.fillStyle = C.pink2; rr(g, -56, 28, 112, 30, 15); g.fill();
      // header text
      g.textAlign = "left"; g.fillStyle = C.pink; g.font = "800 34px " + SANS; spaced(g, "THE NAIL BAWSE", X + 62, 116, 9);
      var hs = fit(g, "Appointment", "italic 600 {s}px " + SERIF, 104, 560, 70);
      var hg = g.createLinearGradient(X + 60, 120, X + 620, 220); hg.addColorStop(0, "#FCE1EB"); hg.addColorStop(.5, C.pink); hg.addColorStop(1, "#E58BAE");
      g.fillStyle = hg; g.font = "italic 600 " + hs + "px " + SERIF; g.fillText("Appointment", X + 58, 206);
      // seal
      var sx = W / 2 - 135, sy = 128;
      g.strokeStyle = C.pink; g.lineWidth = 6; g.beginPath(); g.arc(sx, sy, 78, 0, 7); g.stroke();
      g.lineWidth = 2.5; g.beginPath(); g.arc(sx, sy, 62, 0, 7); g.stroke();
      g.fillStyle = C.pink; g.textAlign = "center"; g.font = "italic 600 60px " + SERIF; g.fillText("NB", sx, sy + 20);

      // body
      g.textAlign = "center"; g.fillStyle = C.rose; g.font = "700 100px " + HAND;
      g.fillText((data.name ? data.name + " is" : "I'm") + " booked for", 0, 395);
      var lines = titleLines(g, data.title || "Build Your AI Agent", 760), ty = lines.length === 1 ? 535 : 500;
      lines.forEach(function (l, i) {
        var s = fit(g, l.toUpperCase(), "600 {s}px " + SERIF, 112, 780, 60);
        g.fillStyle = C.ink; g.font = "600 " + s + "px " + SERIF; g.fillText(l.toUpperCase(), 0, ty + i * 112);
      });
      var by = lines.length === 1 ? 690 : 735;
      // WHEN
      g.textAlign = "left"; g.fillStyle = C.muted; g.font = "800 30px " + SANS; spaced(g, "WHEN:", X + 80, by, 3);
      var ws = fit(g, data.when, "700 {s}px " + HAND, 84, 600, 46);
      g.fillStyle = C.rose; g.font = "700 " + ws + "px " + HAND; g.fillText(data.when, X + 210, by + 6);
      g.strokeStyle = "#CDBDB5"; g.lineWidth = 3; g.setLineDash([16, 12]); g.beginPath(); g.moveTo(X + 80, by + 34); g.lineTo(-X - 80, by + 34); g.stroke(); g.setLineDash([]);
      // Signature
      var sy2 = H - 120;
      g.fillStyle = C.espresso; g.font = "700 96px " + HAND; g.fillText("Anisia", X + 90, sy2 - 26);
      g.strokeStyle = "#9C8A83"; g.lineWidth = 3; g.beginPath(); g.moveTo(X + 80, sy2); g.lineTo(X + 470, sy2); g.stroke();
      g.fillStyle = C.muted; g.font = "700 26px " + SANS; spaced(g, "YOUR TEACHER", X + 82, sy2 + 42, 3);
      // Stamp
      g.save(); g.translate(W / 2 - 215, H - 150); g.rotate(-0.18);
      g.globalAlpha = .9; g.strokeStyle = C.rose; g.lineWidth = 9; rr(g, -170, -62, 340, 112, 18); g.stroke();
      g.fillStyle = C.rose; g.textAlign = "center"; g.font = "800 60px " + SANS; spaced(g, "BOOKED", 0, 18, 6, "center");
      g.restore();
      g.restore();

      // Polish bottle peeking at the card corner
      if (polish) { g.save(); g.translate(150, 1500); g.rotate(-0.28); g.shadowColor = "rgba(42,26,21,.3)"; g.shadowBlur = 24; g.shadowOffsetY = 12; g.drawImage(polish, -60, -112, 120, 225); g.restore(); }

      // Footer
      g.textAlign = "center"; g.fillStyle = C.ink; g.font = "600 46px " + SANS; g.fillText("Free live class with The Nail Bawse", 540, 1730);
      g.fillStyle = C.rose; g.font = "800 32px " + SANS; spaced(g, "BRING YOUR DMS · LIVE ON ZOOM", 540, 1800, 6, "center");
      return c;
    });
  }
  window.NBCard = { draw: draw };
})();
