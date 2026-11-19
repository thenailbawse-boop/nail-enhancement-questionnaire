// One screen: set your brand once, drop a video, it cleans by itself, tap an effect.
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
async function api(path, opts) {
  const r = await fetch(path, opts);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || "Something went wrong.");
  return d;
}

/* ---------- your brand ---------- */
let brand = {};
function drawSample() {
  const f = $("bFont").value, c = $("bAccent").value;
  $("fontSample").style.fontFamily = `'fp-${f}'`;
  $("fontSample").querySelector("b").style.color = c;
  // a dark brand color vanishes on the navy strip, so the strip flips to white for it
  const [r, g, b] = [1, 3, 5].map(i => parseInt(c.slice(i, i + 2), 16));
  const dark = 0.299 * r + 0.587 * g + 0.114 * b < 110;
  $("fontSample").style.background = dark ? "#fff" : "";
  $("fontSample").style.color = dark ? "var(--text)" : "";
  $("fontSample").style.boxShadow = dark ? "inset 0 0 0 1.5px var(--line)" : "";
}
function only(id) { ["bAsk", "bYes", "bNo"].forEach(x => $(x).hidden = x !== id); }
function showForm(open) {
  $("brandForm").hidden = !open;
  $("brandToggle").hidden = open;
  // 2026-11-05, Tiff: once a brand is set, the box leaves the page. A new person still sees it to set theirs
  $("brand").hidden = !open;
  ["bAsk", "bYes", "bNo", "bFound"].forEach(x => $(x).hidden = true);
  $("brandSum").innerHTML = open ? "It saves by itself." :
    `<span style="display:inline-block;width:14px;height:14px;border-radius:4px;vertical-align:-2px;background:#${esc(brand.accent)}"></span> ${esc(brand.name)}, set on every video.`;
}
// everything saves as they go. Nobody hunts for a Save button, and a closed tab loses nothing
let saving = null;
function autoSave() {
  clearTimeout(saving);
  saving = setTimeout(async () => {
    try {
      await api("/api/brand", { method: "POST", body: JSON.stringify({ name: $("bName").value.trim(), accent: $("bAccent").value, font: $("bFont").value, cta: $("bCta").value.trim() }) });
      brand = { ...brand, cta: $("bCta").value.trim(), name: $("bName").value.trim(), accent: $("bAccent").value.slice(1).toUpperCase(), font: $("bFont").value };
      $("bNote").textContent = "Saved.";
    } catch (e) { $("bNote").innerHTML = `<span class="err">${esc(e.message)}</span>`; }
  }, 400);
}
/* Yes, I have one: read it, then ask only for what we couldn't read */
function showFound(d) {
  const color = d.accent && d.accent.toUpperCase() !== "#FFFFFF";
  // a video with no words on it gives the font finder nothing to measure, and its answer is only the default
  const font = brand.fonts.includes(d.font) && d.font_measured_lines !== 0;
  if (color) $("bAccent").value = d.accent.toLowerCase();
  if (font) $("bFont").value = d.font;
  if (d.name) $("bName").value = d.name;
  if (d.logo) { brand.has_logo = true; drawLogo(); }
  drawSample();
  $("bYes").hidden = true;
  $("brandForm").hidden = false;
  $("rowColor").style.display = color ? "none" : "";
  const got = [d.name && "your name", color && "your color", font && "your font", d.logo && "your logo"].filter(Boolean);
  const need = [!d.name && !$("bName").value && "your name", !color && "your color", !font && "your font"].filter(Boolean);
  $("bFound").hidden = false;
  $("bFound").textContent = (got.length ? `We got ${got.join(", ")}. Change anything that's off. ` : "") +
    (need.length ? `We still need ${need.join(" and ")}.` : "") + (d.logo ? "" : " Add your logo if you have one.");
  autoSave();
  if (!$("bName").value) $("bName").focus();
}
function brandError(msg) { $("bFound").hidden = false; $("bFound").textContent = msg; }
$("bHave").onclick = () => { only("bYes"); $("bLink").focus(); };
$("bNeed").onclick = $("bSwitchNo").onclick = () => { only("bNo"); $("bFound").hidden = true; drawFeel(); };
$("bLinkGo").onclick = async () => {
  if (!$("bLink").value.trim()) { brandError("Paste your link first."); return; }
  $("bLinkGo").disabled = true;
  brandError("Looking... this takes up to 30 seconds.");
  const ig = /instagram\.com/i.test($("bLink").value);
  try { showFound(await api(ig ? "/api/brand-link" : "/api/brand-site", { method: "POST", body: JSON.stringify({ link: $("bLink").value }) })); }
  catch (e) { brandError(ig ? "We couldn't read that. Check your account is public, or drop in one of your videos." : e.message); }
  $("bLinkGo").disabled = false;
};
function brandVideo(f) {
  brandError("Looking at your video... about 30 seconds.");
  const x = new XMLHttpRequest();
  x.open("POST", "/api/brand-video");
  x.setRequestHeader("X-File-Name", encodeURIComponent(f.name));
  x.onerror = () => brandError("That didn't upload. Try again.");
  x.onload = () => {
    const d = JSON.parse(x.responseText || "{}");
    if (x.status === 200) showFound(d); else brandError(d.error || "That didn't work. Try another video.");
  };
  x.send(f);
}
$("bDrop").onclick = () => $("bVid").click();
$("bDrop").onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("bVid").click(); } };
$("bDrop").ondragover = e => { e.preventDefault(); $("bDrop").classList.add("on"); };
$("bDrop").ondragleave = () => $("bDrop").classList.remove("on");
$("bDrop").ondrop = e => { e.preventDefault(); $("bDrop").classList.remove("on"); if (e.dataTransfer.files[0]) brandVideo(e.dataTransfer.files[0]); };
$("bVid").onchange = () => { if ($("bVid").files[0]) brandVideo($("bVid").files[0]); $("bVid").value = ""; };
/* No, help me make one: a few taps, no typing a prompt */
const FEELS = {
  "Calm and premium": { font: "Elegant Serif", colors: ["#12355B", "#9A7B2F", "#5B2A86"] },
  "Bold and loud": { font: "Tall", colors: ["#E11D2E", "#FF5A00", "#0A5CFF"] },
  "Warm and friendly": { font: "Clean", colors: ["#E8604C", "#C65D3B", "#E75480"] },
  "Clean and modern": { font: "Simple", colors: ["#0A5CFF", "#0F9D8A", "#334155"] },
  "Fun and playful": { font: "Bold Caps", colors: ["#FF2D78", "#8B2CF5", "#12B76A"] },
};
function drawFeel() {
  $("bFeel").innerHTML = Object.keys(FEELS).map(k => `<button class="ghost" data-k="${esc(k)}">${esc(k)}</button>`).join("");
  $("bFeel").querySelectorAll("button").forEach(b => b.onclick = () => {
    const feel = FEELS[b.dataset.k];
    if (brand.fonts.includes(feel.font)) $("bFont").value = feel.font;
    $("bFeel").querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b));
    $("bPick").hidden = false;
    $("bSwatches").innerHTML = feel.colors.map(c => `<button class="ez-swatch" style="background:${c}" data-c="${c}" aria-label="Pick ${c}"></button>`).join("");
    $("bSwatches").querySelectorAll("button").forEach(s => s.onclick = () => {
      $("bAccent").value = s.dataset.c.toLowerCase();
      drawSample();
      $("bNo").hidden = true;
      $("brandForm").hidden = false;
      $("rowColor").style.display = "";
      autoSave();
      $("bName").focus();
    });
  });
}
async function loadBrand() {
  brand = await api("/api/brand");
  const st = document.createElement("style");
  st.textContent = brand.fonts.map(f => `@font-face{font-family:'fp-${f}';src:url('/font/${encodeURIComponent(f)}');font-display:swap}`).join("");
  document.head.appendChild(st);
  $("bFont").innerHTML = brand.fonts.map(f => `<option value="${esc(f)}">${esc((brand.labels || {})[f] || f)}</option>`).join("");
  $("bFont").value = brand.font;
  $("bName").value = brand.name;
  $("bCta").value = brand.cta || "";
  $("cloneCta").value = brand.cta || "";
  $("bAccent").value = "#" + brand.accent;
  drawLogo();
  drawSample();
  if (brand.name) showForm(false);
  else { $("brandSum").textContent = "Set it once. It goes on every video."; only("bAsk"); }
  if (brand.folder) $("savedTo").textContent = `Also saved in your folder: ${brand.folder}`;
}
function drawLogo() {
  $("logoImg").hidden = !brand.has_logo;
  if (brand.has_logo) $("logoImg").src = "/brand-asset/logo?t=" + Date.now();
  $("logoBtn").textContent = brand.has_logo ? "Change my logo" : "Add my logo";
}
$("bFont").onchange = $("bAccent").oninput = () => { drawSample(); autoSave(); };
$("bName").oninput = $("bCta").oninput = autoSave;
$("brandToggle").onclick = () => { $("rowColor").style.display = ""; showForm(true); };
$("logoBtn").onclick = () => $("logoFile").click();
$("logoFile").onchange = () => {
  const f = $("logoFile").files[0];
  if (!f) return;
  $("bNote").textContent = "Saving your logo...";
  const x = new XMLHttpRequest();
  x.open("POST", "/api/brand-asset");
  x.setRequestHeader("X-Kind", "logo");
  x.setRequestHeader("X-File-Name", encodeURIComponent(f.name));
  x.onload = () => {
    if (x.status !== 200) { $("bNote").innerHTML = `<span class="err">Use a .png or .jpg logo.</span>`; return; }
    brand.has_logo = true; drawLogo(); $("bNote").textContent = "Saved your logo.";
  };
  x.send(f);
  $("logoFile").value = "";
};
$("bSave").onclick = () => {
  if (!$("bName").value.trim()) { $("bNote").innerHTML = `<span class="err">Add your name first.</span>`; $("bName").focus(); return; }
  brand.name = $("bName").value.trim(); brand.accent = $("bAccent").value.slice(1).toUpperCase(); brand.font = $("bFont").value;
  autoSave();
  $("bNote").textContent = "";
  showForm(false);
};

/* ---------- drop a video: it cleans by itself ---------- */
let job = null, busy = false, cleaned = false, base = null, tick = null;
function say(text, bad) { $("said").hidden = !text; $("said").textContent = text || ""; $("said").classList.toggle("bad", !!bad); }
function working(on) {
  busy = on;
  $("work").hidden = !on;
  if (on) $("doneWrap").scrollIntoView({ behavior: "smooth", block: "start" });
  $("drop").style.display = on ? "none" : "";
  fxButtons();
  if (!on) { clearInterval(tick); tick = null; }
}
// the menu always shows, so people see what they get; it turns on once there's a cleaned video to put it on
function fxButtons() {
  // these stay live with no video yet: a button that looks dead reads as broken. It says what to do instead
  $("cloneBtn").disabled = busy;
  $("fxHint").hidden = cleaned;
}
function drawTime() {
  if (!base) return;
  const gone = base.elapsed + (Date.now() - base.at) / 1000;
  const left = Math.max(0, base.estimate - gone);
  // 2026-11-11: past the guess, the bar used to sit at 96% saying "Almost done" and looked stuck. Now it keeps
  // creeping and a clock ticks, so a slow run still looks alive.
  const late = base.estimate && gone > base.estimate;
  const clock = `${Math.floor(gone / 60)}:${String(Math.floor(gone % 60)).padStart(2, "0")}`;
  $("bar").style.width = (!base.estimate ? 4 : late ? 96 + 3 * (1 - Math.exp(-(gone - base.estimate) / 120))
    : Math.min(96, 4 + 92 * gone / Math.max(base.estimate, 1))) + "%";
  $("timeLeft").textContent = !base.estimate ? "Working out how long." :
    late ? `Still working, ${clock} so far. This one is taking a little longer than usual.` :
    left > 60 ? `About ${Math.ceil(left / 60)} minutes left. You can leave this open and walk away.` : "Almost done.";
}
function plainState(s) {
  return s[0].toUpperCase() + s.slice(1) + "...";
}
$("drop").onclick = () => $("file").click();
$("drop").onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("file").click(); } };
$("drop").ondragover = e => { e.preventDefault(); $("drop").classList.add("on"); };
$("drop").ondragleave = () => $("drop").classList.remove("on");
$("drop").ondrop = e => { e.preventDefault(); $("drop").classList.remove("on"); picked(e.dataTransfer.files); };
$("file").onchange = () => { picked($("file").files); $("file").value = ""; };

// 2026-11-09, Tiff dropped two clips to be edited together and only the first came out: this page read one file and
// dropped the rest without a word. Now several clips are shown in order (when they were recorded), can be moved,
// and get joined into one video before the clean up.
let joinFiles = [], joinUrls = [];
// When the video was recorded, from the video's own header (its "mvhd" box). A file's saved date changes when it is
// copied or downloaded, and on 2026-11-09 a copied pair sorted the screen clip before the talking one. 0 if unknown.
async function recordedAt(f) {
  const rd = async (pos, n) => new DataView(await f.slice(pos, pos + n).arrayBuffer());
  const kind = (d, at) => String.fromCharCode(d.getUint8(at), d.getUint8(at + 1), d.getUint8(at + 2), d.getUint8(at + 3));
  let pos = 0;
  for (let k = 0; k < 64 && pos + 8 <= f.size; k++) {
    const h = await rd(pos, 16);
    let size = h.getUint32(0), head = 8;
    if (size === 1) { size = Number(h.getBigUint64(8)); head = 16; } else if (size === 0) size = f.size - pos;
    if (size < 8) return 0;
    if (kind(h, 4) === "moov") {
      for (let p = pos + head, end = pos + size; p + 8 <= end;) {
        const c = await rd(p, 20), cs = c.getUint32(0);
        if (kind(c, 4) === "mvhd") {
          const secs = c.getUint8(8) === 1 ? Number((await rd(p + 12, 8)).getBigUint64(0)) : c.getUint32(12);
          return secs > 2082844800 ? (secs - 2082844800) * 1000 : 0;      // seconds since 1904
        }
        if (cs < 8) return 0;
        p += cs;
      }
      return 0;
    }
    pos += size;
  }
  return 0;
}
async function picked(list) {
  const vids = [...list].filter(f => /\.(mp4|mov|m4v)$/i.test(f.name) || /^video\//.test(f.type));
  if (!vids.length) { say("Use an .mp4 or .mov video.", true); return; }
  if (vids.length === 1) { $("joinBox").hidden = true; upload(vids[0]); return; }
  if (vids.length > 10) { say("Up to 10 videos at a time.", true); return; }
  say("");
  const when = new Map(await Promise.all(vids.map(async f => [f, (await recordedAt(f).catch(() => 0)) || f.lastModified])));
  joinFiles = vids.sort((a, b) => when.get(a) - when.get(b));
  drawJoin();
  $("joinBox").hidden = false;
  $("joinBox").scrollIntoView({ behavior: "smooth", block: "center" });
}
function drawJoin() {
  joinUrls.forEach(u => URL.revokeObjectURL(u));
  joinUrls = joinFiles.map(f => URL.createObjectURL(f));
  const last = joinFiles.length - 1;
  $("joinList").innerHTML = joinFiles.map((f, i) => `<li><video muted playsinline preload="metadata" src="${joinUrls[i]}#t=1"></video>` +
    `<span class="ez-join-name"><b>Video ${i + 1}</b><small data-len="${i}"></small><small>${esc(f.name)}</small></span>` +
    `<span class="ez-join-move"><button class="ghost small" data-up="${i}" ${i ? "" : "disabled"} aria-label="Move video ${i + 1} up">&uarr;</button>` +
    `<button class="ghost small" data-down="${i}" ${i < last ? "" : "disabled"} aria-label="Move video ${i + 1} down">&darr;</button></span></li>`).join("");
  $("joinList").querySelectorAll("video").forEach((v, i) => {
    v.onloadedmetadata = () => {
      const s = Math.round(v.duration || 0), el = $("joinList").querySelector(`[data-len="${i}"]`);
      if (el && s) el.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")} long`;
    };
  });
}
$("joinList").onclick = e => {
  const b = e.target.closest("button");
  if (!b) return;
  const i = +(b.dataset.up ?? b.dataset.down), j = b.dataset.up !== undefined ? i - 1 : i + 1;
  if (j < 0 || j >= joinFiles.length) return;
  [joinFiles[i], joinFiles[j]] = [joinFiles[j], joinFiles[i]];
  drawJoin();
};
$("joinCancel").onclick = () => { $("joinBox").hidden = true; joinFiles = []; };
$("joinGo").onclick = () => uploadMany(joinFiles.slice());

function send(f) {
  return new Promise((ok, bad) => {
    const x = new XMLHttpRequest();
    x.open("POST", "/api/upload");
    x.setRequestHeader("X-File-Name", encodeURIComponent(f.name));
    x.upload.onprogress = e => { if (e.lengthComputable) $("bar").style.width = Math.round(100 * e.loaded / e.total) + "%"; };
    x.onerror = () => bad(new Error("That didn't upload. Try again."));
    x.onload = () => {
      const d = JSON.parse(x.responseText || "{}");
      x.status === 200 ? ok(d) : bad(new Error(d.error || "That didn't upload. Try again."));
    };
    x.send(f);
  });
}
async function uploadMany(files) {
  if (busy || files.length < 2) return;
  $("joinBox").hidden = true;
  say("");
  cleaned = false; $("results").innerHTML = ""; $("noneYet").hidden = false; showTab("tabPick");
  working(true);
  $("timeLeft").textContent = "";
  const ids = [];
  for (let i = 0; i < files.length; i++) {
    $("state").textContent = `Getting video ${i + 1} of ${files.length}...`;
    try { ids.push((await send(files[i])).job); }
    catch (e) { working(false); say(e.message, true); return; }
  }
  $("state").textContent = `Joining your ${files.length} videos...`;
  $("bar").style.width = "60%";
  let d;
  try { d = await api("/api/join", { method: "POST", body: JSON.stringify({ jobs: ids }) }); }
  catch (e) { working(false); say(e.message, true); return; }
  if (d.secs > 600) { working(false); say("Together these are over 10 minutes. Use videos under 10 minutes in all.", true); return; }
  job = d.job;
  run({ template: "cleanup", cleanup: true }, `Joined your ${files.length} videos. Cleaning them up`);
}

function upload(f) {
  if (busy) return;
  say("");
  cleaned = false; $("results").innerHTML = ""; $("noneYet").hidden = false; showTab("tabPick");
  working(true);
  $("state").textContent = `Getting ${f.name}...`;
  $("bar").style.width = "2%"; $("timeLeft").textContent = "";
  const x = new XMLHttpRequest();
  x.open("POST", "/api/upload");
  x.setRequestHeader("X-File-Name", encodeURIComponent(f.name));
  x.upload.onprogress = e => { if (e.lengthComputable) $("bar").style.width = Math.round(100 * e.loaded / e.total) + "%"; };
  x.onerror = () => { working(false); say("That didn't upload. Try again.", true); };
  x.onload = async () => {
    const d = JSON.parse(x.responseText || "{}");
    if (x.status !== 200) { working(false); say(d.error || "That didn't upload. Try again.", true); return; }
    if (d.secs > 600) {
      working(false);
      if (!shorts.unlocked) { say("This one is over 10 minutes. Use a video under 10 minutes.", true); return; }
      job = d.job;
      say("Long video in. Tap Your long videos turned into shorts below.");
      $("shortsCard").scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    job = d.job;
    run({ template: "cleanup", cleanup: true }, "Cleaning up your video");
  };
  x.send(f);
}
async function run(body, label) {
  working(true);
  say("");
  $("state").textContent = label + "...";
  $("bar").style.width = "4%";
  try {
    await api("/api/run", { method: "POST", body: JSON.stringify({ job, ...body }) });
    if (!tick) tick = setInterval(drawTime, 1000);
    poll();
  } catch (e) { working(false); say(e.message, true); }
}
async function poll() {
  let d;
  try { d = await api("/api/job/" + job); }
  catch (e) { working(false); say("Lost touch with your video. Is the little black window still open?", true); return; }
  base = { at: Date.now(), elapsed: d.elapsed, estimate: d.estimate };
  drawTime();
  const over = d.state.startsWith("done") || d.state === "stopped";
  if (!over) {
    if (d.state !== "in line" && d.state !== "starting") $("state").textContent = plainState(d.state);
    setTimeout(poll, 3000);
    return;
  }
  working(false);
  drawResults(d);
  if (d.state === "stopped") {
    const why = (d.steps.slice().reverse().find(s => /STOPPED/.test(s)) || "").replace(/^[\d:]+\s*STOPPED:\s*/, "");
    say(why || d.error || "It stopped. Try again.", true);
    if (!cleaned) return;       // nothing to put an effect on yet
  } else {
    cleaned = true;
    say(summary(d));
  }
  fxButtons();
}
function summary(d) {
  const pick = re => d.steps.map(s => s.match(re)).filter(Boolean).pop();
  const bits = [];
  const pause = pick(/([\d.]+) s down to ([\d.]+) s/);
  if (pause) bits.push(`cut the dead air (${Math.round(pause[1])} seconds down to ${Math.round(pause[2])})`);
  const repeats = d.steps.filter(s => /Cut a repeat/.test(s)).length;
  if (repeats) bits.push(`cut ${repeats} repeat${repeats > 1 ? "s" : ""}`);
  const ums = pick(/Cut (\d+) um/);
  if (ums) bits.push(`cut ${ums[1]} um${ums[1] > 1 ? "s" : ""}`);
  if (d.steps.some(s => /Cleaned the background noise/.test(s))) bits.unshift("cleaned the sound");
  return bits.length ? `Done: we ${bits.join(", ")}. Now tap an effect, or download it as it is.` : "Done. Now tap an effect, or download it as it is.";
}
function showTab(name) {
  // 2026-11-05, Tiff: finished videos and the progress bar sit at the bottom of the page, not in a tab
  if (name === "done") { $("doneWrap").scrollIntoView({ behavior: "smooth", block: "start" }); return; }
  ["tabPick", "tabCopy"].forEach(t => $(t).hidden = t !== name);
  document.querySelectorAll(".ez-tabs button").forEach(b => b.classList.toggle("on", b.dataset.tab === name));
}
document.querySelector(".ez-tabs").onclick = e => { const b = e.target.closest("[data-tab]"); if (b) showTab(b.dataset.tab); };
$("fxWhich").onchange = () => {
  const c = document.querySelector(`.ez-card[data-id="${CSS.escape($("fxWhich").value)}"]`);
  $("fxWhich").value = "";
  if (c) c.click();
};
function drawResults(d) {
  if (!d.shorts.length) return;
  $("noneYet").hidden = true;
  showTab("done");
  $("results").innerHTML = d.shorts.slice().reverse().map(s => {
    const url = `/files/${d.id}/${encodeURIComponent(s.file)}`;
    const title = s.file.replace(/\.mp4$/i, "").split(" - ").pop();
    return `<div class="ez-result"><video src="${url}#t=0.1" controls playsinline preload="metadata"></video>
      <div><h3>${esc(title)}</h3>
      ${s.ok ? "" : `<p class="ez-said bad">One of our checks didn't pass on this one. Watch it before you post it.</p>`}
      <div class="ez-actions"><a class="ez-dl" href="${url}" download="${esc(s.file)}">Download</a></div></div></div>`;
  }).join("");
}

/* ---------- effects, loaded and one tap ---------- */
// These two need something from the person first, so they aren't one tap
const GROUPS = [
  ["Looks", "The whole video gets a new feel.", ["tiff-digital-zoom", "tiff-orbit", "tiff-pop-out", "tiff-phone-peek", "tiff-phone-frame", "tiff-brand-backdrop", "tiff-spotlight", "tiff-split-stage"]],
  ["Reel formats", "The whole video gets designed, timed to what you say.", ["tiff-tier-list", "tiff-top-five", "tiff-always-never", "tiff-flip-cards", "tiff-glow-stack", "tiff-mono-story", "tiff-big-type", "tiff-if-then", "tiff-explainer-panel", "tiff-fitted-stack", "tiff-ear-to-ear", "tiff-quadrant", "tiff-cinema-type", "tiff-line-by-line", "tiff-voice-note", "tiff-paper-cut", "tiff-growth-chart", "tiff-glass-graph", "tiff-end-stack", "tiff-app-world", "tiff-split-steps", "tiff-phase-reel", "tiff-word-morph", "tiff-split-kinetic", "tiff-tool-cards", "tiff-numbered-list", "tiff-number-pop", "tiff-stat-bars", "tiff-checklist", "tiff-step-counter"]],
  ["With your pictures", "Add your own pictures and they show up as you talk.", ["tiff-picture-under", "tiff-picture-above", "tiff-photo-split", "tiff-photo-cluster", "tiff-photo-world", "tiff-testimonial-wall", "tiff-photo-grid", "tiff-float-up", "tiff-behind-you", "tiff-screen-slide", "tiff-screen-zoom", "tiff-picture-stack", "tiff-story-room", "tiff-then-and-now", "tiff-proof-above", "tiff-word-swap", "tiff-logo-spot", "tiff-fast-personal"]],
  ["With your other videos", "Add a screen recording or a second take.", ["tiff-screen-and-you", "tiff-doc-split", "tiff-twin-versus", "tiff-two-roles", "tiff-day-reel", "tiff-screen-karaoke", "tiff-big-screen-caps"]],
  ["Camera moves", "Big moves that make it feel filmed by a crew.", ["tiff-lights-on", "tiff-screen-wipe", "tiff-shutter-strike", "tiff-zoom-through", "tiff-pull-back", "tiff-whip-cut", "tiff-flash-cut", "tiff-black-white-beats", "tiff-match-cut"]],
  ["Words on screen", "Your own words, big, in your brand.", ["tiff-info-cards", "tiff-word-pop", "tiff-glow-words", "tiff-top-banner", "tiff-marker-swipe", "tiff-quote-card"]],
  ["Pacing and captions", "How fast it moves and where your words sit.", ["style-word-highlights", "style-glass-meter", "style-loud-caps", "style-headline-hook", "style-high-words", "style-one-word", "style-easy-read", "tiff-zoom-punch", "style-fast-cuts"]],
];
const id = f => f.mp4.replace(/\.mp4$/, "");
const card = f => `<button class="ez-card" data-id="${esc(id(f))}" data-name="${esc(f.name)}">
    ${f.ready ? `<video src="/fx/${esc(f.mp4)}" poster="/fx/${esc(f.jpg)}" muted loop playsinline preload="none" aria-hidden="true"></video>` : ""}
    <b>${esc(f.name)}</b><small>${esc(f.uses[0] || "")}</small></button>`;
// samples play only while they're on screen, so 20 small videos don't slow the page down
const watcher = "IntersectionObserver" in window ? new IntersectionObserver(es => es.forEach(e => {
  if (e.isIntersecting) e.target.play().catch(() => {}); else e.target.pause();
}), { threshold: 0.4 }) : null;
async function loadEffects() {
  const all = await api("/fx.json");
  const byId = Object.fromEntries(all.map(f => [id(f), f]));
  $("fxGrid").innerHTML = GROUPS.map(([title, line, ids]) => {
    const here = ids.map(x => byId[x]).filter(f => f && f.ready);       // no sample means it isn't proven, so it isn't offered
    return here.length ? `<h3 class="ez-more">${esc(title)}</h3><p class="note ez-line">${esc(line)}</p><div class="ez-grid">${here.map(card).join("")}</div>` : "";
  }).join("");
  const builtin = new Set(GROUPS.flatMap(g => g[2]));
  // cards Tiff took off the page on 2026-11-05. Their files stay, they just aren't offered
  const HIDDEN = new Set(["style-fast-cut-talking-head"]);
  const saved = all.filter(f => f.saved && !builtin.has(id(f)) && !HIDDEN.has(id(f)));
  $("fxWhich").innerHTML = `<option value="">Pick one, or scroll to see them all</option>` + GROUPS.map(([title, , ids]) => {
    const here = ids.map(i => byId[i]).filter(f => f && f.ready);
    return here.length ? `<optgroup label="${esc(title)}">${here.map(f => `<option value="${esc(id(f))}">${esc(f.name)}</option>`).join("")}</optgroup>` : "";
  }).join("");
  $("savedWrap").hidden = !saved.length;
  $("savedGrid").innerHTML = saved.map(card).join("");
  document.querySelectorAll(".ez-card").forEach(c => c.onclick = () => openLook(all.find(f => id(f) === c.dataset.id)));
  if (watcher) document.querySelectorAll(".ez-card video").forEach(v => watcher.observe(v));
  fxButtons();
}

/* ---------- tap a card: see it big, say it your way, then put it on ---------- */
const COMMAS = "Separate them with commas. Leave it blank and we'll pick from what you say.";
const YOUR_WORDS = {
  "tiff-word-pop": ["Which words should pop?", COMMAS], "tiff-glow-words": ["Which words should glow?", COMMAS],
  "tiff-doodles": ["Which words get a doodle?", COMMAS], "tiff-orbit": ["Which words circle your head?", "Up to 6, separated with commas. Leave it blank and we'll pick from what you say."],
  "tiff-tier-list": ["What are you ranking?", "Best first, separated with commas. Leave it blank and we'll use your key words."],
  "tiff-then-and-now": ["What's the line for each photo?", "One per photo, separated with commas. Like: 2019 broke, 2022 first client."],
  "tiff-growth-chart": ["What labels go on your chart?", "Separated with commas. Leave it blank and we'll use your key words."],
  "tiff-glass-graph": ["What labels go on your chart?", "Separated with commas. Leave it blank and we'll use your key words."],
  "tiff-split-steps": ["What are your steps?", "Up to 6, separated with commas. Leave it blank and we'll use your key words."],
  "tiff-if-then": ["What goes in your grid?", "Separated with commas, going If, Then, If, Then. Leave it blank and we'll use your key words."],
  "tiff-quadrant": ["What goes in your 4 boxes?", "4 things, separated with commas. Leave it blank and we'll use your key words."],
  "tiff-short-box": ["What should your hook say?", "One line. Leave it blank and we'll use your first words."],
  "tiff-cover-story": ["What's your keyword?", "Like: Comment \"AI\" For The Free Guide. Or: DM \"READY\" For The Link. Leave it blank and we'll use a word you said."],
  "tiff-top-five": ["What's on your list?", "Up to 5, separated with commas. Leave it blank and we'll use your key words."],
  "tiff-always-never": ["What goes in your chart?", "Separated with commas, going Always, Never, Always, Never. Leave it blank and we'll use your key words."],
  "tiff-numbered-list": ["What's on your list?", "Up to 9, separated with commas. Leave it blank and we'll use your key words."],
  "tiff-top-banner": ["What should your banner say?", "Leave it blank and we'll use your first words."],
  "tiff-note-card": ["What goes on your card?", "One line each, separated with commas. Leave it blank and we'll use your words."],
  "tiff-split-stage": ["What goes up top?", "One line each, separated with commas. Leave it blank and we'll use your words."],
  "tiff-marker-swipe": ["Which words get the marker?", "Leave it blank and we'll pick from what you say."],
  "tiff-lower-third": ["What goes under your name?", "Like: AI Coach"],
  "style-glass-meter": ["What should your meter say?", "A few words, separated with commas. Leave it blank and we'll pick from what you say."],
  "style-headline-hook": ["What should your headline say?", "One line, or two with a new line. Leave it blank and we'll use your first words."],
};
const NEEDS_PICS = new Set(["tiff-phone-peek", "tiff-testimonial-wall", "tiff-picture-under", "tiff-picture-above", "tiff-photo-split", "tiff-photo-world", "tiff-photo-grid", "tiff-float-up", "tiff-photo-cluster", "tiff-behind-you", "tiff-screen-slide", "tiff-screen-zoom", "tiff-picture-stack", "tiff-story-room", "tiff-then-and-now", "tiff-proof-above", "tiff-word-swap", "tiff-logo-spot", "tiff-fast-personal"]);
const NEEDS_CLIPS = new Set(["tiff-screen-and-you", "tiff-doc-split", "tiff-twin-versus", "tiff-two-roles", "tiff-day-reel"]);
let looking = null;
function openLook(f) {
  looking = f;
  $("lookName").textContent = f.name;
  $("lookUses").innerHTML = f.uses.filter(u => !/^Saved from/.test(u)).map(u => `<li>${esc(u)}</li>`).join("");
  $("lookVid").src = "/fx/" + f.mp4;
  $("lookVid").play().catch(() => {});
  const w = YOUR_WORDS[id(f)];
  $("lookWordsWrap").hidden = !w;
  $("lookWords").value = "";
  if (w) { $("lookWordsLabel").textContent = w[0]; $("lookWordsHint").textContent = w[1]; }
  const needClips = NEEDS_CLIPS.has(id(f));
  $("lookPicsWrap").hidden = !NEEDS_PICS.has(id(f)) && !needClips;
  $("lookPicsLabel").textContent = needClips ? "Add your other video" : "Add your pictures";
  $("lookPicsHint").textContent = needClips ? "Your voice stays from your main video. It plays with the sound off." : "Pick as many as you want. Each one shows on a new phrase, in order.";
  $("lookPics").accept = needClips ? "video/mp4,video/quicktime,.mp4,.mov,.m4v" : "image/jpeg,image/png,image/webp";
  $("lookPics").value = "";
  $("lookGo").disabled = busy || !cleaned;
  $("lookNote").textContent = busy ? "Hang on, your last edit is still going." : cleaned ? "" : "Drop your video in first, then come back and tap this.";
  $("look").showModal();
}
function closeLook() { $("lookVid").pause(); $("lookVid").removeAttribute("src"); $("lookVid").load(); $("look").close(); }
$("lookClose").onclick = closeLook;
$("look").oncancel = e => { e.preventDefault(); closeLook(); };
$("look").onclick = e => { if (e.target === $("look")) closeLook(); };
$("lookGo").onclick = async () => {
  const f = looking, words = $("lookWords").value.trim();
  if (NEEDS_PICS.has(id(f)) || NEEDS_CLIPS.has(id(f))) {
    const pics = [...$("lookPics").files];
    if (!pics.length) { $("lookNote").textContent = NEEDS_CLIPS.has(id(f)) ? "Add your other video first." : "Add at least one picture first."; return; }
    $("lookNote").textContent = "Adding your files...";
    try {
      for (const pic of pics) await api("/api/pictures?job=" + encodeURIComponent(job), { method: "POST", headers: { "X-File-Name": encodeURIComponent(pic.name) }, body: pic });
    } catch (e) { $("lookNote").textContent = e.message; return; }
  }
  closeLook();
  $("add").scrollIntoView({ behavior: "smooth" });
  run({ template: "effect", effect: id(f), ...(words ? { words } : {}) }, "Adding " + f.name);
};

/* ---------- copy an edit: read the reel, save its edit, put it on this video ---------- */
$("cloneBtn").onclick = async () => {
  if (!cleaned) { say("Drop your video in first. Then paste the reel and tap this again.", true); $("add").scrollIntoView({ behavior: "smooth" }); return; }
  const link = $("cloneLink").value.trim();
  if (!link) { say("Paste a link to a reel first.", true); $("cloneLink").focus(); return; }
  if ($("cloneCta").value.trim()) {       // their keyword goes where the creator had theirs, never the creator's
    $("bCta").value = $("cloneCta").value.trim();
    await api("/api/brand", { method: "POST", body: JSON.stringify({ name: $("bName").value.trim(), accent: $("bAccent").value, font: $("bFont").value, cta: $("bCta").value }) });
  }
  working(true); say("");
  $("state").textContent = "Reading how that reel is edited...";
  $("timeLeft").textContent = "About 2 minutes for this part.";
  $("bar").style.width = "10%";
  try {
    const { job: sj } = await api("/api/study", { method: "POST", body: JSON.stringify({ links: link }) });
    let s;
    do {
      await new Promise(r => setTimeout(r, 3000));
      s = await api("/api/job/" + sj);
    } while (s.state !== "pick a style" && s.state !== "stopped");
    if (s.state === "stopped") {
      throw new Error("Couldn't read that reel. Check it's public and the link is right.");
    }
    const first = s.styles[0];
    await api("/api/save-styles", { method: "POST", body: JSON.stringify({ style_job: sj, styles: { [first.id]: first.name } }) });
    await loadEffects();
    const builtin = new Set(GROUPS.flatMap(g => g[2]));
    const all = (await api("/fx.json")).filter(f => f.saved && !builtin.has(id(f)));
    const mine = all[all.length - 1];
    $("cloneLink").value = "";
    run({ template: "effect", effect: id(mine) }, "Putting that edit on your video");
  } catch (e) { working(false); say(e.message, true); }
};
// the sound cleaner's download can fail while everything else installs. Then a video would come back with its noise
// still in it and nothing saying so
api("/api/setup").then(st => {
  if (st["clean sound (Box 2)"] === false) {
    $("soundWarn").hidden = false;
    $("soundWarn").textContent = "Your sound cleaner didn't install, so videos will keep their background noise. Close the little black window and open Content Made Easy again to retry. If this stays here, send Tiff a screenshot.";
  }
}).catch(() => {});

/* ---------- long videos: hidden until they unlock it, and they only answer once ---------- */
let shorts = { unlocked: false, answers: {}, questions: [], has_key: false }, askAt = -1;
function drawShorts() {
  $("shortsLocked").hidden = shorts.unlocked;
  $("shortsCard").hidden = !shorts.unlocked;
  // 2026-11-09: say that several clips can go in at once, or nobody finds out the join exists
  $("dropNote").textContent = shorts.unlocked
    ? "Or tap to pick. Got a few clips? Drop them all and they get joined into one. Under 10 minutes cleans up by itself. Longer ones become shorts."
    : "Or tap to pick. Got a few clips? Drop them all and they get joined into one. Under 10 minutes in all. It cleans up by itself.";
}
function drawAsk() {
  const qs = shorts.questions, last = askAt === qs.length;
  $("askErr").hidden = true;
  $("askWrap").hidden = askAt < 0 || last;
  $("askKeyWrap").hidden = !last || shorts.has_key;
  $("askBack").textContent = askAt < 0 ? "Not now" : "Save and finish later";
  $("askNext").textContent = askAt < 0 ? "Allow" : last ? "Unlock it" : "Next";
  if (askAt < 0) $("askLine").textContent = "This sets up long videos on your computer: your tools get checked and anything missing downloads, then you answer 9 quick questions. You only do this once.";
  else if (last) $("askLine").textContent = shorts.has_key ? "That's everything. Tap Unlock it." : "Last step. Long videos need a free Groq key to find your best moments.";
  else {
    $("askLine").textContent = `Question ${askAt + 1} of ${qs.length}. It saves as you go.`;
    $("askQ").textContent = qs[askAt][1];
    $("askA").value = shorts.answers[qs[askAt][0]] || (qs[askAt][0] === "name" ? $("bName").value : "");
    $("askA").focus();
  }
}
async function saveAnswer() {
  if (askAt < 0 || askAt >= shorts.questions.length) return;
  shorts = await api("/api/shorts-setup", { method: "POST", body: JSON.stringify({ answers: { [shorts.questions[askAt][0]]: $("askA").value.trim() } }) });
}
$("shortsUnlock").onclick = () => { askAt = -1; drawAsk(); $("shortsAsk").showModal(); };
$("askBack").onclick = async () => { await saveAnswer().catch(() => {}); $("shortsAsk").close(); };
$("askNext").onclick = async () => {
  try {
    await saveAnswer();
    if (askAt < shorts.questions.length) { askAt++; drawAsk(); return; }
    $("askNext").disabled = true;
    $("askLine").textContent = "Setting it up on your computer. This can take a few minutes.";
    shorts = await api("/api/shorts-unlock", { method: "POST", body: JSON.stringify({ key: $("askKey").value.trim() }) });
    $("askKey").value = "";
    $("shortsAsk").close();
    drawShorts();
    say("Unlocked. Drop in a long video, then tap Your long videos turned into shorts.");
  } catch (e) { $("askErr").hidden = false; $("askErr").textContent = e.message; }
  $("askNext").disabled = false;
};
$("shortsCard").onclick = () => {
  if (!job) { say("Drop your long video in first, then tap this."); $("add").scrollIntoView({ behavior: "smooth" }); return; }
  run({ template: "shorts", count: 3 }, "Finding your best moments");
};
api("/api/shorts-setup").then(d => { shorts = d; drawShorts(); }).catch(() => {});

/* ---------- your videos ---------- */
let videosSeen = "";
async function loadVideos() {
  const rows = await api("/api/videos");
  const key = JSON.stringify(rows);
  if (key === videosSeen) return;
  videosSeen = key;
  if (!rows.length) return;
  $("videoList").innerHTML = rows.map(r => {
    const over = r.state.startsWith("done") || r.state === "stopped";
    const n = r.made.length;
    const line = !over ? "Working on it" : r.state === "stopped" ? "It stopped" : n ? `${n} finished video${n > 1 ? "s" : ""}` : "Ready for an edit";
    return `<div class="ez-vid"><div><b>${esc(r.name)}</b><small>${esc(line)}</small></div>
      <button class="ghost small" data-open="${esc(r.id)}">Open</button></div>`;
  }).join("");
  // 2026-11-11, Tiff: "the video shouldve been spit back out". A video finished from the chat never showed here,
  // so opening the page now shows the newest finished video, ready to watch or take another edit.
  if (firstLook) {
    firstLook = false;
    const r = rows.find(r => r.state.startsWith("done"));
    if (r && !job && !busy) openJob(r.id, false);
  }
}
let firstLook = true;
async function openJob(jid, scroll) {
  const d = await api("/api/job/" + jid);
  if (busy) return;
  let seen = [];
  try { seen = JSON.parse(videosSeen || "[]"); } catch {}
  const row = seen.find(r => r.id === jid);
  job = d.id;
  cleaned = !!(row && row.cleaned);
  $("results").innerHTML = ""; $("noneYet").hidden = false; showTab("tabPick");
  drawResults(d);
  say(cleaned ? `${d.name} is open. Tap an edit to put it on this video.` : `${d.name} is open.`);
  fxButtons();
  if (scroll) $("fx").scrollIntoView({ behavior: "smooth" });
}
$("videoList").onclick = e => {
  const b = e.target.closest("[data-open]");
  if (b && !busy) openJob(b.dataset.open, true).catch(() => {});
};

/* ---------- how words get written down ---------- */
let heard = { engine: "computer", has_key: false };
function drawHeard() {
  const eleven = heard.engine === "elevenlabs";
  $("tEleven").classList.toggle("on", eleven);
  $("tHere").classList.toggle("on", !eleven);
  $("tKeyRow").hidden = !eleven || heard.has_key;
  $("tNote").textContent = eleven
    ? (heard.has_key ? "Your own ElevenLabs key is doing this. They charge you for what you use. If it fails, this computer takes over." : "Sharper word timing with your own ElevenLabs key. They charge you for what you use.")
    : "Free and private. It runs on this computer. If a word comes out wrong in your captions, it's from this step.";
}
async function setHeard(body) {
  try { heard = await api("/api/transcription", { method: "POST", body: JSON.stringify(body) }); drawHeard(); }
  catch (e) { $("tNote").textContent = e.message; }
}
$("tHere").onclick = () => setHeard({ engine: "computer" });
$("tEleven").onclick = () => { if (heard.has_key) setHeard({ engine: "elevenlabs" }); else { heard.engine = "elevenlabs"; drawHeard(); } };
$("tKeySave").onclick = async () => { const key = $("tKey").value.trim(); $("tKey").value = ""; $("tNote").textContent = "Trying your key..."; await setHeard({ engine: "elevenlabs", key }); };
api("/api/transcription").then(d => { heard = d; drawHeard(); }).catch(() => {});

/* ---------- the open Claude chat ---------- */
const DOT = { listening: "Claude is connected", working: "Claude is working on it", off: "Claude isn't connected" };
const NOTE = {
  listening: "Claude is waiting for you. Type what you want and it starts on the video you have open.",
  working: "Claude is on it. Keep your Claude Code chat open.",
  off: "Want Claude to do the work? Open a Claude Code chat and type /contentmadeeasy. When the dot at the top turns green, tell it what you want right here.",
};
let talkSeen = "";
async function loadClaude() {
  let d;
  try { d = await api("/api/claude"); } catch { return; }
  $("topDot").className = "ez-dot " + d.state;
  $("topDotText").textContent = DOT[d.state];
  $("claudeNote").textContent = NOTE[d.state];
  $("claudeAsk").hidden = d.state !== "listening";
  const key = JSON.stringify(d.talk);
  if (key !== talkSeen) {
    talkSeen = key;
    $("claudeTalk").innerHTML = d.talk.map(m => `<p class="${m.who === "you" ? "you" : ""}">${esc(m.text)}</p>`).join("");
    $("claudeTalk").scrollTop = 1e6;
  }
}
async function sendClaude() {
  const text = $("claudeText").value.trim();
  if (!text) return;
  $("claudeErr").hidden = true;
  try {
    await api("/api/claude/ask", { method: "POST", body: JSON.stringify({ text, job }) });
    $("claudeText").value = "";
  } catch (e) { $("claudeErr").hidden = false; $("claudeErr").textContent = e.message; }
  loadClaude();
}
$("claudeSend").onclick = sendClaude;
$("claudeText").onkeydown = e => { if (e.key === "Enter") sendClaude(); };
loadClaude(); loadVideos().catch(() => {});
setInterval(loadClaude, 3000);
setInterval(() => loadVideos().catch(() => {}), 5000);

// 2026-11-11, Tiff: "no way to do like a progress bar somewhere ... is it working or not". A video started from the
// Claude chat ran with nothing moving on this page. Now the page finds whatever is running, wherever it was started,
// and shows its bar and time left. When it's done, the edits turn on for that video.
async function followRunning() {
  if (busy) return;
  let rows;
  try { rows = await api("/api/busy"); } catch { return; }
  const r = rows && rows[0];
  if (!r || busy) return;
  if (r.id !== job) { job = r.id; $("results").innerHTML = ""; $("noneYet").hidden = false; }
  let seen = [];
  try { seen = JSON.parse(videosSeen || "[]"); } catch {}
  const row = seen.find(v => v.id === r.id);
  cleaned = !!(row && row.cleaned);
  working(true);
  say("");
  $("state").textContent = `Working on ${r.name}...`;
  $("bar").style.width = "4%";
  if (!tick) tick = setInterval(drawTime, 1000);
  poll();
}
followRunning();
setInterval(followRunning, 4000);

loadBrand().catch(e => say(e.message, true));
loadEffects().catch(e => say(e.message, true));
