#!/usr/bin/env python3
"""
Scrape specifications from a single robu.in product page.
Usage: poetry run python scrape_product.py <product_url>
Example: poetry run python scrape_product.py "https://robu.in/product/my6812-100w-dc-motor"
"""

import argparse
import re
import sys
import time

import cloudscraper
from bs4 import BeautifulSoup


# Headers to mimic a browser request
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# CSV columns for motor specifications
CSV_COLUMNS = [
    "Product Name",
    "URL",
    "Stock Status",
    "Price (INR)",
    "Voltage (V)",
    "Power (W)",
    "Rated Current (A)",
    "No Load Current (A)",
    "Rated Torque (kg-cm)",
    "Stall Torque (kg-cm)",
    "RPM",
    "Efficiency (%)",
    "Weight (kg)",
    "Shipping Weight (kg)",
    "Shipping Dimensions (cm)",
    "Shaft Diameter (mm)",
    "Motor Type",
    "Model No.",
    "Gearbox",
    "Dimensions",
    "Cable Length (cm)",
]


def fetch_page(url: str, retries: int = 3, verbose: bool = False) -> str | None:
    """Fetch a page with retries using cloudscraper to bypass protection."""
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'mobile': False
        }
    )
    
    for attempt in range(retries):
        try:
            response = scraper.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            if verbose:
                print(f"  Attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
    return None


def clean_number(text: str) -> str:
    """Extract numeric value from text."""
    if not text:
        return ""
    text = text.strip()
    match = re.search(r"[<>~]?\s*([\d.]+)", text)
    return match.group(1) if match else text


def clean_value(text: str) -> str:
    """Clean value by removing extra whitespace but keeping units."""
    if not text:
        return ""
    # Replace multiple spaces with single space, strip leading/trailing
    return re.sub(r'\s+', ' ', text.strip())


def extract_price(soup: BeautifulSoup) -> str:
    """Extract product price."""
    price_elem = soup.find("p", class_="price")
    if price_elem:
        ins = price_elem.find("ins")
        if ins:
            amount = ins.find("bdi")
        else:
            amount = price_elem.find("bdi")
        if amount:
            text = amount.get_text(strip=True)
            match = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
            if match:
                return match.group()
    return ""


def extract_product_name(soup: BeautifulSoup) -> str:
    """Extract product name."""
    title = soup.find("h1", class_=lambda c: c and "product_title" in c)
    if title:
        return title.get_text(strip=True)
    title = soup.find("title")
    if title:
        return title.get_text(strip=True).split(" - ")[0].strip()
    return ""


def extract_stock_status(soup: BeautifulSoup) -> str:
    """Extract stock availability status."""
    # Look for availability div
    availability = soup.find("div", class_="availability")
    if availability:
        stock_span = availability.find("span", class_="electro-stock-availability")
        if stock_span:
            stock_p = stock_span.find("p", class_="stock")
            if stock_p:
                text = stock_p.get_text(strip=True)
                # Normalize status
                text_lower = text.lower()
                if "out of stock" in text_lower:
                    return "Out of Stock"
                elif "in stock" in text_lower:
                    return "In Stock"
                elif "low" in text_lower or "order now" in text_lower:
                    return "Low Stock"
                return text
    
    # Fallback: search page text for stock status
    page_text = soup.get_text().lower()
    if "out of stock" in page_text:
        return "Out of Stock"
    elif "in stock" in page_text:
        return "In Stock"
    elif "low stock" in page_text or "low in stock" in page_text:
        return "Low Stock"
    
    return "Unknown"


def extract_general_info(soup: BeautifulSoup) -> dict:
    """Extract info from the general info div (ordered list)."""
    specs = {}

    # Find the main product content area, but exclude related products sections
    # Look for woocommerce-product-details__short-description or similar
    description_div = soup.find("div", class_="woocommerce-product-details__short-description")
    if not description_div:
        description_div = soup.find("div", id="tab-description")
    if not description_div:
        # Try the main summary area
        summary = soup.find("div", class_="summary")
        if summary:
            description_div = summary

    all_lists = []
    if description_div:
        all_lists.extend(description_div.find_all(["ol", "ul"]))

    # Also check for the product single entry summary
    entry_summary = soup.find("div", class_="entry-summary")
    if entry_summary:
        # Be careful to only get lists in the actual product description, not related products
        for ol in entry_summary.find_all(["ol", "ul"], recursive=False):
            all_lists.append(ol)
        # Also check nested divs but not too deep
        for child_div in entry_summary.find_all("div", recursive=False):
            all_lists.extend(child_div.find_all(["ol", "ul"], recursive=False))

    for ol in all_lists:
        items = ol.find_all("li")
        for item in items:
            text = item.get_text(strip=True)
            if ":" in text:
                parts = text.split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip().lower()
                    value = parts[1].strip()
                    # Skip if key is too long (likely garbage)
                    if len(key) < 50:
                        specs[key] = value

    return specs


def extract_specification_table(soup: BeautifulSoup) -> dict:
    """Extract specs from the specification table."""
    specs = {}

    spec_table = soup.find("table", id=lambda x: x and "specification" in x.lower() if x else False)
    if not spec_table:
        spec_div = soup.find("div", id="tab-specification")
        if spec_div:
            spec_table = spec_div.find("table")

    if not spec_table:
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) > 3:
                spec_table = table
                break

    if spec_table:
        rows = spec_table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True).lower()
                value = cells[1].get_text(strip=True)
                # Clean up key - remove trailing colons and extra spaces
                key = key.rstrip(":").strip()
                if key and value:
                    specs[key] = value

    # Also look for product attributes table (for shipping weight, dimensions, etc.)
    product_attrs = soup.find_all("tr", class_=lambda c: c and "woocommerce-product-attributes-item" in c)
    for row in product_attrs:
        th = row.find("th", class_="woocommerce-product-attributes-item__label")
        td = row.find("td", class_="woocommerce-product-attributes-item__value")
        if th and td:
            key = th.get_text(strip=True).lower()
            value = td.get_text(strip=True)
            if key and value:
                specs[key] = value

    return specs


def extract_via_regex(html: str) -> dict:
    """Extract specifications using regex patterns on entire page."""
    specs = {}
    text = html.lower()

    patterns = {
        "weight_kg": [
            r"weight\s*[:\(]?\s*(\d+\.?\d*)\s*kg",
            r"(\d+\.?\d*)\s*kg\s*weight",
        ],
        "shipping_weight": [
            r"shipping\s*weight\s*[:\s]*(\d+\.?\d*)\s*kg",
        ],
        "shipping_dimensions": [
            r"shipping\s*dimensions?\s*[:\s]*([\d.]+\s*[×x]\s*[\d.]+\s*[×x]\s*[\d.]+)\s*cm",
        ],
        # Note: Voltage/Power/RPM regex removed - too many false positives from related products
        # Rely on spec_table extraction instead
        "rated_current": [
            r"rated?\s*current\s*[:\(]?\s*[<>]?\s*(\d+\.?\d*)\s*a",
        ],
        "no_load_current": [
            r"no\s*load\s*current\s*[:\(]?\s*[<>]?\s*(\d+\.?\d*)\s*a",
        ],
        "rated_torque": [
            r"rated?\s*torque\s*[:\(]?\s*(\d+\.?\d*)\s*(?:kg[.-]?cm|n\.?m)",
        ],
        "stall_torque": [
            r"stall\s*torque\s*[:\(]?\s*(\d+\.?\d*)\s*(?:kg[.-]?cm|n\.?m)",
        ],
        "efficiency": [
            r"efficiency\s*[:\(]?\s*[>]?\s*(\d+)",
        ],
        "shaft_diameter": [
            r"shaft\s*diameter\s*[:\(]?\s*(\d+\.?\d*)\s*mm",
        ],
    }

    for key, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, text)
            if match:
                specs[key] = match.group(1)
                break

    return specs


def scrape_product(url: str, verbose: bool = False) -> dict:
    """Scrape specifications from a single product page."""
    clean_url = url.rstrip("/")
    spec_url = f"{clean_url}/#tab-specification"

    if verbose:
        print(f"Fetching: {clean_url}")
    
    html = fetch_page(spec_url, verbose=verbose)
    if not html:
        if verbose:
            print(f"Failed to fetch: {spec_url}")
        return {}

    soup = BeautifulSoup(html, "lxml")

    product_name = extract_product_name(soup)
    stock_status = extract_stock_status(soup)
    price = extract_price(soup)
    general_info = extract_general_info(soup)
    spec_table = extract_specification_table(soup)
    regex_specs = extract_via_regex(html)

    # Merge all sources (spec_table takes priority, then general_info, then regex)
    all_specs = {**regex_specs, **general_info, **spec_table}

    def get_spec(*keys, clean=True, exact=False):
        """Get first matching key from specs.
        
        Args:
            *keys: Keys to search for (checked in order, returns first match)
            clean: If True, extract only numbers. If False, keep full value with units
            exact: If True, require exact match
        """
        for key in keys:
            key_lower = key.lower()
            # First try exact match
            for spec_key, value in all_specs.items():
                spec_key_lower = spec_key.lower()
                if key_lower == spec_key_lower and value:
                    if clean:
                        return clean_number(value)
                    return clean_value(value)
            
            # If no exact match and not requiring exact, try substring match
            if not exact:
                for spec_key, value in all_specs.items():
                    spec_key_lower = spec_key.lower()
                    if (key_lower in spec_key_lower or spec_key_lower in key_lower) and value:
                        if clean:
                            return clean_number(value)
                        return clean_value(value)
        return ""

    # Helper to get spec with unit-aware extraction
    def get_no_load_current():
        """Get no-load current, handling mA vs A."""
        # First try to find mA value
        for spec_key, value in all_specs.items():
            if "no" in spec_key.lower() and "load" in spec_key.lower() and "current" in spec_key.lower():
                if "ma" in spec_key.lower() or "ma" in value.lower():
                    # Convert mA to A
                    num = clean_number(value)
                    if num:
                        try:
                            return str(float(num) / 1000)
                        except ValueError:
                            pass
                else:
                    return clean_number(value)
        return ""

    def get_efficiency():
        """Get efficiency, handling ratio vs percentage."""
        val = get_spec("efficiency")
        if val:
            try:
                num = float(val)
                if num < 1:  # It's a ratio, convert to percentage
                    return str(int(num * 100))
                return val
            except ValueError:
                return val
        return ""

    def get_weight():
        """Get weight, handling grams vs kg."""
        # First try weight in kg
        for spec_key, value in all_specs.items():
            if "weight" in spec_key.lower() and "shipping" not in spec_key.lower():
                if "(kg)" in spec_key.lower() or "kg" in value.lower():
                    return clean_number(value)
                if "(g)" in spec_key.lower():
                    # Convert grams to kg
                    num = clean_number(value)
                    if num:
                        try:
                            return str(float(num) / 1000)
                        except ValueError:
                            pass
        return get_spec("weight (kg)", "weight:", "weight_kg", exact=True)

    result = {
        "Product Name": product_name,
        "URL": clean_url,
        "Stock Status": stock_status,
        "Price (INR)": price,
        "Voltage (V)": get_spec("rated voltage", "operating voltage", "voltage", "vdc"),
        "Power (W)": get_spec("operating power", "rated power", "power"),
        "Rated Current (A)": get_spec("rated current (a)", "rated current", "rate current"),
        "No Load Current (A)": get_no_load_current(),
        "Rated Torque (kg-cm)": get_spec("rated torque", "rate torque"),
        "Stall Torque (kg-cm)": get_spec("stall torque"),
        "RPM": get_spec("rated speed (rpm)", "rated speed", "speed (rpm)", "rpm"),
        "Efficiency (%)": get_efficiency(),
        "Weight (kg)": get_weight(),
        "Shipping Weight (kg)": get_spec("shipping weight", "shipping_weight", clean=False),
        "Shipping Dimensions (cm)": get_spec("shipping dimensions", "shipping_dimensions", clean=False),
        "Shaft Diameter (mm)": get_spec("shaft diameter", "shaft"),
        "Motor Type": get_spec("motor type", "item type", "brushed", "brushless", clean=False),
        "Model No.": get_spec("model", "model no", clean=False),
        "Gearbox": get_spec("gearbox", "gear box", "gear", clean=False),
        "Dimensions": get_spec("dimensions", "dimension", "lxd", clean=False),
        "Cable Length (cm)": get_spec("cable length", "cable"),
    }

    return result


def print_product_specs(specs: dict) -> None:
    """Print product specifications in a readable format."""
    if not specs:
        print("No specifications found.")
        return

    print("=" * 60)
    print(f"Product: {specs.get('Product Name', 'Unknown')}")
    print("=" * 60)
    
    for key, value in specs.items():
        if value and key != "Product Name":
            print(f"{key}: {value}")
    
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Scrape specifications from a single robu.in product page"
    )
    parser.add_argument(
        "url",
        help="Product URL (e.g., https://robu.in/product/my6812-100w-dc-motor)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of formatted text",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose output",
    )

    args = parser.parse_args()

    specs = scrape_product(args.url, verbose=args.verbose)

    if args.json:
        import json
        print(json.dumps(specs, indent=2))
    else:
        print_product_specs(specs)


if __name__ == "__main__":
    main()
