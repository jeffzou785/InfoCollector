#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs
import email.utils

class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):
        self.text.append(data)

    def get_text(self):
        return ''.join(self.text).strip()

def strip_html(html_content):
    if not html_content:
        return ""
    extractor = HTMLTextExtractor()
    extractor.feed(html_content)
    return extractor.get_text()

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'[​‌‍⁠﻿­]', '', text)
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    return text.strip()

def escape_json_quotes(text):
    if not text:
        return ""
    text = text.replace('"', '"')
    text = text.replace('"', '"')
    text = text.replace('"', "'")
    return text

def clean_description(description, max_length=500):
    if not description:
        return ""
    desc = strip_html(description)
    if desc.startswith('<![CDATA['):
        desc = desc[9:]
    if desc.endswith(']]>'):
        desc = desc[:-3]
    desc = clean_text(desc)
    desc = escape_json_quotes(desc)
    if len(desc) > max_length:
        desc = desc[:max_length].rstrip()
    return desc

def clean_title(title):
    if not title:
        return ""
    title = clean_text(title)
    title = escape_json_quotes(title)
    return title

def clean_url(url):
    if not url:
        return ""
    url = url.strip()
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        tracking_params = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                          'fbclid', 'gclid', 'msclkid', '_ga', '_gid'}
        filtered_params = {k: v for k, v in query_params.items() if k not in tracking_params}
        if filtered_params:
            from urllib.parse import urlencode
            new_query = urlencode(filtered_params, doseq=True)
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"
        else:
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except:
        return url

def parse_date(date_str):
    if not date_str:
        return None
    # 使用 email.utils 解析 RFC 2822 格式日期
    try:
        timestamp = email.utils.parsedate_to_datetime(date_str)
        return timestamp.strftime('%Y-%m-%d')
    except:
        pass
    
    # 尝试其他格式
    formats = [
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%d',
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None

def parse_rss_feed(xml_content):
    root = ET.fromstring(xml_content)
    channel = root.find('.//channel')
    if channel is None:
        channel = root

    items = []
    for item in channel.findall('.//item'):
        title_elem = item.find('title')
        link_elem = item.find('link')
        desc_elem = item.find('description')
        pubdate_elem = item.find('pubDate')

        title = clean_title(title_elem.text if title_elem is not None and title_elem.text else '')
        link = clean_url(link_elem.text if link_elem is not None and link_elem.text else '')
        description = clean_description(desc_elem.text if desc_elem is not None and desc_elem.text else '')
        pub_date = parse_date(pubdate_elem.text if pubdate_elem is not None and pubdate_elem.text else '')

        if not title or not link:
            continue

        items.append({
            'title': title,
            'link': link,
            'pubDate': pub_date,
            'description': description
        })

    if not items:
        for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
            title_elem = entry.find('{http://www.w3.org/2005/Atom}title')
            link_elem = entry.find('{http://www.w3.org/2005/Atom}link')
            summary_elem = entry.find('{http://www.w3.org/2005/Atom}summary')
            pub_elem = entry.find('{http://www.w3.org/2005/Atom}published')
            updated_elem = entry.find('{http://www.w3.org/2005/Atom}updated')

            title = clean_title(title_elem.text if title_elem is not None and title_elem.text else '')
            link = clean_url(link_elem.get('href', '') if link_elem is not None else '')
            description = clean_description(summary_elem.text if summary_elem is not None and summary_elem.text else '')
            pub_date = parse_date((pub_elem.text if pub_elem is not None else None) or
                                 (updated_elem.text if updated_elem is not None else None))

            if not title or not link:
                continue

            items.append({
                'title': title,
                'link': link,
                'pubDate': pub_date,
                'description': description
            })

    return items

def filter_by_time(items, cutoff_timestamp, window_days):
    try:
        cutoff_dt = datetime.fromisoformat(cutoff_timestamp.replace('+08:00', '+00:00').replace('Z', '+00:00'))
        if cutoff_dt.tzinfo is None:
            cutoff_dt = cutoff_dt.replace(tzinfo=timezone.utc)
    except:
        cutoff_dt = datetime.now(timezone.utc)

    start_dt = cutoff_dt - timedelta(days=window_days)

    filtered_items = []
    for item in items:
        pub_date = item.get('pubDate')
        if not pub_date:
            continue

        try:
            # pub_date 是 YYYY-MM-DD 格式，需要转换为 UTC 时间进行比较
            # 假设文章发布时间是当天的任何时间，使用当天的开始时间（00:00:00 UTC）
            item_dt = datetime.strptime(pub_date, '%Y-%m-%d')
            item_dt = item_dt.replace(tzinfo=timezone.utc)
            
            # 为了更准确的时间比较，使用当天的结束时间（23:59:59 UTC）
            item_end_dt = item_dt.replace(hour=23, minute=59, second=59)
            
            # 检查时间窗口：文章发布日期是否在 [起始时间, 截止时间] 范围内
            # 我们检查文章日期（使用当天的结束时间）是否大于等于起始时间
            # 且文章日期（使用当天的开始时间）是否小于等于截止时间
            if item_end_dt >= start_dt and item_dt <= cutoff_dt:
                filtered_items.append(item)
        except Exception as e:
            print(f"Error parsing date {pub_date}: {e}", file=sys.stderr)
            continue

    return filtered_items[:20]

def main():
    if len(sys.argv) < 6:
        print("Usage: python parse_rss_single.py <source_name> <source_url> <feed_url> <cutoff_timestamp> <window_days> <output_dir>")
        sys.exit(1)

    source_name = sys.argv[1]
    source_url = sys.argv[2]
    feed_url = sys.argv[3]
    cutoff_timestamp = sys.argv[4]
    window_days = int(sys.argv[5])
    output_dir = sys.argv[6]

    xml_content = sys.stdin.read()
    items = parse_rss_feed(xml_content)
    total_items = len(items)

    filtered_items = filter_by_time(items, cutoff_timestamp, window_days)

    try:
        cutoff_dt = datetime.fromisoformat(cutoff_timestamp.replace('+08:00', '+00:00').replace('Z', '+00:00'))
        if cutoff_dt.tzinfo is None:
            cutoff_dt = cutoff_dt.replace(tzinfo=timezone.utc)
        start_dt = cutoff_dt - timedelta(days=window_days)
        start_timestamp = start_dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
    except:
        start_timestamp = cutoff_timestamp

    output_data = {
        'source': {
            'name': source_name,
            'url': source_url,
            'feed_url': feed_url,
            'extracted_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')
        },
        'filter': {
            'cutoff': cutoff_timestamp,
            'window_days': window_days,
            'start': start_timestamp
        },
        'stats': {
            'total': total_items,
            'after_time_filter': len(filtered_items)
        },
        'items': filtered_items
    }

    output_file = f"{output_dir}/{source_name}-raw.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"✅ {source_name} 数据提取完成")
    print(f"\n📊 统计:")
    print(f"- Feed 总条目: {total_items}")
    print(f"- 时间过滤后: {len(filtered_items)}")
    print(f"\n📁 输出文件: {output_file}")

if __name__ == '__main__':
    main()
