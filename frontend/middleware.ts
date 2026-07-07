import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

/**
 * Next.js Edge Middleware for client-side Auth Redirection.
 * 
 * ============================================================================
 * TEST SCENARIOS & EXPECTED BEHAVIOR
 * ============================================================================
 * 
 * SCENARIO 1: Not logged in, visits /history
 *   - Middleware checks 'auth_token' cookie -> not found.
 *   - Redirects to /?redirect=/history.
 *   - After Google Auth login, the app redirects back to /history.
 * 
 * SCENARIO 2: Logged in, visits /history
 *   - Middleware checks 'auth_token' cookie -> found (e.g. 'logged_in').
 *   - NextRoute request passes through to page components.
 *   - Component fetches backend API attaching active Firebase Bearer Token.
 * 
 * SCENARIO 3: Cookie expired, visits /history
 *   - Middleware checks 'auth_token' cookie -> not found.
 *   - Redirects user to landing root /; Firebase status checks on client
 *     recognize the logout and update UI/menus accordingly.
 * 
 * SCENARIO 4: Token expired but cookie is still set
 *   - Middleware checks cookie -> found.
 *   - Allows pass-through to /history.
 *   - During API fetch inside browser, getIdToken() refreshes access tokens
 *     automatically behind the scenes before dispatching.
 * 
 * SCENARIO 5: Backend rejects token (e.g. revoked, deleted on Firebase)
 *   - Middleware allows pass-through because client cookie exists.
 *   - Backend returns 401 Unauthorized status error.
 *   - `authFetch()` catches the error, sets page error, clears cookies,
 *     and redirects/prompts the user to re-authenticate.
 * 
 * ============================================================================
 * MANUAL VERIFICATION COMMANDS & STEPS
 * ============================================================================
 * 
 * Test 1: Verify protected routes redirect
 *   1. Open an Incognito/Private browser window.
 *   2. Directly navigate to http://localhost:3000/history.
 *   3. Expected: Immediately redirects to http://localhost:3000/?redirect=%2Fhistory.
 * 
 * Test 2: Verify login + redirect
 *   1. Sign in with Google from the landing dashboard.
 *   2. Visit http://localhost:3000/history.
 *   3. Expected: History page renders successfully. Network tab lists requests to
 *      /api/reports/history including Authorization Bearer header.
 * 
 * Test 3: Verify logout redirects
 *   1. Go to http://localhost:3000/history while logged in.
 *   2. Click the 'Sign Out' button in top navbar header.
 *   3. Expected: Session terminates, cookie gets removed, and routes redirect to /.
 * 
 * Test 4: Verify API token in headers
 *   1. Authenticate user.
 *   2. Go to /history, open DevTools -> Network panel.
 *   3. Inspect request headers of the fetch to /api/reports/history.
 *   4. Expected: `Authorization: Bearer eyJ...` header is populated with valid token.
 */

// Routes that require authentication
const PROTECTED_ROUTES = [
  "/research",
  "/report",
  "/history",
  "/compare"
]

export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname

  // Check if this is a protected route
  const isProtected = PROTECTED_ROUTES.some(
    route => pathname.startsWith(route)
  )

  if (!isProtected) {
    return NextResponse.next()
  }

  // Check for auth token cookie (managed on login/logout state changes)
  const authCookie = request.cookies.get("auth_token")

  // Also check Firebase standard session cookie
  const firebaseCookie = request.cookies.get("__session")

  // If no session signals found, redirect back to root landing page
  if (!authCookie && !firebaseCookie) {
    const url = request.nextUrl.clone()
    url.pathname = "/"
    url.searchParams.set("redirect", pathname)
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    "/research/:path*",
    "/report/:path*",
    "/history",
    "/compare"
  ]
}
