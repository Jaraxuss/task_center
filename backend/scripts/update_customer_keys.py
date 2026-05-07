
import re
import sqlite3

from pypinyin import Style, pinyin

DB_PATH = "backend/data/task_center.db"

def get_slug(name):
    # Use pypinyin to get the phonetic representation
    p = pinyin(name, style=Style.NORMAL)
    slug = "".join([item[0] for item in p]).lower()
    # Remove any non-alphanumeric characters just in case
    slug = re.sub(r'[^a-z0-9]', '', slug)
    return slug

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Get all customers
    cursor.execute("SELECT id, name, key FROM customers")
    customers = cursor.fetchall()

    used_keys = set()
    update_count = 0

    print(f"Starting to update keys for {len(customers)} customers...")

    for customer_id, name, old_key in customers:
        new_slug = get_slug(name)
        
        # Handle uniqueness
        base_slug = new_slug
        counter = 1
        while new_slug in used_keys:
            new_slug = f"{base_slug}-{counter}"
            counter += 1
        
        used_keys.add(new_slug)

        if new_slug != old_key:
            print(f"Updating ID {customer_id}: '{name}' | '{old_key}' -> '{new_slug}'")
            cursor.execute("UPDATE customers SET key = ? WHERE id = ?", (new_slug, customer_id))
            update_count += 1
        else:
            print(f"Skipping ID {customer_id}: '{name}' | Key is already '{new_slug}'")

    conn.commit()
    conn.close()
    print(f"Finished. Updated {update_count} customer keys.")

if __name__ == "__main__":
    main()
