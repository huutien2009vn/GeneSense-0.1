async function request(path, requestOptions = {}) {
  const { timeout = 35000, quiet = false, ...options } = requestOptions;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const isForm = options.body instanceof FormData;
    const response = await fetch(path, { ...options, signal: controller.signal, credentials: "same-origin", cache: "no-store",
      headers: { ...(isForm ? {} : { "Content-Type": "application/json" }), "X-Requested-With": "HealthPredict", ...options.headers } });
    const data = response.status === 204 ? {} : await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = typeof data.detail === "string" ? data.detail : data.detail?.[0]?.msg || "Chưa thể hoàn tất. Vui lòng thử lại.";
      const error = new Error(message);
      error.status = response.status;
      if (response.status === 401 && !quiet) window.dispatchEvent(new Event("session-expired"));
      throw error;
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Kết nối mất nhiều thời gian. Hãy thử lại sau ít phút.");
    if (error instanceof TypeError) throw new Error("Chưa kết nối được. Hãy kiểm tra mạng và thử lại.");
    throw error;
  } finally { clearTimeout(timer); }
}
export const api = {
  authConfig: () => request("/api/auth/config"),
  me: () => request("/api/auth/me", { quiet: true }),
  demo: () => request("/api/auth/demo", { method: "POST" }),
  logout: () => request("/api/auth/logout", { method: "POST" }),
  profile: () => request("/api/profile"),
  saveProfile: body => request("/api/profile", { method: "PUT", body: JSON.stringify(body) }),
  assess: body => request("/api/assessments", { method: "POST", body: JSON.stringify(body) }),
  history: (limit = 30) => request(`/api/assessments?limit=${limit}`),
  assessment: id => request(`/api/assessments/${encodeURIComponent(id)}`),
  feedback: body => request("/api/feedback", { method: "POST", body: JSON.stringify(body) }),
  analyzeMedicalRecord: body => request("/api/medical-records/analyze", { method: "POST", body, timeout: 65000 }),
  saveMedicalRecord: body => request("/api/medical-records", { method: "POST", body: JSON.stringify(body) }),
  medicalRecords: () => request("/api/medical-records"),
  deleteMedicalRecord: id => request(`/api/medical-records/${encodeURIComponent(id)}`, { method: "DELETE" }),
};
