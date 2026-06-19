"use client";

import { api } from "@/lib/api";

export default function UpgradeButton() {
  const upgrade = async () => {
    try {
      const res = await api.post("/billing/checkout");

      window.location.href = res.data.url;
    } catch (err) {
      console.error("Stripe checkout failed", err);
    }
  };

  return (
    <button
      onClick={upgrade}
      className="px-4 py-2 bg-green-600 text-white rounded"
    >
      Upgrade to Pro
    </button>
  );
}