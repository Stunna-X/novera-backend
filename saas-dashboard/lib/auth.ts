const API_KEY_STORAGE = "saas_api_key";

export function setApiKey(key: string) {
  localStorage.setItem(API_KEY_STORAGE, key);
}

export function getApiKey() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(API_KEY_STORAGE);
}

export function clearApiKey() {
  localStorage.removeItem(API_KEY_STORAGE);
}

export function isAuthenticated() {
  return !!getApiKey();
}