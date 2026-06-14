#!/usr/bin/env python3
import xml.etree.ElementTree as ET
from datetime import datetime
import os

home = os.path.expanduser('~')
input_file = f'{home}/.claude/projects/-Users-quartet-data-elements/fec0b881-4af7-4f28-b2c6-33be036a0bba/tool-results/b1ivsto20.txt'

raw_content = open(input_file, 'r', encoding='utf-8', errors='ignore').read()
root = ET.fromstring(raw_content)

items = root.findall('.//item')

print("前10条文章的日期解析:")
print("-" * 80)

for i, elem in enumerate(items[:10]):
    title_elem = elem.find('title')
    title = title_elem.text if title_elem is not None else '(无标题)'

    pub_date_elem = elem.find('pubDate')
    pub_date_str = pub_date_elem.text if pub_date_elem is not None and pub_date_elem.text else ''

    print(f"\n{i+1}. {title[:50]}")
    print(f"   原始日期: {pub_date_str}")

    if pub_date_str:
        try:
            pub_dt = datetime.strptime(pub_date_str[:25].strip(), '%a, %d %b %Y %H:%M:%S')
            pub_date = pub_dt.strftime('%Y-%m-%d')
            print(f"   解析后: {pub_date}")
        except Exception as e:
            print(f"   解析失败: {e}")
    else:
        print("   无日期")

print("\n" + "-" * 80)
print("\n时间窗口: 2026-06-09 到 2026-06-10")
