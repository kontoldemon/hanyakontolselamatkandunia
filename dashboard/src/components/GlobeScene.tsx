"use client";

import { useRef, useMemo, useEffect, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";

// ─── Constants ───────────────────────────────────────────────────────────────

const GLOBE_RADIUS = 2;
const HQ_LAT = 4.5;
const HQ_LNG = 101.69;
const ARC_SEGMENTS = 64;
const MAX_ARCS = 12;
const SPAWN_INTERVAL = 1800;

// ─── Helpers ─────────────────────────────────────────────────────────────────

function latLngToVec3(lat: number, lng: number, radius: number): THREE.Vector3 {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lng + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  );
}

function randomOrigin(): { lat: number; lng: number } {
  const origins = [
    { lat: 39.9, lng: 116.4 },   // Beijing
    { lat: 55.75, lng: 37.62 },   // Moscow
    { lat: -23.55, lng: -46.63 }, // São Paulo
    { lat: 40.71, lng: -74.01 },  // New York
    { lat: 51.51, lng: -0.13 },   // London
    { lat: 35.68, lng: 139.69 },  // Tokyo
    { lat: 28.61, lng: 77.21 },   // Delhi
    { lat: -33.87, lng: 151.21 }, // Sydney
    { lat: 48.86, lng: 2.35 },    // Paris
    { lat: 37.57, lng: 126.98 },  // Seoul
    { lat: 30.04, lng: 31.24 },   // Cairo
    { lat: 19.43, lng: -99.13 },  // Mexico City
    { lat: -34.6, lng: -58.38 },  // Buenos Aires
    { lat: 1.35, lng: 103.82 },   // Singapore
    { lat: 52.52, lng: 13.41 },   // Berlin
    { lat: 41.01, lng: 28.98 },   // Istanbul
    { lat: 33.69, lng: 73.04 },   // Islamabad
    { lat: -1.29, lng: 36.82 },   // Nairobi
    { lat: 14.6, lng: 120.98 },   // Manila
    { lat: 10.82, lng: 106.63 },  // Ho Chi Minh
  ];
  return origins[Math.floor(Math.random() * origins.length)];
}

// ─── Globe Mesh ──────────────────────────────────────────────────────────────

function GlobeWireframe() {
  const meshRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);

  useFrame((_, delta) => {
    if (meshRef.current) meshRef.current.rotation.y += delta * 0.05;
    if (glowRef.current) glowRef.current.rotation.y += delta * 0.05;
  });

  return (
    <group>
      {/* Wireframe sphere */}
      <mesh ref={meshRef}>
        <sphereGeometry args={[GLOBE_RADIUS, 48, 48]} />
        <meshBasicMaterial color="#1e3a5f" wireframe transparent opacity={0.25} />
      </mesh>
      {/* Inner solid dark sphere */}
      <mesh>
        <sphereGeometry args={[GLOBE_RADIUS * 0.99, 48, 48]} />
        <meshBasicMaterial color="#050a14" transparent opacity={0.9} />
      </mesh>
      {/* Outer glow shell */}
      <mesh ref={glowRef}>
        <sphereGeometry args={[GLOBE_RADIUS * 1.005, 48, 48]} />
        <meshBasicMaterial color="#1a4a7a" wireframe transparent opacity={0.08} />
      </mesh>
    </group>
  );
}

// ─── HQ Point ────────────────────────────────────────────────────────────────

function HQPoint() {
  const meshRef = useRef<THREE.Mesh>(null);
  const position = useMemo(() => latLngToVec3(HQ_LAT, HQ_LNG, GLOBE_RADIUS * 1.01), []);

  useFrame(({ clock }) => {
    if (!meshRef.current) return;
    const pulse = 1 + Math.sin(clock.elapsedTime * 3) * 0.3;
    meshRef.current.scale.setScalar(pulse);
  });

  return (
    <mesh ref={meshRef} position={position}>
      <sphereGeometry args={[0.04, 16, 16]} />
      <meshBasicMaterial color="#3b82f6" />
    </mesh>
  );
}

// ─── Attack Arc ──────────────────────────────────────────────────────────────

interface ArcData {
  id: number;
  curve: THREE.CubicBezierCurve3;
  color: string;
  progress: number;
  speed: number;
  fading: boolean;
  opacity: number;
}

const ARC_COLORS = ["#3b82f6", "#06b6d4", "#8b5cf6", "#f43f5e", "#10b981", "#f59e0b"];

function createArcData(id: number): ArcData {
  const origin = randomOrigin();
  const start = latLngToVec3(origin.lat, origin.lng, GLOBE_RADIUS * 1.01);
  const end = latLngToVec3(HQ_LAT, HQ_LNG, GLOBE_RADIUS * 1.01);

  const mid = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5);
  const dist = start.distanceTo(end);
  const altitude = GLOBE_RADIUS + dist * 0.4;
  mid.normalize().multiplyScalar(altitude);

  const ctrl1 = new THREE.Vector3().lerpVectors(start, mid, 0.33);
  ctrl1.normalize().multiplyScalar(GLOBE_RADIUS + dist * 0.25);
  const ctrl2 = new THREE.Vector3().lerpVectors(mid, end, 0.33);
  ctrl2.normalize().multiplyScalar(GLOBE_RADIUS + dist * 0.25);

  return {
    id,
    curve: new THREE.CubicBezierCurve3(start, ctrl1, ctrl2, end),
    color: ARC_COLORS[Math.floor(Math.random() * ARC_COLORS.length)],
    progress: 0,
    speed: 0.4 + Math.random() * 0.3,
    fading: false,
    opacity: 1,
  };
}

function AttackArc({ arc, onDone }: { arc: ArcData; onDone: (id: number) => void }) {
  const progressRef = useRef(arc.progress);
  const fadingRef = useRef(arc.fading);
  const opacityRef = useRef(arc.opacity);

  const fullPoints = useMemo(() => arc.curve.getPoints(ARC_SEGMENTS), [arc.curve]);
  const geometry = useMemo(() => new THREE.BufferGeometry(), []);
  const material = useMemo(() => new THREE.LineBasicMaterial({ color: arc.color, transparent: true, opacity: 1 }), [arc.color]);
  const lineObj = useMemo(() => new THREE.Line(geometry, material), [geometry, material]);

  useFrame((_, delta) => {
    if (!fadingRef.current) {
      progressRef.current += delta * arc.speed;
      if (progressRef.current >= 1) {
        progressRef.current = 1;
        fadingRef.current = true;
      }
      const count = Math.max(2, Math.floor(progressRef.current * fullPoints.length));
      const visiblePoints = fullPoints.slice(0, count);
      geometry.setFromPoints(visiblePoints);
    } else {
      opacityRef.current -= delta * 1.5;
      if (opacityRef.current <= 0) {
        onDone(arc.id);
        return;
      }
      material.opacity = opacityRef.current;
    }
  });

  return <primitive object={lineObj} />;
}

// ─── Attack System ───────────────────────────────────────────────────────────

function AttackArcs() {
  const [arcs, setArcs] = useState<ArcData[]>([]);
  const nextId = useRef(0);

  useEffect(() => {
    // Spawn initial batch
    const initial: ArcData[] = [];
    for (let i = 0; i < 4; i++) {
      initial.push(createArcData(nextId.current++));
    }
    setArcs(initial);

    const interval = setInterval(() => {
      setArcs((prev) => {
        if (prev.length >= MAX_ARCS) return prev;
        return [...prev, createArcData(nextId.current++)];
      });
    }, SPAWN_INTERVAL);

    return () => clearInterval(interval);
  }, []);

  const handleDone = (id: number) => {
    setArcs((prev) => prev.filter((a) => a.id !== id));
  };

  return (
    <group>
      {arcs.map((arc) => (
        <AttackArc key={arc.id} arc={arc} onDone={handleDone} />
      ))}
    </group>
  );
}

// ─── Scene ───────────────────────────────────────────────────────────────────

function Scene() {
  return (
    <>
      <ambientLight intensity={0.15} />
      <pointLight position={[10, 10, 10]} intensity={0.5} color="#3b82f6" />
      <pointLight position={[-10, -5, -10]} intensity={0.2} color="#8b5cf6" />
      <GlobeWireframe />
      <HQPoint />
      <AttackArcs />
      <OrbitControls
        enableZoom={false}
        enablePan={false}
        autoRotate
        autoRotateSpeed={0.3}
        minPolarAngle={Math.PI * 0.3}
        maxPolarAngle={Math.PI * 0.7}
      />
    </>
  );
}

// ─── Exported Component ──────────────────────────────────────────────────────

export default function GlobeScene() {
  return (
    <div className="w-full h-full">
      <Canvas
        camera={{ position: [0, 0, 5.5], fov: 45 }}
        dpr={[1, 2]}
        style={{ background: "transparent" }}
        gl={{ alpha: true, antialias: true }}
      >
        <Scene />
      </Canvas>
    </div>
  );
}
