"""Render the README's P&L split figure: python docs/figures/pnl_split.py

Where AAPL's P&L came from, first version vs final setup, cautious fills. Numbers are
pinned from mm.metrics.attribution runs (experiments/inventory_control.py arms), so the
figure regenerates without the LOBSTER data. Each set of parts sums to its total.
"""
from pathlib import Path

from style import FONT, legend, money, text, write

ROWS = ["Spread earned", "Adverse selection", "Crossing cost", "Inventory drift", "Total"]
BEFORE = [661.33, -1213.15, -76.52, 118.90, -509.44]
AFTER = [1529.72, -1630.03, -126.72, 515.87, 288.84]

W, H = 720, 446
LABELS, RIGHT, TOP, BAR, GAP, ROW = 170, 44, 112, 16, 3, 52
XMIN, XMAX = -2000, 2000


def x(v):
    return LABELS + (v - XMIN) / (XMAX - XMIN) * (W - LABELS - RIGHT)


def bar(top, v, fill):
    """A bar from zero with a 3px rounded data-end."""
    r, z, e = 3, x(0), x(v)
    if abs(e - z) < 2 * r:
        return f'<rect x="{min(z, e)}" y="{top}" width="{abs(e - z)}" height="{BAR}" fill="{fill}"/>'
    d = -r if v > 0 else r
    return (f'<path d="M{z},{top} H{e + d} Q{e},{top} {e},{top + r} V{top + BAR - r} '
            f'Q{e},{top + BAR} {e + d},{top + BAR} H{z} Z" fill="{fill}"/>')


def render(t):
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'role="img" font-family="{FONT}">',
         "<title>Where AAPL's P&amp;L came from: first version vs final setup</title>",
         "<desc>" + "; ".join(f"{r}: {money(b)} before, {money(a)} after" for r, b, a in zip(ROWS, BEFORE, AFTER))
         + ".</desc>",
         f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>',
         text(24, 34, "Fresher quotes earned more than twice as much spread", t, 16, "ink", weight=600),
         text(24, 56, "Where AAPL's P&amp;L came from over one day, with cautious fill assumptions", t, 12.5)]

    items, _ = legend(24, 86, t)
    s += items

    bottom = TOP + ROW * len(ROWS)
    for v in range(-2000, XMAX + 1, 1000):
        stroke = t["base"] if v == 0 else t["grid"]
        s.append(f'<line x1="{x(v)}" x2="{x(v)}" y1="{TOP - 6}" y2="{bottom - 10}" stroke="{stroke}" stroke-width="1"/>')
        s.append(text(x(v), bottom + 6, money(v), t, 11, "muted", "middle"))

    for i, (row, b, a) in enumerate(zip(ROWS, BEFORE, AFTER)):
        top = TOP + ROW * i
        if row == "Total":
            s.append(f'<line x1="24" x2="{W - 24}" y1="{top - 9}" y2="{top - 9}" stroke="{t["base"]}" stroke-width="1"/>')
        s.append(text(24, top + BAR + 2, row, t, 12.5, "ink", weight=600 if row == "Total" else None))
        for j, (v, key) in enumerate(((b, "before"), (a, "after"))):
            by = top + j * (BAR + GAP)
            s.append(bar(by, v, t[key]))
            lx, anchor = (x(v) + 6, "start") if v > 0 else (x(v) - 6, "end")
            s.append(text(lx, by + BAR - 4, money(v), t, 11.5, "ink2", anchor))

    notes = ["Adverse selection: how far the price moved against each fill over the next 100 order book events.",
             "Crossing cost: what forced sales and buybacks paid. Inventory drift: the rest of the price move to the close."]
    for k, note in enumerate(notes):
        s.append(text(24, H - 34 + 17 * k, note, t, 11, "muted"))
    s.append("</svg>")
    return "\n".join(s)


if __name__ == "__main__":
    write(render, "pnl-split", Path(__file__).parent)
