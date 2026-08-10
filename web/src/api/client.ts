import type {
  BeverageTypeOption,
  DeclaredFields,
  ErrorBody,
  VerificationResponse,
} from "./types";

/**
 * The one place that talks to the API.
 *
 * Every failure that leaves this module is an `ErrorBody`: a code, a sentence
 * saying what happened, and a sentence saying what to do next. A screen must
 * never have to render "something went wrong" — that is the message that makes
 * an agent stop using the tool.
 */

const BASE = import.meta.env.VITE_API_BASE ?? "";

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
  what_to_do: "Your entry has been kept — try again in a moment.",
};

async function readError(response: Response): Promise<ErrorBody> {
  try {
    const payload = await response.json();
    const detail = payload?.detail ?? payload;
    if (detail && typeof detail.message === "string") {
      return {
        code: detail.code ?? "verification_failed",
        message: detail.message,
        what_to_do: detail.what_to_do ?? "Try again in a moment.",
      };
    }
  } catch {
    // Fall through to the generic-but-actionable message below.
  }
  return UNREACHABLE;
}

export async function fetchBeverageTypes(): Promise<BeverageTypeOption[]> {
  const response = await fetch(`${BASE}/api/beverage-types`);
  if (!response.ok) throw new ApiError(await readError(response));
  return response.json();
}

export async function verifyLabel(
  image: File,
  beverageType: string,
  declared: DeclaredFields,
  signal?: AbortSignal,
): Promise<VerificationResponse> {
  const form = new FormData();
  form.append("image", image);
  form.append("beverage_type", beverageType);
  for (const [name, value] of Object.entries(declared)) {
    if (value) form.append(name, value);
  }

  let response: Response;
  try {
    response = await fetch(`${BASE}/api/verify`, {
      method: "POST",
      body: form,
      signal,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError(UNREACHABLE);
  }

  if (!response.ok) throw new ApiError(await readError(response));
  return response.json();
}
