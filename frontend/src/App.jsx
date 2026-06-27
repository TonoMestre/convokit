import { AppProvider, useApp } from "./context/AppContext";
import Sidebar from "./components/Sidebar";
import ErrorBanner from "./components/ErrorBanner";
import NuevaConvocatoria from "./components/NuevaConvocatoria";
import DetalleConvocatoria from "./components/DetalleConvocatoria";
import StatsPanel from "./components/StatsPanel";

function AppHeader() {
  return (
    <header
      className="bg-brand-blue flex items-center px-5 h-14 shrink-0"
      style={{ borderBottom: "2px solid var(--color-red)" }}
    >
      <img
        src="/logo-negativo.png"
        alt="Innóvate 4.0"
        className="h-8 mr-3 object-contain"
      />
      <span
        className="text-white text-base tracking-wide"
        style={{ fontFamily: "var(--font-body)", fontWeight: 500 }}
      >
        ConvoKit
      </span>
    </header>
  );
}

function Main() {
  const { view } = useApp();
  return (
    <main className="flex-1 overflow-y-auto bg-white">
      {view === "nueva"   && <NuevaConvocatoria />}
      {view === "detalle" && <DetalleConvocatoria />}
      {view === "stats"   && <StatsPanel />}
    </main>
  );
}

export default function App() {
  return (
    <AppProvider>
      <div className="flex flex-col min-h-screen font-sans">
        <AppHeader />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar />
          <div className="flex-1 flex flex-col overflow-hidden">
            <ErrorBanner />
            <Main />
          </div>
        </div>
      </div>
    </AppProvider>
  );
}
