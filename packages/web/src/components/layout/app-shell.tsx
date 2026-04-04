import { Sidebar } from "./sidebar";
import { Header } from "./header";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <div className="privilege-warning text-center">
          ATTORNEY-CLIENT PRIVILEGED MATERIAL
        </div>
        <Header />
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
