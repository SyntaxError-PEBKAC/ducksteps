/* ducksteps — Custom PGO Training Workload
 * ==========================================
 * WebExtension that drives an instrumented Firefox build through realistic
 * browsing patterns to produce high-quality LLVM profile data.
 *
 * Loaded into the PGO profiling phase via profileserver.py.
 * Runs the full site corpus with scroll behaviors and hot-path exercisers,
 * then navigates to pgo_done.html which calls Quitter.quit() for clean
 * shutdown and profraw flush.
 *
 * Licensed under MPL 2.0.
 */

/* global dump, browser */

const PGO_PORT = 8888;
const PAGE_LOAD_TIMEOUT = 30000;

// ---------------------------------------------------------------------------
// Site corpus: [url, behavior, dwell_seconds]
// Sorted by PGO impact (high -> low) within each category.
// Total estimated runtime: ~112 minutes.
// ---------------------------------------------------------------------------
const SITES = [
  // VIDEO PLAYBACK — codec + compositor + audio sync
  ["https://www.youtube.com/watch?v=u_5wLvlRhc0", "video_late_scroll", 110],
  ["https://www.youtube.com/watch?v=8rwnAj-i1Ps", "video_late_scroll", 110],
  ["https://vimeo.com/32001208?autoplay=1", "video", 75],
  ["https://www.twitch.tv/StreamerHouse", "video", 75],
  ["https://www.dailymotion.com/video/xa5pjb6", "video", 120],

  // JS-HEAVY SPAs — SpiderMonkey JIT, GC, DOM mutation
  ["https://github.com/SyntaxError-PEBKAC/ducksteps/releases", "spa", 60],
  ["https://duckduckgo.com/?q=firefox+ESR+performance", "spa", 22],
  ["https://duck.ai", "spa", 15],
  ["https://claude.ai", "spa", 23],
  ["https://redlib.catsarch.com/", "spa", 90],
  ["https://redlib.catsarch.com/r/pics/comments/haucpf/ive_found_a_few_funny_memories_during_lockdown/", "spa", 182],
  ["https://react.dev/learn", "spa", 85],
  ["https://www.airbnb.com/s/Tokyo/homes", "spa", 35],
  ["https://netflix.com", "spa", 15],
  ["https://angular.dev/overview", "spa", 40],
  ["https://vuejs.org/guide/essentials/component-basics.html", "spa", 73],
  ["https://svelte.dev/docs/svelte/v5-migration-guide", "spa", 185],
  ["https://observablehq.com/@d3/star-map", "spa", 30],
  ["https://d3js.org/d3-zoom", "spa", 110],
  ["https://excalidraw.com", "spa", 15],
  ["https://www.reddit.com/r/firefox/", "spa", 120],
  ["https://old.reddit.com/r/firefox/", "spa", 17],
  ["https://news.ycombinator.com", "spa", 15],
  ["https://stackoverflow.com/questions?tab=active&pagesize=50", "spa", 48],
  ["https://meta.discourse.org/latest", "spa", 110],

  // LONG-FORM READING — reflow, font shaping, glyph cache
  ["https://www.bbc.com/news", "long_read", 45],
  ["https://apnews.com/article/autoimmune-disease-lupus-diagnosis-symptoms-b1f2ba32883c63fff1af689a45281305", "apnews", 120],
  ["https://arstechnica.com/information-technology/2026/02/ai-companies-want-you-to-stop-chatting-with-bots-and-start-managing-them/?comments-page=1#comments", "long_read", 75],
  ["https://liliputing.com/apple-discontinues-iphone-13-mini-in-the-latest-blow-to-small-screen-phones/", "long_read", 100],
  ["https://www.xda-developers.com/linux-distros-are-quietly-abandoning-their-own-desktops-for-kde-plasma-and-i-get-why/", "long_read", 135],
  ["https://www.gsmarena.com/apple_iphone_17_pro_max-review-2884p6.php", "long_read", 153],
  ["https://www.reuters.com/business/retail-consumer/anthropic-releases-ai-upgrade-market-punishes-software-stocks-2026-02-05/", "long_read", 45],
  ["https://www.npr.org/2026/02/27/nx-s1-5727656/what-to-know-about-the-showdown-between-ai-company-anthropic-and-the-pentagon", "long_read", 55],
  ["https://www.theguardian.com/international", "long_read", 140],
  ["https://www.aljazeera.com/news/2026/2/25/anthropic-vs-the-pentagon-why-ai-firm-is-taking-on-trump-administration", "long_read", 65],
  ["https://www.theatlantic.com/podcasts/archive/2024/06/how-to-keep-watch/678554/", "long_read", 170],
  ["https://www.theverge.com/news/672924/mozilla-pocket-fakespot-shutting-down#comments", "long_read", 35],
  ["https://www.wired.com/story/best-dark-web-monitoring-services/", "long_read", 85],
  ["https://techcrunch.com/2026/02/02/firefox-will-soon-let-you-block-all-of-its-generative-ai-features/", "long_read", 110],
  ["https://www.engadget.com/ai/mozilla-will-add-an-ai-window-to-firefox-225032453.html", "long_read", 110],
  ["https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Expressions_and_operators", "long_read", 170],
  ["https://doc.rust-lang.org/book/ch02-00-guessing-game-tutorial.html", "long_read", 120],
  ["https://docs.python.org/3/tutorial/controlflow.html", "long_read", 134],
  ["https://caniuse.com/?search=heic", "long_read", 15],
  ["https://www.npmjs.com/package/@cspell/dict-java/v/5.0.12", "long_read", 15],
  ["https://pypi.org/project/emailproxy/", "long_read", 75],
  // International text (CJK, RTL, complex scripts)
  ["https://www.nhk.or.jp/nhkworld/", "long_read", 40],
  ["https://www3.nhk.or.jp/news/", "long_read", 44],
  ["https://www.naver.com", "long_read", 20],
  ["https://www.aljazeera.net", "long_read", 110],
  ["https://www.thehindu.com", "long_read", 70],
  ["https://zh.wikipedia.org/wiki/%E7%91%9E%E5%A3%AB", "long_read", 210],
  ["https://medium.com/tag/technology", "long_read", 35],
  ["https://dev.to", "long_read", 110],
  ["https://en.wikipedia.org/wiki/Firefox", "long_read", 322],

  // E-COMMERCE — image decode, lazy load, mixed layout
  ["https://www.amazon.com/s?k=mechanical+keyboard", "ecommerce", 48],
  ["https://www.apple.com/shop/buy-mac", "ecommerce", 25],
  ["https://www.ebay.com/sch/i.html?_nkw=gpu", "ecommerce", 68],
  ["https://www.bestbuy.com/site/searchpage.jsp?st=laptop", "ecommerce", 54],
  ["https://www.newegg.com/p/pl?d=ssd", "ecommerce", 55],
  ["https://www.target.com/c/electronics/-/N-5xtg6", "ecommerce", 80],
  ["https://www.etsy.com/search?q=mechanical+keyboard", "ecommerce", 47],

  // COMPLEX CSS / ANIMATION — compositor, transitions
  ["https://stripe.com", "complex_css", 180],
  ["https://linear.app", "complex_css", 110],
  ["https://vercel.com", "complex_css", 75],
  ["https://www.apple.com", "complex_css", 72],
  ["https://github.com/features", "complex_css", 240],
  ["https://tailwindcss.com", "complex_css", 150],

  // MAPS / CANVAS / WEBGL — GPU compositor, tile render
  ["https://globe.adsb.fi", "map", 30],
  ["https://www.google.com/maps/@35.6762,139.6503,12z", "map", 60],
  ["https://www.openstreetmap.org/#map=12/35.6762/139.6503", "map", 60],
  ["https://threejs.org/examples/#webgl_animation_skinning_blending", "map", 40],
  ["https://www.shadertoy.com/view/Xds3zN", "map", 55],

  // SPEED TESTS — canvas rendering + network stack
  ["https://www.speedtest.net", "speedtest", 75],
  ["https://speed.cloudflare.com", "speedtest", 72],
  ["https://librespeed.org", "speedtest", 45],

  // STATIC / REFERENCE — baseline coverage
  ["https://www.boincstats.com/stats/-1/project/detail/credit", "static", 67],
  ["https://time.is", "static", 30],
  ["https://dnscheck.tools", "static", 23],
  ["https://goodwok.day", "static", 20],
  ["https://libera.chat", "static", 21],
  ["https://www.usa.gov", "static", 30],
  ["https://www.cdc.gov/talaromycosis/about/index.html", "static", 59],
  ["https://www.nasa.gov", "static", 58],
  ["https://europa.eu", "static", 35],
  ["https://www.gov.uk", "static", 40],
  ["https://www.craigslist.org", "static", 15],
];

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function log(msg) {
  // dump() writes to stdout; console.error appears in build console as fallback
  dump("[ducksteps PGO] " + msg + "\n");
  console.error("[ducksteps PGO] " + msg);
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function waitForTabLoad(tabId, timeout) {
  timeout = timeout || PAGE_LOAD_TIMEOUT;
  return new Promise(resolve => {
    var done = false;
    var timer = setTimeout(function () {
      if (!done) {
        done = true;
        browser.tabs.onUpdated.removeListener(fn);
        resolve();
      }
    }, timeout);
    function fn(id, info) {
      if (id === tabId && info.status === "complete") {
        if (!done) {
          done = true;
          clearTimeout(timer);
          browser.tabs.onUpdated.removeListener(fn);
          resolve();
        }
      }
    }
    browser.tabs.onUpdated.addListener(fn);
  });
}

// ---------------------------------------------------------------------------
// Hot-path exerciser (injected into every page alongside scroll behavior)
// Runs lightweight operations that exercise rendering, layout, and graphics
// paths not covered by scrolling alone.
// ---------------------------------------------------------------------------
function _exerciseHotPaths(dwellMs) {
  // requestAnimationFrame — compositor timing + vsync
  var rafCount = 0;
  var rafMax = Math.floor(dwellMs / 16);
  (function rafLoop() {
    rafCount++;
    if (rafCount < rafMax) requestAnimationFrame(rafLoop);
  })();

  // IntersectionObserver — lazy loading code paths
  try {
    var io = new IntersectionObserver(function () {});
    var observed = 0;
    document.querySelectorAll("img,video,section,article,div").forEach(
      function (el) {
        if (observed++ < 50) io.observe(el);
      }
    );
    setTimeout(function () {
      io.disconnect();
    }, dwellMs);
  } catch (e) {}

  // MutationObserver — DOM mutation watching paths
  try {
    var mo = new MutationObserver(function () {});
    mo.observe(document.body || document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
    });
    setTimeout(function () {
      mo.disconnect();
    }, dwellMs);
  } catch (e) {}

  // Periodic forced layout + style resolution
  var layoutInterval = setInterval(function () {
    try {
      var el = document.elementFromPoint(
        Math.random() * innerWidth * 0.8 + 50,
        Math.random() * innerHeight * 0.8 + 50
      );
      if (el) {
        getComputedStyle(el).color;
        getComputedStyle(el).transform;
        el.getBoundingClientRect();
      }
    } catch (e) {}
  }, 2000);
  setTimeout(function () {
    clearInterval(layoutInterval);
  }, dwellMs);

  // Canvas 2D micro-draws — graphics pipeline
  try {
    var c = document.createElement("canvas");
    c.width = 64;
    c.height = 64;
    var ctx = c.getContext("2d");
    if (ctx) {
      var canvasInterval = setInterval(function () {
        ctx.fillStyle =
          "rgba(" + Math.floor(Math.random() * 256) + ",100,50,0.5)";
        ctx.fillRect(Math.random() * 48, Math.random() * 48, 16, 16);
        ctx.strokeRect(Math.random() * 48, Math.random() * 48, 16, 16);
        ctx.clearRect(0, 0, 64, 64);
      }, 500);
      setTimeout(function () {
        clearInterval(canvasInterval);
      }, dwellMs);
    }
  } catch (e) {}

  // Performance API — high-resolution timer paths
  var perfInterval = setInterval(function () {
    performance.now();
    try {
      performance.getEntriesByType("resource").slice(0, 5);
    } catch (e) {}
  }, 3000);
  setTimeout(function () {
    clearInterval(perfInterval);
  }, dwellMs);
}

// ---------------------------------------------------------------------------
// Scroll behaviors — each function runs in the page's content script context.
// They set up async timers and return immediately. The background script
// sleeps for the dwell duration independently.
// ---------------------------------------------------------------------------

// Reading pattern: burst 3-5 scrolls, 5-10s read pause, repeat
function _longRead(dwellMs) {
  var end = Date.now() + dwellMs;
  var jitter = function (base, pct) {
    return base * (1 - pct + Math.random() * 2 * pct);
  };
  function cycle() {
    if (Date.now() >= end) return;
    var burst = 3 + Math.floor(Math.random() * 3);
    var i = 0;
    function scrollStep() {
      if (i < burst && Date.now() < end) {
        var px = Math.floor(jitter(350, 0.3));
        window.scrollBy({ top: px, behavior: "smooth" });
        if (i === 0) {
          document.dispatchEvent(
            new MouseEvent("mousemove", {
              clientX: Math.random() * innerWidth * 0.8 + 50,
              clientY: Math.random() * innerHeight * 0.8 + 50,
              bubbles: true,
            })
          );
        }
        i++;
        setTimeout(scrollStep, jitter(250, 0.3));
      } else {
        var pause = 5000 + Math.random() * 5000;
        setTimeout(cycle, pause);
      }
    }
    scrollStep();
  }
  cycle();
}

// Video: play video, scroll comments at dwellMs * 0.6
function _video(dwellMs) {
  setTimeout(function () {
    try {
      var v = document.querySelector("video");
      if (v && v.paused) v.play().catch(function () {});
    } catch (e) {}
  }, 3000);
  var scrollStart = dwellMs * 0.6;
  var end = Date.now() + dwellMs;
  setTimeout(function () {
    var si = setInterval(function () {
      if (Date.now() >= end) {
        clearInterval(si);
        return;
      }
      var px = 300 + Math.floor(Math.random() * 200);
      window.scrollBy({ top: px, behavior: "smooth" });
    }, 1500 + Math.random() * 600);
  }, scrollStart);
}

// Video with fixed 70s scroll delay — play immediately, hold scroll until 70s.
// Used for YouTube: gives the video enough watch-time before scrolling comments.
function _videoLateScroll(dwellMs) {
  setTimeout(function () {
    try {
      var v = document.querySelector("video");
      if (v && v.paused) v.play().catch(function () {});
    } catch (e) {}
  }, 3000);
  var end = Date.now() + dwellMs;
  setTimeout(function () {
    var si = setInterval(function () {
      if (Date.now() >= end) {
        clearInterval(si);
        return;
      }
      var px = 300 + Math.floor(Math.random() * 200);
      window.scrollBy({ top: px, behavior: "smooth" });
    }, 1500 + Math.random() * 600);
  }, 70000); // fixed 70s before scrolling to comments
}

// E-commerce: fast skim, backtrack, slow read
function _ecommerce(dwellMs) {
  var end = Date.now() + dwellMs;
  var skimEnd = Date.now() + dwellMs * 0.4;
  var skimInterval = setInterval(function () {
    if (Date.now() >= skimEnd) {
      clearInterval(skimInterval);
      var sh = Math.max(
        document.body.scrollHeight,
        document.documentElement.scrollHeight
      );
      window.scrollBy({ top: -Math.floor(sh * 0.3), behavior: "smooth" });
      setTimeout(function () {
        var remaining = end - Date.now();
        if (remaining > 5000) {
          _longRead(remaining - 2000);
        }
      }, 2000);
      return;
    }
    var px = 400 + Math.floor(Math.random() * 200);
    window.scrollBy({ top: px, behavior: "smooth" });
    document.dispatchEvent(
      new MouseEvent("mousemove", {
        clientX: Math.random() * innerWidth * 0.8 + 50,
        clientY: Math.random() * innerHeight * 0.8 + 50,
        bubbles: true,
      })
    );
  }, 400 + Math.random() * 200);
}

// SPA: trigger hydration, focus inputs, then reading scroll
function _spa(dwellMs) {
  var end = Date.now() + dwellMs;
  var i = 0;
  function hydrate() {
    if (i < 3) {
      var px = 300 + Math.floor(Math.random() * 200);
      window.scrollBy({ top: px, behavior: "smooth" });
      i++;
      setTimeout(hydrate, 300 + Math.random() * 200);
    } else {
      try {
        var inputs = document.querySelectorAll(
          'input[type="text"],input[type="search"]'
        );
        if (inputs.length > 0) {
          inputs[0].focus();
          inputs[0].dispatchEvent(new Event("focus", { bubbles: true }));
        }
      } catch (e) {}
      setTimeout(function () {
        var remaining = end - Date.now();
        if (remaining > 5000) _longRead(remaining);
      }, 1000);
    }
  }
  setTimeout(hydrate, 2000);
}

// Long-read with bottom-right ad dismissal for AP News.
// Waits 4s for the ad to render, scans the bottom-right viewport quadrant
// for close/dismiss buttons, clicks the first match, then hands off to
// _longRead. Requires _longRead injected as a dependency (see injectBehavior).
function _apnewsRead(dwellMs) {
  setTimeout(function () {
    try {
      var closeSelectors = [
        '[class*="close" i]',
        '[class*="dismiss" i]',
        '[aria-label*="close" i]',
        '[aria-label*="dismiss" i]',
        '[data-testid*="close" i]',
        'button[class*="close"]',
      ];
      for (var s = 0; s < closeSelectors.length; s++) {
        var btns = document.querySelectorAll(closeSelectors[s]);
        for (var b = 0; b < btns.length; b++) {
          var rect = btns[b].getBoundingClientRect();
          // Bottom-right quadrant: x > 55% viewport width, y > 55% viewport height
          if (
            rect.width > 0 &&
            rect.x > window.innerWidth * 0.55 &&
            rect.y > window.innerHeight * 0.55
          ) {
            btns[b].click();
            break;
          }
        }
      }
    } catch (e) {}
  }, 4000);

  // Hand off to _longRead after ad dismissal window
  setTimeout(function () {
    var remaining = dwellMs - 5000;
    if (remaining > 5000) _longRead(remaining);
  }, 5000);
}

// Map/Canvas/WebGL: pan, zoom, hover
function _map(dwellMs) {
  var end = Date.now() + dwellMs;
  setTimeout(function () {
    var mi = setInterval(function () {
      if (Date.now() >= end) {
        clearInterval(mi);
        return;
      }
      document.dispatchEvent(
        new WheelEvent("wheel", {
          deltaY: Math.random() > 0.5 ? 120 : -120,
          clientX: innerWidth / 2,
          clientY: innerHeight / 2,
          bubbles: true,
        })
      );
      setTimeout(function () {
        var cx = innerWidth / 2;
        var cy = innerHeight / 2;
        var dx = Math.floor(Math.random() * 400 - 200);
        var dy = Math.floor(Math.random() * 300 - 150);
        var el = document.elementFromPoint(cx, cy) || document;
        el.dispatchEvent(
          new MouseEvent("mousedown", {
            clientX: cx, clientY: cy, bubbles: true,
          })
        );
        el.dispatchEvent(
          new MouseEvent("mousemove", {
            clientX: cx + dx, clientY: cy + dy, bubbles: true,
          })
        );
        el.dispatchEvent(
          new MouseEvent("mouseup", {
            clientX: cx + dx, clientY: cy + dy, bubbles: true,
          })
        );
      }, 1500);
    }, 5000);
  }, 3000);
}

// Speed test: click start, wait
function _speedtest(dwellMs) {
  setTimeout(function () {
    try {
      var btns = document.querySelectorAll(
        'button, a.button, [role="button"], .start-button, .js-start-test'
      );
      for (var j = 0; j < btns.length; j++) {
        var text = (btns[j].textContent || "").toLowerCase();
        if (
          text.indexOf("go") >= 0 ||
          text.indexOf("start") >= 0 ||
          text.indexOf("test") >= 0 ||
          text.indexOf("begin") >= 0
        ) {
          btns[j].click();
          break;
        }
      }
    } catch (e) {}
  }, 2000);
  setTimeout(function () {
    window.scrollBy({ top: 400, behavior: "smooth" });
  }, dwellMs - 3000);
}

// Complex CSS: slow scroll to trigger animations
function _complexCss(dwellMs) {
  var end = Date.now() + dwellMs;
  function tick() {
    if (Date.now() >= end) return;
    var px = 150 + Math.floor(Math.random() * 100);
    window.scrollBy({ top: px, behavior: "smooth" });
    document.dispatchEvent(
      new MouseEvent("mousemove", {
        clientX: Math.random() * innerWidth * 0.8 + 50,
        clientY: Math.random() * innerHeight * 0.8 + 50,
        bubbles: true,
      })
    );
    // Longer pauses ~25% of the time for CSS transitions
    var delay = Math.random() < 0.25
      ? 3000 + Math.random() * 2000
      : 1500 + Math.random() * 600;
    setTimeout(tick, delay);
  }
  tick();
}

// Static: single slow scroll pass
function _static(dwellMs) {
  var end = Date.now() + dwellMs;
  var si = setInterval(function () {
    if (Date.now() >= end) {
      clearInterval(si);
      return;
    }
    var px = 250 + Math.floor(Math.random() * 100);
    window.scrollBy({ top: px, behavior: "smooth" });
  }, 2000 + Math.random() * 600);
}

// ---------------------------------------------------------------------------
// Behavior dispatch
// ---------------------------------------------------------------------------
const BEHAVIORS = {
  long_read: _longRead,
  video: _video,
  video_late_scroll: _videoLateScroll,
  ecommerce: _ecommerce,
  spa: _spa,
  apnews: _apnewsRead,
  map: _map,
  speedtest: _speedtest,
  complex_css: _complexCss,
  static: _static,
};

// ---------------------------------------------------------------------------
// Inject behavior into a tab via executeScript
// ---------------------------------------------------------------------------
async function injectBehavior(tabId, behavior, dwellSeconds) {
  var dwellMs = dwellSeconds * 1000;
  var behaviorFn = BEHAVIORS[behavior];
  if (!behaviorFn) {
    log("  Unknown behavior: " + behavior + ", falling back to static");
    behaviorFn = _static;
  }

  // _ecommerce, _spa, and _apnewsRead call _longRead internally, so inject
  // it as a dependency when those behaviors are selected
  var code;
  if (behavior === "ecommerce" || behavior === "spa" || behavior === "apnews") {
    code =
      "var _longRead = " + _longRead.toString() + ";\n" +
      "(" + _exerciseHotPaths.toString() + ")(" + dwellMs + ");\n" +
      "(" + behaviorFn.toString() + ")(" + dwellMs + ");";
  } else {
    code =
      "(" + _exerciseHotPaths.toString() + ")(" + dwellMs + ");\n" +
      "(" + behaviorFn.toString() + ")(" + dwellMs + ");";
  }

  try {
    await browser.tabs.executeScript(tabId, { code: code });
  } catch (e) {
    log("  Could not inject behavior: " + e.message);
  }
}

// ---------------------------------------------------------------------------
// Main training orchestrator
// ---------------------------------------------------------------------------
async function runTraining() {
  var totalSites = SITES.length;
  var totalDwell = 0;
  for (var s = 0; s < SITES.length; s++) totalDwell += SITES[s][2];
  log(
    "Training " + totalSites + " sites, estimated " +
    Math.floor(totalDwell / 60) + " minutes"
  );

  // Get the active tab (opened on about:blank by profileserver.py)
  var tabs = await browser.tabs.query({ active: true, currentWindow: true });
  if (!tabs.length) {
    log("ERROR: No active tab found");
    return;
  }
  var tabId = tabs[0].id;

  var succeeded = 0;
  var skipped = 0;
  var startTime = Date.now();

  for (var i = 0; i < SITES.length; i++) {
    var url = SITES[i][0];
    var behavior = SITES[i][1];
    var dwell = SITES[i][2];

    log(
      "[" + (i + 1) + "/" + totalSites + "] " + url +
      " (" + behavior + ", " + dwell + "s)"
    );

    try {
      await browser.tabs.update(tabId, { url: url });
      await waitForTabLoad(tabId);

      // Initial page settle
      await sleep(3000);

      // Inject and run behavior + hot-path exercisers
      await injectBehavior(tabId, behavior, dwell);

      // Wait for the behavior to complete
      await sleep(dwell * 1000);

      // Exercise extension storage API (real-world hot path:
      // every user with uBlock/Bitwarden/etc. hits this)
      try {
        await browser.storage.local.set({
          pgo_last_url: url,
          pgo_index: i,
          pgo_timestamp: Date.now(),
        });
      } catch (e) {}

      succeeded++;
    } catch (e) {
      log("  SKIP: " + e.message);
      skipped++;
      try {
        await browser.tabs.update(tabId, { url: "about:blank" });
        await sleep(1000);
      } catch (e2) {}
    }
  }

  var elapsed = ((Date.now() - startTime) / 60000).toFixed(1);
  log(
    "Done. " + succeeded + " succeeded, " + skipped + " skipped, " +
    elapsed + " minutes elapsed"
  );

  // Clean shutdown via Quitter.quit() on a localhost-served page
  log("Navigating to pgo_done.html for clean shutdown...");
  try {
    await browser.tabs.update(tabId, {
      url: "http://localhost:" + PGO_PORT + "/pgo_done.html",
    });
  } catch (e) {
    log("ERROR: Could not navigate to pgo_done.html: " + e.message);
  }
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------
runTraining().catch(function (e) {
  log("FATAL: " + e.message);
});
