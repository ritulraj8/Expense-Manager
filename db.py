import sqlite3

db_file = "ritul.db"
output_file = "output.txt"

conn = sqlite3.connect(db_file)
cursor = conn.cursor()

with open(output_file, "w", encoding="utf-8") as f:

    cursor.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type='table';
    """)

    tables = cursor.fetchall()

    for table in tables:
        table_name = table[0]

        f.write("\n" + "=" * 60 + "\n")
        f.write(f"TABLE: {table_name}\n")
        f.write("=" * 60 + "\n")

        # Column names
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        f.write(f"Columns: {columns}\n\n")

        # Table contents
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        if not rows:
            f.write("No data found.\n")
        else:
            for row in rows:
                f.write(str(row) + "\n")

        f.write("\n")

conn.close()

print(f"Database contents saved to {output_file}")