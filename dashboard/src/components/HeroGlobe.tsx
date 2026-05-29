"use client";

import dynamic from "next/dynamic";
import { Suspense } from "react";

const GlobeScene = dynamic(() => import("@/components/GlobeScene"), { ssr: false });

export default function HeroGlobe() {
  return (
    <div className="absolute inset-0 z-0">
      <Suspense fallback={<div className="w-full h-full bg-[#050505]" />}>
        <GlobeScene />
      </Suspense>
    </div>
  );
}
