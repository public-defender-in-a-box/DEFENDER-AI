"use client";

import { CaseProvider } from "@/providers/case-provider";

export default function CaseLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { caseId: string };
}) {
  return <CaseProvider caseId={params.caseId}>{children}</CaseProvider>;
}
