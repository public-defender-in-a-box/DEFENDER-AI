"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

const mainNav = [
  { label: "Dashboard", href: "/cases" },
  { label: "Upload", href: "/upload" },
];

interface CaseNavItem {
  label: string;
  href: string;
  agentKey?: string;
}

function caseNav(caseId: string): CaseNavItem[] {
  return [
    { label: "Overview", href: `/cases/${caseId}` },
    { label: "Motions", href: `/cases/${caseId}/motions`, agentKey: "draft_motions" },
    { label: "Plea / Trial", href: `/cases/${caseId}/plea-trial`, agentKey: "plea_trial_assessment" },
    { label: "Sentencing", href: `/cases/${caseId}/sentencing`, agentKey: "sentencing_analysis" },
    { label: "Timeline", href: `/cases/${caseId}/timeline` },
    { label: "Review", href: `/cases/${caseId}/review` },
  ];
}

/** Status dot: green = data available, gray = pending/not started. */
function StatusDot({ available }: { available: boolean }) {
  return (
    <span
      className={`ml-auto inline-block h-2 w-2 rounded-full ${
        available ? "bg-pd-green" : "bg-slate-300"
      }`}
    />
  );
}

export function Sidebar() {
  const pathname = usePathname();

  // Extract caseId from path like /cases/CASE-abc123/...
  const caseMatch = pathname.match(/^\/cases\/([^/]+)/);
  const caseId = caseMatch ? caseMatch[1] : null;

  return (
    <aside className="flex w-56 flex-col border-r bg-pd-gray">
      <div className="p-4">
        <Link href="/cases" className="text-lg font-bold text-pd-navy">
          DEFENDER AI
        </Link>
        <p className="text-xs text-pd-gray-dark">Public Defender Assistant</p>
      </div>

      <Separator />

      <nav className="flex-1 space-y-1 p-2">
        {mainNav.map((item) => (
          <Button
            key={item.href}
            variant="ghost"
            className={`w-full justify-start ${
              pathname === item.href
                ? "bg-white text-pd-blue font-medium shadow-sm"
                : "text-slate-600"
            }`}
            asChild
          >
            <Link href={item.href}>{item.label}</Link>
          </Button>
        ))}

        {caseId && (
          <>
            <Separator className="my-2" />
            <p className="px-3 py-1 text-xs font-semibold uppercase tracking-wider text-pd-gray-dark">
              Case: {caseId}
            </p>
            {caseNav(caseId).map((item) => (
              <Button
                key={item.href}
                variant="ghost"
                className={`w-full justify-start text-sm ${
                  pathname === item.href
                    ? "bg-white text-pd-blue font-medium shadow-sm"
                    : "text-slate-600"
                }`}
                asChild
              >
                <Link href={item.href} className="flex w-full items-center">
                  {item.label}
                  {item.agentKey !== undefined && (
                    <StatusDot available={false} />
                  )}
                </Link>
              </Button>
            ))}
          </>
        )}
      </nav>
    </aside>
  );
}
