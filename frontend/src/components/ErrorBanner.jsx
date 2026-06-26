import { useApp } from "../context/AppContext";

export default function ErrorBanner() {
  const { error, clearError } = useApp();
  if (!error) return null;

  return (
    <div className="flex items-center justify-between bg-brand-red text-white px-4 py-3 text-sm font-sans">
      <span>{error}</span>
      <button onClick={clearError} className="ml-4 font-bold hover:opacity-75">✕</button>
    </div>
  );
}
