# Minecraft Villager Trading Database

## Overview

This is a personal Python-based data management system for Minecraft villager trading using SQLite3 with an ETL pipeline and CLI tools, providing an effective interface for tracking, managing, and optimizing individual villager trades across different locations.

The ETL pipeline automates the extraction of game data directly from Minecraft's source files and loads the reference data into a SQLite3 database. The CLI tools provide a quick and easy way to add and update trades.

## Workflow

1. Run ETL script
2. Create additional tables with SQL
3. Add new librarian trades with `add_lib_trade.py`

## Creating Additional Tables

```sql
CREATE TABLE IF NOT EXISTS locations (
	location TEXT PRIMARY KEY,
	x_coord INTEGER,
	z_coord INTEGER
);
```

```sql
CREATE TABLE IF NOT EXISTS villagers (
	villager_id TEXT PRIMARY KEY,
	location TEXT,
	job TEXT,

	FOREIGN KEY(location) REFERENCES locations(location),
	FOREIGN KEY(job) REFERENCES jobs(job)
);
```

```sql
CREATE TABLE IF NOT EXISTS librarian_trades (
	trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
	villager_id TEXT,
	enchantment TEXT,
	enchantment_level INTEGER,
	cost_emeralds INTEGER,

	FOREIGN KEY(villager_id) REFERENCES villagers(villager_id),
	FOREIGN KEY(enchantment) REFERENCES enchantments(enchantment)
);
```
