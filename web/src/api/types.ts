/** The wire format, mirroring api/app/api/models.py and docs/ui-spec.md. */

export type Verdict = "pass" | "needs_review" | "fail";
export type Outcome = Verdict | "unreadable";

export interface ErrorBody {
  code: string;
  message: string;
  what_to_do: string;
  partial_fields_shown?: boolean;
}

export interface FieldOutcome {
  field: string;
  display_name: string;
  declared: string | null;
  detected: string | null;
  verdict: Verdict;
  confidence: number;
  reason: string;
  /** Null when the field is not on the label, so there is no region to crop. */
  crop_url: string | null;
  citation: string | null;
}

export interface WarningSubCheck {
  check: string;
  display_name: string;
  verdict: Verdict;
  reason: string;
}

export interface VerificationResponse {
  label_id: string | null;
  /** The queue row this upload became; null on recorded seeded results. */
  queue_id?: string | null;
  beverage_type: string;
  overall: Outcome;
  processing_ms: number;
  error: ErrorBody | null;
  fields: FieldOutcome[];
  warning_checks: WarningSubCheck[];
  counts: Record<string, number>;
  stage_ms: Record<string, number>;
  ocr_engine: string | null;
}


export interface DeclaredFields {
  application_id: string;
  brand_name: string;
  class_type: string;
  alcohol_content: string;
  net_contents: string;
  bottler_address: string;
  country_of_origin: string;
}

export const EMPTY_DECLARED: DeclaredFields = {
  application_id: "",
  brand_name: "",
  class_type: "",
  alcohol_content: "",
  net_contents: "",
  bottler_address: "",
  country_of_origin: "",
};


/** A row in the review queue. Deliberately without the evidence crops: the
 * table needs a verdict and a timing, not a megabyte of images per row. */
export interface QueueRow {
  id: string;
  brand: string;
  /** The COLA application number the agent declared, if any. What they
   * will search for, distinct from the row's own id. */
  application_id: string | null;
  beverage_type: string;
  outcome: "pass" | "needs_review" | "fail" | "unreadable";
  processing_ms: number | null;
  source: "seeded" | "uploaded";
  decision: { action: "approve" | "reject" | "override"; note: string; decided_by: string } | null;
}

export interface QueueListing {
  items: QueueRow[];
  counts: Record<string, number>;
  awaiting_decision: number;
}

export interface QueueItemDetail extends QueueRow {
  result: VerificationResponse | null;
  unreadable: { code: string; message: string; what_to_do: string } | null;
  has_image: boolean;
}
