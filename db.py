import sqlite3

conn = sqlite3.connect("ritul.db")
cursor = conn.cursor()

cursor.execute("""
select * from CATEGORY;
""")

for row in cursor.fetchall():
    print(row)

conn.commit()
conn.close()

print("Database and table created!")