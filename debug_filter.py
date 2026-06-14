#!/usr/bin/env python3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import os
import re

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

print(f"时间窗口:")
print(f"  起始: {start_date}")
print(f"  截止: {cutoff_date}")
print()

items = root.findall('.//item')
filtered = []

for elem in items:
    title_elem = elem.find('title')
    title = title_elem.text if title_elem is not None else ''

    pub_date_elem = elem.find('pubDate')
    pub_date_str = pub_date_elem.text if pub_date_elem is not None and pub_date_elem.text else ''

    pub_date = None
    if pub_date_str:
        try:
            pub_dt = datetime.strptime(pub_date_str[:25].strip(), '%a, %d %b %Y %H:%M:%S')
            pub_date = pub_dt.strftime('%Y-%m-%d')
        except:
            pass

    if pub_date and start_date <= pub_date <= cutoff_date:
        filtered.append((title[:60], pub_date))

print(f"符合时间窗口的文章 ({len(filtered)} 条):")
print("-" * 80)
for i, (title, date) in enumerate(filtered[:20]):
    print(f"{i+1}. {date} - {title}")
