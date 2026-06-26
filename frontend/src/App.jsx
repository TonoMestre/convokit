import { AppProvider, useApp } from "./context/AppContext";
import Sidebar from "./components/Sidebar";
import ErrorBanner from "./components/ErrorBanner";
import NuevaConvocatoria from "./components/NuevaConvocatoria";
import DetalleConvocatoria from "./components/DetalleConvocatoria";

function Main() {
  const { view } = useApp();
  return (
    <main className="flex-1 overflow-y-auto bg-white">
      {view === "nueva" ? <NuevaConvocatoria /> : <DetalleConvocatoria />}
    </main>
  );
}

export default function App() {
  return (
    <AppProvider>
      <div className="flex min-h-screen font-sans">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <ErrorBanner />
          <Main />
        </div>
      </div>
    </AppProvider>
  );
}
