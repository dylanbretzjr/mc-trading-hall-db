# Minecraft Villager Trading Database

## Overview

This project is a Python-based ETL and data management system for Minecraft villager trading. It automates the extraction of game data directly from Minecraft's source files and provides an interactive interface for tracking individual villager trades across different locations.

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
