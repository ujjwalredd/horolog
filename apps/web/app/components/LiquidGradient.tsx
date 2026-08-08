"use client";

import { useEffect, useState } from "react";

export function LiquidGradient() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  return (
    <div className="absolute inset-0 -z-10 overflow-hidden bg-bg">
      {/* 
        Liquid Glass animated mesh gradient.
        Using warm stone and gold accents.
      */}
      <div className="absolute left-[-5%] top-[-10%] h-[700px] w-[700px] animate-blob rounded-full bg-stone-300/40 mix-blend-multiply blur-[100px]" />
      <div className="absolute right-[-10%] top-[-20%] h-[600px] w-[600px] animate-blob rounded-full bg-yellow-600/15 mix-blend-multiply blur-[120px] animation-delay-2000" />
      <div className="absolute bottom-[-20%] left-[10%] h-[800px] w-[800px] animate-blob rounded-full bg-stone-400/20 mix-blend-multiply blur-[100px] animation-delay-4000" />
      
      {/* Subtle overlay texture/gradient to ground it */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-bg/50 to-bg" />
    </div>
  );
}
