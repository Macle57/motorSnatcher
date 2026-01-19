This is a python project running on poetry and pyenv, you can directly run the .py or set up the env properly.

If you have poetry and pyenv installed, u may skip these steps
I prefer choco/scoop to set these up since its easy and can be removed in future easily as well

To install them, open admin terminal and run the following:

```bash
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

Set-ExecutionPolicy RemoteSigned -scope CurrentUser
Invoke-Expression (New-Object System.Net.WebClient).DownloadString('https://get.scoop.sh')

```

Restart terminal and open as admin again

```bash
choco install pyenv-win

scoop install poetry
```

Restart terminal to ensure pyenv is in PATH, then set up Python environment:

```bash
# Install Python 3.10 using pyenv
pyenv install 3.10
# Install project dependencies
poetry install
```

## Usage

### Scrape multiple products from listing pages

```bash
# Single listing page
poetry run python scrape_motors.py "https://robu.in/product-category/ebike-parts/e-bike-parts/e-bike-motors/" motors.csv

# Multiple listing pages
poetry run python scrape_motors.py \
  "https://robu.in/product-category/ebike-parts/e-bike-parts/e-bike-motors/" \
  "https://robu.in/product-category/ebike-parts/e-mini-tricycle-parts/e-mini-tricycle-motors/" \
  motors.csv

# With custom options
poetry run python scrape_motors.py "https://robu.in/product-category/ebike-parts/e-bike-parts/e-bike-motors/" motors.csv --workers 8 --delay 0.3

# Scrape all URLs from a file
$urls = Get-Content urls.txt | Where-Object { $_.Trim() -ne "" }
poetry run python scrape_motors.py $urls motors_all.csv --workers 8

# Sequential mode (slower but more reliable)
poetry run python scrape_motors.py "https://robu.in/product-category/ebike-parts/e-bike-parts/e-bike-motors/" motors.csv --sequential --delay 2
```

### To debug
Scrape a single product

```bash
# Basic usage - formatted output
poetry run python scrape_product.py "https://robu.in/product/my6812-100w-dc-motor"

# JSON output
poetry run python scrape_product.py "https://robu.in/product/my6812-100w-dc-motor" --json

# Verbose mode
poetry run python scrape_product.py "https://robu.in/product/my6812-100w-dc-motor" --verbose
```
It prints what its able to get from that product, anything which is shown here will shown in csv as well.

### Options

**scrape_motors.py**:
- `--workers N`: Number of parallel workers (default: 5)
- `--delay N`: Delay between requests in seconds (default: 0.5)
- `--sequential`: Use sequential scraping instead of parallel

**scrape_product.py**:
- `--json`: Output as JSON instead of formatted text
- `--verbose` or `-v`: Show verbose output

