"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function useJobs() {
  const [jobs, setJobs] = useState<any[]>([]);

  const fetchJobs = async () => {
    const res = await api.get("/jobs");
    setJobs(res.data);
  };

  const createJob = async (title: string) => {
    await api.post("/jobs", {
      job_data: { title },
    });

    fetchJobs();
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  return { jobs, createJob };
}