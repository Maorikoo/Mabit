import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import StatCard from "../components/StatCard";

export default function Dashboard() {
  const navigate = useNavigate();

  const stats = useMemo(
    () => ({
      usernames: 42,
      stories: 1280,
      stories24h: 37,
      militaryRelated: 116,
      newItems: 12,
      completeItems: 268,
    }),
    []
  );

  return (
    <>
      <div className="text-sm text-gray-400">Instagram</div>
      <h2 className="text-2xl font-bold mb-6">Dashboard</h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        <StatCard
          title="Usernames"
          value={stats.usernames}
          subtitle="Manage scraping targets"
          onClick={() => navigate("/instagram/usernames")}
        />
        <StatCard title="Stories" value={stats.stories} />
        <StatCard title="Stories - Last 24h" value={stats.stories24h} />
        <StatCard title="Military Related" value={stats.militaryRelated} subtitle="AI analyzed as interesting" />
        <StatCard title="New Items" value={stats.newItems} subtitle="Not seen yet" />
        <StatCard title="Complete Items" value={stats.completeItems} subtitle="Marked as seen" />
      </div>
    </>
  );
}
