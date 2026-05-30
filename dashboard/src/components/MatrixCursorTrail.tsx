"use client";

import { useEffect, useRef } from "react";

interface Particle {
  x: number;
  y: number;
  char: string;
  color: string;
  size: number;
  opacity: number;
  vy: number; // velocity y
  vx: number; // velocity x
  life: number;
  maxLife: number;
}

const CHARS = ["0", "1", "x", "§", "7", "*", "A", "+", "#", "C", "S", "•", "■"];
const COLORS = ["#3b82f6", "#60a5fa", "#34d399", "#a78bfa", "#f43f5e"];

export default function MatrixCursorTrail() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particles = useRef<Particle[]>([]);
  const lastMousePos = useRef({ x: 0, y: 0 });
  const accumulatedDistance = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const handleResize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", handleResize);
    handleResize();

    const addParticle = (x: number, y: number) => {
      const char = CHARS[Math.floor(Math.random() * CHARS.length)];
      const color = COLORS[Math.floor(Math.random() * COLORS.length)];
      const size = 10 + Math.random() * 8;
      const maxLife = 40 + Math.random() * 30;

      particles.current.push({
        x,
        y,
        char,
        color,
        size,
        opacity: 1,
        vy: 1 + Math.random() * 1.5, // falls down
        vx: (Math.random() - 0.5) * 1, // slight horizontal drift
        life: maxLife,
        maxLife,
      });
    };

    const handleMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - lastMousePos.current.x;
      const dy = e.clientY - lastMousePos.current.y;
      const dist = Math.sqrt(dx * dx + dy * dy);

      accumulatedDistance.current += dist;
      lastMousePos.current = { x: e.clientX, y: e.clientY };

      // Add a particle every 12px of cursor movement to avoid excessive particles
      if (accumulatedDistance.current > 12) {
        addParticle(e.clientX, e.clientY);
        accumulatedDistance.current = 0;
      }
    };

    window.addEventListener("mousemove", handleMouseMove);

    let animationId: number;

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      particles.current.forEach((p) => {
        p.life--;
        p.y += p.vy;
        p.x += p.vx;
        p.opacity = p.life / p.maxLife;

        ctx.font = `bold ${p.size}px monospace`;
        ctx.fillStyle = p.color;
        ctx.globalAlpha = p.opacity * 0.7;
        ctx.fillText(p.char, p.x, p.y);
      });

      // Filter out dead particles
      particles.current = particles.current.filter((p) => p.life > 0);

      animationId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("mousemove", handleMouseMove);
      cancelAnimationFrame(animationId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-[99999] w-full h-full"
      style={{ mixBlendMode: "screen" }}
    />
  );
}
