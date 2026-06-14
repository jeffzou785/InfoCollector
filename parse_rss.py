#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import sys
import re
from datetime import datetime, timedelta, timezone
import html

def parse_rss_file(file_path, cutoff_str, window_days):
    """Parse RSS feed file and filter by time"""
    # Parse cutoff time
    try:
        cutoff = datetime.fromisoformat(cutoff_str.replace('+08:00', '').replace('Z', ''))
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone(timedelta(hours=8)))
        start_time = cutoff - timedelta(days=window_days)
    except:
        cutoff = datetime.now(timezone(timedelta(hours=8)))
        start_time = cutoff - timedelta(days=window_days)

    # Read file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse XML
    root = ET.fromstring(content)

    # Find channel/items
    channel = root.find('.//channel')
    if channel is None:
        return None

    items = channel.findall('.//item')
    parsed_items = []

    for item in items:
        try:
            title_elem = item.find('title')
            link_elem = item.find('link')
            pubDate_elem = item.find('pubDate')
            desc_elem = item.find('description')

            if title_elem is None or link_elem is None:
                continue

            title = title_elem.text or ''
            link = link_elem.text or ''
            pubDate_str = pubDate_elem.text if pubDate_elem is not None else None
            description = desc_elem.text if desc_elem is not None else ''

            # Clean title
            title = title.strip()
            title = re.sub(r'[​-‍﻿]', '', title)
            if not title or not link:
                continue

            # Clean link
            link = link.strip()

            # Parse pubDate
            pubDate = None
            if pubDate_str:
                try:
                    # Try RFC 2822 format
                    pubDate = datetime.strptime(pubDate_str, '%a, %d %b %Y %H:%M:%S %z')
                    pubDate = pubDate.strftime('%Y-%m-%d')
                except:
                    try:
                        pubDate = datetime.strptime(pubDate_str, '%a, %d %b %Y %H:%M:%S GMT')
                        pubDate = pubDate.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
                    except:
                        pubDate = None

            if pubDate is None:
                continue

            # Clean description (remove HTML tags)
            description = re.sub(r'<[^>]+>', '', description)
            description = html.unescape(description)
            description = description.strip()
            if len(description) > 500:
                description = description[:500]

            parsed_items.append({
                'title': title,
                'link': link,
                'pubDate': pubDate,
                'description': description
            })

        except Exception as e:
            continue

    # Time filter
    filtered_items = []
    cutoff_str_only = cutoff.strftime('%Y-%m-%d')
    start_str_only = start_time.strftime('%Y-%m-%d')

    for item in parsed_items:
        if item['pubDate']:
            if start_str_only <= item['pubDate'] <= cutoff_str_only:
                filtered_items.append(item)

    # Limit to 20 items
    filtered_items = filtered_items[:20]

    return {
        'total': len(parsed_items),
        'after_time_filter': len(filtered_items),
        'items': filtered_items
    }

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("Usage: parse_rss.py <xml_file> <cutoff_iso> <window_days>", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    cutoff = sys.argv[2]
    window = int(sys.argv[3])

    result = parse_rss_file(file_path, cutoff, window)
    if result:
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
