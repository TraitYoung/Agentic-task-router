/** Next 服务端转发到 FastAPI 的基址；可在 frontend/.env.local 中设置 BACKEND_URL */
export function getBackendBaseUrl(): string {
  const u = process.env.BACKEND_URL?.trim();
  if (u) return u.replace(/\/$/, "");
  return "http://127.0.0.1:8000";
}
