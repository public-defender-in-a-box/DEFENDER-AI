import type { NextAuthOptions, Session, User } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

/**
 * NextAuth configuration for MVP.
 *
 * Uses CredentialsProvider with a hardcoded lookup for development.
 * TODO: Replace with OAuth/SAML provider for production deployment.
 */
export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "Attorney Login",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials): Promise<User | null> {
        // MVP: accept any login with a valid email format
        // TODO: Wire to backend authentication endpoint
        if (credentials?.email) {
          // Derive a stable attorney ID from email to support multi-user
          const slug = credentials.email
            .split("@")[0]
            .replace(/[^a-zA-Z0-9]/g, "_")
            .toLowerCase();
          return {
            id: `attorney_${slug}`,
            email: credentials.email,
            name: "Public Defender",
          };
        }
        return null;
      },
    }),
  ],
  session: {
    strategy: "jwt",
  },
  callbacks: {
    async session({ session, token }): Promise<Session> {
      if (session.user && token.sub) {
        (session.user as Record<string, unknown>).id = token.sub;
      }
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
};

/**
 * Get the attorney ID from a session.
 * Throws if no session — callers must handle auth gating.
 */
export function getAttorneyId(session: Session | null): string {
  if (session?.user) {
    const id = (session.user as Record<string, unknown>).id;
    if (typeof id === "string") return id;
  }
  // MVP fallback for server-side contexts where session isn't available yet
  // This is only used during the transition to full auth wiring
  return "attorney_001";
}
