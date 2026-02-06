#!/usr/bin/env python3
"""
Scrape battery specifications from robu.in product listing pages.
Usage: poetry run python scrape_batteries.py <listing_url> <csv_filename>
Example: poetry run python scrape_batteries.py "https://robu.in/product-category/batteries/" batteries.csv
"""

import argparse
import csv
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from scrape_battery import (
    CSV_COLUMNS,
    fetch_page,
    scrape_battery,
)


# URLs to exclude (services, not batteries)
EXCLUDED_URLS = {
    "https://robu.in/product/metal-laser-cutting",
    "https://robu.in/product/3d-printing-service",
    "https://robu.in/product/online-laser-cutting-service",
    "https://robu.in/product/sla-3d-printing",
    "https://robu.in/product/online-pcb-manufacturing-service",
}


def extract_product_urls(html: str, base_url: str) -> list[str]:
    """Extract all product URLs from a listing page."""
    soup = BeautifulSoup(html, "lxml")
    product_urls = set()

    # Strategy 1: Look for the main product grid ul
    product_grid = soup.find("ul", class_=lambda c: c and "products" in c)
    if product_grid:
        links = product_grid.find_all("a", href=True)
        for link in links:
            href = link["href"]
            if "robu.in/product/" in href and "/product-category/" not in href:
                clean_url = href.rstrip("/")
                if clean_url not in EXCLUDED_URLS:
                    product_urls.add(clean_url)

    # Strategy 2: Find all links matching product pattern (fallback)
    all_links = soup.find_all("a", href=True)
    for link in all_links:
        href = link["href"]
        # Match product URLs but exclude category pages
        if re.match(r"https?://robu\.in/product/[^/]+/?$", href):
            clean_url = href.rstrip("/")
            if clean_url not in EXCLUDED_URLS:
                product_urls.add(clean_url)

    return sorted(product_urls)


def append_to_csv(csv_path: str, data: list[dict]):
    """Append data to CSV file, creating if it doesn't exist."""
    file_exists = os.path.exists(csv_path)

    has_content = False
    if file_exists:
        with open(csv_path, "r", encoding="utf-8") as f:
            has_content = bool(f.read().strip())

    mode = "a" if file_exists and has_content else "w"

    with open(csv_path, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)

        if mode == "w" or not has_content:
            writer.writeheader()

        for row in data:
            row_data = {col: row.get(col, "") for col in CSV_COLUMNS}
            writer.writerow(row_data)


def get_existing_urls(csv_path: str) -> set:
    """Get URLs already in the CSV to avoid duplicates."""
    if not os.path.exists(csv_path):
        return set()

    urls = set()
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "URL" in row:
                    urls.add(row["URL"])
    except Exception:
        pass
    return urls


def scrape_products_parallel(urls: list[str], max_workers: int = 4, delay: float = 1.0) -> list[dict]:
    """Scrape multiple products in parallel."""
    results = []
    total = len(urls)

    def scrape_with_delay(url: str, index: int):
        if delay > 0:
            time.sleep(delay * (index % max_workers))
        return scrape_battery(url)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(scrape_with_delay, url, i): (url, i)
            for i, url in enumerate(urls)
        }

        for future in as_completed(future_to_url):
            url, index = future_to_url[future]
            print(f"[{index + 1}/{total}] Processing: {url}")
            try:
                result = future.result()
                if result:
                    results.append(result)
                    print(f"  ✓ [{index + 1}/{total}] {result.get('Product Name', 'Unknown')[:50]}")
                else:
                    print(f"  ✗ [{index + 1}/{total}] No data extracted")
            except Exception as e:
                print(f"  ✗ [{index + 1}/{total}] Error: {e}")

    return results


def scrape_products_sequential(urls: list[str], delay: float = 1.0) -> list[dict]:
    """Scrape products one by one (slower but more reliable)."""
    results = []
    total = len(urls)

    for i, url in enumerate(urls):
        print(f"[{i + 1}/{total}] Processing: {url}")
        try:
            result = scrape_battery(url)
            if result:
                results.append(result)
                print(f"  ✓ {result.get('Product Name', 'Unknown')[:50]}")
            else:
                print(f"  ✗ No data extracted")
        except Exception as e:
            print(f"  ✗ Error: {e}")

        if delay > 0 and i < total - 1:
            time.sleep(delay)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Scrape battery specifications from robu.in listing pages"
    )
    parser.add_argument(
        "urls",
        nargs="*",
        help="URL(s) of the product listing page(s) to scrape"
    )
    parser.add_argument(
        "csv_file",
        help="Path to the output CSV file"
    )
    parser.add_argument(
        "--url-file", "-f",
        help="File containing URLs (one per line)"
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)"
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--sequential", "-s",
        action="store_true",
        help="Use sequential scraping instead of parallel"
    )

    args = parser.parse_args()

    # Collect URLs from arguments and file
    listing_urls = list(args.urls) if args.urls else []

    if args.url_file:
        try:
            with open(args.url_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        listing_urls.append(line)
            print(f"Loaded {len(listing_urls)} URLs from {args.url_file}")
        except FileNotFoundError:
            print(f"Error: URL file not found: {args.url_file}", file=sys.stderr)
            sys.exit(1)

    if not listing_urls:
        print("Error: No listing URLs provided", file=sys.stderr)
        sys.exit(1)

    # Collect all product URLs from listing pages
    all_product_urls = set()

    for listing_url in listing_urls:
        print(f"Fetching listing page: {listing_url}")
        html = fetch_page(listing_url)
        if html:
            product_urls = extract_product_urls(html, listing_url)
            print(f"Found {len(product_urls)} product URLs from {listing_url}")
            all_product_urls.update(product_urls)
        else:
            print(f"Failed to fetch listing page: {listing_url}")

    if not all_product_urls:
        print("No product URLs found on the listing pages.")
        sys.exit(1)

    product_urls = sorted(all_product_urls)
    print(f"\nTotal unique product URLs: {len(product_urls)}")

    # Skip already scraped products
    existing_urls = get_existing_urls(args.csv_file)
    new_urls = [url for url in product_urls if url not in existing_urls]
    print(f"Skipping {len(existing_urls)} already scraped products")
    print(f"Scraping {len(new_urls)} new products...")

    if not new_urls:
        print("No new products to scrape.")
        return

    # Scrape products
    if args.sequential:
        print(f"Using sequential scraping with {args.delay}s delay")
        results = scrape_products_sequential(new_urls, delay=args.delay)
    else:
        print(f"Using {args.workers} parallel workers with {args.delay}s delay")
        results = scrape_products_parallel(new_urls, max_workers=args.workers, delay=args.delay)

    # Save results
    if results:
        append_to_csv(args.csv_file, results)
        print(f"\n✓ Saved {len(results)} products to {args.csv_file}")
    else:
        print("\n✗ No products scraped successfully")


if __name__ == "__main__":
    main()
