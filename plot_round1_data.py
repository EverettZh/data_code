import argparse
import csv
from collections import defaultdict
from pathlib import Path


def load_price_data(path: Path):
    data = defaultdict(lambda: {"timestamp": [], "mid_price": [], "spread": []})
    with path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            product = row["product"]
            timestamp = int(row["timestamp"])
            mid_price = float(row["mid_price"]) if row["mid_price"] else None
            best_bid = float(row["bid_price_1"]) if row["bid_price_1"] else None
            best_ask = float(row["ask_price_1"]) if row["ask_price_1"] else None
            spread = best_ask - best_bid if best_bid is not None and best_ask is not None else None

            data[product]["timestamp"].append(timestamp)
            data[product]["mid_price"].append(mid_price)
            data[product]["spread"].append(spread)
    return data


def load_trade_data(path: Path):
    data = defaultdict(lambda: {"timestamp": [], "price": [], "quantity": []})
    with path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            product = row["symbol"]
            data[product]["timestamp"].append(int(row["timestamp"]))
            data[product]["price"].append(float(row["price"]))
            data[product]["quantity"].append(float(row["quantity"]))
    return data


def moving_average(values, window):
    result = []
    running_sum = 0.0
    queue = []
    for value in values:
        if value is None:
            result.append(None)
            continue
        queue.append(value)
        running_sum += value
        if len(queue) > window:
            running_sum -= queue.pop(0)
        result.append(running_sum / len(queue))
    return result


def bucket_series(timestamps, values, bucket_size):
    buckets = []
    current_ts = None
    current_values = []

    for timestamp, value in zip(timestamps, values):
        if value is None:
            continue
        bucket_ts = (timestamp // bucket_size) * bucket_size
        if current_ts is None or bucket_ts != current_ts:
            if current_values:
                buckets.append((current_ts, sum(current_values) / len(current_values)))
            current_ts = bucket_ts
            current_values = [value]
        else:
            current_values.append(value)

    if current_values:
        buckets.append((current_ts, sum(current_values) / len(current_values)))

    return buckets


def x_map(timestamp, min_ts, max_ts, left, width):
    if max_ts == min_ts:
        return left + width / 2
    return left + (timestamp - min_ts) / (max_ts - min_ts) * width


def y_map(value, min_value, max_value, top, height):
    if max_value == min_value:
        return top + height / 2
    return top + height - (value - min_value) / (max_value - min_value) * height


def svg_polyline(points, color, width=1.5, opacity=1.0):
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return (
        f"<polyline fill='none' stroke='{color}' stroke-width='{width}' "
        f"stroke-opacity='{opacity}' points='{pts}' />"
    )


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


def render_product_svg(product, price_rows, trade_rows, output_path: Path, title: str, ma_window: int, bucket_size: int):
    width = 1400
    margin_left = 80
    margin_right = 30
    margin_top = 45
    margin_bottom = 50
    panel_gap = 50
    top_panel_height = 280
    bottom_panel_height = 180
    plot_width = width - margin_left - margin_right
    total_height = margin_top + top_panel_height + panel_gap + bottom_panel_height + margin_bottom

    timestamps = price_rows["timestamp"]
    min_ts = min(timestamps)
    max_ts = max(timestamps)

    smoothed_mid = moving_average(price_rows["mid_price"], ma_window)
    bucketed_mid = bucket_series(timestamps, smoothed_mid, bucket_size)
    bucketed_spread = bucket_series(timestamps, price_rows["spread"], bucket_size)
    bucketed_trades = bucket_series(trade_rows["timestamp"], trade_rows["price"], bucket_size)

    price_values = [value for _, value in bucketed_mid] + [value for _, value in bucketed_trades]
    price_min = min(price_values)
    price_max = max(price_values)
    price_pad = max(1.0, (price_max - price_min) * 0.08)
    price_min -= price_pad
    price_max += price_pad

    spread_values = [value for _, value in bucketed_spread]
    spread_min = min(spread_values)
    spread_max = max(spread_values)
    spread_pad = max(0.5, (spread_max - spread_min) * 0.1)
    spread_min -= spread_pad
    spread_max += spread_pad

    top_panel_top = margin_top + 30
    bottom_panel_top = top_panel_top + top_panel_height + panel_gap

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
    svg.append(f"<text x='{width / 2}' y='28' text-anchor='middle' class='title'>{title}</text>")

    svg.append(f"<text x='{margin_left}' y='{top_panel_top - 10}' class='subtitle'>Smoothed Mid Price and Average Trade Price</text>")
    draw_axes(svg, margin_left, top_panel_top, plot_width, top_panel_height, min_ts, max_ts, price_min, price_max)

    mid_points = [
        (x_map(ts, min_ts, max_ts, margin_left, plot_width), y_map(value, price_min, price_max, top_panel_top, top_panel_height))
        for ts, value in bucketed_mid
    ]
    svg.append(svg_polyline(mid_points, "#1f77b4", 2.0, 1.0))

    trade_points = [
        (x_map(ts, min_ts, max_ts, margin_left, plot_width), y_map(value, price_min, price_max, top_panel_top, top_panel_height))
        for ts, value in bucketed_trades
    ]
    if trade_points:
        svg.append(svg_polyline(trade_points, "#111111", 1.4, 0.65))

    svg.append(f"<line x1='{width - 270}' y1='{top_panel_top + 12}' x2='{width - 252}' y2='{top_panel_top + 12}' stroke='#1f77b4' stroke-width='2' />")
    svg.append(f"<text x='{width - 244}' y='{top_panel_top + 16}' class='small'>smoothed mid</text>")
    svg.append(f"<line x1='{width - 140}' y1='{top_panel_top + 12}' x2='{width - 122}' y2='{top_panel_top + 12}' stroke='#111111' stroke-width='2' stroke-opacity='0.65' />")
    svg.append(f"<text x='{width - 114}' y='{top_panel_top + 16}' class='small'>avg trade price</text>")

    svg.append(f"<text x='{margin_left}' y='{bottom_panel_top - 10}' class='subtitle'>Average Spread</text>")
    draw_axes(svg, margin_left, bottom_panel_top, plot_width, bottom_panel_height, min_ts, max_ts, spread_min, spread_max)

    spread_points = [
        (x_map(ts, min_ts, max_ts, margin_left, plot_width), y_map(value, spread_min, spread_max, bottom_panel_top, bottom_panel_height))
        for ts, value in bucketed_spread
    ]
    svg.append(svg_polyline(spread_points, "#d62728", 1.8, 1.0))
    svg.append(f"<line x1='{width - 150}' y1='{bottom_panel_top + 12}' x2='{width - 132}' y2='{bottom_panel_top + 12}' stroke='#d62728' stroke-width='2' />")
    svg.append(f"<text x='{width - 124}' y='{bottom_panel_top + 16}' class='small'>avg spread</text>")

    note = f"Smoothed with {ma_window}-tick moving average, aggregated into {bucket_size}-timestamp buckets"
    svg.append(f"<text x='{margin_left}' y='{total_height - 12}' class='small'>{note}</text>")
    svg.append("</svg>")
    output_path.write_text("\n".join(svg))


def main():
    parser = argparse.ArgumentParser(description="Create simpler per-product SVG charts for Round 1 CSV files.")
    parser.add_argument("--prices", required=True, help="Path to the prices CSV file")
    parser.add_argument("--trades", required=True, help="Path to the trades CSV file")
    parser.add_argument(
        "--output-prefix",
        required=True,
        help="Prefix for generated SVG files. Product names will be appended automatically.",
    )
    parser.add_argument("--title-prefix", default="Round 1", help="Title prefix for each chart")
    parser.add_argument("--ma-window", type=int, default=25, help="Moving average window for mid prices")
    parser.add_argument("--bucket-size", type=int, default=500, help="Timestamp bucket size for averaging")
    args = parser.parse_args()

    prices_path = Path(args.prices)
    trades_path = Path(args.trades)
    output_prefix = Path(args.output_prefix)

    price_data = load_price_data(prices_path)
    trade_data = load_trade_data(trades_path)

    for product in sorted(price_data.keys()):
        safe_name = product.lower()
        output_path = output_prefix.parent / f"{output_prefix.name}_{safe_name}.svg"
        title = f"{args.title_prefix}: {product}"
        render_product_svg(
            product,
            price_data[product],
            trade_data[product],
            output_path,
            title,
            args.ma_window,
            args.bucket_size,
        )
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
