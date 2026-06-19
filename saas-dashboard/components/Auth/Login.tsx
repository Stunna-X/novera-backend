"use client";

import { useState } from "react";
import { setApiKey } from "@/lib/auth";

export default function Login({ onLogin }: { onLogin: () => void }) {
  const [key, setKey] = useState("");

  const handleLogin = () => {
    if (!key) return;

    setApiKey(key);
    onLogin();
  };

  return (
    <div className="flex h-screen items-center justify-center">
      <div className="w-full max-w-sm p-6 border rounded">
        <h1 className="text-xl font-bold mb-4">SaaS Login</h1>

        <input
          className="w-full border p-2 mb-4"
          placeholder="Enter API Key"
          value={key}
          onChange={(e) => setKey(e.target.value)}
        />

        <button
          onClick={handleLogin}
          className="w-full bg-black text-white p-2"
        >
          Login
        </button>
      </div>
    </div>
  );
}