"use client";

import { Sidebar } from "./sidebar";
import { Header } from "./header";
import { ErrorBoundary } from "@/components/shared/error-boundary";
import { usePathname } from "next/navigation";
import { useCase } from "@/hooks/use-case";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();

  // Extract caseId from URL so the header can show breadcrumbs
  const caseMatch = pathname.match(/^\/cases\/([^/]+)/);
  const caseId = caseMatch ? caseMatch[1] : undefined;

  // Hook must be called unconditionally (React rules of hooks)
  const { data: detail } = useCase(caseId ?? null);

  // Auth and client-facing routes get a minimal shell (no sidebar/header)
  const isAuthRoute = pathname === "/login" || pathname === "/register";
  const isClientRoute =
    pathname.startsWith("/intake") || pathname === "/status";

  if (isAuthRoute || isClientRoute) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <div className="privilege-warning text-center">
          ATTORNEY-CLIENT PRIVILEGED MATERIAL
        </div>
        <Header
          caseId={caseId}
          stage={detail?.stage}
          jurisdiction={detail?.jurisdiction}
        />
        <main className="flex-1 p-6">
          <ErrorBoundary>{children}</ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
