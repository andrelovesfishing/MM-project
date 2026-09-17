"""Shared look for the README figures: light and dark palettes and SVG helpers."""

THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
                  grid="#e1e0d9", base="#c3c2b7", before="#b4b2a9", after="#2a78d6"),
    "dark": dict(surface="#1a1a19", ink="#ffffff", ink2="#c3c2b7", muted="#898781",
                 grid="#2c2c2a", base="#4a4a46", before="#6f6e69", after="#3987e5"),
}
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"
BEFORE = "6s timer (first version)"
AFTER = "1-tick requote, flatten only past the limit"


def money(v):
    return f"{'+' if v > 0 else '-' if v < 0 else ''}${abs(v):,.0f}"


def text(x, y, s, t, size=12, color="ink2", anchor="start", weight=None):
    w = f' font-weight="{weight}"' if weight else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}"{w} fill="{t[color]}" '
            f'style="font-variant-numeric:tabular-nums">{s}</text>')


def legend(x, y, t):
    """Colored swatches beside ink text, never colored text."""
    out = []
    for label, key in ((BEFORE, "before"), (AFTER, "after")):
        out.append(f'<rect x="{x}" y="{y - 9}" width="10" height="10" rx="2" fill="{t[key]}"/>')
        out.append(text(x + 16, y, label, t))
        x += 16 + len(label) * 6.4 + 22
    return out, x


def write(render, stem, out_dir):
    for name, theme in THEMES.items():
        (out_dir / f"{stem}-{name}.svg").write_text(render(theme), encoding="utf-8")
        print(f"wrote {stem}-{name}.svg")
