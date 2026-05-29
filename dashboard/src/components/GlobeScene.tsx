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
const MAX_ARCS = 18;
const SPAWN_INTERVAL = 900;

// Grid Segment segment settings to align intersections mathematically
const GRID_WIDTH_SEGMENTS = 48;
const GRID_HEIGHT_SEGMENTS = 24;

const LAT_STEP = 180 / GRID_HEIGHT_SEGMENTS; // 7.5 degrees
const LNG_STEP = 360 / GRID_WIDTH_SEGMENTS; // 7.5 degrees

// ─── Helpers ─────────────────────────────────────────────────────────────────

function snapToGrid(val: number, step: number): number {
  return Math.round(val / step) * step;
}

function latLngToVec3(lat: number, lng: number, radius: number): THREE.Vector3 {
  // Snapped to perfect grid coordinate intersections
  const snappedLat = snapToGrid(lat, LAT_STEP);
  const snappedLng = snapToGrid(lng, LNG_STEP);

  const phi = (90 - snappedLat) * (Math.PI / 180);
  const theta = (snappedLng + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  );
}

interface OriginCity { lat: number; lng: number; color: string }

const ORIGINS: OriginCity[] = [
  { lat: 39.9, lng: 116.4, color: "#f43f5e" },   // Beijing
  { lat: 55.75, lng: 37.62, color: "#8b5cf6" },   // Moscow
  { lat: -23.55, lng: -46.63, color: "#10b981" },  // São Paulo
  { lat: 40.71, lng: -74.01, color: "#3b82f6" },   // New York
  { lat: 51.51, lng: -0.13, color: "#06b6d4" },    // London
  { lat: 35.68, lng: 139.69, color: "#f59e0b" },   // Tokyo
  { lat: 28.61, lng: 77.21, color: "#ec4899" },    // Delhi
  { lat: -33.87, lng: 151.21, color: "#14b8a6" },  // Sydney
  { lat: 48.86, lng: 2.35, color: "#a855f7" },     // Paris
  { lat: 37.57, lng: 126.98, color: "#06b6d4" },   // Seoul
  { lat: 30.04, lng: 31.24, color: "#f43f5e" },    // Cairo
  { lat: 19.43, lng: -99.13, color: "#10b981" },   // Mexico City
  { lat: -34.6, lng: -58.38, color: "#8b5cf6" },   // Buenos Aires
  { lat: 1.35, lng: 103.82, color: "#3b82f6" },    // Singapore
  { lat: 52.52, lng: 13.41, color: "#f59e0b" },    // Berlin
  { lat: 41.01, lng: 28.98, color: "#ec4899" },    // Istanbul
  { lat: 33.69, lng: 73.04, color: "#14b8a6" },    // Islamabad
  { lat: -1.29, lng: 36.82, color: "#a855f7" },    // Nairobi
  { lat: 14.6, lng: 120.98, color: "#f43f5e" },    // Manila
  { lat: 10.82, lng: 106.63, color: "#06b6d4" },   // Ho Chi Minh
];

function randomOrigin(): OriginCity {
  return ORIGINS[Math.floor(Math.random() * ORIGINS.length)];
}

// ─── Origin Dots — glowing dots perfectly snapped to grid intersections ───────

function OriginDots() {
  return (
    <group>
      {ORIGINS.map((city, i) => (
        <OriginDot key={i} lat={city.lat} lng={city.lng} color={city.color} />
      ))}
    </group>
  );
}

function OriginDot({ lat, lng, color }: { lat: number; lng: number; color: string }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const position = useMemo(() => latLngToVec3(lat, lng, GLOBE_RADIUS * 1.002), [lat, lng]);

  useFrame(({ clock }) => {
    if (!meshRef.current) return;
    const pulse = 0.85 + Math.sin(clock.elapsedTime * 2.5 + lat) * 0.15;
    meshRef.current.scale.setScalar(pulse);
  });

  return (
    <mesh ref={meshRef} position={position}>
      <sphereGeometry args={[0.012, 12, 12]} />
      <meshBasicMaterial color={color} transparent opacity={0.9} />
    </mesh>
  );
}

// ─── HQ Point (HQ Snapped on Grid) ───────────────────────────────────────────

function HQPoint() {
  const meshRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const position = useMemo(() => latLngToVec3(HQ_LAT, HQ_LNG, GLOBE_RADIUS * 1.004), []);

  useFrame(({ clock }) => {
    if (!meshRef.current) return;
    const pulse = 1 + Math.sin(clock.elapsedTime * 3) * 0.2;
    meshRef.current.scale.setScalar(pulse);
    if (ringRef.current) {
      const ringPulse = 1 + Math.sin(clock.elapsedTime * 2) * 0.4;
      ringRef.current.scale.setScalar(ringPulse);
      (ringRef.current.material as THREE.MeshBasicMaterial).opacity = 0.4 - Math.sin(clock.elapsedTime * 2) * 0.2;
    }
  });

  return (
    <group position={position}>
      <mesh ref={meshRef}>
        <sphereGeometry args={[0.025, 16, 16]} />
        <meshBasicMaterial color="#3b82f6" />
      </mesh>
      {/* Pulsing ring */}
      <mesh ref={ringRef}>
        <ringGeometry args={[0.03, 0.06, 32]} />
        <meshBasicMaterial color="#3b82f6" transparent opacity={0.4} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}

// ─── Attack Arc — optimized buffer geometry initialization to prevent glitches ──

interface ArcData {
  id: number;
  curve: THREE.CubicBezierCurve3;
  color: string;
  progress: number;
  speed: number;
  fading: boolean;
  opacity: number;
}

function createArcData(id: number): ArcData {
  const origin = randomOrigin();
  const start = latLngToVec3(origin.lat, origin.lng, GLOBE_RADIUS * 1.004);
  const end = latLngToVec3(HQ_LAT, HQ_LNG, GLOBE_RADIUS * 1.004);

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
    color: origin.color,
    progress: 0,
    speed: 0.35 + Math.random() * 0.35,
    fading: false,
    opacity: 1,
  };
}

function AttackArc({ arc, onDone }: { arc: ArcData; onDone: (id: number) => void }) {
  const progressRef = useRef(arc.progress);
  const fadingRef = useRef(arc.fading);
  const opacityRef = useRef(arc.opacity);

  const fullPoints = useMemo(() => arc.curve.getPoints(ARC_SEGMENTS), [arc.curve]);
  
  // Safe geometry initialization with starting vertex so it is never empty or glitched to 0,0,0
  const geometry = useMemo(() => {
    const geom = new THREE.BufferGeometry();
    geom.setFromPoints([fullPoints[0], fullPoints[0]]);
    return geom;
  }, [fullPoints]);

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
      opacityRef.current -= delta * 1.2;
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
    const initial: ArcData[] = [];
    for (let i = 0; i < 6; i++) {
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

// ─── Rotating Earth Assembly ─────────────────────────────────────────────────

function RotatingGlobe() {
  const groupRef = useRef<THREE.Group>(null);

  useFrame((_, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.08; // smooth rotation
    }
  });

  return (
    <group ref={groupRef}>
      {/* Solid dark earth sphere (blocks backside arcs) */}
      <mesh>
        <sphereGeometry args={[GLOBE_RADIUS, 48, 48]} />
        <meshBasicMaterial color="#050a14" transparent opacity={0.96} />
      </mesh>

      {/* Dense longitude & latitude wireframe grid — beautifully snapping nodes */}
      <mesh>
        <sphereGeometry args={[GLOBE_RADIUS * 0.999, GRID_WIDTH_SEGMENTS, GRID_HEIGHT_SEGMENTS]} />
        <meshBasicMaterial color="#3b82f6" wireframe transparent opacity={0.12} />
      </mesh>

      {/* Origin glowing dots perfectly situated on intersections */}
      <OriginDots />

      {/* HQ Point */}
      <HQPoint />

      {/* Attack arcs */}
      <AttackArcs />
    </group>
  );
}

// ─── Scene ───────────────────────────────────────────────────────────────────

function Scene() {
  return (
    <>
      <ambientLight intensity={0.25} />
      <pointLight position={[10, 10, 10]} intensity={0.6} color="#3b82f6" />
      <pointLight position={[-10, -5, -10]} intensity={0.3} color="#8b5cf6" />
      <pointLight position={[0, 8, -5]} intensity={0.2} color="#06b6d4" />
      <RotatingGlobe />
      <OrbitControls
        enableZoom={false}
        enablePan={false}
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
