const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const error = await res.text();
    throw new Error(`API error ${res.status}: ${error}`);
  }

  return res.json();
}

export const api = {
  cases: {
    list: () => request<unknown[]>("/cases"),
    get: (id: string) => request<unknown>(`/cases/${id}`),
    create: (data: unknown) =>
      request<unknown>("/cases", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },
  upload: {
    document: async (file: File, documentType: string) => {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("document_type", documentType);

      const res = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
      return res.json();
    },
  },
};
