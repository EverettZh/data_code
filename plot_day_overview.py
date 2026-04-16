import argparse
import csv
from collections import defaultdict
from pathlib import Path


def load_prices(path: Path):
    data = defaultdict(lambda: {"timestamp": [], "mid_price": []})
    with path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            product = row["product"]
            mid_price = float(row["mid_price"]) if row["mid_price"] else None
            if mid_price is None:
                continue
            data[product]["timestamp"].append(int(row["timestamp"]))
            data[product]["mid_price"].append(mid_price)
    return data


def load_trade_volume(path: Path):
    data = defaultdict(list)
    with path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            product = row["symbol"]
            data[product].append((int(row["timestamp"]), float(row["quantity"])))
    return data


def moving_average(values, window):
    result = []
    queue = []
    running_sum = 0.0

    for value in values:
        queue.append(value)
        running_sum += value
        if len(queue) > window:
            running_sum -= queue.pop(0)
        result.append(running_sum / len(queue))

    return result


def bucket_average(timestamps, values, bucket_size):
    buckets = []
    current_bucket = None
    current_values = []

    for timestamp, value in zip(timestamps, values):
        bucket = (timestamp // bucket_size) * bucket_size
        if current_bucket is None or bucket != current_bucket:
            if current_values:
                buckets.append((current_bucket, sum(current_values) / len(current_values)))
            current_bucket = bucket
            current_values = [value]
        else:
            current_values.append(value)

    if current_values:
        buckets.append((current_bucket, sum(current_values) / len(current_values)))

    return buckets


def bucket_sum(pairs, bucket_size):
    totals = defaultdict(float)
    for timestamp, value in pairs:
        bucket = (timestamp // bucket_size) * bucket_size
        totals[bucket] += value
    return sorted(totals.items())


def x_map(timestamp, min_ts, max_ts, left, width):
    if max_ts == min_ts:
        return left + width / 2
    return left + (timestamp - min_ts) / (max_ts - min_ts) * width


def y_map(value, min_value, max_value, top, height):
    if max_value == min_value:
        return top + height / 2
    return top + height - (value - min_value) / (max_value - min_value) * height


def polyline(points, color, width=2):
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return f"<polyline fill='none' stroke='{color}' stroke-width='{width}' points='{pts}' />"


def draw_axes(svg, left, top, width, height, min_ts, max_ts, min_value, max_value):
    svg.append(f"<rect x='{left}' y='{top}' width='{width}' height='{height}' fill='none' stroke='#cccccc' />")

    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        y_value = min_value + (max_value - min_value) * frac
        y = y_map(y_value, min_value, max_value, top, height)
        svg.append(f"<line x1='{left}' y1='{y:.2f}' x2='{left + width}' y2='{y:.2f}' stroke='#eeeeee' />")
        svg.append(f"<text x='{left - 8}' y='{y + 4:.2f}' text-anchor='end' class='small'>{y_value:.1f}</text>")

    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        timestamp = int(min_ts + (max_ts - min_ts) * frac)
        x = x_map(timestamp, min_ts, max_ts, left, width)
        svg.append(f"<line x1='{x:.2f}' y1='{top}' x2='{x:.2f}' y2='{top + height}' stroke='#f3f3f3' />")
        svg.append(f"<text x='{x:.2f}' y='{top + height + 18}' text-anchor='middle' class='small'>{timestamp}</text>")


def render_svg(product, price_series, volume_series, output_path: Path, title: str):
    width = 1300
    margin_left = 80
    margin_right = 30
    margin_top = 45
    margin_bottom = 50
    panel_gap = 45
    top_height = 280
    bottom_height = 200
    plot_width = width - margin_left - margin_right
    total_height = margin_top + top_height + panel_gap + bottom_height + margin_bottom

    all_ts = [ts for ts, _ in price_series] + [ts for ts, _ in volume_series]
    min_ts = min(all_ts)
    max_ts = max(all_ts)

    price_values = [value for _, value in price_series]
    price_min = min(price_values)
    price_max = max(price_values)
    price_pad = max(1.0, (price_max - price_min) * 0.08)
    price_min -= price_pad
    price_max += price_pad

    volume_values = [value for _, value in volume_series] or [0.0]
    volume_min = 0.0
    volume_max = max(volume_values)
    volume_pad = max(1.0, volume_max * 0.1)
    volume_max += volume_pad

    top_y = margin_top + 30
    bottom_y = top_y + top_height + panel_gap

    svg = []
    svg.append(
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{total_height}' "
        f"viewBox='0 0 {width} {total_height}'>"
    )
    svg.append("<rect width='100%' height='100%' fill='white' />")
    svg.append(
        "<style>"
        "text { font-family: Arial, sans-serif; fill: #222; } "
        ".small { font-size: 12px; } "
        ".title { font-size: 20px; font-weight: bold; } "
        ".subtitle { font-size: 15px; font-weight: bold; }"
        "</style>"
    )
    svg.append(f"<text x='{width/2}' y='28' text-anchor='middle' class='title'>{title}</text>")

    svg.append(f"<text x='{margin_left}' y='{top_y - 10}' class='subtitle'>Average Mid Price Over The Day</text>")
    draw_axes(svg, margin_left, top_y, plot_width, top_height, min_ts, max_ts, price_min, price_max)
    price_points = [
        (x_map(ts, min_ts, max_ts, margin_left, plot_width), y_map(value, price_min, price_max, top_y, top_height))
        for ts, value in price_series
    ]
    svg.append(polyline(price_points, "#1f77b4", 2.2))

    svg.append(f"<text x='{margin_left}' y='{bottom_y - 10}' class='subtitle'>Trade Volume Over The Day</text>")
    draw_axes(svg, margin_left, bottom_y, plot_width, bottom_height, min_ts, max_ts, volume_min, volume_max)

    if volume_series:
        bar_gap = 4
        bar_width = max(2, (plot_width - bar_gap * (len(volume_series) + 1)) / len(volume_series))
        for idx, (ts, value) in enumerate(volume_series):
            x = margin_left + bar_gap + idx * (bar_width + bar_gap)
            bar_height = 0 if volume_max == 0 else bottom_height * (value / volume_max)
            y = bottom_y + bottom_height - bar_height
            svg.append(
                f"<rect x='{x:.2f}' y='{y:.2f}' width='{bar_width:.2f}' height='{bar_height:.2f}' "
                "fill='#111111' fill-opacity='0.75' />"
            )

    svg.append("</svg>")
    output_path.write_text("\n".join(svg))


def main():
    parser = argparse.ArgumentParser(description="Plot simple day overview charts for price and trade volume.")
    parser.add_argument("--prices", required=True, help="Path to prices CSV")
    parser.add_argument("--trades", required=True, help="Path to trades CSV")
    parser.add_argument("--output-prefix", required=True, help="Prefix for output SVG files")
    parser.add_argument("--title-prefix", default="Day Overview", help="Title prefix")
    parser.add_argument("--bucket-size", type=int, default=2000, help="Timestamp bucket size")
    parser.add_argument("--ma-window", type=int, default=50, help="Moving average window for mid price smoothing")
    args = parser.parse_args()

    prices = load_prices(Path(args.prices))
    trades = load_trade_volume(Path(args.trades))
    output_prefix = Path(args.output_prefix)

    for product in sorted(prices.keys()):
        smoothed_mid = moving_average(prices[product]["mid_price"], args.ma_window)
        price_series = bucket_average(prices[product]["timestamp"], smoothed_mid, args.bucket_size)
        volume_series = bucket_sum(trades[product], args.bucket_size)
        safe_name = product.lower()
        output_path = output_prefix.parent / f"{output_prefix.name}_{safe_name}.svg"
        title = f"{args.title_prefix}: {product}"
        render_svg(product, price_series, volume_series, output_path, title)
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
