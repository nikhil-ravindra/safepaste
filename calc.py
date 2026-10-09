"""Local arithmetic on hidden values. Owner: Person 3.

The cloud model never sees the real numbers, so it can't add or average them. Instead we ask it
to write the calculation with placeholders, e.g.

    [[calc:rupees: (⟦AMOUNT_1⟧ + ⟦AMOUNT_2⟧) / 2]]

and we evaluate it here on the laptop with the real values. Units: rupees, percent or number.
Only + - * / ( ) and numbers are allowed (parsed with ast, never eval).
"""
from __future__ import annotations

import ast
import operator
import re

CALC = re.compile(r"\[\[calc:\s*(rupees|percent|number)\s*:\s*(.+?)\]\]", re.IGNORECASE | re.DOTALL)
PLACEHOLDER = re.compile(r"⟦[A-Z]+_\d+⟧")
UNITS = {"cr": 1e7, "crore": 1e7, "crores": 1e7, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "l": 1e5,
         "k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9}
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def parse_number(text: str) -> float | None:
    """'₹4.2 Cr' -> 42000000.0, '₹14,50,000' -> 1450000.0, '18%' -> 18.0. None if it isn't a number."""
    m = re.search(r"(-?\d[\d,]*(?:\.\d+)?)\s*([A-Za-z]+)?", str(text))
    if not m:
        return None
    value = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "").lower()
    return value * UNITS.get(unit, 1.0)


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval(node.operand)
    raise ValueError("only + - * / and brackets are allowed")


def _indian(n: float) -> str:
    s = f"{abs(round(n)):d}"
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = ",".join([head[max(i - 2, 0):i] for i in range(len(head), 0, -2)][::-1])
        s = f"{head},{tail}"
    return ("-" if n < 0 else "") + s


def format_value(value: float, unit: str) -> str:
    unit = unit.lower()
    if unit == "percent":
        return f"{value:.1f}%"
    if unit == "rupees":
        if abs(value) >= 1e7:
            return f"₹{value / 1e7:.2f} Cr"
        if abs(value) >= 1e5:
            return f"₹{value / 1e5:.2f} lakh"
        return f"₹{_indian(value)}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def resolve(answer: str, mapping: dict) -> tuple[str, list[dict]]:
    """Replace every [[calc:...]] in the cloud answer with the result computed from real values.

    Returns (new_answer, steps) where each step is {"formula", "result", "ok"} for the UI.
    The formula keeps placeholders, so the UI can show it without revealing inputs twice.
    """
    steps: list[dict] = []

    def swap(m: re.Match) -> str:
        unit, formula = m.group(1), m.group(2).strip()
        expr, ok = formula, True
        for ph in set(PLACEHOLDER.findall(formula)):
            number = parse_number(mapping.get(ph, "")) if ph in mapping else None
            if number is None:
                ok = False
                break
            expr = expr.replace(ph, repr(number))
        if ok:
            try:
                result = format_value(_eval(ast.parse(expr, mode="eval")), unit)
            except (ValueError, SyntaxError, ZeroDivisionError, TypeError):
                ok = False
        if not ok:
            result = "(skipped: not a number)"
        steps.append({"formula": formula, "result": result, "ok": ok})
        return result

    return CALC.sub(swap, answer), steps


if __name__ == "__main__":
    mp = {"⟦AMOUNT_1⟧": "₹4.2 Cr", "⟦AMOUNT_2⟧": "₹2.1 Cr", "⟦AMOUNT_3⟧": "₹95,00,000"}
    print(resolve("Average deal: [[calc:rupees: (⟦AMOUNT_1⟧ + ⟦AMOUNT_2⟧ + ⟦AMOUNT_3⟧) / 3]]. "
                  "Growth: [[calc:percent: (⟦AMOUNT_1⟧ - ⟦AMOUNT_2⟧) / ⟦AMOUNT_2⟧ * 100]].", mp))
