"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function useStats() {
  const [stats, setStats] = useState(null);

  const fetchStats = async () => {
    const res = await api.get("/analytics/jobs/status-count");
    setStats(res.data);
  };

  useEffect(() => {
    fetchStats();
  }, []);

  return { stats };
}