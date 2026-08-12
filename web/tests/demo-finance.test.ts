import { describe, expect, it } from "vitest";

import { deriveTransactionMoney } from "@/lib/demo-finance";

describe("synthetic transaction money", () => {
  it("derives every displayed total from its scoped components", () => {
    const money = deriveTransactionMoney(91, 39, 46);

    expect(money.total).toBe(money.subtotal + money.fees - money.discount);
  });
});
