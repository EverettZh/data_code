import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


def load_spreads(path: Path):
    spreads = defaultdict(list)
    with path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            product = row["product"]
            bid = float(row["bid_price_1"]) if row["bid_price_1"] else None
            ask = float(row["ask_price_1"]) if row["ask_price_1"] else None
            if bid is None or ask is None:
                continue
            spreads[product].append(int(round(ask - bid)))
    return spreads


def render_histogram_svg(product: str, spread_counts: Counter, output_path: Path, title: str):
    width = 1100
    height = 520
    margin_left = 80
    margin_right = 30
    margin_top = 60
    margin_bottom = 70
    chart_width = width - margin_left - margin_right
    chart_height = height - margin_top - margin_bottom

    spreads = sorted(spread_counts)
    max_count = max(spread_counts.values()) if spread_counts else 1
    total = sum(spread_counts.values()) if spread_counts else 1

    svg = []
    svg.append(
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' "
        f"viewBox='0 0 {width} {height}'>"
    )
    svg.append("<rect width='100%' height='100%' fill='white' />")
    svg.append(
        "<style>"
        "text { font-family: Arial, sans-serif; fill: #222; } "
        ".small { font-size: 12px; } "
        ".title { font-size: 22px; font-weight: bold; } "
        ".subtitle { font-size: 14px; }"
        "</style>"
    )

    svg.append(f"<text x='{width / 2}' y='30' text-anchor='middle' class='title'>{title}</text>")
    svg.append(
        f"<text x='{width / 2}' y='52' text-anchor='middle' class='subtitle'>"
        f"{product} spread frequency from top-of-book bid/ask"
        "</text>"
    )

    svg.append(
        f"<rect x='{margin_left}' y='{margin_top}' width='{chart_width}' height='{chart_height}' "
        "fill='none' stroke='#cccccc' />"
    )

    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        count = max_count * frac
        y = margin_top + chart_height - chart_height * frac
        svg.append(f"<line x1='{margin_left}' y1='{y:.2f}' x2='{margin_left + chart_width}' y2='{y:.2f}' stroke='#eeeeee' />")
        svg.append(f"<text x='{margin_left - 8}' y='{y + 4:.2f}' text-anchor='end' class='small'>{int(round(count))}</text>")

    if spreads:
        gap = 12
        bar_width = max(20, (chart_width - gap * (len(spreads) + 1)) / len(spreads))
        for idx, spread in enumerate(spreads):
            count = spread_counts[spread]
            x = margin_left + gap + idx * (bar_width + gap)
            bar_h = chart_height * (count / max_count) if max_count else 0
            y = margin_top + chart_height - bar_h
            pct = 100 * count / total if total else 0

            svg.append(f"<rect x='{x:.2f}' y='{y:.2f}' width='{bar_width:.2f}' height='{bar_h:.2f}' fill='#1f77b4' fill-opacity='0.85' />")
            svg.append(f"<text x='{x + bar_width / 2:.2f}' y='{margin_top + chart_height + 20}' text-anchor='middle' class='small'>{spread}</text>")
            svg.append(f"<text x='{x + bar_width / 2:.2f}' y='{y - 8:.2f}' text-anchor='middle' class='small'>{pct:.1f}%</text>")

    svg.append(f"<text x='{margin_left + chart_width / 2}' y='{height - 18}' text-anchor='middle' class='small'>Spread size</text>")
    svg.append("</svg>")

    output_path.write_text("\n".join(svg))


def main():
    parser = argparse.ArgumentParser(description="Create per-product spread histograms from a Round 1 prices CSV.")
    parser.add_argument("--prices", required=True, help="Path to the prices CSV file")
    parser.add_argument("--output-prefix", required=True, help="Prefix for generated SVG files")
    parser.add_argument("--title-prefix", default="Spread Histogram", help="Title prefix")
    args = parser.parse_args()

    spreads = load_spreads(Path(args.prices))
    output_prefix = Path(args.output_prefix)

    for product, values in sorted(spreads.items()):
        counts = Counter(values)
        safe_name = product.lower()
        output_path = output_prefix.parent / f"{output_prefix.name}_{safe_name}.svg"
        title = f"{args.title_prefix}: {product}"
        render_histogram_svg(product, counts, output_path, title)
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
