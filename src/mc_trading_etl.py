#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minecraft Trading Data ETL Pipeline
Filename: mc_trading_etl.py
Author: Dylan Bretz Jr.
Date: 2026-02-06
Updated: 2026-03-12

Description:
This script performs an ETL (Extract, Transform, Load) process to gather 
data about Minecraft enchantments and villager jobs from the latest Minecraft 
client JAR file. The data is extracted directly from the JAR file in memory, 
cleaned, and compared against the local SQLite database. If the database is 
missing, outdated, or manually altered, the script automatically heals the 
database by dropping and recreating the tables with the verified source data.

Flow:
1. Fetch the version manifest from piston-meta and parse the latest stable 
   release version.
2. Fetch the URL for the latest release's version-specific JSON from the 
   manifest.
3. Fetch the client JAR download URL from the version-specific JSON.
4. Download client.jar into RAM.
5. Extract enchantment and job data from the JAR in memory.
    - If extraction fails or validation counts mismatch, log a warning 
      and exit.
6. Format extracted data into Pandas DataFrames.
7. Check if `enchantments` and `jobs` tables exist in the database.
8. If tables exist, compare the newly extracted DataFrames against the
   database.
    - If the data matches perfectly, log that no changes are needed and exit.
    - If the data differs (game update or database corruption), proceed to 
      step 9.
9. Drop and recreate the tables with the verified data to ensure integrity.
10. Print summary of loaded data.

Input:
- Latest Minecraft client JAR file (downloaded into RAM)

Output:
- SQLite database file (`mc_trading.db`) with two tables, updated only if
  differences are detected:
    1. enchantments
    2. jobs
- Operational log file (`mc_trading_etl.log`)

Requirements:
- requests
- pandas
"""

import io
import json
import logging
import os
import sqlite3
import zipfile

import pandas as pd
import requests

# --- CONFIGURATION ---

DB_NAME = 'mc_trading.db'
LOG_FILE = 'mc_trading_etl.log'

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

DB_PATH = os.path.join(parent_dir, DB_NAME)
LOG_PATH = os.path.join(parent_dir, LOG_FILE)

MANIFEST_URL = 'https://piston-meta.mojang.com/mc/game/version_manifest.json'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)

# --- HELPER FUNCTIONS ---

def get_latest_version_data():
    """Fetches version manifest to find the URL for latest release's JSON."""
    try:
        logging.info(f'Fetching manifest from {MANIFEST_URL}')
        response = requests.get(MANIFEST_URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        latest_version = data['latest']['release']
        logging.info(f'Found latest release version: {latest_version}')

        for version in data['versions']:
            if version['id'] == latest_version:
                return latest_version, version['url']

        logging.warning(f'Version URL for {latest_version} not found in manifest.')
        return None, None

    except requests.exceptions.Timeout:
        logging.error("Timeout error: Mojang's server took too long to respond.")
        return None, None
    except requests.exceptions.RequestException as e:
        logging.error(f'Network error fetching manifest: {e}')
        return None, None
    except json.JSONDecodeError:
        logging.error('Error parsing manifest JSON. The response might be corrupted.')
        return None, None
    except Exception as e:
        logging.error(f'Unexpected error fetching manifest: {e}', exc_info=True)
        return None, None

def get_client_jar_url(version_url):
    """Fetches version-specific JSON to find client.jar download URL."""
    try:
        logging.info('Fetching version-specific JSON URL...')
        response = requests.get(version_url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logging.error(f'Error fetching version-specific JSON: {e}')
        return None

    try:
        logging.info('Fetching client JAR URL...')
        return data['downloads']['client']['url']
    except Exception as e:
        logging.error(f'Error extracting client URL from JSON: {e}', exc_info=True)
        return None

def extract_data_from_memory(jar_url):
    """Downloads JAR to RAM and extracts enchantment and job data."""
    logging.info(f'Downloading client.jar into memory (this may take a moment)...')
    try:
        response = requests.get(jar_url, timeout=(10, 120))
        response.raise_for_status()
        jar_bytes = io.BytesIO(response.content)
    except Exception as e:
        logging.error(f'Error downloading client.jar from Mojang: {e}')
        return [], []

    try:
        parsed_enchantments = []
        parsed_jobs = []
        expected_enchant_ids = set()
        expected_job_ids = []

        logging.info('Unzipping and parsing files in memory...')

        with zipfile.ZipFile(jar_bytes) as jar:
            # 1. Identify tradeable enchantments from tags
            for tag_path in ['data/minecraft/tags/enchantment/tradeable.json',
                             'data/minecraft/tags/enchantment/non_treasure.json']:
                if tag_path in jar.namelist():
                    with jar.open(tag_path) as tag_file:
                        tag_data = json.load(tag_file)
                        for item in tag_data.get('values', []):
                            if not item.startswith('#'):
                                expected_enchant_ids.add(item.split(':')[-1])

            logging.info(f'Identified {len(expected_enchant_ids)} tradeable enchantments from tags.')

            # 2. Extract tradeable enchantments and jobs
            for file_info in jar.infolist():

                # --- A. ENCHANTMENTS ---
                if file_info.filename.startswith('data/minecraft/enchantment/') and file_info.filename.endswith('.json'):
                    with jar.open(file_info) as file:
                        data = json.load(file)
                        description = data.get('description')

                        if not description:
                            raise ValueError(f"Missing 'description' field in {file_info.filename}")

                        if isinstance(description, dict):
                            raw_name = description.get('translate')
                            if not raw_name:
                                raise ValueError(f"Missing 'translate' key in {file_info.filename}")
                        else:
                            raw_name = str(description)

                        clean_name = raw_name.split('.')[-1]

                        supported_items = data.get('supported_items')
                        clean_items = str(supported_items).split('/')[-1] if supported_items else 'unknown'

                        if clean_name in expected_enchant_ids:
                            parsed_enchantments.append({
                                'enchantment': clean_name,
                                'max_level': data.get('max_level'),
                                'supported_items': clean_items
                            })

                # --- B. JOBS ---
                elif file_info.filename == 'data/minecraft/tags/point_of_interest_type/acquirable_job_site.json':
                    with jar.open(file_info) as file:
                        data = json.load(file)
                        expected_job_ids = data.get('values', [])

                        logging.info(f'Identified {len(expected_job_ids)} possible jobs in tags.')

                        for raw_job in expected_job_ids:
                            parsed_jobs.append({'job': raw_job.split(':')[-1]})

        logging.info(f'Successfully parsed {len(parsed_enchantments)} tradeable enchantments.')
        logging.info(f'Successfully parsed {len(parsed_jobs)} possible jobs.')

        if len(parsed_enchantments) != len(expected_enchant_ids):
            logging.warning(
                f'Enchantment count mismatch! Tags expected {len(expected_enchant_ids)}, '
                f'but parsed {len(parsed_enchantments)}.'
            )
            return [], []
        
        if len(parsed_jobs) != len(expected_job_ids):
            logging.warning(
                f'Job count mismatch! Expected {len(expected_job_ids)}, '
                f'but parsed {len(parsed_jobs)}.'
            )
            return [], []

        return parsed_enchantments, parsed_jobs

    except zipfile.BadZipFile:
        logging.error('Downloaded client.jar is corrupted or not a valid ZIP file.')
        return [], []
    except Exception as e:
        logging.error(f'Error extracting data from client.jar: {e}', exc_info=True)
        return [], []

# --- MAIN LOGIC ---

def run_etl():
    latest_version, version_url = get_latest_version_data()

    if latest_version and version_url:

        client_url = get_client_jar_url(version_url)

        if client_url:
            enchantments, jobs = extract_data_from_memory(client_url)

            if enchantments and jobs:
                # DB: Consider refactoring into new helper function
                try:
                    df_ench = pd.DataFrame(enchantments).sort_values('enchantment').reset_index(drop=True)
                    df_jobs = pd.DataFrame(jobs).sort_values('job').reset_index(drop=True)

                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()

                        logging.info(f'Connecting to database at: {DB_PATH}')

                        cursor.execute("""
                            SELECT name FROM sqlite_master
                            WHERE type='table' AND name='enchantments';
                        """)
                        ench_exists = cursor.fetchone()

                        cursor.execute("""
                            SELECT name FROM sqlite_master
                            WHERE type='table' AND name='jobs';
                        """)
                        jobs_exists = cursor.fetchone()

                        if ench_exists and jobs_exists:
                            logging.info('Comparing source data against existing database records...')

                            df_existing_ench = pd.read_sql_query('SELECT * FROM enchantments ORDER BY enchantment', conn)
                            df_existing_jobs = pd.read_sql_query('SELECT * FROM jobs ORDER BY job', conn)

                            if df_ench.equals(df_existing_ench) and df_jobs.equals(df_existing_jobs):
                                logging.info(f'Database integrity verified. Data exactly matches Minecraft {latest_version}. No update required.')
                                return

                        logging.info('Database changes or missing tables detected. Updating database...')

                        cursor.execute('DROP TABLE IF EXISTS enchantments')
                        cursor.execute('DROP TABLE IF EXISTS jobs')

                        cursor.execute("""
                            CREATE TABLE IF NOT EXISTS enchantments (
                                enchantment TEXT PRIMARY KEY,
                                max_level INTEGER NOT NULL CHECK (max_level BETWEEN 1 AND 5),
                                supported_items TEXT NOT NULL
                            );
                        """)

                        cursor.execute("""
                            CREATE TABLE IF NOT EXISTS jobs (
                                job TEXT PRIMARY KEY
                            );
                        """)

                        df_ench.to_sql('enchantments', conn, if_exists='append', index=False)
                        df_jobs.to_sql('jobs', conn, if_exists='append', index=False)

                        logging.info(f'SUCCESS: Loaded {len(df_ench)} tradeable enchantments and {len(df_jobs)} possible jobs for Minecraft {latest_version}')
                
                except sqlite3.IntegrityError as e:
                    logging.error(f'Data integrity error: {e}', exc_info=True)
                except sqlite3.Error as e:
                    logging.error(f'Database error: {e}', exc_info=True)

            else:
                logging.warning('No data extracted. Database not updated.')

# --- MAIN EXECUTION ---

if __name__ == '__main__':
    logging.info('--- Starting ETL Pipeline ---')
    run_etl()
    logging.info('--- ETL Pipeline Finished ---')
