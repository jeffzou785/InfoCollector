#!/usr/bin/env python3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import json
import os
import re

# 读取RSS内容
home = os.path.expanduser('~')
input_file = f'{home}/.claude/projects/-Users-quartet-data-elements/fec0b881-4af7-4f28-b2c6-33be036a0bba/tool-results/b1ivsto20.txt'
raw_content = open(input_file, 'r', encoding='utf-8', errors='ignore').read()
root = ET.fromstring(raw_content)

# 时间参数
cutoff_str = '2026-06-10T00:10:41+08:00'
cutoff_dt = datetime.fromisoformat(cutoff_str.replace('+08:00', ''))
window_days = 1
start_dt = cutoff_dt - timedelta(days=window_days)

start_date = start_dt.strftime('%Y-%m-%d')
cutoff_date = cutoff_dt.strftime('%Y-%m-%d')

print(f"时间窗口: {start_date} 到 {cutoff_date}\n")

# 提取items
items = []
for elem in root.findall('.//item'):
    try:
        title_elem = elem.find('title')
        title = title_elem.text if title_elem is not None else ''
        title = title.strip()

        link_elem = elem.find('link')
        link = link_elem.text if link_elem is not None else ''

        pub_date_elem = elem.find('pubDate')
        pub_date_str = pub_date_elem.text if pub_date_elem is not None and pub_date_elem.text else ''

        pub_date = None
        if pub_date_str:
            try:
                pub_dt = datetime.strptime(pub_date_str[:25].strip(), '%a, %d %b %Y %H:%M:%S')
                pub_date = pub_dt.strftime('%Y-%m-%d')
            except:
                pass

        if not title or not link:
            continue

        desc_elem = elem.find('description')
        description = desc_elem.text if desc_elem is not None else ''
        if description:
            description = re.sub(r'<[^>]+>', ' ', description)
            description = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', description, flags=re.DOTALL)
            description = re.sub(r'\s+', ' ', description).strip()[:500]

        title = title.replace('"', '"').replace('"', '"')
        description = description.replace('"', '"').replace('"', '"')

        items.append({
            'title': title,
            'link': link,
            'pubDate': pub_date,
            'description': description
        })
    except:
        continue

print(f"总文章数: {len(items)}")

# 时间过滤
filtered = [item for item in items if item.get('pubDate') and start_date <= item['pubDate'] <= cutoff_date]
print(f"时间过滤后: {len(filtered)}")

# 输出JSON
output = {
    "source": {
        "name": "数据要素社",
        "url": "http://localhost:5001/api/rss/Mzg2MDgzNDEzMw==",
        "feed_url": "http://localhost:5001/api/rss/Mzg2MDgzNDEzMw==",
        "extracted_at": datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00')
    },
    "filter": {
        "cutoff": cutoff_str,
        "window_days": window_days,
        "start": start_dt.isoformat() + '+08:00'
    },
    "stats": {
        "total": len(items),
        "after_time_filter": len(filtered)
    },
    "items": filtered[:20]
}

output_file = '/Users/quartet/data-elements/reports/2026-06-10/数据要素社-raw.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n输出文件: {output_file}")
print(f"\n过滤后的文章:")
for i, item in enumerate(filtered):
    print(f"{i+1}. {item['pubDate']} - {item['title'][:50]}")
