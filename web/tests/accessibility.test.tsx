import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { InputScreen } from "../src/screens/InputScreen";
import { SignInScreen } from "../src/screens/SignInScreen";
import { ResultsScreen } from "../src/screens/ResultsScreen";
import { EMPTY_DECLARED } from "../src/api/types";
import type { DeclaredFields, VerificationResponse } from "../src/api/types";

/**
 * The nine hard constraints in .claude/rules/accessibility.md, checked.
 *
 * They are acceptance criteria, not guidelines: half this team is over 50, one
 * agent still prints his emails, and the stated bar is "something my mother
 * could figure out — she's 73". Visual layout is verified in a browser; these
 * are the parts a test can actually observe.
 */

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

describe("Constraint 9 — the primary action is never a silent dead end", () => {
  // The button is always enabled, so rule 9 (a disabled control explains
  // itself) is satisfied by never disabling it. What it must do instead is
  // explain itself when pressed too early.

  it("names every missing item when pressed with nothing filled in", async () => {
    const user = userEvent.setup();
    const { props } = renderInput();
    await user.click(screen.getByRole("button", { name: /check this label/i }));

    const blocked = screen.getByRole("alert");
    expect(blocked).toHaveTextContent("a label image");
    expect(blocked).toHaveTextContent("Brand name");
    expect(blocked).toHaveTextContent("Net contents");
    expect(props.onSubmit).not.toHaveBeenCalled();
  });

  it("names only what is actually missing", async () => {
    const user = userEvent.setup();
    renderInput({ declared: FILLED });
    await user.click(screen.getByRole("button", { name: /check this label/i }));

    const blocked = screen.getByRole("alert");
    expect(blocked).toHaveTextContent("a label image");
    expect(blocked).not.toHaveTextContent("Brand name");
  });

  it("submits without commentary once nothing is missing", async () => {
    const user = userEvent.setup();
    const { props } = renderInput({
      declared: FILLED,
      image: new File(["x"], "label.png", { type: "image/png" }),
    });
    await user.click(screen.getByRole("button", { name: /check this label/i }));

    expect(props.onSubmit).toHaveBeenCalledOnce();
    expect(screen.queryByRole("alert")).toBeNull();
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

describe("The Why? disclosure — detail on demand, essentials in the open", () => {
  // A deliberate deviation from rule 5, decided by the product owner on
  // 2026-08-11: the reason, confidence, citation, and decision controls sit
  // behind a per-card disclosure. What an agent acts on — verdict, declared,
  // detected, evidence — never moves behind it.

  it("reveals the reason, confidence and rule on request", async () => {
    const user = userEvent.setup();
    render(<ResultsScreen response={RESPONSE} reviewer="" onCheckAnother={vi.fn()} />);
    const card = screen.getByRole("region", { name: /net contents/i });

    expect(within(card).queryByText(/reading confidence/i)).toBeNull();
    const why = within(card).getByRole("button", { name: /why/i });
    expect(why).toHaveAttribute("aria-expanded", "false");
    await user.click(why);

    expect(why).toHaveAttribute("aria-expanded", "true");
    expect(within(card).getByText(/net contents were not found/i)).toBeInTheDocument();
    expect(within(card).getByText(/reading confidence/i)).toBeInTheDocument();
    expect(within(card).getByText(/27 CFR 5\.70/)).toBeInTheDocument();
  });
});

describe("Override — the tool advises, the agent decides", () => {
  const openWhy = async (user: ReturnType<typeof userEvent.setup>, card: HTMLElement) => {
    await user.click(within(card).getByRole("button", { name: /why/i }));
  };

  it("asks agreement on flagged fields and asks nothing on passing ones", async () => {
    const user = userEvent.setup();
    render(<ResultsScreen response={RESPONSE} reviewer="R. Delgado" onCheckAnother={vi.fn()} />);

    const flagged = screen.getByRole("region", { name: /net contents/i });
    await openWhy(user, flagged);
    expect(within(flagged).getByRole("button", { name: /accept this field/i })).toBeInTheDocument();
    expect(within(flagged).getByRole("button", { name: /it is a problem/i })).toBeInTheDocument();

    // A passing field explains itself but carries no decision controls: the
    // recorded disagreement with a clean label is the application-level
    // Reject on the review screen (decided 2026-08-11).
    const passing = screen.getByRole("region", { name: /brand name/i });
    await openWhy(user, passing);
    expect(within(passing).getByText(/matches once formatting differences/i)).toBeInTheDocument();
    expect(within(passing).queryByRole("button", { name: /accept this field/i })).toBeNull();
    expect(within(passing).queryByRole("button", { name: /flag as a problem/i })).toBeNull();
  });

  it("keeps the tool's verdict visible after the agent accepts a field", async () => {
    const user = userEvent.setup();
    render(<ResultsScreen response={RESPONSE} reviewer="R. Delgado" onCheckAnother={vi.fn()} />);

    const card = screen.getByRole("region", { name: /net contents/i });
    await openWhy(user, card);
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
    await openWhy(user, card);
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

describe("Evidence crops enlarge on request", () => {
  it("opens a dialog and closes it with Escape", async () => {
    const user = userEvent.setup();
    render(<ResultsScreen response={RESPONSE} reviewer="" onCheckAnother={vi.fn()} />);

    const crop = screen.getAllByRole("button", { name: /click to enlarge/i })[0];
    await user.click(crop);
    expect(screen.getByRole("dialog", { name: /enlarged/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /zoom in/i })).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
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

describe("Constraint 7 — everything has an accessible name", () => {
  it("names the mark rather than leaving a screen reader an empty image", () => {
    render(<SignInScreen onSignedIn={vi.fn()} />);
    expect(
      screen.getByRole("img", { name: /alcohol and tobacco tax and trade bureau/i }),
    ).toBeInTheDocument();
  });
});
