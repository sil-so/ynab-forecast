#!/usr/bin/env python3
"""
YNAB Temp Forecast Transaction Cleanup Script

Automatically deletes 'dummy' forecast transactions (with "TEMPFORCST" in payee name)
once their date has passed.
"""

import os
from datetime import date
from dotenv import load_dotenv
import ynab
from ynab.rest import ApiException


def main():
    # Load environment variables from .env file (for local development)
    load_dotenv()

    # Get credentials from environment
    token = os.environ.get("YNAB_TOKEN")
    budget_id = os.environ.get("BUDGET_ID")

    if not token:
        print("❌ Error: YNAB_TOKEN environment variable not set")
        return 1
    if not budget_id:
        print("❌ Error: BUDGET_ID environment variable not set")
        return 1

    # Configure YNAB API client
    configuration = ynab.Configuration(access_token=token)

    today = date.today()
    deleted_count = 0

    with ynab.ApiClient(configuration) as api_client:
        transactions_api = ynab.TransactionsApi(api_client)

        try:
            # Fetch all transactions from the budget
            print(f"📥 Fetching transactions from budget {budget_id}...")
            response = transactions_api.get_transactions(budget_id)
            transactions = response.data.transactions

            print(f"📊 Found {len(transactions)} total transactions")

            # Filter for temp forecast transactions with past dates
            for txn in transactions:
                payee_name = txn.payee_name or ""
                txn_date = txn.var_date

                # Check if this is a temp forecast transaction with a past date
                if "TEMPFORCST" in payee_name.upper() and txn_date < today:
                    print(f"🗑️  Deleting: {txn.var_date} | {payee_name} | {txn.amount / 1000:.2f}")

                    try:
                        transactions_api.delete_transaction(budget_id, txn.id)
                        deleted_count += 1
                    except ApiException as e:
                        print(f"   ⚠️  Failed to delete transaction {txn.id}: {e}")

        except ApiException as e:
            print(f"❌ API Error: {e}")
            return 1

    print(f"\n✅ Done! Deleted {deleted_count} forecast transaction(s)")
    return 0


if __name__ == "__main__":
    exit(main())
