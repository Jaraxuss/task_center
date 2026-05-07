
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
        # 童方元 (31): + 南京童方元
        update_aliases(cursor, 31, add_aliases=["南京童方元"])
        
        # 江苏润天医药 (28): + 江苏润天, 润天
        update_aliases(cursor, 28, add_aliases=["江苏润天", "润天"])
        
        # 无锡公安 (23): + 无锡GA
        update_aliases(cursor, 23, add_aliases=["无锡GA"])
        
        # 常熟公安 (19): + 常熟GA
        update_aliases(cursor, 19, add_aliases=["常熟GA"])
        
        # 华孚 (12): + 马鞍山华孚, 华孚精密
        update_aliases(cursor, 12, add_aliases=["马鞍山华孚", "华孚精密"])
        
        # 欧裳妮 (26): + 上海欧裳妮
        update_aliases(cursor, 26, add_aliases=["上海欧裳妮"])
        
        # 正大天晴 (27): + 南京正大天晴
        update_aliases(cursor, 27, add_aliases=["南京正大天晴"])
        
        # 麦豆健康 (35): + 南京麦豆健康
        update_aliases(cursor, 35, add_aliases=["南京麦豆健康"])
        
        # 南京初藜 (13): + 瑞纹娜
        update_aliases(cursor, 13, add_aliases=["瑞纹娜"])
        
        # 途牛科技 (8): + 南京途牛, 途牛
        update_aliases(cursor, 8, add_aliases=["南京途牛", "途牛"])
        
        # 苏中药业 (3): - 黄葵, 黄葵胶囊
        update_aliases(cursor, 3, remove_aliases=["黄葵", "黄葵胶囊"])

        # 2. Merges
        # 29-江苏润天医药-电商 -> 28-江苏润天医药
        print("Merging 29 -> 28")
        merge_customers(cursor, 29, 28)
        
        # 15-喵婉美 -> 4-无锡喵婉美
        print("Merging 15 -> 4")
        merge_customers(cursor, 15, 4)
        
        # 22-无锡GA -> 23-无锡公安
        print("Merging 22 -> 23")
        merge_customers(cursor, 22, 23)
        
        # 17-常熟GA -> 19-常熟公安
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
