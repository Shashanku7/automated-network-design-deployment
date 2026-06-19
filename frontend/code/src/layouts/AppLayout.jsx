/**
 * AppLayout — Shared layout wrapper for all pages
 *
 * Renders the persistent Sidebar + TopBar,
 * and an <Outlet /> for the current page.
 * The sidebar stays static during page transitions.
 */

import { Outlet } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import TopBar from "../components/TopBar";

export default function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 ml-64 overflow-hidden">
        <TopBar />
        <main className="flex-1 bg-surface relative overflow-hidden">
          {/* Each page renders here with a slide-in animation */}
          <div className="h-full page-enter">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
