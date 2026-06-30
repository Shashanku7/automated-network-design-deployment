/**
 * AppLayout — Shared layout wrapper for all pages
 *
 * Renders the persistent Sidebar + TopBar,
 * and an <Outlet /> for the current page.
 * The sidebar stays static during page transitions.
 */

import { Outlet } from "react-router-dom";
import { SidebarProvider } from "../context/SidebarContext";
import Sidebar from "../components/Sidebar";
import TopBar from "../components/TopBar";

export default function AppLayout() {
  return (
    <SidebarProvider>
      <div className="flex flex-col h-screen overflow-hidden">
        <TopBar />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar />
          <main className="flex-1 bg-surface relative overflow-hidden">
            {/* Each page renders here with a slide-in animation */}
            <div className="h-full page-enter">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}
