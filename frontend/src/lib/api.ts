/** Thin typed client for the local backend. Errors carry the backend's readable message. */
export class ApiError extends Error {
  status: number;
  data: any;
  constructor(status: number, message: string, data?: any) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

async function handle(res: Response) {
  if (res.ok) return res.status === 204 ? null : res.json();
  let detail: any = null;
  try { detail = (await res.json()).detail; } catch { /* not json */ }
  const msg = typeof detail === "string" ? detail : detail?.message ?? `Request failed (${res.status})`;
  throw new ApiError(res.status, msg, detail);
}

function req(method: string, path: string, body?: unknown) {
  return fetch(`/api${path}`, {
    method,
    credentials: "same-origin",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  }).then(handle);
}

export const api = {
  get: <T = any>(path: string): Promise<T> => req("GET", path),
  post: <T = any>(path: string, body: unknown = {}): Promise<T> => req("POST", path, body),
  put: <T = any>(path: string, body: unknown): Promise<T> => req("PUT", path, body),
  patch: <T = any>(path: string, body: unknown): Promise<T> => req("PATCH", path, body),
  del: <T = any>(path: string): Promise<T> => req("DELETE", path),
  /** Upload with real byte progress (fetch cannot report upload progress). */
  upload<T = any>(path: string, file: File, onProgress?: (frac: number) => void, field = "file"): Promise<T> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `/api${path}`);
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total);
      xhr.onload = () => {
        let data: any = null;
        try { data = JSON.parse(xhr.responseText); } catch { /* ignore */ }
        if (xhr.status >= 200 && xhr.status < 300) resolve(data);
        else {
          const d = data?.detail;
          reject(new ApiError(xhr.status, typeof d === "string" ? d : d?.message ?? `Upload failed (${xhr.status})`, d));
        }
      };
      xhr.onerror = () => reject(new ApiError(0, "The upload was interrupted. Check the connection to the PC."));
      const form = new FormData();
      form.append(field, file);
      xhr.send(form);
    });
  },
};

export const media = {
  video: (pid: string) => `/api/media/video/${pid}`,
  projectThumb: (pid: string) => `/api/media/thumb/project/${pid}`,
  candidateThumb: (cid: string) => `/api/media/thumb/candidate/${cid}`,
  exportFile: (eid: string, download = false) => `/api/media/export/${eid}${download ? "?download=true" : ""}`,
};
