import { Job } from "@/types/job";

export default function JobsPanel({
  jobs,
  onCreate,
}: {
  jobs: Job[];
  onCreate: () => void;
}) {
  return (
    <div className="space-y-4">
      <button
        onClick={onCreate}
        className="px-4 py-2 bg-blue-600 text-white rounded"
      >
        Create Job
      </button>

      <div className="space-y-2">
        {jobs.map((job) => (
          <div key={job.id} className="border p-3 rounded">
            <div className="font-bold">{job.data.title}</div>
            <div>Score: {job.score}</div>
            <div>Status: {job.status}</div>
          </div>
        ))}
      </div>
    </div>
  );
}