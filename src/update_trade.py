#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minecraft Villager Trading Data Update Script
Filename: update_trade.py
Author: Dylan Bretz Jr.
Date: 2026-03-12

Description:
This interactive CLI tool allows for the manual updating of emerald costs for 
existing villager trades. It is specifically designed to handle the "curing" 
workflow, prompting the user to update a villager's cured status and then 
modifying associated trade costs to reflect discounts.

Flow:
1. Prompt for a valid Villager ID.
2. Retrieve the villager's profession and current cured status.
3. If uncured, prompt the user to update the status to "Cured" in the database.
4. Dynamically fetch and display all trades from the appropriate profession table.
5. Prompt the user to select a specific trade and enter a new emerald cost (1-64).
6. Update the record using the unique rowid and allow for additional updates.

Input:
- `villager_id` (string): The unique ID of the villager (e.g., 'sp001').
- `emerald_cost` (int): The new discounted price for a selected trade.

Output:
- Updated `cured` status in the `villagers` table (if applicable).
- Updated `emerald_cost` for the selected trade in the job-specific trade table.
"""

import sqlite3
import os
import sys

# --- CONFIGURATION ---

DB_NAME = 'mc_trading.db'
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) 
DB_PATH = os.path.join(parent_dir, DB_NAME)

# --- HELPER SCRIPTS ---

def get_db_connection():
    if not os.path.exists(DB_PATH):
        print(f'Error: Database not found at {DB_PATH}')
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def check_and_update_cured(conn, villager_id, current_status):
    """Prompts to update cured status if currently uncured (0)."""
    if current_status == 0:
        while True:
            choice = (
                input(
                    f'\n{villager_id} is currently marked as UNCURED. '
                    'Update to CURED? (y/n): '
                ).strip().lower()
            )
            if choice == 'y':
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE villagers SET cured = 1 WHERE villager_id = ?
                """, (villager_id,))
                conn.commit()
                print(f'{villager_id} status updated to CURED.')
                return 1
            elif choice == 'n':
                return 0
            print("Invalid input. Please enter 'y' or 'n'.")
    return current_status

def main():
    conn = get_db_connection()
    cursor = conn.cursor()

    while True:
        # 1. Prompt for villager_id
        v_id = input("\nEnter Villager ID (or 'q' to quit): ").strip().lower()
        if v_id == 'q':
            break
        if not v_id:
            continue

        # 2. Get profession and cured status
        cursor.execute("""
            SELECT job, cured FROM villagers WHERE villager_id = ?
        """, (v_id,))
        villager = cursor.fetchone()

        if not villager:
            print(f"Villager '{v_id}' not found.")
            continue

        job = villager['job']
        cured_status = villager['cured']
        print(
            f"\nTarget: {v_id} | Job: {job.capitalize()} | "
            f"Cured: {'Yes' if cured_status == 1 else 'No'}"
        )

        # Check for cured status update if uncured
        cured_status = check_and_update_cured(conn, v_id, cured_status)

        # 3. Determine trade table
        trade_table = f'{job}_trades'

        while True:
            # Get trades using rowid to ensure unique selection for updates
            try:
                cursor.execute(f"""
                    SELECT rowid AS id, * FROM {trade_table}
                    WHERE villager_id = ?
                """, (v_id,))
                trades = cursor.fetchall()
            except sqlite3.OperationalError:
                print(f"Error: Table '{trade_table}' does not exist.")
                break

            if not trades:
                print(f'No trades found for {v_id} in {trade_table}.')
                break

            # Display Trades
            print(f"\n--- {v_id}'s Trades ---")
            trade_map = {}
            for idx, t in enumerate(trades, start=1):
                trade_map[str(idx)] = t['id']

                # Dynamic display based on columns present (item vs enchantment)
                desc = []
                if 'item' in t.keys() and t['item']:
                    desc.append(f"Item: {t['item']}")
                if 'enchantment' in t.keys() and t['enchantment']:
                    desc.append(f"Enchant: {t['enchantment']}")
                if 'enchantment_level' in t.keys() and t['enchantment_level']:
                    desc.append(f"Lvl: {t['enchantment_level']}")

                print(
                    f"[{idx}] {' | '.join(desc)} => Cost: {t['emerald_cost']}"
                )

            # 4. User Selection
            print(
                '\nOptions: [1-N] Select trade | '
                '[v] Different villager | [q] Exit'
            )
            choice = input('Choice: ').strip().lower()

            if choice == 'q':
                conn.close()
                sys.exit(0)
            elif choice == 'v':
                break
            elif choice in trade_map:
                # 5. Prompt for new emerald_cost
                while True:
                    try:
                        new_cost = int(
                            input(
                                f'New emerald_cost for trade {choice} (1-64): '
                            )
                            .strip()
                        )
                        if 1 <= new_cost <= 64:
                            break
                        print('Cost must be between 1 and 64.')
                    except ValueError:
                        print('Invalid number. Try again.')

                # 6. Update Database
                cursor.execute(f"""
                    UPDATE {trade_table} SET emerald_cost = ? WHERE rowid = ?
                """, (new_cost, trade_map[choice]))
                conn.commit()
                print(f'Success: Updated trade to {new_cost} emeralds.')

                # 7. Prompt for next action
                after = (
                    input('\nUpdate another trade for this villager? (y/n): ')
                    .strip().lower()
                )
                if after != 'y':
                    break
            else:
                print('Invalid selection.')

    conn.close()

if __name__ == '__main__':
    main()
