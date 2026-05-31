
import json
import sqlite3
from datetime import datetime

DB_PATH = "backend/data/task_center.db"

def update_aliases(cursor, customer_id, add_aliases=None, remove_aliases=None):
    cursor.execute("SELECT aliases_json FROM customers WHERE id = ?", (customer_id,))
    row = cursor.fetchone()
    if not row:
        return
    
    aliases = set(json.loads(row[0]))
    
    if add_aliases:
        for a in add_aliases:
            aliases.add(a)
    
    if remove_aliases:
        for r in remove_aliases:
            if r in aliases:
                aliases.remove(r)
    
    new_aliases_json = json.dumps(sorted(list(aliases)), ensure_ascii=False)
    cursor.execute("UPDATE customers SET aliases_json = ?, updated_at = ? WHERE id = ?", 
                   (new_aliases_json, datetime.utcnow().isoformat() + "Z", customer_id))

def merge_customers(cursor, source_id, target_id):
    # Tables with customer_id column
    tables = ["tasks", "facts", "customer_materials", "projects"]
    for table in tables:
        cursor.execute(f"UPDATE {table} SET customer_id = ? WHERE customer_id = ?", (target_id, source_id))
    
    # After updating references, delete the source customer
    cursor.execute("DELETE FROM customers WHERE id = ?", (source_id,))

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Update aliases
        # 客户_D (31): + 客户_D Alias
        update_aliases(cursor, 31, add_aliases=["客户_D Alias"])
        
        # 客户_A (28): + 客户_A, 客户_A
        update_aliases(cursor, 28, add_aliases=["客户_A", "客户_A"])
        
        # 客户_C (23): + 客户_C
        update_aliases(cursor, 23, add_aliases=["客户_C"])
        
        # 客户_C (19): + 客户_C
        update_aliases(cursor, 19, add_aliases=["客户_C"])
        
        # 客户_E (12): + 客户_E Alias A, 客户_E Alias B
        update_aliases(cursor, 12, add_aliases=["客户_E Alias A", "客户_E Alias B"])
        
        # 客户_F (26): + 客户_F Alias
        update_aliases(cursor, 26, add_aliases=["客户_F Alias"])
        
        # 客户_G (27): + 客户_G Alias
        update_aliases(cursor, 27, add_aliases=["客户_G Alias"])
        
        # 客户_H (35): + 客户_H Alias
        update_aliases(cursor, 35, add_aliases=["客户_H Alias"])
        
        # 客户_I (13): + 客户_I Alias
        update_aliases(cursor, 13, add_aliases=["客户_I Alias"])
        
        # 客户_J (8): + 客户_J Alias A, 客户_J Alias B
        update_aliases(cursor, 8, add_aliases=["客户_J Alias A", "客户_J Alias B"])
        
        # 客户_K (3): - 客户_K Alias A, 客户_K Alias B
        update_aliases(cursor, 3, remove_aliases=["客户_K Alias A", "客户_K Alias B"])

        # 2. Merges
        # 29-客户_A -> 28-客户_A
        print("Merging 29 -> 28")
        merge_customers(cursor, 29, 28)
        
        # 15-客户_B -> 4-客户_B
        print("Merging 15 -> 4")
        merge_customers(cursor, 15, 4)
        
        # 22-客户_C -> 23-客户_C
        print("Merging 22 -> 23")
        merge_customers(cursor, 22, 23)
        
        # 17-客户_C -> 19-客户_C
        print("Merging 17 -> 19")
        merge_customers(cursor, 17, 19)

        # 3. Deletions (not customers)
        print("Deleting 36, 37, 38")
        cursor.execute("DELETE FROM customers WHERE id IN (36, 37, 38)")

        conn.commit()
        print("Data refinement completed successfully.")
        
    except Exception as e:
        conn.rollback()
        print(f"Error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
