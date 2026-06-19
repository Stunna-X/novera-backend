"use client";

import { clearApiKey } from "@/lib/auth";

export default function Logout() {
  return (
    <button
      onClick={() => {
        clearApiKey();
        window.location.reload();
      }}
      className="px-3 py-1 border rounded"
    >
      Logout
    </button>
  );
}