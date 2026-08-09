import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Vercel sets this automatically on every build and request there; it is
// never set locally or in the Docker image, so this only ever fires on
// Vercel. The app routes below need the FastAPI backend, which does not
// exist on Vercel — vercel.json builds the Next.js half only, as a landing
// page. Anyone reaching one of these paths there gets sent home instead of a
// page that loads and then fails every request.
const LANDING_ONLY = process.env.VERCEL === "1";

export function middleware(request: NextRequest) {
  if (!LANDING_ONLY) return NextResponse.next();
  return NextResponse.redirect(new URL("/", request.url));
}

export const config = {
  matcher: ["/login", "/planner", "/inbox", "/habits", "/analytics", "/connect", "/book/:path*"],
};
