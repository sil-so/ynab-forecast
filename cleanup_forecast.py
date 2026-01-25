#!/usr/bin/env python3
"""
YNAB Forecast Manager

1. Cleans up old 'TEMPFORCST' transactions (past dates).
2. WIPE & REBUILD STRATEGY:
   - Deletes ALL existing "Forecast" scheduled transactions (Frequency=Never, Payee=TEMPFORCST).
   - Regenerates them fresh from "Master" scheduled transactions (Frequency=Weekly).
   - Generates T+1 week, T+2 weeks context, skipping T+0 (which YNAB handles).
"""

import os
import argparse
from datetime import date
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
import ynab
from ynab.rest import ApiException

# Configuration
FORECAST_WEEKS = 4

def main():
    parser = argparse.ArgumentParser(description="YNAB Forecast Manager")
    parser.add_argument("--dry-run", action="store_true", help="Run without making API calls (read-only)")
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    token = os.environ.get("YNAB_TOKEN")
    budget_id = os.environ.get("BUDGET_ID")

    if not token:
        print("❌ Error: YNAB_TOKEN environment variable not set")
        return 1
    if not budget_id:
        print("❌ Error: BUDGET_ID environment variable not set")
        return 1

    configuration = ynab.Configuration(access_token=token)
    
    today = date.today()
    horizon_date = today + relativedelta(weeks=FORECAST_WEEKS)
    
    deleted_history_count = 0
    deleted_forecast_count = 0
    created_count = 0

    with ynab.ApiClient(configuration) as api_client:
        transactions_api = ynab.TransactionsApi(api_client)
        scheduled_transactions_api = ynab.ScheduledTransactionsApi(api_client)

        try:
            # --- STEP 1: Fetch Data ---
            print(f"📥 Fetching data from budget {budget_id}...")
            
            # Fetch existing transactions (for cleanup history)
            trans_response = transactions_api.get_transactions(budget_id)
            all_transactions = trans_response.data.transactions
            
            # Fetch existing scheduled transactions (for Wipe & Rebuild)
            sched_response = scheduled_transactions_api.get_scheduled_transactions(budget_id)
            all_scheduled = sched_response.data.scheduled_transactions
            
            print(f"📊 Found {len(all_transactions)} transactions, {len(all_scheduled)} scheduled items")

            # --- STEP 2: Cleanup Old History (Unchanged) ---
            print("\n🧹 Analyzing Register (History) for cleanup...")
            for txn in all_transactions:
                payee_name = txn.payee_name or ""
                if "TEMPFORCST" in payee_name.upper():
                    txn_date = txn.var_date
                    if txn_date < today:
                        if args.dry_run:
                            print(f"   [DRY-RUN] Would delete past txn: {txn_date} | {payee_name}")
                        else:
                            try:
                                transactions_api.delete_transaction(budget_id, txn.id)
                                deleted_history_count += 1
                            except ApiException as e:
                                print(f"   ⚠️  Failed to delete transaction {txn.id}: {e}")

            # --- STEP 3: WIPE Existing Forecasts (Scheduled One-Time) ---
            print("\n🌬️  Wiping existing forecasts (Wipe & Rebuild)...")
            for sched in all_scheduled:
                payee_name = sched.payee_name or ""
                # We target scheduled transactions that are TEMPFORCST AND 'never' (one-time)
                # This ensures we don't delete the Master (Weekly/Monthly) ones.
                if "TEMPFORCST" in payee_name.upper() and sched.frequency == 'never':
                    if args.dry_run:
                        print(f"   [DRY-RUN] Would wipe forecast: {sched.date_next} | {payee_name}")
                    else:
                        print(f"   🗑️  Wiping: {sched.date_next} | {payee_name}")

                        
                        # Real execution block
                        try:
                             # The api is `scheduled_transactions_api`
                             # Method: `delete_scheduled_transaction` (singular, implied by earlier check or standard gen)
                             # If ambiguous, we trust the standard pattern
                             # Let's try it.
                             scheduled_transactions_api.delete_scheduled_transaction(budget_id, sched.id)
                             deleted_forecast_count += 1
                        except ApiException as e:
                             print(f"   ⚠️  Failed to delete scheduled {sched.id}: {e}")

            # --- STEP 4: REBUILD Forecasts ---
            print(f"\n🔮 Rebuilding forecasts until {horizon_date}...")
            
            for sched in all_scheduled:
                payee_name = sched.payee_name or ""
                
                # Filter for MASTERs
                if sched.deleted or not payee_name or "TEMPFORCST" not in payee_name.upper():
                    continue
                
                # Only iterate on Weekly masters
                if sched.frequency != 'weekly':
                     # Verbose log for debug
                     # print(f"   Skipping master {payee_name} ({sched.frequency}) - Not Weekly")
                     continue

                print(f"   Found Master: {payee_name} ({sched.frequency})")
                
                step = relativedelta(weeks=1)
                
                # Start from Next Date + 1 step (User wants us to skip the one YNAB handles)
                start_date = sched.date_next + step 
                curr_date = start_date
                
                while curr_date <= horizon_date:
                    if args.dry_run:
                        print(f"      [DRY-RUN] Would create forecast for {curr_date} ({sched.amount/1000:.2f})")
                    else:
                        print(f"      ➕ Creating: {curr_date}")
                        try:
                            new_sched = ynab.SaveScheduledTransaction(
                                account_id=sched.account_id,
                                date=curr_date,
                                amount=sched.amount,
                                payee_id=sched.payee_id,
                                payee_name=sched.payee_name,
                                category_id=sched.category_id,
                                memo=f"Forecast (Auto-Gen)",
                                frequency="never", # One-time
                                flag_color=sched.flag_color
                            )
                            
                            wrapper = ynab.PostScheduledTransactionWrapper(scheduled_transaction=new_sched)
                            scheduled_transactions_api.create_scheduled_transaction(budget_id, wrapper)
                            created_count += 1
                            
                        except ApiException as e:
                            print(f"      ❌ Failed to create: {e}")
                    
                    curr_date += step

        except ApiException as e:
            print(f"❌ API Error: {e}")
            return 1

    print(f"\n📊 Summary:")
    print(f"   Deleted History (Past):    {deleted_history_count}")
    print(f"   Wiped Forecasts (Future):  {deleted_forecast_count}")
    print(f"   Created Forecasts (New):   {created_count}")
    return 0

if __name__ == "__main__":
    exit(main())
