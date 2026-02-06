#!/usr/bin/env python3
"""
Scrape specifications from a single robu.in battery product page.
Usage: poetry run python scrape_battery.py <product_url>
Example: poetry run python scrape_battery.py "https://robu.in/product/3-7v-500mah-lipo-battery-wly752530"
"""

import argparse
import json
import re
import sys

from bs4 import BeautifulSoup

# Import shared functions from scrape_product
from scrape_product import (
    fetch_page,
    clean_number,
    clean_value,
    extract_price,
    extract_product_name,
    extract_stock_status,
    extract_general_info,
    extract_specification_table,
)


# CSV columns for battery specifications
CSV_COLUMNS = [
    "Product Name",
    "URL",
    "Stock Status",
    "Price (INR)",
    "Model No.",
    "Nominal Voltage (V)",
    "Capacity (mAh)",
    "Continuous Charge Current",
    "Continuous Discharge Current",
    "Max Charge Rate",
    "Max Discharge Rate",
    "Connector Type",
    "Life Cycles",
    "Application",
    "Thickness (mm)",
    "Breadth (mm)",
    "Length (mm)",
    "Dimensions",
    "Weight (g)",
    "Shipping Weight (kg)",
    "Shipping Dimensions (cm)",
    "Additional Specs",
]


def scrape_battery(url: str, verbose: bool = False) -> dict | None:
    """Scrape battery specifications from a product page."""
    clean_url = url.rstrip("/")
    spec_url = f"{clean_url}/#tab-specification"
    
    if verbose:
        print(f"Fetching: {clean_url}")

    html = fetch_page(spec_url, verbose=verbose)
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")

    product_name = extract_product_name(soup)
    if not product_name:
        return None

    price = extract_price(soup)
    stock_status = extract_stock_status(soup)

    # Clean URL
    clean_url = url.rstrip("/")

    # Extract specs from different sources
    spec_table = extract_specification_table(soup)
    general_info = extract_general_info(soup)

    # Merge all specs
    all_specs = {}
    all_specs.update(general_info)
    all_specs.update(spec_table)

    def get_spec(*keys, clean: bool = True, exact: bool = False) -> str:
        """Get a spec value by trying multiple possible keys."""
        for key in keys:
            key_lower = key.lower()
            # Try exact match first
            for spec_key, value in all_specs.items():
                if exact and spec_key == key_lower:
                    return clean_number(value) if clean else clean_value(value)
                elif not exact and key_lower in spec_key:
                    return clean_number(value) if clean else clean_value(value)
        return ""

    def get_weight():
        """Get weight in grams."""
        for spec_key, value in all_specs.items():
            key_lower = spec_key.lower()
            if "weight" in key_lower and "shipping" not in key_lower:
                # Return the value with units
                num = clean_number(value)
                if num:
                    return num
        return ""

    def get_dimension(dim_type: str) -> str:
        """Get a specific dimension (thickness/breadth/length)."""
        for spec_key, value in all_specs.items():
            if dim_type in spec_key.lower():
                return clean_number(value)
        return ""

    def get_full_dimensions() -> str:
        """Try to get full dimensions string."""
        for spec_key, value in all_specs.items():
            if "dimension" in spec_key.lower() and "shipping" not in spec_key.lower():
                # Skip individual dimensions
                if any(x in spec_key.lower() for x in ["thickness", "breadth", "length", "width", "height"]):
                    continue
                return clean_value(value)
        # Build from individual dimensions
        t = get_dimension("thickness")
        b = get_dimension("breadth") or get_dimension("width")
        l = get_dimension("length")
        if t and b and l:
            return f"{t} × {b} × {l} mm"
        return ""

    result = {
        "Product Name": product_name,
        "URL": clean_url,
        "Stock Status": stock_status,
        "Price (INR)": price,
        "Model No.": get_spec("model no", "model", clean=False),
        "Nominal Voltage (V)": get_spec("nominal voltage", "voltage"),
        "Capacity (mAh)": get_spec("nominal capacity", "capacity"),
        "Continuous Charge Current": get_spec("continuous charge current", "charge current", clean=False),
        "Continuous Discharge Current": get_spec("continuous dischg", "continuous discharge", "discharge current", clean=False),
        "Max Charge Rate": get_spec("max. charge rate", "max charge rate", "max. charge", clean=False),
        "Max Discharge Rate": get_spec("max discharge rate", "max. discharge", "max dischg", clean=False),
        "Connector Type": get_spec("connector type", "connector", clean=False),
        "Life Cycles": get_spec("life cycle", "cycle", clean=False),
        "Application": get_spec("application", clean=False),
        "Thickness (mm)": get_dimension("thickness"),
        "Breadth (mm)": get_dimension("breadth") or get_dimension("width"),
        "Length (mm)": get_dimension("length"),
        "Dimensions": get_full_dimensions(),
        "Weight (g)": get_weight(),
        "Shipping Weight (kg)": get_spec("shipping weight", clean=False),
        "Shipping Dimensions (cm)": get_spec("shipping dimensions", clean=False),
        "Additional Specs": get_spec("additional spec", clean=False),
    }

    return result


def print_battery_specs(specs: dict) -> None:
    """Print battery specifications in a readable format."""
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
        description="Scrape battery specifications from a robu.in product page"
    )
    parser.add_argument("url", help="URL of the product page to scrape")
    parser.add_argument(
        "--json", action="store_true", help="Output as JSON instead of formatted text"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show verbose output"
    )

    args = parser.parse_args()

    specs = scrape_battery(args.url, verbose=args.verbose)

    if not specs:
        print("Failed to scrape product specifications.", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(specs, indent=2, ensure_ascii=False))
    else:
        print_battery_specs(specs)


if __name__ == "__main__":
    main()
