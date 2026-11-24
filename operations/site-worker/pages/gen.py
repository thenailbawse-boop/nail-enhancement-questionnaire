"""Builds site/ from her Wix pages (wix-src/) in The Nail Bawse main-site branding.
/resources pages are BODY FRAGMENTS: pages.js wraps them in the main site's header, footer and styles (worker.js page()).
First line of each fragment: <!--page {"title": ..., "desc": ...}-->
The digital business card (/card) stays a standalone page, restyled with the main site's brand tokens and NB mark.
Run: python3 gen.py   (then commit, then python3 build.py <commit>)"""
import html, json, os, re, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SRC, OUT = os.path.join(HERE, "wix-src"), os.path.join(HERE, "site")
MAIL = "hello@thenailbawse.com"
IG, TT = "https://www.instagram.com/thenailbawse/", "https://www.tiktok.com/@anisiaaaaaaaaaa"
D = "https://thenailbawse.com"
A_HOST = "https://headless-fdiwdhtxoee-thenailbawse-140c.wix-site-host.com"
B_HOST = "https://headless-aoacqllxhgu-thenailbawse-140c.wix-site-host.com"
L_HOST = "https://headless-lidgzngnfxg-thenailbawse-140c.wix-site-host.com"
LESSONS = [  # slug, label, title, blurb (from her learning hub)
    ("nail-tech-pricing", "Pricing & profit", "How to price nail services", "Break down time, materials, overhead and labor targets; build a repeatable pricing decision."),
    ("beauty-business-marketing", "Marketing & clients", "How to get more beauty clients", "How to make your services discoverable, earn trust and build a consistent route from content to inquiry."),
    ("ai-business-assistant-beauty", "AI workflows", "How to use AI as a beauty business assistant", "Five realistic workflows for beauty entrepreneurs, with safety and privacy checkpoints."),
    ("beauty-business-systems", "Operations", "Beauty business systems checklist", "A practical operating process for client messages, pricing records, stock and weekly planning."),
    ("nail-trends-2026", "2026 trends", "Nail searches: French tips, chrome, cat eye", "What measured search interest can teach a nail technician about useful marketing content."),
    ("lash-artist-marketing", "Lash professionals", "How to market a lash business", "Create educational lash content and a client journey built around real questions."),
    ("esthetician-marketing", "Estheticians", "How to market an esthetics business", "Use clear consultation expectations, responsible content and trust-building marketing."),
    ("hairstylist-business-systems", "Hair professionals", "Business systems for hairstylists", "Organize pricing, client inquiries, consultations and relevant hair content."),
    ("beauty-trends-2026", "Across the beauty industry", "2026 beauty trends by specialty", "What reported hair, brow, nail and skincare searches can teach working professionals."),
]
TONES = ["pink", "cream", "brown", "light"]
ARR = ' <span aria-hidden="true">→</span>'
GUIDE_MAIL = "mailto:" + MAIL + "?subject=Send%20me%20the%20You%20Are%20the%20Asset%20guide"
SESSION_MAIL = "mailto:" + MAIL + "?subject=Reserve%20a%20%24150%20AI%20session"
BUILD_MAIL = "mailto:" + MAIL + "?subject=Custom%20AI%20system%20or%20website%20inquiry"

# Extra styles for these pages only; everything else comes from the main site (style.css + page CSS).
RCSS = ("<style>"
        ".res-nav{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 28px}.res-nav a{border:1px solid var(--espresso);padding:8px 14px;font-size:10px;font-weight:800;letter-spacing:.14em;text-transform:uppercase}"
        ".res-nav a[aria-current]{background:var(--espresso);color:#fff}"
        ".res-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.res-grid .solution-card{min-height:300px}.solution-card h3{font:normal 28px/1.15 var(--serif);letter-spacing:-.03em;margin:22px 0 12px}.solution-card p{font-size:13px;line-height:1.85;opacity:.9}"
        ".offer-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.offer-grid .card .eyebrow{margin-bottom:6px}.offer-grid .price small{font:700 11px var(--sans);letter-spacing:.08em;text-transform:uppercase;color:var(--body)}"
        ".prose{max-width:760px;margin:0 auto}.prose h2{font:normal 500 clamp(30px,3.2vw,42px)/1.18 var(--serif);letter-spacing:-.03em;margin:56px 0 18px}.prose h3{font:normal 24px/1.3 var(--serif);margin:34px 0 12px}"
        ".prose p,.prose li{font-size:16px;line-height:1.9;color:var(--body)}.prose ol,.prose ul{padding-left:22px}.prose li{margin-bottom:10px}.prose strong{color:var(--ink)}.prose a{text-decoration:underline;text-underline-offset:3px;color:#9c5671}"
        ".prose .banner{background:#f2d4df;padding:28px 30px;margin:30px 0}.prose .banner p{margin:10px 0 0}.prose .sources{border-top:1px solid var(--line);margin-top:40px;padding-top:20px}.prose .sources p,.prose .sources li{font-size:13px}"
        ".prose>h2:first-child{margin-top:0}.prose{padding-top:0}"
        ".keep{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:20px}"
        "@media(max-width:850px){.res-grid,.offer-grid,.keep{grid-template-columns:1fr}.res-grid .solution-card{min-height:230px}}"
        "</style>")


def frag(path, title, desc, body):
    p = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write("<!--page " + json.dumps({"title": title, "desc": desc}) + "-->\n" + RCSS + body)


def resnav(cur):
    items = [("/resources", "Overview"), ("/resources/free", "Free guide"), ("/resources/learn", "Free lessons"), ("/resources/sessions", "AI sessions"), ("/webinar", "Free class")]
    return '<nav class="res-nav" aria-label="Free resources">' + "".join(
        '<a href="%s"%s>%s</a>' % (h, ' aria-current="page"' if h == cur else "", t) for h, t in items) + "</nav>"


def hero(eyebrow, h1, lede, extra="", cur=None):
    return ('<section class="page-hero"><div class="container">' + (resnav(cur) if cur else "") +
            '<p class="eyebrow"><span class="eyebrow-line"></span> ' + eyebrow + '</p><h1>' + h1 + '</h1><p class="lede">' + lede + '</p>' + extra + '</div></section>')


def band(kicker, h2, text, label, href):
    return ('<section class="contact section"><div class="container"><div class="contact-inner"><div><p class="eyebrow eyebrow--light">' + kicker +
            '</p><h2>' + h2 + '</h2><p>' + text + '</p></div><div class="contact-actions"><a class="button button--light" href="' + href + '">' + label + ARR + '</a></div></div></div></section>')


def lesson_card(i, slug, label, title, blurb, link="Read the free lesson"):
    return ('<article class="solution-card solution-card--%s"><span class="card-index">%02d / %s</span><h3>%s</h3><p>%s</p><a class="card-link" href="/resources/learn/%s">%s%s</a></article>'
            % (TONES[i % 4], i + 1, html.escape(label.upper()), html.escape(title), html.escape(blurb), slug, link, ARR))


def fix_links(s):
    s = s.replace(A_HOST + "/_paylink/vLVuWN0AkjFN", SESSION_MAIL).replace(L_HOST + "/resources.html", "/resources/free").replace(A_HOST + "/", "/")
    for a, b in [("/shop.html#ai-starter", "/shop"), ("/shop.html#pricing", "/shop"), ("/shop.html", "/shop"), ("/learn.html", "/resources/learn"),
                 ("/sessions.html", "/resources/sessions"), ("/resources.html", "/resources/free"), ("/community.html", "/community")]:
        s = s.replace('"' + a, '"' + b)
    s = re.sub(r'"/learn/([a-z0-9-]+)\.html', r'"/resources/learn/\1', s)
    return s.replace("thenailbawse@gmail.com", MAIL)


# ---------------- /resources ----------------
def build_index():
    lessons3 = "".join(lesson_card(i, *LESSONS[k]) for i, k in enumerate([0, 1, 2]))
    body = hero("FREE RESOURCES · BUSINESS EDUCATION FOR BEAUTY PROS",
                "Your expertise is the asset. <em>Build beyond the service.</em>",
                "Learn to turn professional skills into stronger business decisions, useful systems and new opportunities. Led by Anisia Burroughs, licensed cosmetologist and entrepreneur with experience across beauty services, education and business operations since 2018.",
                '<div class="meta-row"><span class="pill">Beauty entrepreneurship since 2018</span><span class="pill">Licensed cosmetologist</span><span class="pill">Education + community + AI systems</span></div>'
                '<div class="btn-row"><a class="button button--primary" href="/resources/free">Get the free guide' + ARR + '</a><a class="text-link" href="#start">Find your starting point <span aria-hidden="true">↓</span></a></div>',
                cur="/resources")
    body += ('<section class="solutions section" id="start"><div class="container"><div class="section-top"><div><p class="eyebrow">01 — FIND YOUR STARTING POINT</p>'
             '<h2 class="heading">What do you need <em>help with?</em></h2></div><p>No generic advice. Start with a real problem in your beauty business, and follow the lesson, tool or offer that addresses it.</p></div>'
             '<div class="res-grid">' + lessons3 + '</div><p style="margin-top:30px"><a class="text-link" href="/resources/learn">Open all free lessons' + ARR + '</a></p></div></section>')
    body += ('<section class="feature-band section"><div class="container feature__grid"><div class="feature__copy"><p class="eyebrow">02 — LEARN LIVE, FREE</p>'
             '<h2 class="heading">Free class: <em>Build Your AI Agent.</em></h2><p>A free live class on Google Meet for anyone in beauty: beauty pros, salon and suite owners, beauty creators and DIY beauty creators. 45 minutes of teaching, then 15 minutes of live Q&amp;A.</p>'
             '<ul class="checkpoints"><li><span>–</span> Bring the DM you\'re tired of answering</li><li><span>–</span> Watch an AI agent get built live</li><li><span>–</span> Leave with your next step</li></ul>'
             '<div class="btn-row"><a class="button button--primary" href="/webinar">Save my free seat' + ARR + '</a><a class="text-link" href="' + IG + '" target="_blank" rel="noopener">Free tips on Instagram' + ARR + '</a></div></div>'
             '<div class="feature__quote" aria-label="A reminder from the founder"><blockquote>"You are the asset. The system is here to support you."</blockquote><div class="quote-sign">— Anisia Burroughs, The Nail Bawse</div>'
             '<span class="vertical-note" aria-hidden="true">ANISIA BURROUGHS · THE NAIL BAWSE</span></div></div></section>')
    body += ('<section class="section intro"><div class="container"><p class="eyebrow">03 — WHEN YOU\'RE READY FOR MORE</p><h2 class="heading">Tools and support that make <em>your expertise work harder.</em></h2>'
             '<div class="offer-grid">'
             '<article class="card"><p class="eyebrow">Featured system</p><h3>Never Start Over</h3><p><em>The AI Business Starter System.</em> Learn to talk to AI, organize your business knowledge and set up your first AI employee. Includes a 45-minute live onboarding with Anisia.</p>'
             '<div class="price">$97 <small>Black Friday · Nov 27–30</small></div><p>Regular price $197 from December 1.</p><a class="button button--primary" href="/shop">See Never Start Over' + ARR + '</a></article>'
             '<article class="card"><p class="eyebrow">Community on Skool</p><h3>Beauty Bawse Club</h3><p>Business conversations, professional positioning, shared learning and practical resources for people working in beauty who want support beyond the next appointment.</p>'
             '<div class="price">$37 <small>per month</small></div><p>Live calls, courses, templates and beauty business education.</p><a class="button button--primary" href="/community">Join the club' + ARR + '</a></article>'
             '<article class="card"><p class="eyebrow">Private support</p><h3>AI working session</h3><p>A 60-minute session to define a repetitive task, map a practical solution and build or outline your first AI business assistant.</p>'
             '<div class="price">$150 <small>per session</small></div><p>Custom apps and websites are quoted separately.</p><a class="button button--primary" href="/resources/sessions">See session details' + ARR + '</a></article>'
             '</div></div></section>')
    body += band("START FREE", "You are <em>the asset.</em>", "Get the free guide to finding the business bottleneck that's slowing you down, and using your expertise more intentionally.", "Get the free guide", "/resources/free")
    frag("resources/index.html", "Free Resources | The Nail Bawse™",
         "Free beauty business education from The Nail Bawse: pricing, marketing, AI workflows and systems for beauty professionals, plus a free live class.", body)


def build_free():
    menu = "".join('<li><span>%02d</span><a href="/resources/learn/%s">%s</a></li>' % (i + 1, s, q) for i, (s, q) in enumerate([
        ("nail-tech-pricing", "How do I price my nail services?"), ("beauty-business-marketing", "How do I get more beauty clients?"),
        ("ai-business-assistant-beauty", "What can AI do for my business?"), ("beauty-business-systems", "How do I organize my business?"),
        ("nail-trends-2026", "What nail trends are people searching?")]))
    body = hero("FREE GUIDE", "YOU ARE <em>THE ASSET.</em>",
                "Start by identifying the business bottleneck slowing you down. Use this guide to organize what you know and think through which tasks could become simpler, repeatable processes.",
                '<div class="meta-row"><span class="pill">Free</span><span class="pill">No purchase required</span></div><div class="btn-row"><a class="button button--primary" href="' + GUIDE_MAIL + '">Get the free guide' + ARR +
                '</a></div><p class="note">Tap the button and send the email. Anisia sends you the guide.</p>', cur="/resources/free")
    body += ('<section class="section solutions"><div class="container split"><div><p class="eyebrow">QUICK LEARNING MENU</p><h2 class="heading">Choose <em>a question.</em></h2>'
             '<p class="section-copy">Each answer is a free lesson you can use today.</p></div><div><ul class="ticks">' + menu + '</ul></div></div></section>')
    body += ('<section class="section feature-band"><div class="container split"><div><p class="eyebrow">FREE SOCIAL LEARNING</p><h2 class="heading">Take a tip <em>with you.</em></h2></div><div>'
             '<p class="section-copy">Join the free live class, Build Your AI Agent, on Google Meet. Visit Instagram for bite-sized business education, or TikTok for demonstrations and LIVE conversations.</p>'
             '<div class="btn-row"><a class="button button--primary" href="/webinar">Free class' + ARR + '</a><a class="text-link" href="' + IG + '" target="_blank" rel="noopener">Instagram' + ARR +
             '</a><a class="text-link" href="' + TT + '" target="_blank" rel="noopener">TikTok + LIVE' + ARR + '</a></div></div></div></section>')
    frag("resources/free.html", "Free Guide: You Are the Asset | The Nail Bawse™", "Get the free You Are the Asset guide from The Nail Bawse and find the business bottleneck slowing you down.", body)


def build_learn():
    cards = "".join(lesson_card(i, *l) for i, l in enumerate(LESSONS))
    body = hero("BEAUTY BUSINESS LEARNING HUB", "Questions you Google. <em>Answers you can apply.</em>",
                "Independent beauty pros need more than inspiration. Explore pricing, content, client visibility, business systems and timely industry search trends.", cur="/resources/learn")
    body += '<section class="section solutions"><div class="container"><div class="res-grid">' + cards + '</div></div></section>'
    body += band("FREE GUIDE", "Start with <em>one bottleneck.</em>", "Use the free You Are the Asset guide to find one repeatable problem worth solving.", "Get the free guide", "/resources/free")
    frag("resources/learn.html", "Free Beauty Business Lessons | The Nail Bawse™", "Free lessons for beauty professionals: pricing, marketing, AI workflows, business systems and 2026 trends.", body)


def build_sessions():
    body = hero("PRIVATE EDUCATION AND IMPLEMENTATION", "Build your first <em>AI business assistant.</em>",
                "Bring your real business problem. We'll work together to define an outcome and create a practical system you can keep improving.",
                '<div class="meta-row"><span class="pill">60 minutes</span><span class="pill">One-to-one</span><span class="pill">$150</span></div><div class="btn-row"><a class="button button--primary" href="' + SESSION_MAIL +
                '">Request a $150 session' + ARR + '</a><a class="text-link" href="' + BUILD_MAIL + '">Ask about a custom build' + ARR + '</a></div><p class="note">Tap to send a request. Anisia replies with open times and your payment link.</p>',
                cur="/resources/sessions")
    body += ('<section class="section solutions"><div class="container split"><div><p class="eyebrow">60-MINUTE PRIVATE WORKING SESSION</p><h2 class="heading">A real workflow, <em>not another vague tutorial.</em></h2>'
             '<p class="section-copy">Use your session to organize one repeated business task and learn the fundamentals of using an AI assistant responsibly. Examples include outlining client FAQs, brainstorming educational content, organizing service policies, or designing a follow-up process.</p>'
             '<p class="note">Custom apps, websites, and complex integrations require a separate scope and quote. Your access to third-party tools may affect implementation options.</p></div>'
             '<div><ul class="ticks"><li><span>01</span>Identify the current problem and desired result</li><li><span>02</span>Map the workflow and information it needs</li><li><span>03</span>Build or outline a first assistant together</li><li><span>04</span>Leave with clear next actions</li></ul></div></div></section>')
    faqs = [("Is this a full custom app or website build?", "No. The base session focuses on a 60-minute working session and practical workflow. Complex build projects are scoped and quoted separately."),
            ("Do I have to be a nail technician?", "No. Nail techs, lash artists, hairstylists, makeup artists, estheticians and other independent beauty professionals can apply the methods to their own businesses."),
            ("How do I book the time?", 'Send a request and Anisia replies with open times and your payment link. Questions first? Email <a href="mailto:' + MAIL + '">' + MAIL + '</a>.')]
    body += ('<section class="faq section"><div class="container faq__grid"><div><p class="eyebrow">QUESTIONS ANSWERED</p><h2 class="heading">Know what <em>to expect.</em></h2></div><div class="faq-list">' +
             "".join('<details><summary>%s<span class="faq-plus" aria-hidden="true">+</span></summary><p>%s</p></details>' % (q, a) for q, a in faqs) + '</div></div></section>')
    body += band("PRIVATE SUPPORT · $150", "Work on your AI workflow <em>together.</em>", "One-to-one guidance on one real task in your business.", "Request a session", SESSION_MAIL)
    frag("resources/sessions.html", "AI Business Assistant Sessions | The Nail Bawse™", "A 60-minute private working session with Anisia Burroughs to build your first AI business assistant. $150.", body)


def build_lessons():
    for i, (slug, label, title, blurb) in enumerate(LESSONS):
        s = open(os.path.join(SRC, "a/learn/%s.html" % slug), encoding="utf-8").read()
        h = re.search(r'(?s)<div class="article-hero">(.*?)</div></div>', s).group(1)
        crumb = re.sub(r"<[^>]+>", "", re.search(r'(?s)<p class="breadcrumb">(.*?)</p>', h).group(1)).split("/")[-1].strip()
        h1 = re.search(r"(?s)<h1>(.*?)</h1>", h).group(1)
        lede = re.findall(r"(?s)<p>(.*?)</p>", h)[-1]
        art = re.search(r'(?s)<article class="main-article wrap">(.*?)</article>', s).group(1)
        art = re.sub(r'(?s)<div class="article-nav">.*$', "", art)
        art = art.replace('class="article-banner"', 'class="banner"')
        art = re.sub(r'(?s)<h2>Get personalized help</h2>.*?(?=<h2|$)', "", art)
        art = re.sub(r'Pair this process with the <a[^>]*>Checklist Bundle</a> or <a[^>]*>CEO Systems Starter Kit</a>, and read the', "Read the", art)
        art = re.sub(r'The Nail Bawse Pricing Formula Kit is part of the <a[^>]*>shop resource collection</a>; you can also review the', "Then review the", art)
        art = fix_links(art)
        if re.search(r"Checklist Bundle|CEO Systems Starter Kit|Pricing Formula Kit", art):
            raise SystemExit("product not in shop still mentioned in " + slug)
        others = [l for l in LESSONS if l[0] != slug][:3]
        title_text = re.sub(r"<[^>]+>", "", h1)
        body = hero("FREE LESSON · " + html.escape(crumb.upper()), h1, lede, '<p><a class="text-link" href="/resources/learn"><span aria-hidden="true">←</span> All free lessons</a></p>')
        body += '<section class="section"><div class="container"><article class="prose">' + art + '</article></div></section>'
        body += ('<section class="section intro"><div class="container"><p class="eyebrow">KEEP LEARNING</p><div class="keep">' +
                 "".join(lesson_card(j, *o) for j, o in enumerate(others)) + '</div></div></section>')
        body += band("GET PERSONALIZED HELP", "Build it <em>with Anisia.</em>", "One-to-one AI business working sessions start at $150. Or join the free live class, Build Your AI Agent.", "See AI sessions", "/resources/sessions")
        frag("resources/learn/%s.html" % slug, title_text + " | The Nail Bawse™", blurb, body)


# ---------------- /card (standalone, main-site brand tokens) ----------------
BRAND_CSS = (
    ":root{--espresso:#39261F;--espresso-2:#281b17;--rose:#df9fb5;--rose-mist:#f8d8e2;--cream:#fffaf6;--paper:#fffaf6;--ink:#39261F;--muted:#65534a;--border:#e5d6cd;--serif:Georgia,'Times New Roman',serif;--sans:Arial,'Helvetica Neue',Helvetica,sans-serif}"
    "body{font-family:var(--sans)!important;background:var(--paper)!important}"
    ".nb-brand{display:flex;align-items:center;gap:12px;text-decoration:none;color:var(--espresso)}.nb-symbol{width:42px;height:42px;display:grid;place-items:center;background:var(--espresso);color:#fff7f3;font:italic 17px var(--serif);letter-spacing:-.04em}"
    ".nb-word{display:flex;flex-direction:column;line-height:1.15}.nb-word strong{font:800 12px var(--sans);letter-spacing:.2em}.nb-word small{font:700 9px var(--sans);letter-spacing:.24em;color:#78574b;margin-top:4px}"
    ".top-tag{border-radius:0!important;border-color:var(--espresso)!important;background:transparent!important;letter-spacing:.14em!important}"
    ".hero,.card-face,.lower,.lower-qr{border-radius:5px!important}.hero{box-shadow:none!important}"
    ".eyebrow{letter-spacing:.22em!important;font-size:10px!important;color:var(--rose)!important}.hero h1 em{color:var(--rose)!important}"
    ".chip{border-radius:0!important;letter-spacing:.14em!important;font-weight:800}"
    ".btn{border-radius:0!important;text-transform:uppercase;letter-spacing:.15em;font-size:10px!important;min-height:52px}.btn.primary:hover{background:#5a3930}"
    ".direct-links a{text-transform:uppercase;letter-spacing:.12em;font-size:11px;font-weight:800;text-decoration:none;border-bottom:1px solid var(--espresso);padding-bottom:6px}"
    ".section-kicker,.scan-label{color:#78574b!important;letter-spacing:.22em!important}.section-head h2,.card-front h3,.lower h3{letter-spacing:-.04em!important}"
    ".flip-card:nth-child(1) .card-front{background:#f2d4df!important;border-color:#f2d4df!important}.flip-card:nth-child(2) .card-front{background:#fffaf5!important;border-color:var(--border)!important}"
    ".flip-card:nth-child(4) .card-front{background:#e9ded7!important;border-color:#e9ded7!important}.card-face{box-shadow:none!important}"
    ".mini-link{border-radius:0!important;text-transform:uppercase;letter-spacing:.12em;font-size:10px!important;background:#f2d4df!important}"
    ".lower{background:#fffaf5!important}.footer-wordmark{font:normal 28px var(--serif);letter-spacing:-.04em}.footer-wordmark em{color:#ad627e}"
)
NB_MARK = '<a class="nb-brand" href="/" aria-label="The Nail Bawse home"><span class="nb-symbol" aria-hidden="true">NB</span><span class="nb-word"><strong>THE NAIL BAWSE</strong><small>ANISIA BURROUGHS</small></span></a>'


def build_card():
    import qrcode
    os.makedirs(OUT + "/card", exist_ok=True)

    def base(s):
        s = re.sub(r'<script[^>]*manage\.wix\.com[^>]*></script>', "", s)
        s = s.replace("thenailbawse@gmail.com", MAIL).replace(B_HOST + "/", D + "/card")
        s = s.replace(L_HOST + "/paid-teaching.html", "mailto:" + MAIL + "?subject=Speaking%20or%20paid%20education%20inquiry")
        s = s.replace(L_HOST + "/ai-build.html", BUILD_MAIL).replace(L_HOST + "/resources.html", "/resources").replace(L_HOST + "/", D + "/")
        s = s.replace('href="save-contact.html"', 'href="/card/save-contact"').replace('href="work-with-me.html"', 'href="/card/work-with-me"')
        s = s.replace('href="favicon.svg"', 'href="/favicon.svg"')
        return s

    def must(s, a, b):
        if s.count(a) != 1: raise SystemExit("card: expected 1 of %r, found %d" % (a[:60], s.count(a)))
        return s.replace(a, b)

    s = base(open(os.path.join(SRC, "b/index.html"), encoding="utf-8").read())
    s = must(s, '<div class="logo"><span class="star">✦</span> THE NAIL BAWSE</div>', NB_MARK)
    s = must(s, '<div class="art-monogram">AB</div>', '<img class="art-photo" src="/card/anisia.jpg" alt="Anisia Burroughs" width="585" height="600">')
    s = must(s, '<div class="hero-art" aria-hidden="true">', '<div class="hero-art">')
    s = must(s, '<a href="/card/work-with-me" target="_blank" rel="noopener noreferrer">Book speaking or education', '<a href="/card/work-with-me">Book speaking or education') if '"/card/work-with-me" target' in s else s
    s = s.replace('<a href="mailto:' + MAIL + '?subject=Speaking%20or%20paid%20education%20inquiry" target="_blank" rel="noopener noreferrer">Book speaking or education', '<a href="/card/work-with-me">Book speaking or education')
    s = must(s, '<a href="/resources" target="_blank" rel="noopener noreferrer">Explore AI and business resources <span aria-hidden="true">↗</span></a>',
             '<a href="/resources">Free business resources <span aria-hidden="true">↗</span></a><a href="/webinar">Free class: Build Your AI Agent <span aria-hidden="true">↗</span></a>'
             '<a href="/community">Beauty Bawse Club · $37/mo <span aria-hidden="true">↗</span></a><a href="/shop">Shop: Never Start Over <span aria-hidden="true">↗</span></a>')
    s = s.replace(D + '/" target="_blank" rel="noopener noreferrer">Visit my website', D + '/">Visit my website').replace(D + '/" target="_blank" rel="noopener noreferrer">OPEN WEBSITE', D + '/">OPEN WEBSITE')
    for old, new in [("nail-bawse-qr", "qr-website"), ("work-qr", "qr-work"), ("contact-qr", "qr-contact"), ("share-card-qr", "qr-card"), ("instagram-qr", "qr-instagram")]:
        s = s.replace('src="assets/%s.png"' % old, 'src="/card/%s.png"' % new)
    s = s.replace('<div class="back-url">' + MAIL + '</div>', '<div class="back-url">Speaking · AI builds · Brands</div>')
    s = must(s, '<footer class="footer"><span>', '<footer class="footer"><span><span class="footer-wordmark">THE NAIL <em>BAWSE.</em></span><br>')
    s = must(s, '<a href="mailto:' + MAIL + '">Email</a>', '<a href="/">thenailbawse.com</a> &nbsp; · &nbsp; <a href="mailto:' + MAIL + '">Email</a>')
    photo = (".art-photo{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:50% 12%;z-index:0}"
             ".art-frame:before{content:'';position:absolute;inset:0;background:linear-gradient(180deg,rgba(57,38,31,0) 55%,rgba(57,38,31,.55) 100%);z-index:1}"
             ".art-stamp{color:#fff!important}.art-frame:after{z-index:2;border-color:rgba(255,255,255,.45)!important}"
             "@media(max-width:760px){.art-frame{aspect-ratio:.86!important;max-width:320px!important;margin:0 auto;border-radius:150px 150px 5px 5px!important}.art-frame:after{border-radius:140px 140px 3px 3px!important}"
             ".direct-links{display:flex!important;flex-direction:column;align-items:flex-start;gap:6px}.direct-links a{white-space:nowrap}}")
    s = must(s, "</style>", BRAND_CSS + photo + "</style>")
    open(OUT + "/card/index.html", "w", encoding="utf-8").write(s)

    for name in ["save-contact", "work-with-me"]:
        s = base(open(os.path.join(SRC, "b/%s.html" % name), encoding="utf-8").read())
        s = re.sub(r"<header>✦ THE NAIL BAWSE[^<]*</header>", "<header>" + NB_MARK + "</header>", s)
        if name == "save-contact":
            s = must(s, '"item1.URL:"+location.origin+"/"', '"item1.URL:' + D + '/card"')
            s = must(s, '"TITLE:Founder and Beauty Educator"', '"TITLE:Founder, The Nail Bawse"')
        s = s.replace('href="mailto:' + MAIL + '?subject=Speaking%20or%20paid%20education%20inquiry" target="_blank" rel="noopener noreferrer"', 'href="mailto:' + MAIL + '?subject=Speaking%20or%20paid%20education%20inquiry"')
        s = s.replace(BUILD_MAIL + '" target="_blank" rel="noopener noreferrer"', BUILD_MAIL + '"')
        s = must(s, "</style>", BRAND_CSS + "main>header{display:flex;justify-content:center;margin-bottom:18px}.panel,.option,.card,section{border-radius:5px!important}a.btn,.btn{border-radius:0!important}</style>")
        if "✦" in s: raise SystemExit("old logo left in " + name)
        open(OUT + "/card/%s.html" % name, "w", encoding="utf-8").write(s)

    def qr(url, fn):
        q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2); q.add_data(url); q.make(fit=True)
        q.make_image(fill_color="#39261F", back_color="white").save(OUT + "/card/" + fn)
    qr(D + "/", "qr-website.png"); qr(D + "/card/work-with-me", "qr-work.png"); qr(D + "/card/save-contact", "qr-contact.png")
    qr(D + "/card", "qr-card.png"); qr(IG, "qr-instagram.png")
    from PIL import Image
    im = Image.open(os.path.join(HERE, "../../../funnel-site/public/assets/anisia.jpg")).convert("RGB").crop((60, 0, 840, 800))
    im.thumbnail((600, 600)); im.save(OUT + "/card/anisia.jpg", quality=84, optimize=True, progressive=True)


if __name__ == "__main__":
    if os.path.isdir(OUT): shutil.rmtree(OUT)
    os.makedirs(OUT)
    build_index(); build_free(); build_learn(); build_sessions(); build_lessons(); build_card()
    bad = []
    for root, _, fs in os.walk(OUT):
        for f in fs:
            if f.endswith(".html"):
                t = open(os.path.join(root, f), encoding="utf-8").read()
                for b in ["wix-site-host", "manage.wix.com", "gmail.com", '.html"', "Zoom", "$27/", "Checklist Bundle", "CEO Systems"]:
                    if b in t: bad.append((f, b))
    print("leftovers:", bad or "none")
