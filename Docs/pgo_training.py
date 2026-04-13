#!/usr/bin/env python3
"""
ducksteps — Custom PGO training workload
=========================================
Drives an instrumented Firefox build through realistic browsing patterns
to produce high-quality LLVM profile data.

Called from build/pgo/profileserver.py during the PGO profiling phase.
Zero external dependencies — uses in-tree marionette_driver.

Site corpus covers: JS-heavy SPAs, long-form reading, video playback,
e-commerce, maps/canvas, speed tests, complex CSS animations, and
international text layouts.

Scroll behaviors are deterministic per site category.
Timing jitter within behaviors is randomized for realistic branch bias.

Licensed under MPL 2.0.
"""

import os
import sys
import time
import random

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MARIONETTE_PORT = 2828
CONNECT_TIMEOUT = 120   # seconds to wait for Firefox's Marionette server
PAGE_LOAD_TIMEOUT = 30  # seconds per navigation before skipping

# ---------------------------------------------------------------------------
# Site corpus
# ---------------------------------------------------------------------------
# Each entry: (url, behavior, dwell_seconds)
#
# Behaviors:
#   long_read    — burst 3-5 scrolls, 5-10s read pause, repeat
#   video        — navigate to video, play, scroll comments
#   ecommerce    — skim listings, click product, read reviews
#   spa          — search/navigate/click, exercise JS + DOM mutations
#   map          — pan/zoom, hover for tooltips, let tiles render
#   speedtest    — trigger test, wait for completion
#   complex_css  — scroll to trigger animations, pause at transitions
#   static       — single slow scroll pass, brief idle
#
# Sorted by PGO impact (high -> low) within each group.
# Total estimated runtime: ~90-100 minutes.

SITES = [
    # ===== VIDEO PLAYBACK (90s each) — codec + compositor + audio sync =====
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "video", 90),
    ("https://www.youtube.com/watch?v=jNQXAC9IVRw", "video", 90),
    ("https://vimeo.com/channels/staffpicks", "video", 75),
    ("https://www.twitch.tv/directory", "video", 75),
    ("https://www.dailymotion.com/us", "video", 60),

    # ===== JS-HEAVY SPAs (60s each) — SpiderMonkey JIT, GC, DOM mutation ===
    # Personal sites
    ("https://github.com/SyntaxError-PEBKAC/ducksteps", "spa", 60),
    ("https://duckduckgo.com/?q=firefox+ESR+performance", "spa", 60),
    ("https://duck.ai", "spa", 45),
    ("https://claude.ai", "spa", 30),
    ("https://redlib.catsarch.com/", "spa", 60),
    # React ecosystem
    ("https://react.dev/learn", "spa", 60),
    ("https://www.airbnb.com/s/Tokyo/homes", "spa", 60),
    ("https://www.netflix.com/browse", "spa", 45),
    # Angular
    ("https://angular.dev/overview", "spa", 45),
    # Vue
    ("https://gitlab.com/explore/projects/trending", "spa", 60),
    ("https://vuejs.org/guide/introduction", "spa", 45),
    # Svelte
    ("https://svelte.dev/tutorial/basics", "spa", 45),
    # Productivity / dashboards
    ("https://observablehq.com/@d3/gallery", "spa", 60),
    ("https://d3js.org/", "spa", 45),
    ("https://excalidraw.com", "spa", 45),
    # Community
    ("https://www.reddit.com/r/firefox/", "spa", 60),
    ("https://old.reddit.com/r/firefox/", "spa", 45),
    ("https://news.ycombinator.com", "spa", 45),
    ("https://stackoverflow.com/questions?tab=Active", "spa", 60),
    ("https://meta.discourse.org/latest", "spa", 45),

    # ===== LONG-FORM READING (60s each) — reflow, font shaping, glyph cache =
    # Personal sites
    ("https://www.bbc.com/news", "long_read", 60),
    ("https://apnews.com", "long_read", 60),
    ("https://arstechnica.com", "long_read", 60),
    ("https://liliputing.com", "long_read", 50),
    ("https://www.xda-developers.com", "long_read", 50),
    ("https://www.gsmarena.com/reviews.php3", "long_read", 50),
    # Broad news / media
    ("https://www.reuters.com", "long_read", 60),
    ("https://www.npr.org", "long_read", 50),
    ("https://www.theguardian.com/international", "long_read", 60),
    ("https://www.aljazeera.com", "long_read", 50),
    ("https://www.theatlantic.com", "long_read", 50),
    ("https://www.theverge.com", "long_read", 50),
    ("https://www.wired.com", "long_read", 50),
    ("https://techcrunch.com", "long_read", 45),
    ("https://www.engadget.com", "long_read", 45),
    # Developer docs (long-form, code-heavy layout)
    ("https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide", "long_read", 60),
    ("https://doc.rust-lang.org/book/", "long_read", 50),
    ("https://docs.python.org/3/tutorial/", "long_read", 45),
    ("https://caniuse.com", "long_read", 30),
    ("https://www.npmjs.com", "long_read", 30),
    ("https://pypi.org", "long_read", 30),
    # International text (CJK, RTL, complex scripts)
    ("https://www.nhk.or.jp/nhkworld/", "long_read", 45),
    ("https://www3.nhk.or.jp/news/", "long_read", 45),
    ("https://www.naver.com", "long_read", 40),
    ("https://www.aljazeera.net", "long_read", 45),
    ("https://www.thehindu.com", "long_read", 40),
    ("https://zh.wikipedia.org/wiki/Wikipedia:%E9%A6%96%E9%A1%B5", "long_read", 40),
    # Blogs / publications
    ("https://medium.com/tag/technology", "long_read", 45),
    ("https://dev.to", "long_read", 45),
    ("https://en.wikipedia.org/wiki/Firefox", "long_read", 60),

    # ===== E-COMMERCE (50s each) — image decode, lazy load, mixed layout ====
    # Personal sites
    ("https://www.amazon.com/s?k=mechanical+keyboard", "ecommerce", 55),
    ("https://www.apple.com/shop/buy-mac", "ecommerce", 40),
    # Broad
    ("https://www.ebay.com/sch/i.html?_nkw=gpu", "ecommerce", 50),
    ("https://www.bestbuy.com/site/searchpage.jsp?st=laptop", "ecommerce", 50),
    ("https://www.newegg.com/p/pl?d=ssd", "ecommerce", 45),
    ("https://www.target.com/c/electronics/-/N-5xtg6", "ecommerce", 40),
    ("https://www.etsy.com/search?q=mechanical+keyboard", "ecommerce", 45),

    # ===== COMPLEX CSS / ANIMATION (45s each) — compositor, transitions =====
    ("https://stripe.com", "complex_css", 50),
    ("https://linear.app", "complex_css", 45),
    ("https://vercel.com", "complex_css", 45),
    ("https://www.apple.com", "complex_css", 45),
    ("https://github.com/features", "complex_css", 40),
    ("https://tailwindcss.com", "complex_css", 40),

    # ===== MAPS / CANVAS / WEBGL (45s each) — GPU compositor, tile render ===
    # Personal sites
    ("https://globe.adsb.fi", "map", 50),
    # Broad
    ("https://www.google.com/maps/@35.6762,139.6503,12z", "map", 50),
    ("https://www.openstreetmap.org/#map=12/35.6762/139.6503", "map", 45),
    ("https://threejs.org/examples/#webgl_animation_skinning_blending", "map", 45),
    ("https://www.shadertoy.com/view/Xds3zN", "map", 40),

    # ===== SPEED TESTS (40s each) — canvas rendering + network stack =======
    # Personal sites
    ("https://www.speedtest.net", "speedtest", 45),
    ("https://speed.cloudflare.com", "speedtest", 40),
    ("https://librespeed.org", "speedtest", 35),

    # ===== STATIC / REFERENCE (20s each) — baseline coverage ===============
    # Personal sites
    ("https://www.boincstats.com", "static", 25),
    ("https://time.is", "static", 15),
    ("https://dnscheck.tools", "static", 20),
    ("https://goodwok.day", "static", 15),
    ("https://libera.chat", "static", 15),
    # Government / institutional (forms, tables, accessibility markup)
    ("https://www.usa.gov", "static", 25),
    ("https://www.cdc.gov", "static", 25),
    ("https://www.nasa.gov", "static", 25),
    ("https://europa.eu", "static", 20),
    ("https://www.gov.uk", "static", 20),
    ("https://www.craigslist.org", "static", 15),
]


# ---------------------------------------------------------------------------
# Scroll behaviors — deterministic per category, jitter within execution
# ---------------------------------------------------------------------------

def _jitter(base, pct=0.2):
    """Return base +/- pct variation. Prevents pathologically uniform profiles."""
    return base * random.uniform(1.0 - pct, 1.0 + pct)


def _mouse_jiggle(client):
    """Small mouse move to trigger hover states and intersection observers."""
    client.execute_script("""
        document.dispatchEvent(new MouseEvent('mousemove', {
            clientX: Math.floor(Math.random() * window.innerWidth * 0.8 + 50),
            clientY: Math.floor(Math.random() * window.innerHeight * 0.8 + 50),
            bubbles: true
        }));
    """)


def _get_scroll_height(client):
    """Return total scrollable height of the page."""
    return client.execute_script(
        "return Math.max("
        "document.body.scrollHeight, "
        "document.documentElement.scrollHeight)"
    )


def _get_scroll_pos(client):
    """Return current vertical scroll position."""
    return client.execute_script(
        "return window.pageYOffset || document.documentElement.scrollTop"
    )


def behave_long_read(client, dwell):
    """
    Reading pattern: burst 3-5 scrolls, read 5-10 seconds, repeat.
    Exercises reflow, font shaping, glyph caching, and paint.
    """
    start = time.time()
    cycle = 0
    while (time.time() - start) < dwell:
        # Burst: 3-5 scroll increments
        burst = random.randint(3, 5)
        for i in range(burst):
            px = int(_jitter(350, 0.3))
            client.execute_script(
                "window.scrollBy({top: %d, behavior: 'smooth'})" % px
            )
            time.sleep(_jitter(0.25, 0.3))

        # Mouse jiggle every other cycle to trigger IntersectionObserver
        if cycle % 2 == 0:
            _mouse_jiggle(client)

        # Read pause: 5-10 seconds
        time.sleep(random.uniform(5.0, 10.0))
        cycle += 1

    # Settle: let deferred layout/paint complete
    time.sleep(2.0)


def behave_video(client, dwell):
    """
    Video playback: let video play, brief comment scroll, continue watching.
    Exercises codec, compositor, audio sync, and infinite-scroll comments.
    """
    # Wait for video player to initialize
    time.sleep(5.0)

    # Attempt to start playback (handles autoplay-blocked pages)
    client.execute_script("""
        const v = document.querySelector('video');
        if (v && v.paused) { v.play().catch(() => {}); }
    """)

    # Watch for ~60% of dwell
    watch_time = dwell * 0.6
    time.sleep(watch_time)

    # Scroll through comments/related content for remaining time
    remaining = dwell - watch_time - 5.0
    start = time.time()
    while (time.time() - start) < remaining:
        px = int(_jitter(400, 0.25))
        client.execute_script(
            "window.scrollBy({top: %d, behavior: 'smooth'})" % px
        )
        time.sleep(_jitter(1.5, 0.3))

    time.sleep(2.0)


def behave_ecommerce(client, dwell):
    """
    E-commerce: fast skim through listings, then slow-read on details.
    Exercises image decode, lazy loading, and mixed content layouts.
    """
    skim_time = dwell * 0.4
    start = time.time()

    # Phase 1: skim listings (~40% of dwell)
    while (time.time() - start) < skim_time:
        burst = random.randint(2, 4)
        for _ in range(burst):
            px = int(_jitter(500, 0.25))
            client.execute_script(
                "window.scrollBy({top: %d, behavior: 'smooth'})" % px
            )
            time.sleep(_jitter(0.2, 0.3))
        time.sleep(random.uniform(2.0, 4.0))
        _mouse_jiggle(client)

    # Phase 2: scroll back up ~30% and slow-read (like reading reviews)
    scroll_height = _get_scroll_height(client)
    backtrack = int(scroll_height * 0.3)
    client.execute_script(
        "window.scrollBy({top: -%d, behavior: 'smooth'})" % backtrack
    )
    time.sleep(2.0)

    # Phase 3: reading pattern on the reviews section
    elapsed_so_far = time.time() - start
    remaining = dwell - elapsed_so_far
    if remaining > 5.0:
        behave_long_read(client, max(remaining - 2.0, 5.0))

    time.sleep(2.0)


def behave_spa(client, dwell):
    """
    SPA interaction: search/navigate, click through pages, scroll results.
    Exercises SpiderMonkey JIT, DOM mutation, GC, virtual scrolling.
    """
    # Phase 1: initial page scroll to trigger lazy hydration
    time.sleep(3.0)
    for _ in range(3):
        px = int(_jitter(400, 0.25))
        client.execute_script(
            "window.scrollBy({top: %d, behavior: 'smooth'})" % px
        )
        time.sleep(_jitter(0.3, 0.3))

    # Phase 2: simulate tab-like interaction (trigger focus events)
    client.execute_script("""
        const inputs = document.querySelectorAll(
            'input[type="text"], input[type="search"]'
        );
        if (inputs.length > 0) {
            inputs[0].focus();
            inputs[0].dispatchEvent(new Event('focus', {bubbles: true}));
        }
    """)
    time.sleep(1.0)

    # Phase 3: scroll through content using the reading pattern
    remaining = dwell - 6.0
    if remaining > 5.0:
        behave_long_read(client, remaining)


def behave_map(client, dwell):
    """
    Map/Canvas/WebGL: pan, zoom, hover to trigger tile renders and
    GPU compositor paths.
    """
    time.sleep(4.0)  # let initial tile load complete

    start = time.time()
    while (time.time() - start) < (dwell - 4.0):
        # Simulate scroll-zoom (triggers wheel events for map zoom)
        direction = random.choice([120, -120])
        client.execute_script("""
            document.dispatchEvent(new WheelEvent('wheel', {
                deltaY: %d,
                clientX: window.innerWidth / 2,
                clientY: window.innerHeight / 2,
                bubbles: true
            }));
        """ % direction)
        time.sleep(_jitter(2.0, 0.3))

        # Simulate pan via mouse drag (move events)
        dx = random.randint(-200, 200)
        dy = random.randint(-150, 150)
        client.execute_script("""
            const cx = window.innerWidth / 2;
            const cy = window.innerHeight / 2;
            const el = document.elementFromPoint(cx, cy) || document;
            el.dispatchEvent(new MouseEvent('mousedown', {
                clientX: cx, clientY: cy, bubbles: true
            }));
            el.dispatchEvent(new MouseEvent('mousemove', {
                clientX: cx + %d, clientY: cy + %d, bubbles: true
            }));
            el.dispatchEvent(new MouseEvent('mouseup', {
                clientX: cx + %d, clientY: cy + %d, bubbles: true
            }));
        """ % (dx, dy, dx, dy))
        time.sleep(_jitter(3.0, 0.3))

    time.sleep(2.0)


def behave_speedtest(client, dwell):
    """
    Speed test: attempt to trigger the test, then wait for completion.
    Exercises canvas rendering and network stack hot paths.
    """
    time.sleep(3.0)

    # Try clicking a "start" or "go" button
    client.execute_script("""
        const btns = document.querySelectorAll(
            'button, a.button, [role="button"], .start-button, .js-start-test'
        );
        for (const btn of btns) {
            const text = (btn.textContent || '').toLowerCase();
            if (['go', 'start', 'test', 'begin'].some(w => text.includes(w))) {
                btn.click();
                break;
            }
        }
    """)

    # Wait for test to run (most speed tests take 20-30s)
    time.sleep(dwell - 5.0)

    # Scroll to see results
    client.execute_script("window.scrollBy({top: 400, behavior: 'smooth'})")
    time.sleep(2.0)


def behave_complex_css(client, dwell):
    """
    Complex CSS/animation sites: scroll slowly to trigger CSS transitions,
    pause at animation-heavy sections.
    """
    start = time.time()

    while (time.time() - start) < dwell:
        # Slow scroll to trigger scroll-linked animations
        px = int(_jitter(200, 0.25))
        client.execute_script(
            "window.scrollBy({top: %d, behavior: 'smooth'})" % px
        )
        time.sleep(_jitter(1.5, 0.3))

        # Pause longer every ~4 scrolls (lets CSS transitions complete)
        if random.random() < 0.25:
            time.sleep(_jitter(4.0, 0.3))
            _mouse_jiggle(client)

    time.sleep(2.0)


def behave_static(client, dwell):
    """
    Static/reference: single slow scroll pass, minimal interaction.
    Just enough to exercise basic layout and font rendering.
    """
    time.sleep(2.0)
    elapsed = 0.0
    while elapsed < (dwell - 3.0):
        px = int(_jitter(300, 0.25))
        client.execute_script(
            "window.scrollBy({top: %d, behavior: 'smooth'})" % px
        )
        pause = _jitter(2.0, 0.3)
        time.sleep(pause)
        elapsed += pause + 0.3
    time.sleep(1.0)


# Behavior dispatch — deterministic mapping, no randomness in selection
BEHAVIOR_DISPATCH = {
    "long_read":    behave_long_read,
    "video":        behave_video,
    "ecommerce":    behave_ecommerce,
    "spa":          behave_spa,
    "map":          behave_map,
    "speedtest":    behave_speedtest,
    "complex_css":  behave_complex_css,
    "static":       behave_static,
}


# ---------------------------------------------------------------------------
# Marionette connection
# ---------------------------------------------------------------------------

def connect_marionette(topsrcdir, port=MARIONETTE_PORT, timeout=CONNECT_TIMEOUT):
    """
    Connect to Firefox's Marionette server with retry.
    Adds marionette_driver to sys.path from the in-tree client if needed.
    """
    # Ensure marionette_driver is importable (may not be on default PYTHONPATH)
    client_path = os.path.join(topsrcdir, "testing", "marionette", "client")
    if os.path.isdir(client_path) and client_path not in sys.path:
        sys.path.insert(0, client_path)

    from marionette_driver.marionette import Marionette

    print("[ducksteps PGO] Connecting to Marionette on port %d..." % port)
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            client = Marionette(host="127.0.0.1", port=port)
            client.start_session()
            print("[ducksteps PGO] Connected.")
            return client
        except Exception as e:
            last_err = e
            time.sleep(2)

    raise RuntimeError(
        "Could not connect to Marionette after %ds: %s" % (timeout, last_err)
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_training(topsrcdir):
    """
    Main entry point. Called from profileserver.py with build.topsrcdir.
    Connects to the already-running instrumented Firefox, drives workloads,
    then cleanly quits Firefox to flush profraw data.
    """
    total_sites = len(SITES)
    total_dwell = sum(s[2] for s in SITES)
    print("[ducksteps PGO] Training %d sites, estimated %d minutes" % (
        total_sites, total_dwell // 60
    ))

    client = connect_marionette(topsrcdir)

    # Set page load timeout
    client.timeout.page_load = PAGE_LOAD_TIMEOUT

    succeeded = 0
    skipped = 0
    start_all = time.time()

    for i, (url, behavior, dwell) in enumerate(SITES, 1):
        print("[ducksteps PGO] [%d/%d] %s (%s, %ds)" % (
            i, total_sites, url, behavior, dwell
        ))
        try:
            client.navigate(url)
            time.sleep(3)  # initial page load settle
            BEHAVIOR_DISPATCH[behavior](client, dwell)
            succeeded += 1
        except Exception as e:
            print("[ducksteps PGO]   SKIP: %s" % e)
            skipped += 1
            # Try to recover by navigating to about:blank
            try:
                client.navigate("about:blank")
                time.sleep(1)
            except Exception:
                pass
            continue

    elapsed = (time.time() - start_all) / 60.0
    print("[ducksteps PGO] Done. %d succeeded, %d skipped, %.1f minutes elapsed" % (
        succeeded, skipped, elapsed
    ))

    # Clean shutdown — triggers atexit -> flushes .profraw
    print("[ducksteps PGO] Quitting Firefox (clean shutdown for profraw flush)...")
    try:
        client.quit(in_app=True)
    except Exception:
        pass  # connection drops during quit — expected
