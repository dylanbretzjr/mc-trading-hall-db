#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minecraft Villager Trading Data Entry Script
Filename: add_trade.py
Author: Dylan Bretz Jr.
Date: 2026-03-10

Description:
This script provides an interactive command-line interface for adding new trades to the Minecraft trading database.
It guides the user through the process of entering trade details, including location, villager ID, profession, item (if applicable), enchantments, and cost.
The script validates user input against existing database entries and ensures that trade constraints are respected (e.g., maximum trades per villager, valid enchantments and items).

Flow:
1. Prompt user for `location`.
	- If not found, prompt user to add new location with coordinates.
2. Prompt user for `villager_id`.
	- If found, retrieve `profession` from the `villagers` table.
	- If not found, prompt user for `profession`, then add new villager to `villagers`.
	- If exists, but at a different location, prompt to change location or to move them to the new location.
3. Check trade capacity.
	- Librarian: check that this villager has fewer than 4 existing trades.
	- Armorer / Toolsmith / Weaponsmith: prompt user for `item`, validate against the fixed list for the profession, and check that this villager does not already have a trade for this item.
4. Prompt user for `emerald_cost`.
	- Validate that `emerald_cost` is between 1 and 64.
5. Insert row into the profession's trades table and retrieve the new `trade_id`.
6. Prompt user for `enchantment` and `enchantment_level`.
	- Librarian: collect one enchantment/level pair. Validate `enchantment` exists in `enchantments` table. Validate level is between 1 and `max_level`. Check for duplicate trade; if found, prompt user to confirm before adding.
	- Armorer / Toolsmith / Weaponsmith: collect one or more enchantment/level pairs in a loop until the user is done. For each, validate enchantment exists in `enchantments` table. Validate level is between 1 and 5. Validate enchantment is not a duplicate on this item.
7. Insert enchantment row(s) into the appropriate enchantments table.
8. After each entry, prompt user if they want to add another trade or exit.

Input:
- `location` (string): Name of the trading hall location (e.g. 'spawn')
- `villager_id` (string): Unique identifier for the villager (e.g. 'spa001')
- `profession` (string): Villager profession (i.e., `librarian`, `armorer`, `toolsmith`, `weaponsmith`)
- `item` (string): Item offered in the trade, validated against a fixed list for the profession (armorers, toolsmiths, and weaponsmiths only)
- enchantment (string): Name of the enchantment (e.g. 'mending')
- enchantment_level (int): Level of the enchantment (e.g. 1)
- emerald_cost (int): Cost in emeralds for the trade (e.g. 15)

Output:
- If new location, add a new row to `locations` (`location`, `x_coord`, `z_coord`)
- If new villager, add a new row to `villagers` (`villager_id`, `location`, `profession`)
- Add a new row to the corresponding profession's table:
	- `librarian_trades` (`villager_id`, `enchantment`, `enchantment_level`, `emerald_cost`)
	- `armorer_trades`, `toolsmith_trades`, or `weaponsmith_trades` (`villager_id`, `item`, `emerald_cost`)
- For armorer, toolsmith, and weaponsmith trades, add one or more rows to the corresponding enchantments table (`trade_id`, `enchantment`, `enchantment_level`)
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

def get_profession():
    """Prompt user to select a valid profession."""
    valid_profs = ['librarian', 'armorer', 'toolsmith', 'weaponsmith']
    while True:
        prof = input(f'\nProfession ({", ".join(valid_profs)}): ').strip().lower()
        if prof in valid_profs:
            return prof
        print('❌ Error: Invalid profession. Try again.')

def get_villager_id(cursor, conn, current_loc):
    """Loop until a valid villager ID is confirmed."""
    while True:
        v_id = input('\nVillager ID (e.g. "spa001"): ').strip().lower()
        if not v_id:
            print('❌ Error: Villager ID cannot be empty. Try again.')
            continue

        # Check if villager exists and retrieve profession and location
        cursor.execute('SELECT job, location FROM villagers WHERE villager_id = ?', (v_id,))
        existing = cursor.fetchone()

        if existing:
            job, registered_loc = existing

            # Check if existing villager is at the same location
            if registered_loc != current_loc:
                print(f'⚠️ Warning: Villager {v_id} is currently registered at "{registered_loc}".')

                while True:
                    move = input(f'Move them to "{current_loc}"? (y/n): ').strip().lower()
                    if move == 'y':
                        cursor.execute('UPDATE villagers SET location = ? WHERE villager_id = ?', (current_loc, v_id))
                        conn.commit()
                        print(f'✅ Moved {v_id} to {current_loc}.')
                        return v_id, job
                    elif move == 'n':
                        print('❌ Villager mismatch. Please enter a different Villager ID.')
                        break
                    else:
                        print('Invalid input. Please enter "y" or "n".')
                continue 

            return v_id, job

        # If villager ID not found, prompt to add new villager
        while True:
            confirm = input(f'\nVillager ID "{v_id}" not found. Add new villager at "{current_loc}"? (y/n): ').strip().lower()
            if confirm == 'y':
                job = get_profession()
                cursor.execute("""
                    INSERT INTO villagers (villager_id, location, job)
                    VALUES (?, ?, ?)
                """, (v_id, current_loc, job))
                conn.commit()
                print(f'✅ Added new {job.capitalize()} "{v_id}" at "{current_loc}".')
                return v_id, job
            elif confirm == 'n':
                print('❌ Action cancelled. Please enter a different Villager ID.')
                break
            else:
                print('Invalid input. Please enter "y" or "n".')

def get_item(profession):
    """Prompt for a valid item based on the villager's profession."""
    valid_items = {
        'armorer': ['diamond_boots', 'diamond_leggings', 'diamond_chestplate', 'diamond_helmet'],
        'toolsmith': ['diamond_axe', 'diamond_shovel', 'diamond_pickaxe'],
        'weaponsmith': ['diamond_axe', 'diamond_sword']
    }.get(profession, [])

    while True:
        item = input(f'\nItem offered ({", ".join(valid_items)}): ').strip().lower()
        if item in valid_items:
            return item
        print(f'❌ Error: Invalid item for a {profession}. Try again.')

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

def get_enchantments(cursor):
    """Loop to collect one or more enchantment/level pairs for gear trades."""
    enchantments = []
    while True:
        ench, max_lvl = get_enchantment(cursor)

        if any(e[0] == ench for e in enchantments):
            print(f'❌ Error: "{ench}" is already added to this item. Try a different enchantment.')
            continue

        if max_lvl == 1:
            print(f'Setting enchantment level for "{ench}" to 1 (max level).')
            level = 1
        else:
            # Constrain to 5 per schema, or lower if the enchantment naturally maxes out earlier
            limit = min(max_lvl, 5)
            level = get_level(limit)

        enchantments.append((ench, level))

        while True:
            more = input('\nAdd another enchantment to this item? (y/n): ').strip().lower()
            if more in ['y', 'n']:
                break
            print('Invalid input. Please enter "y" or "n".')
        
        if more == 'n':
            break

    return enchantments

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

def add_trade(pre_loc=None, pre_v_id=None):
    """
    Main function to add a new trade based on villager profession.
    Accepts optional pre-filled location and villager ID for streamlined entry.
    """

    print('\n--- New Villager Trade Entry ---')

    conn = None

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

            # Get villager ID and profession (skip if provided)
            if pre_v_id:
                print(f'Villager ID: {pre_v_id}')
                v_id = pre_v_id
                cursor.execute('SELECT job FROM villagers WHERE villager_id = ?', (v_id,))
                job = cursor.fetchone()[0]
            else:
                v_id, job = get_villager_id(cursor, conn, loc)

            # --- LIBRARIAN BRANCH ---
            if job == 'librarian':
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
                    WHERE villager_id = ? AND enchantment = ? AND enchantment_level = ? AND emerald_cost = ?
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
                    INSERT INTO librarian_trades (villager_id, enchantment, enchantment_level, emerald_cost)
                    VALUES (?, ?, ?, ?)
                """, (v_id, ench, level, cost))

                print(f'✅ Saved: Villager "{v_id}" sells "{ench} {level}" for {cost} emeralds.')
                return loc, v_id, 'success'

            # --- ARMORER, TOOLSMITH, & WEAPONSMITH BRANCH ---
            else:
                item = get_item(job)
                table_name = f'{job}_trades'
                ench_table_name = f'{job}_trade_enchantments'

                cursor.execute(f'SELECT 1 FROM {table_name} WHERE villager_id = ? AND item = ?', (v_id, item))
                if cursor.fetchone():
                    print(f'❌ Error: {job.capitalize()} "{v_id}" already has a registered trade for "{item}".')
                    return loc, v_id, 'cancelled'

                cost = get_cost()
                print(f'\n--- Enchantments for {item} ---')
                enchantments = get_enchantments(cursor)

                cursor.execute(f"""
                    INSERT INTO {table_name} (villager_id, item, emerald_cost)
                    VALUES (?, ?, ?)
                """, (v_id, item, cost))

                trade_id = cursor.lastrowid

                for ench, level in enchantments:
                    cursor.execute(f"""
                        INSERT INTO {ench_table_name} (trade_id, enchantment, enchantment_level)
                        VALUES (?, ?, ?)
                    """, (trade_id, ench, level))

                print(f'✅ Saved: {job.capitalize()} "{v_id}" sells "{item}" with {len(enchantments)} enchantment(s) for {cost} emeralds.')

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
        loc, v_id, status = add_trade(last_loc, last_v_id)

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
