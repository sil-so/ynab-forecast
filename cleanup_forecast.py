#!/usr/bin/env python3
"""
YNAB Forecast Manager

Automates the creation of future forecast transactions in YNAB for recurring
scheduled transactions using a Delta Sync strategy:

1. Fetches all scheduled transactions from YNAB
2. Calculates desired forecasts for the next N months
3. Compares with existing forecast transactions
4. Only creates/deletes the difference (minimizes API calls)

Forecast transactions are created as one-time scheduled transactions with:
- Payee: "🔮 Forecast | [Original Memo]"
- Memo: "Forecast (Auto-Gen) from [frequency]"
- Frequency: "never" (one-time)

Note: Recurring transactions without a memo are skipped.
"""

import os
import sys
import argparse
import time
from datetime import date
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
import ynab
from ynab.exceptions import ApiException
from ynab.models.scheduled_transaction_frequency import ScheduledTransactionFrequency

# Configuration
FORECAST_MONTHS = 2
FORECAST_PREFIX = "🔮 Forecast |"
# Proactive rate limiting: YNAB allows 200 requests/hour
# Using 2 second delays between writes = max 30 writes/minute = 1800/hour (safe margin)
API_DELAY_SECONDS = 2.0
RATE_LIMIT_RETRY_SECONDS = 65  # Wait slightly over a minute if rate limited


def get_frequency_step(frequency: str) -> relativedelta | None:
    """Returns the relativedelta step for a given YNAB frequency."""
    frequency_map = {
        'daily': relativedelta(days=1),
        'weekly': relativedelta(weeks=1),
        'everyOtherWeek': relativedelta(weeks=2),
        'every4Weeks': relativedelta(weeks=4),
        'monthly': relativedelta(months=1),
        'everyOtherMonth': relativedelta(months=2),
        'every3Months': relativedelta(months=3),
        'every4Months': relativedelta(months=4),
        'twiceAYear': relativedelta(months=6),
        'yearly': relativedelta(years=1),
        'everyOtherYear': relativedelta(years=2),
    }
    return frequency_map.get(frequency)


def generate_twice_a_month_dates(start_date: date, horizon_date: date) -> list[date]:
    """
    Generate dates for 'twiceAMonth' frequency.
    YNAB's twiceAMonth typically means the same day of the month, twice per month
    (e.g., 1st and 15th, or the original date and ~14 days later).
    We'll generate on the original day and the same day + ~15 days offset.
    """
    dates = []
    # Start from the month of start_date
    current = date(start_date.year, start_date.month, 1)
    original_day = start_date.day
    
    while current <= horizon_date:
        # First occurrence: original day of the month
        first_date = None
        try:
            first_date = current.replace(day=min(original_day, 28))  # Cap at 28 for safety
            if first_date >= start_date and first_date <= horizon_date:
                dates.append(first_date)
        except ValueError:
            pass
        
        # Second occurrence: ~15 days later (or 15th if original is 1st)
        second_day = (original_day + 14) if original_day <= 14 else (original_day - 14)
        try:
            second_date = current.replace(day=min(second_day, 28))
            if second_date >= start_date and second_date <= horizon_date and second_date != first_date:
                dates.append(second_date)
        except ValueError:
            pass
        
        # Move to next month
        current = current + relativedelta(months=1)
    
    return sorted(dates)


def api_call_with_retry(func, *args, max_retries: int = 3, **kwargs):
    """Execute an API call with retry logic for rate limits."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except ApiException as e:
            if e.status == 429 and attempt < max_retries - 1:
                print(f"   Rate limit hit. Waiting {RATE_LIMIT_RETRY_SECONDS}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(RATE_LIMIT_RETRY_SECONDS)
            else:
                raise
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="YNAB Forecast Manager")
    parser.add_argument("--dry-run", action="store_true", 
                        help="Preview changes without making API calls")
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    token = os.environ.get("YNAB_TOKEN")
    budget_id = os.environ.get("BUDGET_ID")

    if not token:
        print("Error: YNAB_TOKEN environment variable not set")
        return 1
    if not budget_id:
        print("Error: BUDGET_ID environment variable not set")
        return 1

    configuration = ynab.Configuration(access_token=token)
    
    today = date.today()
    horizon_date = today + relativedelta(months=FORECAST_MONTHS)
    
    # Counters
    deleted_forecast_count = 0
    created_count = 0
    skipped_splits = 0

    print(f"YNAB Forecast Manager")
    print(f"{'=' * 40}")
    print(f"Forecast horizon: {today} to {horizon_date} ({FORECAST_MONTHS} months)")
    if args.dry_run:
        print("MODE: Dry run (no changes will be made)")
    print()

    with ynab.ApiClient(configuration) as api_client:
        scheduled_transactions_api = ynab.ScheduledTransactionsApi(api_client)

        try:
            # --- STEP 1: Fetch Scheduled Transactions ---
            print("Fetching scheduled transactions...")
            
            sched_response = api_call_with_retry(
                scheduled_transactions_api.get_scheduled_transactions,
                budget_id
            )
            if sched_response is None:
                print("Error: Failed to fetch scheduled transactions after retries")
                return 1
                
            all_scheduled = sched_response.data.scheduled_transactions
            print(f"Found {len(all_scheduled)} scheduled transactions")

            # --- STEP 2: Generate Desired Forecasts (In-Memory) ---
            print("\nCalculating desired forecasts...")
            desired_forecasts: list[dict] = []
            
            for sched in all_scheduled:
                # Skip deleted or one-time transactions
                if sched.deleted or sched.frequency == 'never':
                    continue
                
                # Skip transactions that already are forecasts (avoid recursion)
                original_payee = sched.payee_name or ""
                if FORECAST_PREFIX in original_payee:
                    continue
                
                # Check for split transactions (subtransactions)
                has_splits = (hasattr(sched, 'subtransactions') and 
                              sched.subtransactions and 
                              len(sched.subtransactions) > 0)
                if has_splits:
                    print(f"   Warning: Skipping split transaction '{original_payee}' "
                          f"(YNAB API doesn't support creating split scheduled transactions)")
                    skipped_splits += 1
                    continue
                
                # Skip transactions without a memo (required for forecast naming)
                original_memo = sched.memo or ""
                if not original_memo.strip():
                    print(f"   Warning: Skipping '{original_payee}' (no memo set)")
                    continue
                
                # Build forecast payee name using the memo
                forecast_payee = f"{FORECAST_PREFIX} {original_memo}"
                
                # Handle special frequency: twiceAMonth
                if sched.frequency == 'twiceAMonth':
                    if sched.date_next:
                        future_dates = generate_twice_a_month_dates(
                            sched.date_next + relativedelta(days=1),  # Start after next scheduled
                            horizon_date
                        )
                        for fut_date in future_dates:
                            desired_forecasts.append({
                                "date": fut_date,
                                "payee_name": forecast_payee,
                                "amount": sched.amount,
                                "account_id": sched.account_id,
                                "category_id": sched.category_id,
                                "memo": f"Forecast (Auto-Gen) from {sched.frequency}",
                                "flag_color": sched.flag_color,
                            })
                    continue
                
                # Standard frequency handling
                step = get_frequency_step(sched.frequency)
                if step is None:
                    # Unknown frequency, skip
                    continue
                    
                start_date = sched.date_next + step
                curr_date = start_date
                
                while curr_date <= horizon_date:
                    desired_forecasts.append({
                        "date": curr_date,
                        "payee_name": forecast_payee,
                        "amount": sched.amount,
                        "account_id": sched.account_id,
                        "category_id": sched.category_id,
                        "memo": f"Forecast (Auto-Gen) from {sched.frequency}",
                        "flag_color": sched.flag_color,
                    })
                    curr_date = curr_date + step

            print(f"   Calculated {len(desired_forecasts)} desired forecast entries")
            if skipped_splits > 0:
                print(f"   Skipped {skipped_splits} split transactions")

            # --- STEP 3: Identify Existing Forecasts ---
            print("\nIdentifying existing forecasts...")
            existing_forecasts = []
            for sched in all_scheduled:
                if sched.deleted:
                    continue
                payee_name = sched.payee_name or ""
                memo = sched.memo or ""
                # Match forecasts by prefix in payee OR by auto-gen memo
                is_forecast = (FORECAST_PREFIX in payee_name or 
                               memo.startswith("Forecast (Auto-Gen)"))
                
                if is_forecast and sched.frequency == 'never':
                    existing_forecasts.append(sched)
            
            print(f"   Found {len(existing_forecasts)} existing forecast transactions")

            # --- STEP 4: Calculate Delta (Diff) ---
            print("\nCalculating delta...")
            
            # Create signature sets for comparison: "YYYY-MM-DD|Payee|Amount"
            def make_signature(dt: date, payee: str, amount: int) -> str:
                return f"{dt}|{payee}|{amount}"
            
            desired_sigs: dict[str, dict] = {
                make_signature(d['date'], d['payee_name'], d['amount']): d 
                for d in desired_forecasts
            }
            
            existing_sigs = {
                make_signature(e.date_next, e.payee_name, e.amount): e 
                for e in existing_forecasts
            }
            
            # To DELETE: existing items not in desired
            to_delete = [
                existing_sigs[sig] 
                for sig in existing_sigs 
                if sig not in desired_sigs
            ]
            
            # To CREATE: desired items not in desired
            to_create = [
                desired_sigs[sig] 
                for sig in desired_sigs 
                if sig not in existing_sigs
            ]
            
            unchanged = len(desired_forecasts) - len(to_create)
            
            print(f"   To delete: {len(to_delete)}")
            print(f"   To create: {len(to_create)}")
            print(f"   Unchanged: {unchanged}")

            # Estimate time for API calls
            total_api_calls = len(to_delete) + len(to_create)
            if total_api_calls > 0:
                estimated_time = total_api_calls * API_DELAY_SECONDS
                print(f"\n   Estimated time: ~{int(estimated_time)}s ({total_api_calls} API calls at {API_DELAY_SECONDS}s intervals)")

            # --- STEP 5: Execute Deletes ---
            if to_delete:
                print(f"\nDeleting {len(to_delete)} obsolete forecasts...")
                for i, item in enumerate(to_delete, 1):
                    if args.dry_run:
                        print(f"   [{i}/{len(to_delete)}] Would delete: {item.date_next} | {item.payee_name}")
                    else:
                        print(f"   [{i}/{len(to_delete)}] Deleting: {item.date_next} | {item.payee_name}")
                        try:
                            api_call_with_retry(
                                scheduled_transactions_api.delete_scheduled_transaction,
                                budget_id, 
                                item.id
                            )
                            deleted_forecast_count += 1
                            time.sleep(API_DELAY_SECONDS)
                        except ApiException as e:
                            print(f"      Failed to delete: {e}")
            
            # --- STEP 6: Execute Creates ---
            if to_create:
                print(f"\nCreating {len(to_create)} new forecasts...")
                for i, item in enumerate(to_create, 1):
                    if args.dry_run:
                        print(f"   [{i}/{len(to_create)}] Would create: {item['date']} | {item['payee_name']}")
                    else:
                        print(f"   [{i}/{len(to_create)}] Creating: {item['date']} | {item['payee_name']}")
                        try:
                            # For inflows (positive amounts), omit category_id
                            # (goes to "Ready to Assign" automatically)
                            category_id = None if item['amount'] > 0 else item['category_id']
                            
                            new_sched = ynab.SaveScheduledTransaction(
                                account_id=item['account_id'],
                                date=item['date'],
                                amount=item['amount'],
                                payee_name=item['payee_name'],
                                category_id=category_id,
                                memo=item['memo'],
                                frequency=ScheduledTransactionFrequency.NEVER,
                                flag_color=item['flag_color'],
                            )
                            
                            wrapper = ynab.PostScheduledTransactionWrapper(
                                scheduled_transaction=new_sched
                            )
                            api_call_with_retry(
                                scheduled_transactions_api.create_scheduled_transaction,
                                budget_id,
                                wrapper
                            )
                            created_count += 1
                            time.sleep(API_DELAY_SECONDS)
                            
                        except ApiException as e:
                            print(f"      Failed to create: {e}")
                            if e.status == 429:
                                print(f"      Rate limit exceeded. Stopping to avoid further issues.")
                                print(f"      Run the script again later to continue.")
                                break

        except ApiException as e:
            print(f"\nAPI Error: {e}")
            return 1

    # --- Summary ---
    print(f"\n{'=' * 40}")
    print(f"Summary:")
    print(f"   Forecasts deleted: {deleted_forecast_count}")
    print(f"   Forecasts created: {created_count}")
    if skipped_splits > 0:
        print(f"   Split transactions skipped: {skipped_splits}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
