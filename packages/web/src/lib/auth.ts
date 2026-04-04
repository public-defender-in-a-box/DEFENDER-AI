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
          return {
            id: "attorney_001",
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
 * Get the attorney ID from a session, with fallback for MVP.
 */
export function getAttorneyId(session: Session | null): string {
  if (session?.user) {
    return (session.user as Record<string, unknown>).id as string ?? "attorney_001";
  }
  return process.env.NEXT_PUBLIC_ATTORNEY_ID || "attorney_001";
}
