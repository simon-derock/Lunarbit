export interface TransactionMoney {
  subtotal: number;
  fees: number;
  discount: number;
  total: number;
}

export function deriveTransactionMoney(spendSignal: number, feeSignal: number, discountSignal: number): TransactionMoney {
  const subtotal = 248 + Math.round(spendSignal * 2.9);
  const fees = 12 + Math.round(feeSignal * .38);
  const discount = Math.round(discountSignal * .72);
  return { subtotal, fees, discount, total: subtotal + fees - discount };
}
