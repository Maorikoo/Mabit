import Logo from "../shared/components/Logo";

export default function Layout({ children }) {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Full-width header, logo top-left */}
      <header className="relative h-24 border-b border-gray-800 bg-gray-950">
        <div className="absolute left-8 top-1/2 -translate-y-1/2 h-16">
          <Logo />
        </div>
      </header>

      {/* Centered page content */}
      <div className="max-w-6xl mx-auto px-6 py-6">{children}</div>
    </div>
  );
}
