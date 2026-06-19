"use client";

import { useEffect, useState } from "react";
import { isAuthenticated } from "@/lib/auth";

import Login from "./Auth/Login";
import Logout from "./Auth/Logout";
import UpgradeButton from "./UpgradeButton";

import { useJobs } from "@/hooks/useJobs";
import { useStats } from "@/hooks/useStats";

import StatsCard from "./StatsCard";
import JobsPanel from "./JobsPanel";

export default function Dashboard() {
  const [auth, setAuth] = useState(false);

  const { jobs, createJob } = useJobs();
  const { stats } = useStats();

  useEffect(() => {
    setAuth(isAuthenticated());
  }, []);

  if (!auth) {
    return <Login onLogin={() => setAuth(true)} />;
  }

  return (
    <div className="p-8 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">SaaS Dashboard</h1>

        <div className="flex gap-2 items-center">
          <UpgradeButton />
          <Logout />
        </div>
      </div>

      <StatsCard stats={stats} />

      <JobsPanel
        jobs={jobs}
        onCreate={() => createJob("Backend Engineer")}
      />
    </div>
  );
}