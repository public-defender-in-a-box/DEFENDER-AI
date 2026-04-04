import { withAuth } from "next-auth/middleware";

/**
 * Protect attorney routes — unauthenticated users redirect to /login.
 * The /login, /register, /intake, /status, and API routes are public.
 */
export default withAuth({
  pages: {
    signIn: "/login",
  },
});

export const config = {
  matcher: ["/cases/:path*", "/upload/:path*"],
};
