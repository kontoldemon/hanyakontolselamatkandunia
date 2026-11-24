const CACHE_NAME = "cloudsentinel-offline-v2";

const OFFLINE_HTML = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="theme-color" content="#050505" />
  <title>CloudSentinel &bull; Offline</title>
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z'/%3E%3Cpath d='M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' fill='%2394a3b8' fill-opacity='0.25'/%3E%3C/svg%3E" />
  <style>
    :root { color-scheme: dark; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      background: #050505;
      color: #f8fafc;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      position: relative;
      overflow: hidden;
      -webkit-font-smoothing: antialiased;
    }
    .brand {
      position: absolute;
      top: 20px;
      left: 20px;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      text-decoration: none;
      z-index: 20;
      opacity: 0.9;
    }
    .brand span {
      font-size: 13px;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: #f8fafc;
    }
    .bg-glow-1 {
      position: absolute;
      top: 50%;
      left: 50%;
      width: 520px;
      height: 520px;
      transform: translate(-50%, -50%);
      border-radius: 9999px;
      background: rgba(59, 130, 246, 0.12);
      filter: blur(130px);
      pointer-events: none;
    }
    .bg-glow-2 {
      position: absolute;
      top: 33%;
      left: 50%;
      width: 320px;
      height: 320px;
      transform: translate(-50%, -50%);
      border-radius: 9999px;
      background: rgba(99, 102, 241, 0.10);
      filter: blur(110px);
      pointer-events: none;
    }
    .bg-grid {
      position: absolute;
      inset: 0;
      background-image:
        linear-gradient(to right, rgba(128,128,128,0.05) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(128,128,128,0.05) 1px, transparent 1px);
      background-size: 24px 24px;
      mask-image: radial-gradient(ellipse 65% 55% at 50% 50%, #000 60%, transparent 100%);
      -webkit-mask-image: radial-gradient(ellipse 65% 55% at 50% 50%, #000 60%, transparent 100%);
      pointer-events: none;
    }
    .card {
      position: relative;
      z-index: 10;
      width: 100%;
      max-width: 380px;
      border-radius: 24px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      background: rgba(10, 10, 12, 0.82);
      padding: 32px 24px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      text-align: center;
    }
    .code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: clamp(38px, 10vw, 48px);
      font-weight: 700;
      letter-spacing: -0.02em;
      color: #f8fafc;
      line-height: 1;
    }
    .title {
      margin-top: 12px;
      font-size: 17px;
      font-weight: 600;
      letter-spacing: -0.01em;
      color: #f8fafc;
    }
    .message {
      margin: 8px auto 0;
      font-size: 12px;
      line-height: 1.6;
      color: #94a3b8;
      max-width: 300px;
    }
    .actions {
      margin-top: 24px;
      display: flex;
      gap: 8px;
      flex-direction: column;
    }
    @media (min-width: 480px) {
      .actions { flex-direction: row; }
      .brand { top: 24px; left: 32px; }
      .brand span { font-size: 14px; }
      .card { padding: 36px 32px; }
    }
    .btn-primary {
      height: 38px;
      border-radius: 9999px;
      background: #2563eb;
      color: #ffffff;
      font-size: 12px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      border: none;
      cursor: pointer;
      text-decoration: none;
      flex: 1;
      transition: background 0.15s, transform 0.1s;
    }
    .btn-primary:hover { background: #3b82f6; }
    .btn-primary:active { transform: scale(0.97); }
    .btn-secondary {
      height: 38px;
      border-radius: 9999px;
      border: 1px solid rgba(255, 255, 255, 0.14);
      background: rgba(255, 255, 255, 0.05);
      color: #f8fafc;
      font-size: 12px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      cursor: pointer;
      text-decoration: none;
      flex: 1;
      transition: background 0.15s, transform 0.1s;
    }
    .btn-secondary:hover { background: rgba(255, 255, 255, 0.1); }
    .btn-secondary:active { transform: scale(0.97); }
  </style>
</head>
<body>
  <div class="brand">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" fill="#94a3b8" fill-opacity="0.25"/>
    </svg>
    <span>Cloud<span style="color:#60a5fa">Sentinel</span></span>
  </div>

  <div class="bg-glow-1"></div>
  <div class="bg-glow-2"></div>
  <div class="bg-grid"></div>

  <main class="card">
    <div class="code">OFFLINE</div>
    <h1 class="title">No connection</h1>
    <p class="message">You appear to be offline. Reconnect to internet or VPN and retry.</p>
    <div class="actions">
      <button type="button" class="btn-primary" onclick="window.location.reload()">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>
          <path d="M21 3v5h-5"/>
          <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>
          <path d="M8 16H3v5"/>
        </svg>
        <span>Retry</span>
      </button>
      <a href="/" class="btn-secondary">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
          <polyline points="9 22 9 12 15 12 15 22"/>
        </svg>
        <span>Dashboard</span>
      </a>
    </div>
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
