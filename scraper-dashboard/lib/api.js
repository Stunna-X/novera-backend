export async function fetchJobs() {
  const res = await fetch("http://127.0.0.1:8000/jobs", {
    cache: "no-store",
  });

  if (!res.ok) throw new Error("Failed to fetch jobs");

  return res.json();
}