import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { InputScreen } from "../src/screens/InputScreen";
import { ResultsScreen } from "../src/screens/ResultsScreen";
import { EMPTY_DECLARED } from "../src/api/types";
import type { BeverageTypeOption, DeclaredFields, VerificationResponse } from "../src/api/types";

/**
 * The nine hard constraints in .claude/rules/accessibility.md, checked.
 *
 * They are acceptance criteria, not guidelines: half this team is over 50, one
 * agent still prints his emails, and the stated bar is "something my mother
 * could figure out — she's 73". Visual layout is verified in a browser; these
 * are the parts a test can actually observe.
 */

const TYPES: BeverageTypeOption[] = [
  {
    beverage_type: "spirits",
    display_name: "Spirits",
    citation: "27 CFR part 5",
    available: true,
    unavailable_reason: null,
    alcohol_content_required: true,
    alcohol_content_note: null,
  },
  {
    beverage_type: "wine",
    display_name: "Wine",
    citation: "27 CFR part 4",
    available: false,
    unavailable_reason: "Wine checking is coming next. Distilled spirits work today.",
    alcohol_content_required: false,
    alcohol_content_note: 'Wine at 14% or less may omit the percentage if it says "table wine".',
  },
];

const FILLED: DeclaredFields = {
  ...EMPTY_DECLARED,
  brand_name: "OLD TOM DISTILLERY",
  class_type: "Kentucky Straight Bourbon Whiskey",
  alcohol_content: "45% Alc./Vol. (90 Proof)",
  net_contents: "750 mL",
  bottler_address: "Bottled by Old Tom Distillery, Bardstown, Kentucky",
};

function renderInput(overrides: Partial<Parameters<typeof InputScreen>[0]> = {}) {
  const props = {
    beverageTypes: TYPES,
    beverageType: "spirits",
    onBeverageType: vi.fn(),
    declared: EMPTY_DECLARED,
    onDeclared: vi.fn(),
    image: null,
    onImage: vi.fn(),
    onSubmit: vi.fn(),
    ...overrides,
  };
  return { ...render(<InputScreen {...props} />), props };
}

const RESPONSE: VerificationResponse = {
  label_id: "app-10482",
  beverage_type: "spirits",
  overall: "needs_review",
  processing_ms: 2310,
  reviewer: null,
  error: null,
  counts: { pass: 4, needs_review: 1, fail: 1 },
  stage_ms: {},
  ocr_engine: "cloud",
  fields: [
    {
      field: "brand_name",
      display_name: "Brand name",
      declared: "Stone's Throw",
      detected: "STONE'S THROW",
      verdict: "pass",
      confidence: 1,
      reason: "Matches once formatting differences are ignored.",
      crop_url: "data:image/png;base64,AAAA",
      citation: "27 CFR 5.63(a)",
    },
    {
      field: "net_contents",
      display_name: "Net contents",
      declared: "750 mL",
      detected: null,
      verdict: "fail",
      confidence: 1,
      reason: "Net contents were not found anywhere on the label.",
      crop_url: null,
      citation: "27 CFR 5.70",
    },
    {
      field: "alcohol_content",
      display_name: "Alcohol content",
      declared: "45% Alc./Vol.",
      detected: "45.2% Alc./Vol.",
      verdict: "needs_review",
      confidence: 0.91,
      reason: "The application declares 45% and the label states 45.2%.",
      crop_url: "data:image/png;base64,AAAA",
      citation: "27 CFR 5.65",
    },
    {
      field: "government_warning",
      display_name: "Government warning",
      declared: "GOVERNMENT WARNING: (1) ...",
      detected:
        "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not " +
        "drink alcoholic beverages during pregnancy because of the risk of birth defects. " +
        "(2) Consumption of alcoholic beverages impairs your ability to drive a car or " +
        "operate machinery, and may cause health problems.",
      verdict: "needs_review",
      confidence: 1,
      reason: "Check the warning: GOVERNMENT WARNING may not be bold.",
      crop_url: "data:image/png;base64,AAAA",
      citation: "27 CFR 16.21, 16.22",
    },
  ],
  warning_checks: [
    {
      check: "text_exact",
      display_name: "Text matches 27 CFR 16.21 exactly",
      verdict: "pass",
      reason: "The wording matches 27 CFR 16.21 exactly.",
    },
    {
      check: "bold",
      display_name: "GOVERNMENT WARNING in bold",
      verdict: "needs_review",
      reason: "Stroke weight is only slightly above the body text.",
    },
  ],
};

describe("Constraint 7 — every control is queryable by role and name", () => {
  it("names the primary action in words", () => {
    renderInput();
    expect(screen.getByRole("button", { name: /check this label/i })).toBeInTheDocument();
  });

  it("gives every beverage type a text label, not an icon", () => {
    renderInput();
    expect(screen.getByRole("button", { name: /spirits/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /wine/i })).toBeInTheDocument();
  });

  it("labels every declared field", () => {
    renderInput();
    for (const label of [
      /brand name/i,
      /class or type/i,
      /alcohol content/i,
      /net contents/i,
      /bottler or producer/i,
      /country of origin/i,
    ]) {
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    }
  });

  it("labels the file input, which is visually hidden behind a button", () => {
    renderInput();
    expect(screen.getByLabelText(/label image file/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /choose file/i })).toBeInTheDocument();
  });
});

describe("Constraint 9 — a disabled control explains itself", () => {
  it("names every missing item beside the disabled button", () => {
    renderInput();
    expect(screen.getByRole("button", { name: /check this label/i })).toBeDisabled();
    const blocked = screen.getByText(/still needed before this button works/i);
    expect(blocked).toHaveTextContent("a label image");
    expect(blocked).toHaveTextContent("Brand name");
    expect(blocked).toHaveTextContent("Net contents");
  });

  it("names only what is actually missing", () => {
    renderInput({ declared: FILLED });
    const blocked = screen.getByText(/still needed before this button works/i);
    expect(blocked).toHaveTextContent("a label image");
    expect(blocked).not.toHaveTextContent("Brand name");
  });

  it("says so plainly once nothing is missing", () => {
    renderInput({
      declared: FILLED,
      image: new File(["x"], "label.png", { type: "image/png" }),
    });
    expect(screen.getByText(/everything required is filled in/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /check this label/i })).toBeEnabled();
  });

  it("explains why an unavailable beverage type is disabled", () => {
    renderInput();
    expect(screen.getByRole("button", { name: /wine/i })).toBeDisabled();
    expect(screen.getByText(/wine checking is coming next/i)).toBeInTheDocument();
  });
});

describe("Conditional rules reach the form", () => {
  it("stops requiring alcohol content when the beverage type does not", () => {
    renderInput({ beverageType: "wine", declared: FILLED });
    // Wine at 14% or less may omit it (27 CFR 4.36), so its absence must not
    // block the button.
    const blocked = screen.getByText(/still needed before this button works/i);
    expect(blocked).not.toHaveTextContent("Alcohol content");
  });
});

describe("Constraint 5 — no meaning carried by colour alone", () => {
  it("gives every verdict a word as well as a colour", () => {
    render(<ResultsScreen response={RESPONSE} reviewer="" onCheckAnother={vi.fn()} />);
    expect(screen.getAllByText("Pass").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Fail").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Needs review").length).toBeGreaterThan(0);
  });

  it("shows both the declared and the detected value without opening anything", () => {
    render(<ResultsScreen response={RESPONSE} reviewer="" onCheckAnother={vi.fn()} />);
    expect(screen.getByText("Stone's Throw")).toBeInTheDocument();
    expect(screen.getByText("STONE'S THROW")).toBeInTheDocument();
  });

  it("shows the evidence crop inline rather than behind a control", () => {
    render(<ResultsScreen response={RESPONSE} reviewer="" onCheckAnother={vi.fn()} />);
    expect(
      screen.getByRole("img", { name: /the part of the label showing brand_name/i }),
    ).toBeInTheDocument();
  });

  it("keeps the panel and says so when a field is not on the label", () => {
    render(<ResultsScreen response={RESPONSE} reviewer="" onCheckAnother={vi.fn()} />);
    expect(screen.getAllByText(/not found anywhere on the label/i).length).toBeGreaterThan(0);
  });
});

describe("Problems first", () => {
  it("puts the failing field above the passing one", () => {
    render(<ResultsScreen response={RESPONSE} reviewer="" onCheckAnother={vi.fn()} />);
    const headings = screen.getAllByRole("heading", { level: 3 }).map((node) => node.textContent);
    expect(headings.indexOf("Net contents")).toBeLessThan(headings.indexOf("Brand name"));
  });
});

describe("Override — the tool advises, the agent decides", () => {
  it("asks only about the fields it flagged", () => {
    render(<ResultsScreen response={RESPONSE} reviewer="R. Delgado" onCheckAnother={vi.fn()} />);
    // One FAIL, one NEEDS_REVIEW, and the government warning. The passing
    // field is not asked about: there is nothing to disagree with.
    expect(screen.getAllByRole("button", { name: /accept this field/i }).length).toBe(3);
    expect(screen.getAllByRole("button", { name: /it is a problem/i }).length).toBe(3);

    const passing = screen.getByRole("region", { name: /brand name/i });
    expect(within(passing).queryByRole("button", { name: /accept this field/i })).toBeNull();
  });

  it("keeps the tool's verdict visible after the agent accepts a field", async () => {
    const user = userEvent.setup();
    render(<ResultsScreen response={RESPONSE} reviewer="R. Delgado" onCheckAnother={vi.fn()} />);

    const card = screen.getByRole("region", { name: /net contents/i });
    await user.click(within(card).getByRole("button", { name: /accept this field/i }));

    expect(within(card).getByText(/you: accepted/i)).toBeInTheDocument();
    expect(within(card).getByText(/stays on the export beside your decision/i)).toBeInTheDocument();
    // The tool's own verdict is still shown, not replaced.
    expect(within(card).getAllByText("Fail").length).toBeGreaterThan(0);
  });

  it("says where the decision goes rather than claiming it is stored", async () => {
    const user = userEvent.setup();
    render(<ResultsScreen response={RESPONSE} reviewer="R. Delgado" onCheckAnother={vi.fn()} />);
    const card = screen.getByRole("region", { name: /net contents/i });
    await user.click(within(card).getByRole("button", { name: /accept this field/i }));
    expect(within(card).getByText(/R\. Delgado/)).toBeInTheDocument();
    expect(within(card).getByText(/nothing is stored after this session/i)).toBeInTheDocument();
  });

  it("lets the agent disagree with the government warning too", async () => {
    const user = userEvent.setup();
    render(<ResultsScreen response={RESPONSE} reviewer="R. Delgado" onCheckAnother={vi.fn()} />);
    const block = screen.getByRole("region", { name: /government warning/i });
    await user.click(within(block).getByRole("button", { name: /accept this field/i }));
    expect(within(block).getByText(/you: accepted/i)).toBeInTheDocument();
  });
});

describe("The government warning gets its own block", () => {
  it("lists each sub-check with its own verdict and reason", () => {
    render(<ResultsScreen response={RESPONSE} reviewer="" onCheckAnother={vi.fn()} />);
    expect(screen.getByText(/text matches 27 cfr 16.21 exactly/i)).toBeInTheDocument();
    expect(screen.getByText(/government warning in bold/i)).toBeInTheDocument();
  });

  it("says plainly when nothing in the wording differs", () => {
    render(<ResultsScreen response={RESPONSE} reviewer="" onCheckAnother={vi.fn()} />);
    expect(screen.getByText(/nothing is highlighted/i)).toBeInTheDocument();
  });
});
