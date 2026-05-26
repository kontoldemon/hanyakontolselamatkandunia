import {
  Activity,
  Ban,
  Fingerprint,
  Gauge,
  RadioTower,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { LiveMetrics } from "@/components/LiveMetrics";
import { events, points, techniques } from "@/lib/data";

export default function Dashboard() {
  const adminUrl =
    process.env.NEXT_PUBLIC_CLOUDSENTINEL_ADMIN_API_URL || "https://sensor.example/healthz";
  const socketUrl =
    process.env.NEXT_PUBLIC_CLOUDSENTINEL_SOCKET_URL || "wss://sensor.example/socket.io";

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <ShieldCheck aria-hidden="true" />
          <div>
            <strong>CloudSentinel</strong>
            <span>FYP Prototype</span>
          </div>
        </div>
        <nav aria-label="Primary">
          <a className="active" href="#overview">
            <Gauge aria-hidden="true" /> Overview
          </a>
          <a href="#map">
            <RadioTower aria-hidden="true" /> Threat Map
          </a>
          <a href="#sessions">
            <Terminal aria-hidden="true" /> Sessions
          </a>
          <a href="#identity">
            <Fingerprint aria-hidden="true" /> HASSH DNA
          </a>
        </nav>
        <div className="sensor-card">
          <span className="pulse" />
          <div>
            <strong>Phase 1 Sensor</strong>
            <p>{adminUrl}</p>
          </div>
        </div>
      </aside>

      <section className="content">
        <header className="topbar" id="overview">
          <div>
            <p>DigitalOcean sensor plus Vercel dashboard</p>
            <h1>War Room</h1>
          </div>
          <div className="connection">
            <Activity aria-hidden="true" />
            <span>{socketUrl}</span>
          </div>
        </header>

        <LiveMetrics />

        <section className="grid">
          <article className="panel map-panel" id="map">
            <div className="panel-title">
              <div>
                <span>Global telemetry</span>
                <h2>Attack Origin Map</h2>
              </div>
              <RadioTower aria-hidden="true" />
            </div>
            <div className="map">
              <div className="equator" />
              {points.map((point) => (
                <span
                  className="map-point"
                  key={point.label}
                  style={{
                    left: point.left,
                    top: point.top,
                    width: point.size,
                    height: point.size,
                  }}
                  title={point.label}
                >
                  {point.label}
                </span>
              ))}
            </div>
          </article>

          <article className="panel" id="identity">
            <div className="panel-title">
              <div>
                <span>Identity tracking</span>
                <h2>MITRE Coverage</h2>
              </div>
              <Fingerprint aria-hidden="true" />
            </div>
            <div className="techniques">
              {techniques.map((technique) => (
                <div className="technique" key={technique.id}>
                  <div>
                    <strong>{technique.id}</strong>
                    <span>{technique.name}</span>
                  </div>
                  <meter min="0" max="45" value={technique.count} />
                </div>
              ))}
            </div>
          </article>
        </section>

        <section className="panel events" id="sessions">
          <div className="panel-title">
            <div>
              <span>Live feed</span>
              <h2>Recent Attack Events</h2>
            </div>
            <Ban aria-hidden="true" />
          </div>
          <div className="table" role="table" aria-label="Recent attack events">
            <div className="row header" role="row">
              <span>Time</span>
              <span>IP</span>
              <span>TTP</span>
              <span>Command</span>
              <span>Action</span>
            </div>
            {events.map((event) => (
              <div className="row" role="row" key={event.id}>
                <span>{event.time}</span>
                <span>
                  {event.ip} <small>{event.country}</small>
                </span>
                <span>{event.technique}</span>
                <code>{event.command}</code>
                <strong>{event.action}</strong>
              </div>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}
