# YNAB Forecast Automation

Automatically create forecast transactions in YNAB for recurring scheduled transactions to visualize future cash flow in your Running Balance.

> [!WARNING]
> This project is provided **as-is** for personal use. Use at your own risk—always test with `--dry-run` first.

## Features

🔮 **Automatic forecasting** — Creates one-time scheduled transactions for all your recurring transactions

🏷️ **Memo-based naming** — Forecast payee uses the memo from the master transaction

🔄 **Delta sync** — Only creates/deletes what's needed (minimizes API calls)

📅 **2-month horizon** — Projects transactions 2 months into the future

🛡️ **Rate limit protection** — Proactive pacing to stay within YNAB's API limits

🤖 **GitHub Actions ready** — Runs automatically on a daily schedule

🧪 **Dry-run mode** — Preview changes without modifying your budget

## How It Works

The script:

1. Fetches all scheduled transactions from your YNAB budget
2. Identifies recurring transactions (weekly, monthly, etc.)
3. Calculates future occurrences for the next 2 months
4. Creates one-time scheduled transactions with payee `🔮 Forecast [Memo]`
5. Uses delta sync to only create/delete what's changed since last run

### Naming Convention

Generated forecasts use the **memo** from the master recurring transaction:

| Master Transaction      | Master Memo  | Generated Forecast Payee |
| ----------------------- | ------------ | ------------------------ |
| `ING Bank` (monthly)    | `Bankkosten` | `🔮 Forecast Bankkosten` |
| `Albert Heijn` (weekly) | `Groceries`  | `🔮 Forecast Groceries`  |

> [!NOTE]
> Recurring transactions **without a memo** are skipped. Set a memo on your master transactions to include them in forecasting.
>
> If your source memo already starts with `🔮` (e.g. from a previous forecast), it will be automatically stripped before adding the new prefix to avoid duplication.

### Supported Frequencies

| Frequency         | Supported |
| ----------------- | --------- |
| Daily             | Yes       |
| Weekly            | Yes       |
| Every other week  | Yes       |
| Every 4 weeks     | Yes       |
| Twice a month     | Yes       |
| Monthly           | Yes       |
| Every other month | Yes       |
| Every 3 months    | Yes       |
| Every 4 months    | Yes       |
| Twice a year      | Yes       |
| Yearly            | Yes       |
| Every other year  | Yes       |

## Usage

### Running Locally

```bash
# Preview changes (recommended first run)
python cleanup_forecast.py --dry-run

# Execute
python cleanup_forecast.py
```

### Running via GitHub Actions

The included workflow (`.github/workflows/main.yml`) runs daily at **21:00 UTC**.

1. Fork this repository
2. Add secrets: **Settings > Secrets and variables > Actions**
   - `YNAB_TOKEN` - Your YNAB Personal Access Token
   - `BUDGET_ID` - Your budget ID
3. Enable the workflow in the **Actions** tab

## Installation

### Environment Variables

| Variable     | Description                                                                                   |
| ------------ | --------------------------------------------------------------------------------------------- |
| `YNAB_TOKEN` | Personal Access Token from [YNAB Developer Settings](https://app.ynab.com/settings/developer) |
| `BUDGET_ID`  | Budget ID (found in the URL: `app.ynab.com/{budget_id}/...`)                                  |

For local runs, create a `.env` file:

```
YNAB_TOKEN=your_token_here
BUDGET_ID=your_budget_id_here
```

### Local Setup

```bash
git clone https://github.com/sil-so/ynab-tempforcst.git
cd ynab-tempforcst
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Limitations

- **Split transactions are skipped** — The YNAB API doesn't support creating split scheduled transactions
- **Memo required** — Recurring transactions without a memo are skipped
- **Rate limits** — YNAB allows 200 API requests per hour. The script uses 2-second delays between operations to stay within this limit.

## License

[MIT](LICENSE)
