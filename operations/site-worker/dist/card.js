/* The Nail Bawse appointment card as a 1080x1920 story picture.
   It redraws the card shown on the thank-you page (same layout, colors and type).
   NBCard.draw({ name, title, date, time }) -> Promise<HTMLCanvasElement> */
(function () {
  var C = { espresso: "#3B2621", ink: "#2A1A15", cream: "#FBF6F1", paper: "#FFFDFB", pink: "#F4A6C4", rose: "#A24D6E", muted: "#76605A", line: "#E7D8CE" };
  var SERIF = "Fraunces, Georgia, serif", SANS = "Inter, Arial, sans-serif", HAND = "Caveat, 'Segoe Print', cursive";

  function fontsReady() {
    if (!document.fonts || !document.fonts.load) return Promise.resolve();
    return Promise.all(["400 100px Fraunces", "italic 400 100px Fraunces", "italic 600 100px Fraunces", "700 100px Caveat", "800 40px Inter"]
      .map(function (f) { return document.fonts.load(f).catch(function () {}); })).then(function () { return document.fonts.ready; });
  }
  function rr(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
  function caps(g, text, x, y, sp, align) {
    var w = 0, i; for (i = 0; i < text.length; i++) w += g.measureText(text[i]).width + (i < text.length - 1 ? sp : 0);
    var cx = align === "center" ? x - w / 2 : align === "right" ? x - w : x;
    var ta = g.textAlign; g.textAlign = "left";
    for (i = 0; i < text.length; i++) { g.fillText(text[i], cx, y); cx += g.measureText(text[i]).width + sp; }
    g.textAlign = ta; return w;
  }
  function fit(g, text, font, size, max, min) { do { g.font = font.replace("{s}", size); if (g.measureText(text).width <= max) break; size -= 2; } while (size > min); return size; }

  function draw(d) {
    return fontsReady().then(function () {
      var c = document.createElement("canvas"); c.width = 1080; c.height = 1920;
      var g = c.getContext("2d");

      // Page background: cream with the site's dot grid
      g.fillStyle = C.cream; g.fillRect(0, 0, 1080, 1920);
      g.fillStyle = "rgba(59,38,33,.08)";
      for (var x = 22; x < 1080; x += 44) for (var y = 22; y < 1920; y += 44) { g.beginPath(); g.arc(x, y, 2.6, 0, 7); g.fill(); }

      // Brand line + headline, as on the thank-you page
      g.font = "800 30px " + SANS; var bw = 76 + 20 + caps({ measureText: g.measureText.bind(g), fillText: function () {}, textAlign: "left" }, "THE NAIL BAWSE", 0, 0, 6);
      var bx = 540 - bw / 2;
      g.fillStyle = C.espresso; rr(g, bx, 150, 76, 76, 18); g.fill();
      g.fillStyle = C.cream; g.textAlign = "center"; g.font = "italic 400 38px " + SERIF; g.fillText("NB", bx + 38, 202);
      g.textAlign = "left"; g.fillStyle = C.ink; g.font = "800 30px " + SANS; caps(g, "THE NAIL BAWSE", bx + 96, 198, 6);
      g.font = "400 150px " + SERIF; var w1 = g.measureText("You're ").width;
      g.font = "italic 400 150px " + SERIF; var w2 = g.measureText("booked.").width;
      var sx = 540 - (w1 + w2) / 2;
      g.fillStyle = C.ink; g.font = "400 150px " + SERIF; g.fillText("You're ", sx, 410);
      g.fillStyle = C.rose; g.font = "italic 400 150px " + SERIF; g.fillText("booked.", sx + w1, 410);

      // ---- The appointment card ----
      var W = 900, H = 960, X = -W / 2, P = 56;
      g.save(); g.translate(540, 520); g.rotate(-0.028);
      g.fillStyle = C.espresso; rr(g, X + 26, 26, W, H, 52); g.fill();          // offset shadow, as on the page
      g.fillStyle = C.paper; rr(g, X, 0, W, H, 52); g.fill();
      g.strokeStyle = C.espresso; g.lineWidth = 5; rr(g, X, 0, W, H, 52); g.stroke();

      // header
      g.fillStyle = C.espresso; rr(g, X + P, 50, 84, 84, 22); g.fill();
      g.fillStyle = C.cream; g.textAlign = "center"; g.font = "italic 400 40px " + SERIF; g.fillText("NB", X + P + 42, 106);
      g.textAlign = "left"; g.fillStyle = C.ink; g.font = "italic 600 62px " + SERIF; g.fillText("The Nail Bawse", X + P + 112, 104);
      g.fillStyle = C.muted; g.font = "800 24px " + SANS; caps(g, "APPOINTMENT CARD", X + P + 114, 142, 6);
      g.save(); g.translate(-X - P - 70, 92); g.rotate(0.07);
      g.fillStyle = C.pink; rr(g, -70, -38, 140, 76, 16); g.fill();
      g.fillStyle = C.espresso; g.textAlign = "center"; g.font = "700 60px " + HAND; g.fillText("Free", 0, 20); g.restore();
      g.fillStyle = C.espresso; g.fillRect(X + P, 178, W - 2 * P, 5);

      // rows
      var rows = [["FOR", d.name || "You"], ["SERVICE", d.title || "Build Your AI Agent"], ["DATE", d.date || ""], ["TIME", d.time || ""], ["WITH", "Anisia"]];
      rows.forEach(function (r, i) {
        var ry = 290 + i * 122;
        g.fillStyle = C.muted; g.font = "800 25px " + SANS; g.textAlign = "left"; caps(g, r[0], X + P + 4, ry, 5);
        var s = fit(g, r[1], "700 {s}px " + HAND, 80, W - 2 * P - 200, 44);
        g.fillStyle = C.rose; g.font = "700 " + s + "px " + HAND; g.fillText(r[1], X + P + 196, ry + 8);
        g.strokeStyle = C.line; g.lineWidth = 4; g.setLineDash([14, 10]); g.beginPath(); g.moveTo(X + P, ry + 40); g.lineTo(-X - P, ry + 40); g.stroke(); g.setLineDash([]);
      });

      // footer
      g.fillStyle = C.ink; g.font = "800 25px " + SANS;
      caps(g, "LIVE ON GOOGLE MEET", X + P + 4, H - 56, 6); caps(g, "@THENAILBAWSE", -X - P - 4, H - 56, 6, "right");

      // stamp
      g.save(); g.translate(-X - P - 190, H - 200); g.rotate(-0.24); g.globalAlpha = .88;
      g.strokeStyle = C.rose; g.lineWidth = 7; rr(g, -190, -52, 380, 96, 16); g.stroke();
      g.fillStyle = C.rose; g.font = "800 50px " + SANS; caps(g, "CONFIRMED", 0, 18, 8, "center"); g.restore();
      g.restore();

      // ---- Tag line ----
      g.textAlign = "center"; g.fillStyle = C.rose; g.font = "700 72px " + HAND; g.fillText("free live class with Anisia", 540, 1640);
      g.fillStyle = C.espresso; rr(g, 230, 1700, 620, 104, 52); g.fill();
      g.fillStyle = C.pink; g.font = "800 38px " + SANS; caps(g, "TAG @THENAILBAWSE", 540, 1766, 5, "center");
      return c;
    });
  }
  window.NBCard = { draw: draw };
})();
