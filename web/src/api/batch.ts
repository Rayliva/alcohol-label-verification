import { ApiError } from "./client";
import type { ErrorBody, Outcome } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

/** Batch routes require the session like everything else; without this,
 * cross-origin development gets a 401 on every call while same-origin
 * production quietly works. */
const CREDENTIALED: RequestInit = { credentials: "include" };

export interface PreflightProblem {
  kind: string;
  detail: string;
}

export interface PreflightReport {
  image_count: number;
  row_count: number;
  matched_count: number;
  problem_count: number;
  problems: PreflightProblem[];
  ready: boolean;
}

export interface BatchResultRow {
  application_id: string;
  image: string;
  outcome: Outcome | "error";
  brand_name: string | null;
  issues: number;
  error?: ErrorBody;
}

export interface BatchProgress {
  job_id: string;
  state: "pending" | "running" | "stopped" | "finished";
  done: number;
  total: number;
  elapsed_seconds: number;
  seconds_per_label: number | null;
  estimated_seconds_remaining: number;
  counts: Record<string, number>;
  problems: PreflightProblem[];
  results: BatchResultRow[];
}

function body(images: File[], manifest: File): FormData {
  const form = new FormData();
  for (const image of images) form.append("images", image);
  form.append("manifest", manifest);
  return form;
}

async function unwrap<T>(response: Response): Promise<T> {
  if (response.ok) return response.json();
  let detail: ErrorBody = {
    code: "batch_failed",
    message: "The batch could not be started.",
    what_to_do: "Check the spreadsheet and the images, then try again.",
  };
  try {
    const payload = await response.json();
    if (payload?.detail?.message) detail = payload.detail;
  } catch {
    /* keep the actionable default */
  }
  throw new ApiError(detail);
}

export async function preflight(images: File[], manifest: File): Promise<PreflightReport> {
  return unwrap(
    await fetch(`${BASE}/api/batch/preflight`, {
      method: "POST",
      body: body(images, manifest),
      ...CREDENTIALED,
    }),
  );
}

export async function startBatch(
  images: File[],
  manifest: File,
): Promise<PreflightReport & { job_id: string }> {
  return unwrap(
    await fetch(`${BASE}/api/batch`, {
      method: "POST",
      body: body(images, manifest),
      ...CREDENTIALED,
    }),
  );
}

export async function batchProgress(jobId: string): Promise<BatchProgress> {
  return unwrap(await fetch(`${BASE}/api/batch/${jobId}`, CREDENTIALED));
}

export async function stopBatch(jobId: string): Promise<BatchProgress> {
  return unwrap(await fetch(`${BASE}/api/batch/${jobId}/stop`, { method: "POST", ...CREDENTIALED }));
}

export const templateUrl = `${BASE}/api/batch/template`;
export const exportUrl = (jobId: string) => `${BASE}/api/batch/${jobId}/export`;
