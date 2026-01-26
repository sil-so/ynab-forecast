# YNAB Forecast Automation 🔮

A custom Python script that bridges the gap between your **Budget** and your **Running Balance** by automatically forecasting recurring variable expenses (like groceries or fuel).

## The Problem

YNAB is great at tracking fixed bills, but the "Running Balance" column often paints an overly optimistic picture because it ignores future variable spending.

## The Solution

This script implements a **"Wipe & Rebuild"** strategy:

1.  **Clean:** It scans your register for previously auto-generated forecast transactions (identified by a specific Payee) and deletes them.
2.  **Read:** It looks for your "Master" scheduled transactions (e.g., a weekly grocery trip).
3.  **Forecast:** It generates new, one-time scheduled transactions for the next **4 weeks**.

This ensures your Running Balance always reflects the reality of your upcoming weeks, without clogging up your schedule with duplicate recurring events.

---

## Setup

### 1. Prerequisites

- A YNAB Account
- A GitHub Account (to run via Actions) OR a local Python environment.
- Your **YNAB Personal Access Token** & **Budget ID**.

### 2. YNAB Configuration

Create a scheduled transaction in YNAB for the expense you want to forecast:

- **Payee:** Must contain `TEMPFORCST` (e.g., `Groceries TEMPFORCST`).
- **Frequency:** `Weekly` or `Every Other Week`.
- **Amount:** Your average weekly spend.

### 3. Environment Variables

The script requires two environment variables to function. If running locally, you can use a `.env` file. If running on GitHub Actions, add these to your Repository Secrets.

| Variable     | Description                                                      |
| :----------- | :--------------------------------------------------------------- |
| `YNAB_TOKEN` | Your Personal Access Token from YNAB Developer Settings.         |
| `BUDGET_ID`  | The ID of your budget (found in the URL when you open YNAB web). |

---

## How to Run

### Option A: GitHub Actions (Recommended)

This repository includes a workflow `.github/workflows/cleanup.yml` that runs the script automatically every day at **21:00 UTC**.

1.  Fork this repository.
2.  Go to **Settings** > **Secrets and variables** > **Actions**.
3.  Add `YNAB_TOKEN` and `BUDGET_ID`.
4.  Enable the workflow in the **Actions** tab.

### Option B: Local Execution

1.  Clone the repo.
2.  Install requirements:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the script:
    ```bash
    python cleanup_forecast.py
    ```
    _Use `--dry-run` to see what would happen without actually changing data._

---

## Disclaimer

This is a personal project used to interact with the YNAB API. Use at your own risk. The script is designed to only delete transactions that match the specific `TEMPFORCST` criteria, but always back up your budget or test with a dry run first!
