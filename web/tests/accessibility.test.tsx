import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { InputScreen } from "../src/screens/InputScreen";
import { QueueScreen } from "../src/screens/QueueScreen";
import { ReviewScreen } from "../src/screens/ReviewScreen";
import { SignInScreen } from "../src/screens/SignInScreen";
import { ResultsScreen } from "../src/screens/ResultsScreen";
import { fetchQueue, fetchQueueItem } from "../src/api/client";
import { EMPTY_DECLARED } from "../src/api/types";
import type {
  DeclaredFields,
  QueueItemDetail,
  QueueListing,
  VerificationResponse,
} from "../src/api/types";

vi.mock("../src/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/api/client")>();
  return { ...actual, fetchQueue: vi.fn(), fetchQueueItem: vi.fn() };
});

// jsdom has no layout, so the review screen's scroll reset is a no-op stub.
window.scrollTo = vi.fn();

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

  it("names the overall outcome in the headline, not just a count", () => {
    // One flagged field and one failing field must not both read "1 issue
    // found": the glyph is aria-hidden, so without a word the two summaries
    // are identical to a screen reader and differ only by colour to everyone
    // else.
    const { unmount } = render(
      <ResultsScreen response={RESPONSE} reviewer="" onCheckAnother={vi.fn()} />,
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/this label needs review/i);
    unmount();

    render(
      <ResultsScreen
        response={{ ...RESPONSE, overall: "fail" }}
        reviewer=""
        onCheckAnother={vi.fn()}
      />,
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/this label fails/i);
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

describe("The agent decides once, per application", () => {
  // Per-field accept/reject controls were removed on 2026-08-11: they asked
  // the same question up to seven times per label. The decision lives on the
  // review screen as Approve/Reject for the whole application; the cards
  // only ever advise.

  it("offers no decision controls on any field card", async () => {
    const user = userEvent.setup();
    render(<ResultsScreen response={RESPONSE} reviewer="R. Delgado" onCheckAnother={vi.fn()} />);

    const flagged = screen.getByRole("region", { name: /net contents/i });
    await user.click(within(flagged).getByRole("button", { name: /why/i }));
    expect(within(flagged).queryByRole("button", { name: /accept this field/i })).toBeNull();
    expect(within(flagged).queryByRole("button", { name: /it is a problem/i })).toBeNull();

    const warningBlock = screen.getByRole("region", { name: /government warning/i });
    expect(within(warningBlock).queryByRole("button", { name: /accept/i })).toBeNull();
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

const LISTING: QueueListing = {
  items: [
    {
      id: "001_bourbon_clean",
      brand: "OLD TOM DISTILLERY",
      beverage_type: "spirits",
      outcome: "pass",
      processing_ms: 1900,
      source: "seeded",
      decision: null,
    },
    {
      id: "014_stones_throw",
      brand: "STONE'S THROW",
      beverage_type: "spirits",
      outcome: "needs_review",
      processing_ms: 2100,
      source: "seeded",
      decision: { action: "approve", note: "", decided_by: "agent" },
    },
  ],
  counts: {},
  awaiting_decision: 1,
};

describe("The queue is searchable and filterable", () => {
  it("filters rows as the agent types, and says so when nothing matches", async () => {
    vi.mocked(fetchQueue).mockResolvedValue(LISTING);
    const user = userEvent.setup();
    render(<QueueScreen onOpen={vi.fn()} onStart={vi.fn()} reloadKey={0} />);

    expect(await screen.findByText("OLD TOM DISTILLERY")).toBeInTheDocument();
    const search = screen.getByLabelText(/search/i);
    await user.type(search, "stone");
    expect(screen.queryByText("OLD TOM DISTILLERY")).toBeNull();
    expect(screen.getByText("STONE'S THROW")).toBeInTheDocument();

    await user.clear(search);
    await user.type(search, "zzz");
    expect(screen.getByRole("status")).toHaveTextContent(/no applications match/i);
  });

  it("filters by decision state and by result, each behind a labelled dropdown", async () => {
    vi.mocked(fetchQueue).mockResolvedValue(LISTING);
    const user = userEvent.setup();
    render(<QueueScreen onOpen={vi.fn()} onStart={vi.fn()} reloadKey={0} />);
    expect(await screen.findByText("OLD TOM DISTILLERY")).toBeInTheDocument();

    const decision = screen.getByLabelText(/decision/i);
    await user.selectOptions(decision, "undecided");
    expect(screen.getByText("OLD TOM DISTILLERY")).toBeInTheDocument();
    expect(screen.queryByText("STONE'S THROW")).toBeNull();

    await user.selectOptions(decision, "all");
    await user.selectOptions(screen.getByLabelText(/result/i), "needs_review");
    expect(screen.getByText("STONE'S THROW")).toBeInTheDocument();
    expect(screen.queryByText("OLD TOM DISTILLERY")).toBeNull();
  });
});

describe("Two ways into an application", () => {
  it("starts a reviewing run at the first undecided application", async () => {
    vi.mocked(fetchQueue).mockResolvedValue(LISTING);
    const user = userEvent.setup();
    const onStart = vi.fn();
    render(<QueueScreen onOpen={vi.fn()} onStart={onStart} reloadKey={0} />);

    await user.click(await screen.findByRole("button", { name: /start reviewing/i }));
    expect(onStart).toHaveBeenCalledWith("001_bourbon_clean");
  });

  it("offers no run when everything is decided", async () => {
    const allDecided: QueueListing = {
      ...LISTING,
      awaiting_decision: 0,
      items: LISTING.items.map((row) => ({
        ...row,
        decision: { action: "approve" as const, note: "", decided_by: "agent" },
      })),
    };
    vi.mocked(fetchQueue).mockResolvedValue(allDecided);
    render(<QueueScreen onOpen={vi.fn()} onStart={vi.fn()} reloadKey={0} />);

    expect(await screen.findByText("OLD TOM DISTILLERY")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start reviewing/i })).toBeNull();
  });

  it("names the application on screen during a run, as a live region", async () => {
    const detail: QueueItemDetail = {
      ...LISTING.items[0],
      result: RESPONSE,
      unreadable: null,
      has_image: false,
    };
    vi.mocked(fetchQueueItem).mockResolvedValue(detail);
    render(<ReviewScreen id="001_bourbon_clean" queueRun onBack={vi.fn()} onDecided={vi.fn()} />);

    const banner = await screen.findByRole("status");
    expect(banner).toHaveTextContent(/now reviewing/i);
    expect(banner).toHaveTextContent("OLD TOM DISTILLERY");
  });

  it("shows no run banner when opened from a row's own Review button", async () => {
    const detail: QueueItemDetail = {
      ...LISTING.items[0],
      result: RESPONSE,
      unreadable: null,
      has_image: false,
    };
    vi.mocked(fetchQueueItem).mockResolvedValue(detail);
    render(<ReviewScreen id="001_bourbon_clean" onBack={vi.fn()} onDecided={vi.fn()} />);

    expect(await screen.findByText(/your decision/i)).toBeInTheDocument();
    expect(screen.queryByText(/now reviewing/i)).toBeNull();
  });
});

describe("The wait is reported where it was spent", () => {
  it("shows the measured time, and where the application went, on a fresh upload", () => {
    render(
      <ResultsScreen
        response={RESPONSE}
        reviewer=""
        onCheckAnother={vi.fn()}
        elapsedSeconds={4.2}
      />,
    );
    expect(screen.getByText(/checked in 4\.2 seconds/i)).toBeInTheDocument();
    expect(screen.getByText(/now in the review queue/i)).toBeInTheDocument();
  });

  it("shows no stopwatch on a recorded result opened from the queue", () => {
    render(<ResultsScreen response={RESPONSE} reviewer="" onCheckAnother={vi.fn()} embedded />);
    expect(screen.queryByText(/checked in/i)).toBeNull();
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
