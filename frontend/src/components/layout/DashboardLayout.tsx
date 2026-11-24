import { Sidebar } from "./Sidebar";
import { Header } from "./Header";

export function DashboardLayout({ children, contentClassName = "" }: {
  children: React.ReactNode;
  contentClassName?: string;
}) {
  return (
    <div className="min-h-screen bg-bg-primary">
      <Sidebar />
      <div className="flex min-h-screen min-w-0 flex-col lg:ml-[220px]">
        <Header />
        <main className={`min-w-0 flex-1 p-4 sm:p-6 ${contentClassName}`}>{children}</main>
      </div>
    </div>
  );
}
