# Skill: SQLite Database Administrator

## Overview
Use this skill when interacting with local SQLite databases (`.db` or `.sqlite` files).

## Workflow & Best Practices
1. **Inspection**: To see what tables exist in a SQLite database, connect to it and run: `SELECT name FROM sqlite_master WHERE type='table';`
2. **Schema**: To understand a table's structure, run: `PRAGMA table_info(table_name);`
3. **Querying**: Use the `execute_python` tool with the built-in `sqlite3` library to run queries and format the output nicely.
4. **Safety**: NEVER run `DROP TABLE` or `DELETE FROM` without an explicit user instruction and a `WHERE` clause. Always take a backup of the `.db` file (e.g., `cp data.db data.db.bak`) before performing bulk updates or deletions.

## Example Python Execution
```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('database.db')
df = pd.read_sql_query("SELECT * FROM users LIMIT 5", conn)
print(df.to_markdown())
conn.close()
```