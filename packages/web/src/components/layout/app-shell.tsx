"use client";

import { Sidebar } from "./sidebar";
import { Header } from "./header";
import { ErrorBoundary } from "@/components/shared/error-boundary";
import { usePathname } from "next/navigation";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();

  // Extract caseId from URL so the header can show breadcrumbs
  const caseMatch = pathname.match(/^\/cases\/([^/]+)/);
  const caseId = caseMatch ? caseMatch[1] : undefined;

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <div className="privilege-warning text-center">
          ATTORNEY-CLIENT PRIVILEGED MATERIAL
        </div>
        <Header caseId={caseId} />
        <main className="flex-1 p-6">
          <ErrorBoundary>{children}</ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
