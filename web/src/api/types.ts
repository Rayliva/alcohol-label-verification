/** The wire format, mirroring api/app/api/models.py and docs/ui-spec.md. */

export type Verdict = "pass" | "needs_review" | "fail";
export type Outcome = Verdict | "unreadable";

export interface ErrorBody {
  code: string;
  message: string;
  what_to_do: string;
  partial_fields_shown?: boolean;
}

export interface Override {
  decision: "accepted" | "rejected";
  note: string;
  at: string;
}

export interface FieldOutcome {
  field: string;
  display_name: string;
  declared: string | null;
  detected: string | null;
  verdict: Verdict;
  confidence: number;
  reason: string;
  /** Null when the field is not on the label — there is no region to crop. */
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
  beverage_type: string;
  overall: Outcome;
  processing_ms: number;
  reviewer: string | null;
  error: ErrorBody | null;
  fields: FieldOutcome[];
  warning_checks: WarningSubCheck[];
  counts: Record<string, number>;
  stage_ms: Record<string, number>;
  ocr_engine: string | null;
}

export interface BeverageTypeOption {
  beverage_type: string;
  display_name: string;
  citation: string;
  available: boolean;
  unavailable_reason: string | null;
  alcohol_content_required: boolean;
  alcohol_content_note: string | null;
}

export interface DeclaredFields {
  application_id: string;
  reviewer: string;
  brand_name: string;
  class_type: string;
  alcohol_content: string;
  net_contents: string;
  bottler_address: string;
  country_of_origin: string;
}

export const EMPTY_DECLARED: DeclaredFields = {
  application_id: "",
  reviewer: "",
  brand_name: "",
  class_type: "",
  alcohol_content: "",
  net_contents: "",
  bottler_address: "",
  country_of_origin: "",
};
