"use client";

import { useEffect, useMemo, useState } from "react";

type Job = {
  title: string;
  company: string;
  location: string;
};

export default function Home() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  async function fetchJobs() {
    try {
      setLoading(true);

      const res = await fetch("http://127.0.0.1:8000/jobs");

      if (!res.ok) {
        throw new Error("Failed to fetch jobs");
      }

      const data = await res.json();

      setJobs(data || []);
    } catch (error) {
      console.error("Error fetching jobs:", error);
      setJobs([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchJobs();

    const interval = setInterval(fetchJobs, 30000);

    return () => clearInterval(interval);
  }, []);

  const filteredJobs = useMemo(() => {
    return jobs.filter((job) =>
      `${job.title} ${job.company} ${job.location}`
        .toLowerCase()
        .includes(search.toLowerCase())
    );
  }, [jobs, search]);

  return (
    <main className="min-h-screen bg-zinc-100 p-8">
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold">
            Job Dashboard
          </h1>

          <p className="text-zinc-600 mt-2">
            {filteredJobs.length} jobs found
          </p>
        </div>

        <button
          onClick={fetchJobs}
          className="rounded-lg bg-black px-4 py-2 text-white hover:opacity-90"
        >
          Refresh Jobs
        </button>
      </div>

      <input
        className="w-full rounded-lg border bg-white p-3 mb-6"
        placeholder="Search jobs..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      {loading ? (
        <p>Loading jobs...</p>
      ) : filteredJobs.length === 0 ? (
        <p>No jobs found</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredJobs.map((job, index) => (
            <div key={index} className="rounded-xl bg-white p-5 shadow">
              <h2 className="text-xl font-semibold">{job.title}</h2>

              <p className="mt-2 text-zinc-700">{job.company}</p>

              <p className="text-sm text-zinc-500">{job.location}</p>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}