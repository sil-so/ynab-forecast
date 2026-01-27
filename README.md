# YNAB Forecast Automation

Automatically forecast recurring variable expenses in YNAB to get a realistic Running Balance.

> [!WARNING]
> This project is provided **as-is** for personal use. Use at your own risk—always test with `--dry-run` first.

## Features

🔮 **Smart forecasting** — Projects variable expenses (groceries, fuel, etc.) into your Running Balance

🧹 **Wipe & Rebuild** — Cleans up old forecasts before generating fresh ones, no duplicates

📅 **4-week projection** — Creates one-time scheduled transactions for the next 4 weeks

⚡ **GitHub Actions ready** — Runs automatically on a daily schedule

🧪 **Dry-run mode** — Preview changes without modifying your budget

## Usage

Mark any scheduled transaction for forecasting by including `TEMPFORCST` in the payee name:

| Field     | Value                          |
| --------- | ------------------------------ |
| Payee     | `Groceries TEMPFORCST`         |
| Frequency | `Weekly` or `Every Other Week` |
| Amount    | Your average weekly spend      |

The script scans for these "master" transactions and generates forecast entries for the next 4 weeks.

### Running Locally

```bash
# Preview changes (recommended first run)
python cleanup_forecast.py --dry-run

# Execute
python cleanup_forecast.py
```

### Running via GitHub Actions

The included workflow (`.github/workflows/cleanup.yml`) runs daily at **21:00 UTC**.

1. Fork this repository
2. Add secrets: **Settings → Secrets and variables → Actions**
3. Enable the workflow in the **Actions** tab

## Installation

### Environment Variables

| Variable     | Description                                         |
| ------------ | --------------------------------------------------- |
| `YNAB_TOKEN` | Personal Access Token from YNAB Developer Settings  |
| `BUDGET_ID`  | Budget ID (found in the URL when you open YNAB web) |

For local runs, create a `.env` file. For GitHub Actions, add these as Repository Secrets.

### Local Setup

```bash
git clone https://github.com/sil-so/ynab-tempforcst.git
cd ynab-tempforcst
pip install -r requirements.txt
```

## License

[MIT](LICENSE)
