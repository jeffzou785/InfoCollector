#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import html
import re
from datetime import datetime, timedelta, timezone
import json
import sys

def clean_html(text):
    """去除 HTML 标签，只保留纯文本"""
    if not text:
        return ""
    # 去除 CDATA 包裹
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
    # 去除所有 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    # 解码 HTML 实体
    text = html.unescape(text)
    # 去除多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def clean_title(title):
    """清洗标题"""
    if not title:
        return None
    title = clean_html(title)
    # 去除零宽空格等特殊字符
    title = re.sub(r'[​‌‍⁠﻿]', '', title)
    title = title.strip()
    return title if title else None

def clean_link(link):
    """清洗链接"""
    if not link:
        return None
    link = link.strip()
    # 去除追踪参数
    link = re.sub(r'[?&](utm_[^&]*|fbclid|ref_[^&]*)', '', link)
    link = re.sub(r'\?$', '', link)  # 去除末尾单独的 ?
    return link if link else None

def parse_date(date_str):
    """解析日期为 YYYY-MM-DD 格式"""
    if not date_str:
        return None
    try:
        # 尝试多种日期格式
        formats = [
            '%a, %d %b %Y %H:%M:%S %z',
            '%a, %d %b %Y %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%d',
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                # 转换为时区无关的 YYYY-MM-DD
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                return dt.strftime('%Y-%m-%d')
            except (ValueError, IndexError):
                continue
        return None
    except:
        return None

def parse_rss_feed(xml_content, cutoff_date, window_days):
    """解析 RSS Feed 并执行时间过滤"""
    root = ET.fromstring(xml_content)

    # 确定时间范围
    start_date = cutoff_date - timedelta(days=window_days)

    items = []
    total_items = 0

    # RSS 2.0
    for item in root.findall('.//item'):
        total_items += 1

        title_elem = item.find('title')
        link_elem = item.find('link')
        desc_elem = item.find('description')
        date_elem = item.find('pubDate')

        title = clean_title(title_elem.text if title_elem is not None else None)
        link = clean_link(link_elem.text if link_elem is not None else None)
        pub_date = parse_date(date_elem.text if date_elem is not None else None)

        # 跳过缺失关键字段的条目
        if not title or not link:
            continue

        # 描述截断
        description = clean_html(desc_elem.text if desc_elem is not None else "")
        if description:
            description = description[:500]

        # 时间过滤
        if pub_date:
            try:
                item_date = datetime.strptime(pub_date, '%Y-%m-%d').date()
                if start_date.date() <= item_date <= cutoff_date.date():
                    items.append({
                        'title': title,
                        'link': link,
                        'pubDate': pub_date,
                        'description': description
                    })
            except ValueError:
                # pubDate 解析失败，跳过
                pass

    # 最多保留 20 条
    return items[:20], total_items

def main():
    # 读取参数
    if len(sys.argv) < 6:
        print("Usage: parse_rss_feed.py <xml_file> <source_name> <source_url> <feed_url> <cutoff_iso> <window_days> <output_dir>", file=sys.stderr)
        sys.exit(1)

    xml_file = sys.argv[1]
    source_name = sys.argv[2]
    source_url = sys.argv[3]
    feed_url = sys.argv[4]
    cutoff_iso = sys.argv[5]
    window_days = int(sys.argv[6])
    output_dir = sys.argv[7]

    # 读取 XML
    with open(xml_file, 'r', encoding='utf-8') as f:
        xml_content = f.read()

    # 解析截止时间
    try:
        cutoff_date = datetime.fromisoformat(cutoff_iso.replace('+08:00', '+00:00').replace('+00:00', ''))
    except:
        cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None)

    # 解析 RSS
    items, total_items = parse_rss_feed(xml_content, cutoff_date, window_days)

    # 构建输出
    output = {
        'source': {
            'name': source_name,
            'url': source_url,
            'feed_url': feed_url,
            'extracted_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')
        },
        'filter': {
            'cutoff': cutoff_iso,
            'window_days': window_days,
            'start': (cutoff_date - timedelta(days=window_days)).isoformat() + '+08:00'
        },
        'stats': {
            'total': total_items,
            'after_time_filter': len(items)
        },
        'items': items
    }

    # 保存 JSON
    output_file = f"{output_dir}/{source_name}-raw.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Total: {len(items)}, Filtered: {len(items)}")
    print(f"Output: {output_file}")

if __name__ == '__main__':
    main()
