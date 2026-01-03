export default function StatCard({ title, value, subtitle, onClick }) {
    const clickable = typeof onClick === "function";
  
    return (
      <div
        onClick={onClick}
        role={clickable ? "button" : undefined}
        tabIndex={clickable ? 0 : undefined}
        className={[
          "bg-gray-900 border border-gray-800 rounded-xl p-6",
          clickable ? "cursor-pointer hover:border-gray-700 hover:bg-gray-900/80" : "",
        ].join(" ")}
      >
        <div className="flex flex-col items-center text-center gap-2">
          <div className="text-sm text-gray-400 break-words">{title}</div>
          <div className="text-4xl font-bold text-white leading-tight break-words">{value}</div>
          {subtitle ? <div className="text-xs text-gray-500 break-words">{subtitle}</div> : null}
        </div>
      </div>
    );
  }
  