"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

const mainNav = [
  { label: "Dashboard", href: "/cases" },
  { label: "Upload", href: "/upload" },
];

function caseNav(caseId: string) {
  return [
    { label: "Overview", href: `/cases/${caseId}` },
    { label: "Motions", href: `/cases/${caseId}/motions` },
    { label: "Plea / Trial", href: `/cases/${caseId}/plea-trial` },
    { label: "Sentencing", href: `/cases/${caseId}/sentencing` },
    { label: "Timeline", href: `/cases/${caseId}/timeline` },
    { label: "Review", href: `/cases/${caseId}/review` },
  ];
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
                <Link href={item.href}>{item.label}</Link>
              </Button>
            ))}
          </>
        )}
      </nav>
    </aside>
  );
}
