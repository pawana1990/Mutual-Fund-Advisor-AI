import { describe, expect, it } from "vitest";
import { cn, formatCurrency, formatPercent, scoreColorClass } from "./utils";

describe("formatCurrency", () => {
  it("formats a positive number as INR", () => {
    expect(formatCurrency(150000)).toBe("₹1,50,000");
  });

  it("accepts a numeric string (the API's wire format)", () => {
    expect(formatCurrency("150000.00")).toBe("₹1,50,000");
  });

  it("falls back to ₹0 for unparseable input", () => {
    expect(formatCurrency("not-a-number")).toBe("₹0");
  });
});

describe("formatPercent", () => {
  it("adds a + sign for positive values", () => {
    expect(formatPercent(12.345)).toBe("+12.35%");
  });

  it("does not add a sign for negative values", () => {
    expect(formatPercent(-8.2)).toBe("-8.20%");
  });

  it("respects the digits parameter", () => {
    expect(formatPercent(12.345, 1)).toBe("+12.3%");
  });
});

describe("scoreColorClass", () => {
  it("returns success for scores >= 75", () => {
    expect(scoreColorClass(80)).toBe("text-success");
  });

  it("returns warning for mid-range scores", () => {
    expect(scoreColorClass(60)).toBe("text-warning");
  });

  it("returns danger for low scores", () => {
    expect(scoreColorClass(30)).toBe("text-danger");
  });
});

describe("cn", () => {
  it("merges tailwind classes, letting the later one win on conflicts", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
  });

  it("drops falsy values", () => {
    expect(cn("a", false && "b", undefined, "c")).toBe("a c");
  });
});
