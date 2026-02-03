#!/usr/bin/env python3
"""
Scrape motor specifications from robu.in product listing pages.
Usage: poetry run python scrape_motors.py <listing_url> <csv_filename>
Example: poetry run python scrape_motors.py "https://robu.in/product-category/ebike-parts/" motors.csv
"""

import argparse
import csv
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from scrape_product import (
    CSV_COLUMNS,
    fetch_page,
    scrape_product,
)


# URLs to exclude (services, not motors)
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


def scrape_product_safe(url: str, index: int, total: int) -> dict | None:
    """Wrapper for scrape_product with error handling for parallel execution."""
    print(f"[{index}/{total}] Processing: {url}")
    try:
        data = scrape_product(url, verbose=False)
        if data and data.get("Product Name"):
            print(f"  ✓ [{index}/{total}] {data.get('Product Name', 'Unknown')[:50]}")
            return data
        else:
            print(f"  ✗ [{index}/{total}] No data extracted")
            return None
    except Exception as e:
        print(f"  ✗ [{index}/{total}] Error: {e}")
        return None


def scrape_products_parallel(urls: list[str], max_workers: int = 5, delay: float = 0.5) -> list[dict]:
    """Scrape multiple products in parallel using ThreadPoolExecutor."""
    scraped_data = []
    total = len(urls)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(scrape_product_safe, url, i + 1, total): url 
            for i, url in enumerate(urls)
        }
        
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
                if result:
                    scraped_data.append(result)
            except Exception as e:
                print(f"  ✗ Exception processing {url}: {e}")
            
            time.sleep(delay)
    
    return scraped_data


def main():
    parser = argparse.ArgumentParser(
        description="Scrape motor specifications from robu.in"
    )
    parser.add_argument(
        "url",
        nargs="*",
        help="One or more URLs of product listing pages (e.g., https://robu.in/product-category/ebike-parts/)",
    )
    parser.add_argument(
        "csv_file",
        help="Output CSV filename (will append if exists)",
    )
    parser.add_argument(
        "--url-file",
        "-f",
        type=str,
        help="File containing URLs (one per line)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between requests in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="Number of parallel workers (default: 5)",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Use sequential scraping instead of parallel",
    )

    args = parser.parse_args()

    # Collect URLs from command line or file
    urls_to_scrape = []
    
    if args.url_file:
        # Read URLs from file
        try:
            with open(args.url_file, "r", encoding="utf-8") as f:
                urls_to_scrape = [line.strip() for line in f if line.strip()]
            print(f"Loaded {len(urls_to_scrape)} URLs from {args.url_file}")
        except FileNotFoundError:
            print(f"Error: URL file '{args.url_file}' not found!")
            sys.exit(1)
    elif args.url:
        # Use URLs from command line
        urls_to_scrape = args.url
    else:
        print("Error: Must provide either URLs or --url-file")
        parser.print_help()
        sys.exit(1)

    # Handle multiple URLs
    all_product_urls = set()
    
    for listing_url in urls_to_scrape:
        print(f"Fetching listing page: {listing_url}")
        html = fetch_page(listing_url, verbose=True)
        if not html:
            print(f"Failed to fetch listing page: {listing_url}")
            continue

        product_urls = extract_product_urls(html, listing_url)
        print(f"Found {len(product_urls)} product URLs from {listing_url}")
        all_product_urls.update(product_urls)
    
    all_product_urls = sorted(all_product_urls)
    print(f"\nTotal unique product URLs: {len(all_product_urls)}")

    if not all_product_urls:
        print("No products found!")
        sys.exit(1)

    existing_urls = get_existing_urls(args.csv_file)
    new_urls = [url for url in all_product_urls if url not in existing_urls]
    print(f"Skipping {len(all_product_urls) - len(new_urls)} already scraped products")
    print(f"Scraping {len(new_urls)} new products...")

    if args.sequential:
        scraped_data = []
        for i, url in enumerate(new_urls, 1):
            print(f"\n[{i}/{len(new_urls)}] Processing...")
            try:
                data = scrape_product(url, verbose=True)
                if data and data.get("Product Name"):
                    scraped_data.append(data)
                    print(f"  ✓ {data.get('Product Name', 'Unknown')[:50]}")
            except Exception as e:
                print(f"  ✗ Error: {e}")

            if i < len(new_urls):
                time.sleep(args.delay)
    else:
        print(f"Using {args.workers} parallel workers with {args.delay}s delay")
        scraped_data = scrape_products_parallel(new_urls, max_workers=args.workers, delay=args.delay)

    if scraped_data:
        append_to_csv(args.csv_file, scraped_data)
        print(f"\n✓ Saved {len(scraped_data)} products to {args.csv_file}")
    else:
        print("\nNo new data to save.")


if __name__ == "__main__":
    main()
