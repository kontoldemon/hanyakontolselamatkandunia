const CACHE_NAME = "cloudsentinel-offline-v1";

const OFFLINE_HTML = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="theme-color" content="#050505" />
  <title>CloudSentinel Offline</title>
  <style>
    :root { color-scheme: dark; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
      background: #050505;
      color: #f8fafc;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main {
      width: min(440px, 100%);
      text-align: center;
    }
    .mark {
      width: 58px;
      height: 58px;
      margin: 0 auto 22px;
      display: grid;
      place-items: center;
      border: 1px solid rgba(255,255,255,.12);
      border-radius: 14px;
      background: #0a0a0a;
      color: #60a5fa;
      box-shadow: 0 16px 45px rgba(0,0,0,.35);
    }
    .mark svg { width: 30px; height: 30px; }
    .code {
      margin: 0 0 10px;
      color: #94a3b8;
      font: 700 11px/1 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      letter-spacing: .34em;
      text-transform: uppercase;
    }
    h1 {
      margin: 0;
      font-size: clamp(26px, 7vw, 36px);
      line-height: 1.05;
      letter-spacing: 0;
    }
    p {
      margin: 16px auto 0;
      max-width: 360px;
      color: #94a3b8;
      font-size: 14px;
      line-height: 1.65;
    }
    button {
      margin-top: 28px;
      height: 42px;
      border: 0;
      border-radius: 10px;
      padding: 0 18px;
      background: #2563eb;
      color: white;
      font-weight: 700;
      font-size: 14px;
      cursor: pointer;
    }
    button:hover { background: #3b82f6; }
    .hint {
      margin-top: 18px;
      color: #64748b;
      font-size: 12px;
    }
  </style>
</head>
<body>
  <main>
    <div class="mark" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
        <path d="m9 12 2 2 4-4" />
      </svg>
    </div>
    <p class="code">offline mode</p>
    <h1>CloudSentinel link lost</h1>
    <p>No network connection right now. Dashboard shell is protected, and this local fallback is served from your browser cache.</p>
    <button type="button" onclick="location.reload()">Retry connection</button>
    <div class="hint">Reconnect internet or VPN, then retry.</div>
  </main>
</body>
</html>`;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.put(
        "/__cloudsentinel_offline_fallback__",
        new Response(OFFLINE_HTML, {
          headers: {
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "no-store",
          },
        }),
      );
    }),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)));
    }),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.mode !== "navigate") {
    return;
  }

  event.respondWith(
    fetch(event.request).catch(async () => {
      const cached = await caches.match("/__cloudsentinel_offline_fallback__");
      return cached || new Response(OFFLINE_HTML, { headers: { "Content-Type": "text/html; charset=utf-8" } });
    }),
  );
});
