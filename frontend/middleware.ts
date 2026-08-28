import { NextRequest, NextResponse } from "next/server";

/**
 * Route gate. Everything under /dashboard/* requires a signed-in user.
 * We check for the `cor1x_session` HttpOnly cookie the backend sets on
 * successful OTP verify (for existing mobiles) or /auth/signup completion.
 *
 * We don't validate the cookie's signature here — that's the backend's job
 * on every API call. Middleware only checks *presence* so we can short-
 * circuit the page render and redirect to /login?next=<original url>.
 *
 * Unauthenticated pages (/, /login, /signup, /products, /privacy, /terms)
 * are excluded by the matcher below.
 */
export function middleware(req: NextRequest) {
  const session = req.cookies.get("cor1x_session");
  if (session) return NextResponse.next();

  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = `?next=${encodeURIComponent(req.nextUrl.pathname + req.nextUrl.search)}`;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: [
    // Gate dashboard + any /me-driven page
    "/dashboard/:path*",
    // Note: /admin has its own admin_session cookie + login page —
    // handled separately inside those routes.
  ],
};
