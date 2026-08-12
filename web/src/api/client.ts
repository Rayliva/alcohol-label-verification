import type {
  DeclaredFields,
  ErrorBody,
  QueueItemDetail,
  QueueListing,
  VerificationResponse,
} from "./types";

/**
 * The one place that talks to the API.
 *
 * Every failure that leaves this module is an `ErrorBody`: a code, a sentence
 * saying what happened, and a sentence saying what to do next. A screen must
 * never have to render "something went wrong", which is the message that makes
 * an agent stop using the tool.
 */

const BASE = import.meta.env.VITE_API_BASE ?? "";

/** The session lives in a cookie the browser will not send cross-origin
 * unless asked. In production the UI and API share an origin; in development
 * they do not, and forgetting this is a 401 that only appears locally. */
const CREDENTIALED: RequestInit = { credentials: "include" };

export class ApiError extends Error {
  readonly body: ErrorBody;

  constructor(body: ErrorBody) {
    super(body.message);
    this.body = body;
  }
}

const UNREACHABLE: ErrorBody = {
  code: "service_unreachable",
  message: "Can't reach the label checking service right now.",
  what_to_do: "Your entry has been kept. Try again in a moment.",
};

/** Shape whatever the API said into something a screen can render. */
function errorFrom(payload: any): ErrorBody {
  const detail = payload?.detail ?? payload;
  if (detail && typeof detail.message === "string") {
    return {
      code: detail.code ?? "verification_failed",
      message: detail.message,
      what_to_do: detail.what_to_do ?? "Try again in a moment.",
    };
  }
  return UNREACHABLE;
}

async function readError(response: Response): Promise<ErrorBody> {
  try {
    return errorFrom(await response.json());
  } catch {
    // Fall through to the generic-but-actionable message.
    return UNREACHABLE;
  }
}

/**
 * Check one label.
 *
 * XMLHttpRequest rather than fetch, for one reason: it reports how much of the
 * image has actually gone up. The progress screen used to move through named
 * stages on a timer, so "checking each field" was always the stage on screen
 * when the wait got long, whether or not anything was being checked. Real
 * upload progress is the one part of the wait a browser can honestly measure,
 * so it is the only part the screen now claims to know.
 */
export function verifyLabel(
  image: File,
  beverageType: string,
  declared: DeclaredFields,
  signal?: AbortSignal,
  onUploaded?: (fraction: number) => void,
): Promise<VerificationResponse> {
  const form = new FormData();
  form.append("image", image);
  form.append("beverage_type", beverageType);
  for (const [name, value] of Object.entries(declared)) {
    if (value) form.append(name, value);
  }

  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const request = new XMLHttpRequest();
    request.open("POST", `${BASE}/api/verify`);
    request.withCredentials = true;

    const abort = () => request.abort();
    signal?.addEventListener("abort", abort);
    const done = () => signal?.removeEventListener("abort", abort);

    request.upload.onprogress = (event) => {
      if (event.lengthComputable && onUploaded) onUploaded(event.loaded / event.total);
    };
    request.upload.onload = () => onUploaded?.(1);

    request.onload = () => {
      done();
      let payload: unknown;
      try {
        payload = JSON.parse(request.responseText);
      } catch {
        reject(new ApiError(UNREACHABLE));
        return;
      }
      if (request.status >= 200 && request.status < 300) {
        resolve(payload as VerificationResponse);
        return;
      }
      reject(new ApiError(errorFrom(payload)));
    };
    request.onerror = () => {
      done();
      reject(new ApiError(UNREACHABLE));
    };
    request.onabort = () => {
      done();
      reject(new DOMException("Aborted", "AbortError"));
    };

    request.send(form);
  });
}


export async function signIn(username: string, password: string): Promise<string> {
  const response = await fetch(`${BASE}/api/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
    ...CREDENTIALED,
  });
  if (!response.ok) throw new ApiError(await readError(response));
  return (await response.json()).username;
}

export async function signOut(): Promise<void> {
  await fetch(`${BASE}/api/logout`, { method: "POST", ...CREDENTIALED });
}

/** Who is signed in, or null. A 401 here is the ordinary signed-out case, not
 * an error worth showing anyone. */
export async function currentAgent(): Promise<string | null> {
  try {
    const response = await fetch(`${BASE}/api/session`, CREDENTIALED);
    if (!response.ok) return null;
    return (await response.json()).username;
  } catch {
    return null;
  }
}

export async function fetchQueue(): Promise<QueueListing> {
  const response = await fetch(`${BASE}/api/queue`, CREDENTIALED);
  if (!response.ok) throw new ApiError(await readError(response));
  return response.json();
}

export async function fetchQueueItem(id: string): Promise<QueueItemDetail> {
  const response = await fetch(`${BASE}/api/queue/${encodeURIComponent(id)}`, CREDENTIALED);
  if (!response.ok) throw new ApiError(await readError(response));
  return response.json();
}

export async function recordDecision(
  id: string,
  action: "approve" | "reject" | "override",
  note: string,
): Promise<void> {
  const response = await fetch(
    `${BASE}/api/queue/${encodeURIComponent(id)}/decision`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, note }),
      ...CREDENTIALED,
    },
  );
  if (!response.ok) throw new ApiError(await readError(response));
}

export function labelImageUrl(id: string): string {
  return `${BASE}/api/queue/${encodeURIComponent(id)}/image`;
}
