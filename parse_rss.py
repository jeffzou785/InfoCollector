#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import sys
from datetime import datetime, timedelta

# RSS 文件路径
rss_file = "/Users/quartet/.claude/projects/-Users-quartet-data-elements/67b4faad-74f6-4d16-9276-4f7469a06888/tool-results/bv6pexhvs.txt"

# 时间范围：过去7天
cutoff_date = datetime.now() - timedelta(days=7)

# 解析 RSS
tree = ET.parse(rss_file)
root = tree.getroot()

# 命名空间
ns = {'rss': 'http://purl.org/rss/1.0/'}

# 查找所有 item
items = root.findall('.//item')

print(f"总共找到 {len(items)} 篇文章\n")
print("=" * 80)

count = 0
for item in items:
    title = item.find('title')
    link = item.find('link')
    pub_date = item.find('pubDate')

    if title is not None and link is not None:
        title_text = title.text.strip() if title.text else ""
        link_text = link.text.strip() if link.text else ""

        # 解析时间
        if pub_date is not None and pub_date.text:
            try:
                # 解析 RFC 2822 时间格式
                date_obj = datetime.strptime(pub_date.text.strip(), "%a, %d %b %Y %H:%M:%S %z")
                # 转换为无时区时间以便比较
                date_obj = date_obj.replace(tzinfo=None)

                # 检查是否在7天内
                if date_obj >= cutoff_date:
                    count += 1
                    print(f"\n[{count}] {title_text}")
                    print(f"URL: {link_text}")
                    print(f"发布时间: {pub_date.text.strip()}")
                    print(f"本地时间: {date_obj.strftime('%Y-%m-%d %H:%M:%S')}")
                    print("-" * 80)
            except Exception as e:
                pass

print(f"\n\n过去7天内共有 {count} 篇文章")
