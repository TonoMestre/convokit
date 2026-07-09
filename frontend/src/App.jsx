import { AppProvider, useApp } from "./context/AppContext";
import Sidebar from "./components/Sidebar";
import ErrorBanner from "./components/ErrorBanner";
import NuevaConvocatoria from "./components/NuevaConvocatoria";
import DetalleConvocatoria from "./components/DetalleConvocatoria";
import StatsPanel from "./components/StatsPanel";
import LoginScreen from "./components/LoginScreen";

function AppHeader() {
  const { logout } = useApp();
  const hasToken = !!localStorage.getItem("convokit_token");
  return (
    <header
      className="bg-brand-blue flex items-center justify-between shrink-0"
      style={{ padding: "16px 24px", borderBottom: "2px solid var(--color-red)" }}
    >
      <div className="flex flex-col">
        <span style={{ fontFamily: "var(--font-titles)", fontWeight: 700, fontSize: "22px", color: "#fff", lineHeight: 1.1 }}>
          ConvoKit
        </span>
        <span style={{ fontFamily: "var(--font-body)", fontWeight: 400, fontSize: "11px", color: "rgba(255,255,255,0.6)", letterSpacing: "0.15em", marginTop: "2px" }}>
          by innóvate 4.0
        </span>
      </div>
      <div className="flex items-center gap-4">
        {hasToken && (
          <button
            onClick={logout}
            className="text-xs text-white/60 hover:text-white transition-colors"
            style={{ letterSpacing: "0.05em" }}
          >
            Cerrar sesión
          </button>
        )}
        <img
          src="/logo-negativo.png"
          alt="Innóvate 4.0"
          style={{ height: "28px", objectFit: "contain" }}
        />
      </div>
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

function AppShell() {
  const { authNeeded } = useApp();
  if (authNeeded) return <LoginScreen />;
  return (
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
  );
}

export default function App() {
  return (
    <AppProvider>
      <AppShell />
    </AppProvider>
  );
}
