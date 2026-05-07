
import json
import re
import sqlite3
from datetime import datetime

DB_PATH = "backend/data/task_center.db"
ALIASES_PATH = "/home/velen/.openclaw/workspace/memory/customer_aliases.json"

def slugify(text):
    # Very basic slugify for Chinese if pypinyin is not available
    # Just lowercase and remove non-alphanumeric
    text = text.lower()
    text = re.sub(r'[^a-z0-9\-]', '', text)
    return text

def main():
    # 1. Load aliases
    with open(ALIASES_PATH, encoding='utf-8') as f:
        aliases_raw = json.load(f)
    
    # Target name -> list of aliases
    canonical_to_aliases = {}
    for alias, full_name_prefixed in aliases_raw.items():
        name = full_name_prefixed.replace("客户_", "")
        if name not in canonical_to_aliases:
            canonical_to_aliases[name] = set()
        canonical_to_aliases[name].add(full_name_prefixed)
        canonical_to_aliases[name].add(alias)

    # 2. Connect to DB and get projects from tasks
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT project FROM tasks WHERE project LIKE '客户_%'")
    task_projects = [row[0] for row in cursor.fetchall()]
    
    for p in task_projects:
        name = p.replace("客户_", "")
        if name not in canonical_to_aliases:
            canonical_to_aliases[name] = set()
        canonical_to_aliases[name].add(p)

    # 3. Get existing customers
    cursor.execute("SELECT name FROM customers")
    existing_names = {row[0] for row in cursor.fetchall()}

    # 4. Insert new customers
    now = datetime.utcnow().isoformat() + "Z"
    
    # Try to import pypinyin for better slugs
    try:
        from pypinyin import Style, pinyin
        def get_slug(name):
            p = pinyin(name, style=Style.NORMAL)
            return "".join([item[0] for item in p]).lower()
    except ImportError:
        def get_slug(name):
            # Fallback to just name or some placeholder if we can't do pinyin
            # User can manually fix later if needed
            return re.sub(r'[^a-z0-9]', '', name.lower()) or "customer-" + str(hash(name))[:8]

    new_customers_count = 0
    for name, aliases in canonical_to_aliases.items():
        if name in existing_names:
            print(f"Skipping existing customer: {name}")
            continue
        
        slug = get_slug(name)
        # Ensure slug is unique if it's already used
        cursor.execute("SELECT id FROM customers WHERE key = ?", (slug,))
        if cursor.fetchone():
            slug = f"{slug}-{new_customers_count}"
        
        aliases_list = sorted(list(aliases))
        aliases_json = json.dumps(aliases_list, ensure_ascii=False)
        tags_json = json.dumps(["初始导入"], ensure_ascii=False)
        
        print(f"Creating customer: {name} (key: {slug}, aliases: {aliases_json})")
        
        cursor.execute("""
            INSERT INTO customers (name, key, aliases_json, status, description, area, tags_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, slug, aliases_json, 'active', f"初始批量导入: {name}", None, tags_json, now, now))
        new_customers_count += 1

    conn.commit()
    conn.close()
    print(f"Successfully added {new_customers_count} new customers.")

if __name__ == "__main__":
    main()
