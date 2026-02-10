#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minecraft Librarian Trading Data Entry Script
Filename: add_lib_trade.py
Author: Dylan Bretz Jr.
Date: 2026-02-06

Description:
This script allows users to register new librarian villagers and their enchantment trades into a SQLite database for a Minecraft trading system.
It includes robust input validation and checks for duplicates before inserting new trades.
The script also handles the addition of new trading hall locations and villager registrations as needed.
The user is guided through each step with clear prompts and error messages to ensure data integrity.

Flow:
    1. Prompt user for `location`, `villager_id`, `enchantment`, `enchantment_level`, and `cost_emeralds`.
    2. Check if `location` exists in `locations` table.
        - If not, prompt user to add new location with coordinates.
    3. Check if `villager_id` exists in `villagers` table.
        - If not, prompt user to add new librarian at the specified location.
        - If exists but is not a librarian, show error and prompt for different ID.
        - If exists and is a librarian but at a different location, prompt to move them to the new location.
    4. Check if `enchantment` exists in `enchantments` table and get its `max_level`.
        - If not, show error and prompt for a different enchantment.
    5. Validate that `enchantment_level` is between 1 and `max_level`.
    6. Validate that `cost_emeralds` is between 1 and 64.
    7. Check for duplicate trade (same villager_id, enchantment, level, and cost).
        - If duplicate exists, prompt user to confirm if they want to add it anyway.
    8. If all validations pass, insert new trade into `librarian_trades` table.
    9. After each entry, prompt user if they want to add another trade or exit.

Input:
- location (string): Name of the location of the trading hall (e.g. 'spawn')
- villager_id (string): Unique identifier for the villager (e.g. 'spa001')
- enchantment (string): Name of the enchantment (e.g. 'mending')
- enchantment_level (int): Level of the enchantment (e.g. 1)
- cost_emeralds (int): Cost in emeralds for the trade (e.g. 15)

Output:
- If the villager location is new, a new row is added to the `locations` table with the `location` and coordinate data (`x_coord`, `z_coord`)
- If the `villager_id` is not in `villagers` table, then add a new row to the `villagers` table (`villager_id`, `location`, 'librarian') (notice that it should automatically record 'librarian' as the job)
- Else add new row to `librarian_trades` table (`villager_id`, `enchantment`, `enchantment_level`, `cost_emeralds`)
"""

import os
import sqlite3

# --- CONFIGURATION ---

DB_NAME = 'mc_trading.db'

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
DB_PATH = os.path.join(parent_dir, DB_NAME)

# --- INPUT HELPER FUNCTIONS ---

def get_location(cursor, conn):
    """Loop until a valid location is confirmed or added."""
    while True:
        # Return list of existing locations for user reference
        cursor.execute('SELECT location FROM locations')
        valid_locations = sorted([row[0] for row in cursor.fetchall()])
        print(f'\nExisting locations: {", ".join(valid_locations) if valid_locations else "None"}')

        loc = input('Trading hall location (e.g. "spawn"): ').strip().lower()
        if not loc:
            print('❌ Error: Location cannot be empty. Try again.')
            continue

        # Check if location exists in 'locations' table
        cursor.execute('SELECT 1 FROM locations WHERE location = ?', (loc,))
        if cursor.fetchone():
            return loc

        # Confirmation steps for new location
        while True:
            print(f'\nLocation "{loc}" not found.')
            confirm = input(f'Add "{loc}" as a new location? (y/n): ').strip().lower()
            if confirm == 'y':
                while True:
                    try:
                        x = int(input(f'X coordinate of "{loc}" trading hall: ').strip())
                        z = int(input(f'Z coordinate of "{loc}" trading hall: ').strip())
                        break
                    except ValueError:
                        print('❌ Error: Coordinates must be numbers. Try again.')

                cursor.execute("""
                    INSERT INTO locations (location, x_coord, z_coord)
                    VALUES (?, ?, ?)
                """, (loc, x, z))
                conn.commit()
                print(f'Added new location "{loc}" with coordinates ({x}, {z}).')
                return loc
            elif confirm == 'n':
                print('❌ Action cancelled. Please enter a different location.')
                break
            else:
                print('Invalid input. Please enter "y" or "n".')

def get_villager_id(cursor, conn, current_loc):
    """Loop until a valid villager ID is confirmed."""
    while True:
        v_id = input('\nVillager ID (e.g. "spa001"): ').strip().lower()
        if not v_id:
            print('❌ Error: Villager ID cannot be empty. Try again.')
            continue

        # Check if villager exists and if they are a librarian
        cursor.execute('SELECT job, location FROM villagers WHERE villager_id = ?', (v_id,))
        existing = cursor.fetchone()

        if existing:
            job, registered_loc = existing

            # Check if existing villager is a librarian
            if job != 'librarian':
                print(f'❌ Error: Villager {v_id} is a "{job}", not a librarian. Try again.')
                continue

            # Check if existing villager is at the same location
            if registered_loc != current_loc:
                print(f'⚠️ Warning: Villager {v_id} is currently registered at "{registered_loc}".')

                while True:
                    move = input(f'Move them to "{current_loc}"? (y/n): ').strip().lower()
                    if move == 'y':
                        cursor.execute('UPDATE villagers SET location = ? WHERE villager_id = ?', (current_loc, v_id))
                        conn.commit()
                        print(f'✅ Moved {v_id} to {current_loc}.')
                        return v_id
                    elif move == 'n':
                        print('❌ Villager mismatch. Please enter a different Villager ID.')
                        break
                    else:
                        print('Invalid input. Please enter "y" or "n".')
                continue 

            return v_id

        # Confirmation steps for new villager
        while True:
            confirm = input(f'\nVillager ID "{v_id}" not found. Add new Librarian at "{current_loc}"? (y/n): ').strip().lower()
            if confirm == 'y':
                cursor.execute("""
                    INSERT INTO villagers (villager_id, location, job)
                    VALUES (?, ?, 'librarian')
                """, (v_id, current_loc))
                conn.commit()
                print(f'✅ Added new Librarian "{v_id}" at "{current_loc}".')
                return v_id
            elif confirm == 'n':
                print('❌ Action cancelled. Please enter a different Villager ID.')
                break
            else:
                print('Invalid input. Please enter "y" or "n".')

def get_enchantment(cursor):
    """Loop until a valid enchantment is confirmed."""
    while True:
        ench = input('\nEnchantment (e.g. "looting"): ').strip().lower()
        if not ench:
            print('❌ Error: Enchantment cannot be empty. Try again.')
            continue

        cursor.execute('SELECT max_level FROM enchantments WHERE enchantment = ?', (ench,))
        result = cursor.fetchone()

        if result:
            return ench, result[0]
        else:
            print(f'❌ Error: The enchantment "{ench}" is not in the database (or is not tradeable). Try again.')

def get_level(max_lvl):
    """Loop until a valid level (1 to max_lvl) is entered."""
    while True:
        try:
            level = int(input(f'\nEnchantment level (1-{max_lvl}): ').strip())
            if 1 <= level <= max_lvl:
                return level
            else:
                print(f'❌ Error: Level must be between 1 and {max_lvl}. Try again.')
        except ValueError:
            print('❌ Error: Level must be a number. Try again.')

def get_cost():
    """Loop until a valid cost (1 to 64) is entered."""
    while True:
        try:
            cost = int(input('\nCost in emeralds (1-64): ').strip())
            if 1 <= cost <= 64:
                return cost
            else:
                print('❌ Error: Cost must be between 1 and 64 emeralds. Try again.')
        except ValueError:
            print('❌ Error: Cost must be a number. Try again.')

# --- MAIN LOGIC ---

def add_librarian_trade(pre_loc=None, pre_v_id=None):
    """Add librarian trade with input validation and database checks."""

    print('\n--- 📚 New Librarian Trade Entry ---')

    try:
        try:
            conn = sqlite3.connect(DB_PATH)
        except sqlite3.Error as e:
            print(f'❌ Database connection error: {e}')
            return None, None, 'error'

        with conn:
            cursor = conn.cursor()
            cursor.execute('PRAGMA foreign_keys = ON;')

            # Get location (skip if provided)
            if pre_loc:
                print(f'Location: {pre_loc}')
                loc = pre_loc
            else:
                loc = get_location(cursor, conn)

            # Get villager ID (skip if provided)
            if pre_v_id:
                print(f'Villager ID: {pre_v_id}')
                v_id = pre_v_id
            else:
                v_id = get_villager_id(cursor, conn, loc)

            # Check if villager already has 4 trades
            cursor.execute('SELECT COUNT(*) FROM librarian_trades WHERE villager_id = ?', (v_id,))
            trade_count = cursor.fetchone()[0]

            if trade_count >= 4:
                print(f'❌ Error: Villager "{v_id}" already has {trade_count} out of 4 trades.')
                return loc, v_id, 'full'

            # Get trade details
            ench, max_lvl = get_enchantment(cursor)

            if max_lvl == 1:
                print(f'Setting enchantment level for "{ench}" to 1 (max level).')
                level = 1
            else:
                level = get_level(max_lvl)

            cost = get_cost()

            # Check for duplicates
            cursor.execute("""
                SELECT 1 FROM librarian_trades 
                WHERE villager_id = ? AND enchantment = ? AND enchantment_level = ? AND cost_emeralds = ?
            """, (v_id, ench, level, cost))

            # If duplicate exists, confirm before adding
            if cursor.fetchone():
                print(f'⚠️ Warning: This exact trade for Villager "{v_id}" already exists.')

                while True:
                    confirm = input('Add duplicate trade anyway? (y/n): ').strip().lower()
                    if confirm == 'n':
                        print('❌ Action cancelled. Trade not added.')
                        return loc, v_id, 'cancelled'
                    elif confirm == 'y':
                        break
                    else:
                        print('Invalid input. Please enter "y" or "n".')

            # Save to database
            cursor.execute("""
                INSERT INTO librarian_trades (villager_id, enchantment, enchantment_level, cost_emeralds)
                VALUES (?, ?, ?, ?)
            """, (v_id, ench, level, cost))

            print(f'✅ Saved: Villager "{v_id}" sells "{ench} {level}" for {cost} emeralds.')
            return loc, v_id, 'success'

    except Exception as e:
        print(f'\n❌ Error: {e}')
        return None, None, 'error'

    finally:
        if conn:
            conn.close()

# --- MAIN EXECUTION ---

if __name__ == '__main__':
    last_loc = None
    last_v_id = None

    while True:
        # 1. Run trade entry function
        loc, v_id, status = add_librarian_trade(last_loc, last_v_id)

        # 2. Update memory based on status
        if status in ['success', 'cancelled']:
            last_loc = loc
            last_v_id = v_id
        elif status == 'full':
            last_loc = loc
            last_v_id = None

        # 3. Prompt for next action

        # --- Same villager and location ---
        if last_v_id:
            prompt = f'\nAdd another trade for Villager "{last_v_id}" at "{last_loc}"? (y/n/exit): '

            while True:
                choice = input(prompt).strip().lower()
                if choice == 'y':
                    break
                elif choice == 'n':
                    last_v_id = None
                    break
                elif choice == 'exit':
                    print('\nExiting...')
                    exit()
                else:
                    print('Invalid input. Please enter "y", "n", or "exit".')
            if last_v_id:
                continue

        # --- Same location, different villager ---
        if last_loc:
            prompt = f'\nAdd a trade for a different villager at "{last_loc}"? (y/n/exit): '

            while True:
                choice = input(prompt).strip().lower()
                if choice == 'y':
                    last_v_id = None
                    break
                elif choice == 'n':
                    last_loc = None
                    last_v_id = None
                    break
                elif choice == 'exit':
                    print('\nExiting...')
                    exit()
                else:
                    print('Invalid input. Please enter "y", "n", or "exit".')
            if last_loc:
                continue

        # --- Different location and villager ---
        while True:
            choice = input('\nAdd another trade at a different location? (y/n): ').strip().lower()
            if choice == 'y':
                last_loc = None
                last_v_id = None
                break
            elif choice == 'n':
                print('\nExiting...')
                exit()
            else:
                print('Invalid input. Please enter "y" or "n".')
