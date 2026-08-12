import { describe, expect, it } from "vitest";

import { csvSafe } from "../src/screens/ResultsScreen";

/**
 * The exported results CSV is opened in Excel or Sheets, which execute any
 * cell that opens like a formula, quoted or not. The detected values are OCR
 * of whatever was printed on the artwork, so they are attacker-authored.
 */
describe("The client CSV export defuses formula cells", () => {
  it("prefixes every formula lead character", () => {
    for (const lead of ["=", "+", "-", "@", "\t", "\r"]) {
      expect(csvSafe(`${lead}HYPERLINK("http://evil")`)).toBe(
        `'${lead}HYPERLINK("http://evil")`,
      );
    }
  });

  it("leaves ordinary values alone", () => {
    expect(csvSafe("45% Alc./Vol. (90 Proof)")).toBe("45% Alc./Vol. (90 Proof)");
    expect(csvSafe("")).toBe("");
  });
});
