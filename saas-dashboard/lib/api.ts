import axios from "axios";
import { getApiKey } from "./auth";

export const api = axios.create({
  baseURL: "http://127.0.0.1:8000",
});

api.interceptors.request.use((config) => {
  const key = getApiKey();

  if (key) {
    config.headers["x-api-key"] = key;
  }

  return config;
});