#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minecraft Villager ID Migration Script
Filename: migrate_ids.py
Author: Dylan Bretz Jr.
Date: 2026-03-12

Description:
This script performs a one-time database migration to standardize the formatting 
of librarian `villager_id`s in the Minecraft trading database. It converts 
3-letter prefixed IDs (e.g., 'spa001') into 2-letter prefixed IDs (e.g., 'sp001') 
to match the updated naming convention. The script safely updates these primary 
and foreign keys across both the parent `villagers` table and the child 
`librarian_trades` table.

Flow:
1. Connect to the local `mc_trading.db` SQLite database.
2. Temporarily disable SQLite foreign key constraints to allow safe in-place 
   updating of primary keys.
3. Query the `villagers` table to retrieve all existing `villager_id`s where 
   the job is 'librarian'.
4. Iterate through the retrieved IDs, using a regular expression to identify 
   any ID starting with exactly three letters followed by digits.
5. For matching IDs, generate the new ID by slicing the prefix to two letters 
   and appending the original digits.
6. Execute `UPDATE` statements to replace the old ID with the new ID in the 
   `librarian_trades` table first, followed by the `villagers` table.
7. Commit the database transaction and re-enable foreign key constraints.
8. Print a console summary detailing each change and the total records migrated.

Input:
- Local SQLite database file (`mc_trading.db`) containing populated `villagers` 
  and `librarian_trades` tables.

Output:
- Modified SQLite database with updated `villager_id` strings.
- Standard output (console) logging the specific ID changes and the total 
  number of updates executed.
"""

import sqlite3
import os
import re

# --- CONFIGURATION ---

DB_NAME = 'mc_trading.db'
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
DB_PATH = os.path.join(parent_dir, DB_NAME)

def migrate_librarian_ids():
    if not os.path.exists(DB_PATH):
        print(f"[-] Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Temporarily disable foreign key constraints to safely update primary keys
    cursor.execute("PRAGMA foreign_keys = OFF;")

    # Fetch all librarians
    cursor.execute("SELECT villager_id FROM villagers WHERE job = 'librarian'")
    villagers = cursor.fetchall()

    updates_made = 0

    for (old_id,) in villagers:
        # Regex to match exactly 3 letters followed by numbers (e.g., 'spa001', 'lib002')
        match = re.match(r'^([a-zA-Z]{3})(\d+)$', old_id)
        
        if match:
            letters = match.group(1)
            numbers = match.group(2)
            
            # Slice the 3 letters down to 2 and append the numbers (e.g., 'sp' + '001')
            new_id = letters[:2] + numbers
            
            try:
                # 1. Update the child table (librarian_trades)
                cursor.execute("UPDATE librarian_trades SET villager_id = ? WHERE villager_id = ?", (new_id, old_id))
                
                # 2. Update the parent table (villagers)
                cursor.execute("UPDATE villagers SET villager_id = ? WHERE villager_id = ?", (new_id, old_id))
                
                updates_made += 1
                print(f"[+] Migrated {old_id} -> {new_id} in both tables")
                
            except sqlite3.Error as e:
                print(f"[-] Error migrating {old_id}: {e}")

    conn.commit()
    
    # Re-enable foreign key constraints
    cursor.execute("PRAGMA foreign_keys = ON;")
    conn.close()

    print(f"\nMigration complete! Successfully updated {updates_made} librarian IDs.")

if __name__ == '__main__':
    print("--- Starting Librarian ID Migration ---")
    migrate_librarian_ids()
