#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minecraft Trading Data ETL Pipeline
Filename: mc_trading_etl.py
Author: Dylan Bretz Jr.
Date: 2026-02-06

Description:
This script performs an ETL (Extract, Transform, Load) process to gather
data about Minecraft enchantments and villager jobs from the latest Minecraft
client JAR file. The data is extracted directly from the JAR file in memory,
cleaned, and then loaded into a SQLite database.

Flow:
    1. Fetch version manifest from piston-meta
    2. Parse JSON to extract latest release version
    3. Parse JSON to extract URL for latest release's JSON
    4. Download client.jar into RAM
    5. Extract enchantment and job data from JAR in memory
    6. Load cleaned data into SQLite database
    7. Print summary of loaded data

Input:
- Latest Minecraft client JAR file (downloaded into RAM)

Output:
- SQLite database file (mc_trading.db) with two tables:
    1. enchantments
    2. jobs

Requirements:
- requests
- pandas

TODO:
- [ ] Add error handling for network issues and JSON parsing
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

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest.json"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)

def get_latest_version_url():
    """Fetches version manifest to find the URL for latest release's JSON."""
    try:
        logging.info(f"Fetching manifest from {MANIFEST_URL}")
        response = requests.get(MANIFEST_URL)
        response.raise_for_status()
        data = response.json()

        latest_version = data["latest"]["release"]
        logging.info(f"Found latest release version: {latest_version}")

        for version in data["versions"]:
            if version["id"] == latest_version:
                return version["url"]

        logging.warning(f"Version URL for {latest_version} not found in manifest.")

        return None

    except Exception as e:
        logging.error(f"Error fetching manifest: {e}", exc_info=True)
        return None

def get_client_jar_url(version_url):
    """Fetches version-specific JSON to find client.jar download URL."""
    try:
        logging.info("Fetching client JAR URL...")
        response = requests.get(version_url)
        response.raise_for_status()
        data = response.json()
        return data["downloads"]["client"]["url"]
    except Exception as e:
        logging.error(f"Error extracting client URL: {e}", exc_info=True)
        return None

def extract_data_from_memory(jar_url):
    """Downloads JAR to RAM and extracts enchantment and job data."""
    logging.info(f"Downloading client.jar into memory (this may take a moment)...")
    try:
        response = requests.get(jar_url)
        response.raise_for_status()
        jar_bytes = io.BytesIO(response.content)

        enchant_list = []
        job_list = []
        tradeable_ids = set()

        with zipfile.ZipFile(jar_bytes) as jar:
            logging.info("Unzipping and parsing files in memory...")

            # 1. Identify tradeable enchantments from tags
            for tag_path in ['data/minecraft/tags/enchantment/tradeable.json',
                             'data/minecraft/tags/enchantment/non_treasure.json']:
                if tag_path in jar.namelist():
                    with jar.open(tag_path) as tag_file:
                        tag_data = json.load(tag_file)
                        for item in tag_data.get('values', []):
                            if not item.startswith('#'):
                                    tradeable_ids.add(item.split(':')[-1])

            logging.info(f"Found {len(tradeable_ids)} tradeable enchantments.")

            # 2. Extract tradeable enchantments and jobs
            for file_info in jar.infolist():

                # --- A. ENCHANTMENTS ---
                if file_info.filename.startswith("data/minecraft/enchantment/") and file_info.filename.endswith(".json"):
                    with jar.open(file_info) as file:
                        data = json.load(file)

                        # Cleaning Logic
                        clean_name = data.get('description', {}).get('translate').split('.')[-1]
                        
                        supported_items = data.get('supported_items')
                        clean_items = str(supported_items).split('/')[-1] if supported_items else "unknown"
                        
                        if clean_name in tradeable_ids:
                            enchant_list.append({
                                "enchantment": clean_name,
                                "max_level": data.get('max_level'),
                                "supported_items": clean_items
                            })

                # --- B. JOBS ---
                elif file_info.filename == "data/minecraft/tags/point_of_interest_type/acquirable_job_site.json":
                    with jar.open(file_info) as file:
                        data = json.load(file)

                        for raw_job in data.get('values', []):
                            job_list.append({'job': raw_job.split(':')[-1]})

        return enchant_list, job_list

    except Exception as e:
        logging.error(f"Error processing JAR: {e}", exc_info=True)
        return [], []

# --- MAIN EXECUTION ---

if __name__ == "__main__":
    logging.info("--- Starting ETL Pipeline ---")

    version_url = get_latest_version_url()

    if version_url:
        client_url = get_client_jar_url(version_url)

        if client_url:
            enchantments, jobs = extract_data_from_memory(client_url)

            # 2. Database Loading
            if enchantments and jobs:
                try:
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()

                        logging.info(f"Connecting to database at: {DB_PATH}")


                        cursor.execute("DROP TABLE IF EXISTS enchantments")
                        cursor.execute("DROP TABLE IF EXISTS jobs")

                        cursor.execute("""
                            CREATE TABLE IF NOT EXISTS enchantments (
                                enchantment TEXT PRIMARY KEY,
                                max_level INTEGER,
                                supported_items TEXT
                            )
                        """)

                        cursor.execute("""
                            CREATE TABLE IF NOT EXISTS jobs (
                                job TEXT PRIMARY KEY)
                        """)

                        df_ench = pd.DataFrame(enchantments).sort_values("enchantment")
                        df_ench.to_sql('enchantments', conn, if_exists='append', index=False)

                        df_jobs = pd.DataFrame(jobs).sort_values("job")
                        df_jobs.to_sql('jobs', conn, if_exists='append', index=False)

                        logging.info(f"SUCCESS: Loaded {len(df_ench)} tradeable enchantments and {len(df_jobs)} possible jobs.")
                
                except sqlite3.Error as e:
                    logging.error(f"Database error: {e}", exc_info=True)
            else:
                logging.warning("No data extracted. Database not updated.")
    logging.info("--- ETL Pipeline Finished ---")
