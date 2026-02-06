from scrape_product import fetch_page
from scrape_batteries import extract_product_urls

url = 'https://robu.in/product-category/batteries/batteries-batteries/lithium-polymer-battery-packs/single-cell-micro-lipo-battery/'
html = fetch_page(url)
if html:
    print(f'Got {len(html)} chars')
    urls = extract_product_urls(html, url)
    print(f'Found {len(urls)} URLs:')
    for u in urls:
        print(u)
else:
    print('Failed to fetch listing page')
