import { formatStage } from "@/lib/utils";

interface HeaderProps {
  caseId?: string;
  stage?: string;
  jurisdiction?: string;
}

export function Header({ caseId, stage, jurisdiction }: HeaderProps) {
  return (
    <header className="flex h-14 items-center border-b bg-white px-6">
      <div className="flex items-center gap-4">
        <h1 className="text-sm font-semibold text-slate-900">
          DEFENDER AI
        </h1>
        {caseId && (
          <>
            <span className="text-slate-300">/</span>
            <span className="text-sm text-slate-600">
              Case {caseId}
            </span>
            {stage && (
              <>
                <span className="text-slate-300">|</span>
                <span className="text-xs font-medium text-pd-blue">
                  {formatStage(stage)}
                </span>
              </>
            )}
            {jurisdiction && (
              <>
                <span className="text-slate-300">|</span>
                <span className="text-xs text-slate-500">
                  {jurisdiction}
                </span>
              </>
            )}
          </>
        )}
      </div>
    </header>
  );
}
