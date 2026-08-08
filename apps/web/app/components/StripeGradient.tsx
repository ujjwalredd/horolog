"use client";

import { useEffect, useState } from "react";

export function StripeGradient() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  return (
    <div className="absolute inset-0 -z-10 overflow-hidden bg-[#F6F9FC]">
      {/* 
        Stripe-style animated mesh gradient.
        Created using blurred, rotating elliptical blobs in brand colors.
      */}
      <div className="absolute left-[-10%] top-[-20%] h-[600px] w-[600px] animate-blob rounded-full bg-purple-300/40 mix-blend-multiply blur-[80px]" />
      <div className="absolute right-[-10%] top-[-10%] h-[500px] w-[500px] animate-blob rounded-full bg-blue-300/40 mix-blend-multiply blur-[80px] animation-delay-2000" />
      <div className="absolute bottom-[-20%] left-[20%] h-[600px] w-[600px] animate-blob rounded-full bg-indigo-300/30 mix-blend-multiply blur-[80px] animation-delay-4000" />
      
      {/* Slanted overlay to give that signature Stripe diagonal cut */}
      <div className="absolute bottom-0 left-0 right-0 h-32 origin-bottom-left -skew-y-3 bg-bg" />
    </div>
  );
}
