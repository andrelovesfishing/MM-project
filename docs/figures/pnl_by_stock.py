"""Render the README's headline figure: python docs/figures/pnl_by_stock.py

Total P&L per stock, first version vs final setup. Numbers are pinned from
docs/inventory-control.md so the figure regenerates without the LOBSTER data.
"""
from pathlib import Path

from style import FONT, legend, money, text, write

# (cautious, generous) fill assumptions, dollars over 2012-06-21
BEFORE = {"AAPL": (-509, -411), "AMZN": (-317, -296), "GOOG": (-319, -506),
          "INTC": (-630, -1021), "MSFT": (-625, -1575)}
AFTER = {"AAPL": (289, 9), "AMZN": (-8, -189), "GOOG": (154, -169),
         "INTC": (-398, -878), "MSFT": (-232, -1748)}

W, H = 720, 410
LEFT, RIGHT, TOP, BOTTOM = 64, 20, 118, 318   # plot spans y TOP..BOTTOM
YMIN, YMAX, BAR = -1800, 500, 30


def y(v):
    return TOP + (YMAX - v) / (YMAX - YMIN) * (BOTTOM - TOP)


def column(x, v, fill):
    """A column from zero with a 3px rounded data-end."""
    r, z, e = 3, y(0), y(v)
    if abs(e - z) < r:
        return f'<rect x="{x}" y="{min(z, e)}" width="{BAR}" height="{max(abs(e - z), 1.5)}" fill="{fill}"/>'
    d = r if v > 0 else -r
    return (f'<path d="M{x},{z} V{e + d} Q{x},{e} {x + r},{e} H{x + BAR - r} '
            f'Q{x + BAR},{e} {x + BAR},{e + d} V{z} Z" fill="{fill}"/>')


def whisker(cx, lo, hi, t):
    """Thin line from the cautious value to the generous one, capped at the generous end."""
    return (f'<line x1="{cx}" x2="{cx}" y1="{y(lo)}" y2="{y(hi)}" stroke="{t["ink2"]}" stroke-width="1.5"/>'
            f'<line x1="{cx - 6}" x2="{cx + 6}" y1="{y(hi)}" y2="{y(hi)}" stroke="{t["ink2"]}" stroke-width="1.5"/>')


def render(t):
    plot = W - LEFT - RIGHT
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'role="img" font-family="{FONT}">',
         "<title>Total P&amp;L per stock over one day: first version vs final setup</title>",
         "<desc>With cautious fill assumptions the final setup loses less or makes money on all five stocks: "
         + ", ".join(f"{k} {money(BEFORE[k][0])} to {money(AFTER[k][0])}" for k in BEFORE)
         + ". With generous fill assumptions it does better on four of five; MSFT is slightly worse.</desc>",
         f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>',
         text(LEFT, 34, "Requoting faster and flattening less cut the losses on every stock", t, 16, "ink", weight=600),
         text(LEFT, 56, "Total P&amp;L for one day. Bars use cautious fill assumptions; lines run to the generous ones.", t, 12.5)]

    items, _ = legend(LEFT, 86, t)
    s += items

    for v in range(-1500, YMAX + 1, 500):
        stroke = t["base"] if v == 0 else t["grid"]
        s.append(f'<line x1="{LEFT}" x2="{LEFT + plot}" y1="{y(v)}" y2="{y(v)}" stroke="{stroke}" stroke-width="1"/>')
        s.append(text(LEFT - 8, y(v) + 4, money(v), t, 11, "muted", "end"))

    band = plot / len(BEFORE)
    for i, stock in enumerate(BEFORE):
        cx = LEFT + band * (i + 0.5)
        for x, key, (lo, hi) in ((cx - BAR - 3, "before", BEFORE[stock]), (cx + 3, "after", AFTER[stock])):
            s.append(column(x, lo, t[key]))
            s.append(whisker(x + BAR / 2, lo, hi, t))
        s.append(text(cx, BOTTOM + 22, stock, t, 12, "ink", "middle", 600))
        s.append(text(cx, BOTTOM + 40, f"{money(BEFORE[stock][0])} → {money(AFTER[stock][0])}", t, 12, "ink2", "middle"))

    s.append(text(LEFT, H - 16, "Tuned on AAPL only; the other four use the same settings. "
                                "LOBSTER sample, NASDAQ, 21 June 2012.", t, 11, "muted"))
    s.append("</svg>")
    return "\n".join(s)


if __name__ == "__main__":
    write(render, "pnl-by-stock", Path(__file__).parent)
