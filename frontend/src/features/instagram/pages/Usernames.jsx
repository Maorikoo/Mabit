import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

const MOCK = [
  {
    id: 1,
    username: "test_user",
    profilePic: "https://i.pravatar.cc/80?img=12",
    isPrivate: false,
    lastScraped: "2026-01-03 14:10",
    isScraped: true,
    addedDate: "2026-01-01",
    totalStories: 120,
    stories24h: 4,
    comments: "Watch this account",
  },
];

function AddUsernameModal({ open, onClose, onSubmit }) {
  const [username, setUsername] = useState("");
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <button className="absolute inset-0 bg-black/60" onClick={onClose} aria-label="Close overlay" />
      <div className="absolute left-1/2 top-1/2 w-[92%] max-w-md -translate-x-1/2 -translate-y-1/2 bg-gray-950 border border-gray-800 rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="text-lg font-semibold">Add Username</div>
          <button onClick={onClose} className="text-gray-400 hover:text-white">✕</button>
        </div>

        <label className="block text-sm text-gray-400 mb-2">Instagram username</label>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="e.g. some_user"
          className="w-full rounded-lg bg-gray-900 border border-gray-800 px-3 py-2 outline-none focus:border-gray-700"
        />

        <div className="flex gap-3 mt-5 justify-end">
          <button onClick={onClose} className="px-4 py-2 rounded-lg border border-gray-800 text-gray-200 hover:border-gray-700">
            Cancel
          </button>
          <button
            onClick={() => {
              const u = username.trim();
              if (!u) return;
              onSubmit(u);
              setUsername("");
            }}
            disabled={!username.trim()}
            className="px-4 py-2 rounded-lg bg-blue-600 text-white disabled:opacity-40"
          >
            Submit
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Usernames() {
  const [rows, setRows] = useState(MOCK);
  const [q, setQ] = useState("");
  const [modalOpen, setModalOpen] = useState(false);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return rows;
    return rows.filter((r) => r.username.toLowerCase().includes(s));
  }, [q, rows]);

  function toggleIsScraped(id) {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, isScraped: !r.isScraped } : r)));
  }

  function addUsername(username) {
    if (rows.some((r) => r.username.toLowerCase() === username.toLowerCase())) {
      setModalOpen(false);
      return;
    }
    const newRow = {
      id: Math.max(0, ...rows.map((r) => r.id)) + 1,
      username,
      profilePic: "https://i.pravatar.cc/80?u=" + encodeURIComponent(username),
      isPrivate: false,
      lastScraped: "",
      isScraped: true,
      addedDate: new Date().toISOString().slice(0, 10),
      totalStories: 0,
      stories24h: 0,
      comments: "",
    };
    setRows((prev) => [newRow, ...prev]);
    setModalOpen(false);
  }

  return (
    <>
      <div className="flex items-end justify-between gap-4 mb-6">
        <div>
          <div className="text-sm text-gray-400">Instagram</div>
          <h2 className="text-2xl font-bold">Usernames</h2>
          <Link to="/instagram/dashboard" className="text-sm text-blue-400 hover:underline">
            ← Back to dashboard
          </Link>
        </div>

        <button onClick={() => setModalOpen(true)} className="h-10 px-4 rounded-lg bg-blue-600 text-white hover:bg-blue-500">
          + Add
        </button>
      </div>

      <div className="mb-4">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search username..."
          className="w-full max-w-md rounded-lg bg-gray-900 border border-gray-800 px-3 py-2 outline-none focus:border-gray-700"
        />
      </div>

      <div className="overflow-auto rounded-xl border border-gray-800">
        <table className="min-w-[1100px] w-full text-sm">
          <thead className="bg-gray-900/60 text-gray-300">
            <tr>
              <th className="text-left px-4 py-3">Username</th>
              <th className="text-left px-4 py-3">Profile Pic</th>
              <th className="text-left px-4 py-3">Is Private</th>
              <th className="text-left px-4 py-3">Last Scraped</th>
              <th className="text-left px-4 py-3">Is Scraped</th>
              <th className="text-left px-4 py-3">Added Date</th>
              <th className="text-left px-4 py-3">Total Stories</th>
              <th className="text-left px-4 py-3">Stories Last 24h</th>
              <th className="text-left px-4 py-3">Comments</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-gray-800">
            {filtered.map((r) => (
              <tr key={r.id} className="bg-gray-950 hover:bg-gray-900/30">
                <td className="px-4 py-3 font-medium">@{r.username}</td>
                <td className="px-4 py-3">
                  <img src={r.profilePic} alt="" className="h-10 w-10 rounded-full border border-gray-800 object-cover" />
                </td>
                <td className="px-4 py-3">
                  <span className={r.isPrivate ? "text-amber-300" : "text-gray-400"}>{r.isPrivate ? "Yes" : "No"}</span>
                </td>
                <td className="px-4 py-3 text-gray-300">{r.lastScraped || "—"}</td>
                <td className="px-4 py-3">
                  <input type="checkbox" checked={r.isScraped} onChange={() => toggleIsScraped(r.id)} className="h-4 w-4 accent-blue-600" />
                </td>
                <td className="px-4 py-3 text-gray-300">{r.addedDate}</td>
                <td className="px-4 py-3 text-gray-300">{r.totalStories}</td>
                <td className="px-4 py-3 text-gray-300">{r.stories24h}</td>
                <td className="px-4 py-3 text-gray-300">{r.comments || "—"}</td>
              </tr>
            ))}

            {filtered.length === 0 && (
              <tr>
                <td className="px-4 py-10 text-center text-gray-400" colSpan={9}>
                  No results
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <AddUsernameModal open={modalOpen} onClose={() => setModalOpen(false)} onSubmit={addUsername} />
    </>
  );
}
