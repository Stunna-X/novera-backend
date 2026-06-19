export default function StatsCard({ stats }: any) {
  if (!stats) return null;

  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="p-4 border rounded">Running: {stats.running}</div>
      <div className="p-4 border rounded">Completed: {stats.completed}</div>
      <div className="p-4 border rounded">Failed: {stats.failed}</div>
    </div>
  );
}