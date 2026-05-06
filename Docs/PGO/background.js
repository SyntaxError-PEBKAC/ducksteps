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
// Total estimated runtime: ~135 minutes.
// LAST UPDATED 05/MAY/2026
// ---------------------------------------------------------------------------
const SITES = [
  // VIDEO PLAYBACK — codec + compositor + audio sync
  ["https://www.youtube.com/watch?v=u_5wLvlRhc0", "video_late_scroll", 110],
  ["https://www.youtube.com/watch?v=8rwnAj-i1Ps", "video_late_scroll", 110],
  ["https://vimeo.com/32001208?autoplay=1", "video", 75],
  ["https://www.twitch.tv/StreamerHouse", "video", 75],
  ["https://www.dailymotion.com/video/xa5pjb6", "video", 120],

  // SPEED TESTS — canvas rendering + network stack
  ["https://www.speedtest.net", "speedtest_ookla", 75],          // dedicated behavior: clicks a.js-start-test
  ["https://librespeed.org", "librespeed", 45],                   // dedicated behavior: clicks #start-button, retries at 6s
  ["https://speed.cloudflare.com", "speedtest", 72],              // generic heuristic still fine here
  ["http://localhost:8000/InteractiveRunner.html?startAutomatically=true", "static", 285], // Speedometer 3 — auto-fires via URL param; ~3.5min on 9950X3D, 4:45 dwell for headroom

  // JS-HEAVY SPAs — SpiderMonkey JIT, GC, DOM mutation
  ["https://duck.ai", "duckai", 90],                              // consent dismiss + Haiku 4.5 + SpiderMonkey prompt
  ["https://github.com/SyntaxError-PEBKAC/ducksteps/releases", "spa", 60],
  ["https://duckduckgo.com/?q=firefox+ESR+performance", "spa", 45],
  ["https://claude.ai", "spa", 45],
  ["https://redlib.catsarch.com/", "spa", 90],
  ["https://redlib.catsarch.com/r/pics/comments/haucpf/ive_found_a_few_funny_memories_during_lockdown/", "spa", 182],
  ["https://react.dev/learn", "spa", 85],
  ["https://www.airbnb.com/s/Tokyo/homes", "airbnb", 35],        // dedicated behavior: dismisses popup before scrolling
  ["https://netflix.com", "spa", 45],
  ["https://angular.dev/overview", "spa", 40],
  ["https://vuejs.org/guide/essentials/component-basics.html", "spa", 73],
  ["https://svelte.dev/docs/svelte/v5-migration-guide", "spa", 185],
  ["https://observablehq.com/@d3/star-map", "spa", 30],
  ["https://d3js.org/d3-zoom", "spa", 110],
  ["https://excalidraw.com", "spa", 45],
  ["https://www.reddit.com/r/firefox/", "spa", 120],
  ["https://old.reddit.com/r/firefox/", "spa", 45],
  ["https://news.ycombinator.com", "spa", 45],
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
  ["https://caniuse.com/?search=heic", "long_read", 45],
  ["https://www.npmjs.com/package/@cspell/dict-java/v/5.0.12", "long_read", 45],
  ["https://pypi.org/project/emailproxy/", "long_read", 75],
  // International text (CJK, RTL, complex scripts)
  ["https://www.nhk.or.jp/nhkworld/", "long_read", 40],
  ["https://www3.nhk.or.jp/news/", "long_read", 44],
  ["https://www.naver.com", "long_read", 45],
  ["https://www.aljazeera.net", "long_read", 110],
  ["https://www.thehindu.com", "long_read", 70],
  ["https://zh.wikipedia.org/wiki/%E7%91%9E%E5%A3%AB", "long_read", 210],
  ["https://medium.com/tag/technology", "long_read", 35],
  ["https://dev.to", "long_read", 110],
  ["https://en.wikipedia.org/wiki/Firefox", "long_read", 322],

  // E-COMMERCE — image decode, lazy load, mixed layout
  ["https://www.amazon.com/s?k=mechanical+keyboard", "ecommerce", 48],
  ["https://www.apple.com/shop/buy-mac", "ecommerce", 45],
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

  // STATIC / REFERENCE — baseline coverage
  ["https://www.boincstats.com/stats/-1/project/detail/credit", "static", 67],
  ["https://time.is", "static", 45],
  ["https://dnscheck.tools", "static", 45],
  ["https://goodwok.day", "static", 45],
  ["https://libera.chat", "static", 45],
  ["https://www.usa.gov", "static", 45],
  ["https://www.cdc.gov/talaromycosis/about/index.html", "static", 59],
  ["https://www.nasa.gov", "static", 58],
  ["https://europa.eu", "static", 45],
  ["https://www.gov.uk", "static", 45],
  ["https://www.craigslist.org", "static", 45],
];

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function log(msg) {
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
// ---------------------------------------------------------------------------
function _exerciseHotPaths(dwellMs) {
  var rafCount = 0;
  var rafMax = Math.floor(dwellMs / 16);
  (function rafLoop() {
    rafCount++;
    if (rafCount < rafMax) requestAnimationFrame(rafLoop);
  })();

  try {
    var io = new IntersectionObserver(function () {});
    var observed = 0;
    document.querySelectorAll("img,video,section,article,div").forEach(
      function (el) {
        if (observed++ < 50) io.observe(el);
      }
    );
    setTimeout(function () { io.disconnect(); }, dwellMs);
  } catch (e) {}

  try {
    var mo = new MutationObserver(function () {});
    mo.observe(document.body || document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
    });
    setTimeout(function () { mo.disconnect(); }, dwellMs);
  } catch (e) {}

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
  setTimeout(function () { clearInterval(layoutInterval); }, dwellMs);

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
      setTimeout(function () { clearInterval(canvasInterval); }, dwellMs);
    }
  } catch (e) {}

  var perfInterval = setInterval(function () {
    performance.now();
    try { performance.getEntriesByType("resource").slice(0, 5); } catch (e) {}
  }, 3000);
  setTimeout(function () { clearInterval(perfInterval); }, dwellMs);
}

// ---------------------------------------------------------------------------
// Scroll behaviors
// ---------------------------------------------------------------------------

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

// Video: play, scroll comments at 60% of dwell.
// Fullscreen removed — ads and interstitials on YouTube/Twitch/etc. block
// the request or trap the browser in a broken state.
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
      if (Date.now() >= end) { clearInterval(si); return; }
      var px = 300 + Math.floor(Math.random() * 200);
      window.scrollBy({ top: px, behavior: "smooth" });
    }, 1500 + Math.random() * 600);
  }, scrollStart);
}

// Video with fixed 70s scroll delay — gives YouTube enough watch-time
// before scrolling comments. Fullscreen removed (same reason as _video).
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
      if (Date.now() >= end) { clearInterval(si); return; }
      var px = 300 + Math.floor(Math.random() * 200);
      window.scrollBy({ top: px, behavior: "smooth" });
    }, 1500 + Math.random() * 600);
  }, 70000);
}

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
        if (remaining > 5000) _longRead(remaining - 2000);
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
  setTimeout(function () {
    var remaining = dwellMs - 5000;
    if (remaining > 5000) _longRead(remaining);
  }, 5000);
}

// Airbnb: dismiss the "Got it" / X popup that blocks scrolling on load,
// then hand off to _spa for the remainder.
function _airbnb(dwellMs) {
  var end = Date.now() + dwellMs;
  setTimeout(function () {
    try {
      var btns = document.querySelectorAll('button');
      var dismissed = false;
      for (var i = 0; i < btns.length; i++) {
        var t = btns[i].textContent.trim().toLowerCase();
        if (t === 'got it' || t === 'ok' || t === 'okay' || t === 'close') {
          btns[i].click();
          dismissed = true;
          break;
        }
      }
      if (!dismissed) {
        var closeBtn = document.querySelector(
          '[aria-label*="close" i], [aria-label*="dismiss" i], ' +
          '[data-testid*="close" i], [data-testid*="dismiss" i]'
        );
        if (closeBtn) closeBtn.click();
      }
    } catch (e) {}
  }, 3000);
  setTimeout(function () {
    var remaining = end - Date.now();
    if (remaining > 5000) _spa(remaining);
  }, 5000);
}

function _map(dwellMs) {
  var end = Date.now() + dwellMs;
  setTimeout(function () {
    var mi = setInterval(function () {
      if (Date.now() >= end) { clearInterval(mi); return; }
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
        el.dispatchEvent(new MouseEvent("mousedown", { clientX: cx, clientY: cy, bubbles: true }));
        el.dispatchEvent(new MouseEvent("mousemove", { clientX: cx + dx, clientY: cy + dy, bubbles: true }));
        el.dispatchEvent(new MouseEvent("mouseup", { clientX: cx + dx, clientY: cy + dy, bubbles: true }));
      }, 1500);
    }, 5000);
  }, 3000);
}

// Generic speedtest: textContent heuristic (used for Cloudflare)
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

// Speedtest.net (Ookla): clicks a.js-start-test directly.
// The GO button's visible text lives in a child <span class="start-text"> —
// textContent scanning on the parent <a> misses it. Target the anchor
// by its stable class instead.
function _speedtestOokla(dwellMs) {
  setTimeout(function () {
    try {
      var btn = document.querySelector("a.js-start-test");
      if (btn) {
        btn.click();
      } else {
        var fallback = document.querySelector('[aria-label*="start speed test" i]');
        if (fallback) fallback.click();
      }
    } catch (e) {}
  }, 3000);
  setTimeout(function () {
    window.scrollBy({ top: 400, behavior: "smooth" });
  }, dwellMs - 3000);
}

// LibreSpeed: clicks #start-button directly.
// Button initializes disabled until server ping completes (~1-2s).
// Retries at 6s in case of slow server selection — double-click is safe
// since the button is a no-op while disabled.
function _librespeed(dwellMs) {
  function tryClick() {
    try {
      var btn = document.querySelector("#start-button");
      if (btn) btn.click();
    } catch (e) {}
  }
  setTimeout(tryClick, 4000);
  setTimeout(tryClick, 6000);
  setTimeout(function () {
    window.scrollBy({ top: 400, behavior: "smooth" });
  }, dwellMs - 3000);
}

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
    var delay = Math.random() < 0.25
      ? 3000 + Math.random() * 2000
      : 1500 + Math.random() * 600;
    setTimeout(tick, delay);
  }
  tick();
}

// Duck.ai: dismiss onboarding modal, select Claude Haiku 4.5, submit a
// prompt that elicits a long streaming response.
// Exercises: React reconciler, streaming DOM mutation, font shaping,
// smooth-scroll on a tall response.
function _duckai(dwellMs) {
  var end = Date.now() + dwellMs;

  // Step 1 — Dismiss "Agree and Continue" modal (stable data-testid)
  setTimeout(function () {
    try {
      var btn = document.querySelector('[data-testid="DUCKAI_ONBOARDING_AGREE"]');
      if (btn) btn.click();
    } catch (e) {}
  }, 2000);

  // Step 2 — Open model picker
  setTimeout(function () {
    try {
      var btn = document.querySelector('button[data-testid="model-select-button"]');
      if (btn) btn.click();
    } catch (e) {}
  }, 4000);

  // Step 3 — Click Haiku 4.5 radio label (stable for= attribute)
  setTimeout(function () {
    try {
      var label = document.querySelector('label[for="claude-haiku-4-5"]');
      if (label) label.click();
    } catch (e) {}
  }, 6000);

  // Step 4 — Confirm with "Start New Chat"
  setTimeout(function () {
    try {
      var btns = document.querySelectorAll('button');
      for (var i = 0; i < btns.length; i++) {
        if (btns[i].textContent.trim() === 'Start New Chat') {
          btns[i].click();
          break;
        }
      }
    } catch (e) {}
  }, 7500);

  // Step 5 — Type prompt via React synthetic event.
  // Direct .value= is silently ignored by React controlled inputs;
  // nativeInputValueSetter bypasses the wrapper so the value actually sticks.
  setTimeout(function () {
    try {
      var textarea = document.querySelector('textarea[name="user-prompt"]');
      if (textarea) {
        textarea.focus();
        var setter = Object.getOwnPropertyDescriptor(
          window.HTMLTextAreaElement.prototype, 'value'
        ).set;
        setter.call(textarea,
          'Please explain in detail how Firefox\'s SpiderMonkey JavaScript engine ' +
          'works, covering the interpreter, baseline JIT compiler, IonMonkey ' +
          'optimizing compiler, garbage collector, and how they interact during ' +
          'real-world page execution. Include how type inference and ' +
          'deoptimization work.'
        );
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
      }
    } catch (e) {}
  }, 10000);

  // Step 6 — Submit: Enter keydown first, send button as fallback 1s later.
  setTimeout(function () {
    try {
      var textarea = document.querySelector('textarea[name="user-prompt"]');
      if (textarea) {
        textarea.dispatchEvent(
          new KeyboardEvent('keydown', {
            key: 'Enter', code: 'Enter', keyCode: 13,
            which: 13, bubbles: true, cancelable: true
          })
        );
      }
    } catch (e) {}
  }, 11500);

  setTimeout(function () {
    try {
      var sendBtn =
        document.querySelector('[aria-label*="send" i]') ||
        document.querySelector('[aria-label*="submit" i]') ||
        document.querySelector('button[type="submit"]');
      if (sendBtn) sendBtn.click();
    } catch (e) {}
  }, 12500);

  // Step 7 — Scroll streaming response
  setTimeout(function () {
    var remaining = end - Date.now();
    if (remaining > 5000) {
      var si = setInterval(function () {
        if (Date.now() >= end) { clearInterval(si); return; }
        window.scrollBy({ top: 200, behavior: 'smooth' });
      }, 3000);
    }
  }, 15000);
}

function _static(dwellMs) {
  var end = Date.now() + dwellMs;
  var si = setInterval(function () {
    if (Date.now() >= end) { clearInterval(si); return; }
    var px = 250 + Math.floor(Math.random() * 100);
    window.scrollBy({ top: px, behavior: "smooth" });
  }, 2000 + Math.random() * 600);
}

// ---------------------------------------------------------------------------
// Behavior dispatch
// ---------------------------------------------------------------------------
const BEHAVIORS = {
  long_read:         _longRead,
  video:             _video,
  video_late_scroll: _videoLateScroll,
  ecommerce:         _ecommerce,
  spa:               _spa,
  apnews:            _apnewsRead,
  airbnb:            _airbnb,           // popup dismiss + spa scroll
  map:               _map,
  speedtest:         _speedtest,
  speedtest_ookla:   _speedtestOokla,   // Ookla-specific: targets a.js-start-test
  librespeed:        _librespeed,       // LibreSpeed-specific: #start-button, retries at 6s
  complex_css:       _complexCss,
  duckai:            _duckai,           // consent + Haiku 4.5 + SpiderMonkey prompt
  static:            _static,
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

  var code;
  if (behavior === "ecommerce" || behavior === "spa" || behavior === "apnews") {
    // These call _longRead internally — inject it as a dependency
    code =
      "var _longRead = " + _longRead.toString() + ";\n" +
      "(" + _exerciseHotPaths.toString() + ")(" + dwellMs + ");\n" +
      "(" + behaviorFn.toString() + ")(" + dwellMs + ");";
  } else if (behavior === "airbnb") {
    // _airbnb calls _spa which calls _longRead — inject both
    code =
      "var _longRead = " + _longRead.toString() + ";\n" +
      "var _spa = " + _spa.toString() + ";\n" +
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
      await sleep(3000);
      await injectBehavior(tabId, behavior, dwell);
      await sleep(dwell * 1000);

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
