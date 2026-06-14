#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import json
import re
import sys
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, urlencode

def strip_html(text):
    if not text:
        return ""
    text = re.sub(r'<!\[CDATA\[|\]\]>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#39;', "'", text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def make_json_safe(text):
    if not text:
        return ""
    text = text.replace('"', "'")
    return text

def clean_url(url):
    if not url:
        return ""
    url = url.strip()
    try:
        parsed = urlparse(url)
        tracking_params = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'source', 'medium', 'campaign', 'ref', 'referrer', 'share'}
        query_params = parse_qs(parsed.query)
        filtered_params = {k: v for k, v in query_params.items() if k not in tracking_params}
        if filtered_params:
            new_query = urlencode(filtered_params, doseq=True)
            return parsed._replace(query=new_query).geturl()
        else:
            return parsed._replace(query='').geturl()
    except:
        return url

def parse_date(date_str):
    if not date_str:
        return None
    date_str = date_str.strip()
    formats = ['%a, %d %b %Y %H:%M:%S %z', '%a, %d %b %Y %H:%M:%S', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d', '%Y%m%d']
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except:
            continue
    date_str = re.sub(r'\s*[+-]\d{4}$', '', date_str)
    date_str = re.sub(r'\s*GMT$', '', date_str, flags=re.IGNORECASE)
    for fmt in formats[:3]:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except:
            continue
    return None

def parse_rss(xml_content):
    items = []
    try:
        root = ET.fromstring(xml_content)
        for item in root.findall('.//item'):
            title_elem = item.find('title')
            link_elem = item.find('link')
            desc_elem = item.find('description')
            date_elem = item.find('pubDate')

            title = strip_html(title_elem.text) if title_elem is not None and title_elem.text else ""
            link = clean_url(link_elem.text) if link_elem is not None and link_elem.text else ""
            description = strip_html(desc_elem.text) if desc_elem is not None and desc_elem.text else ""
            pub_date_str = date_elem.text if date_elem is not None and date_elem.text else None

            if not title or not link:
                continue

            pub_date = parse_date(pub_date_str)
            if not pub_date:
                continue

            description = description[:500]
            title = make_json_safe(title)
            description = make_json_safe(description)

            items.append({
                'title': title,
                'link': link,
                'pubDate': pub_date,
                'description': description
            })
    except Exception as e:
        print(f"Error parsing RSS: {e}", file=sys.stderr)
    return items

def time_filter(items, cutoff_date_str, window_days):
    try:
        cutoff_dt = datetime.fromisoformat(cutoff_date_str.replace('+08:00', '').replace('+00:00', ''))
        start_dt = cutoff_dt - timedelta(days=window_days)
        start_date = start_dt.strftime('%Y-%m-%d')
        cutoff_date = cutoff_dt.strftime('%Y-%m-%d')
    except:
        return []

    filtered = []
    for item in items:
        pub_date = item['pubDate']
        if pub_date and start_date <= pub_date <= cutoff_date:
            filtered.append(item)
    return filtered[:20]

def main():
    xml_file = sys.argv[1]
    source_name = sys.argv[2]
    source_url = sys.argv[3]
    feed_url = sys.argv[4]
    cutoff_timestamp = sys.argv[5]
    window_days = int(sys.argv[6])
    output_dir = sys.argv[7]

    with open(xml_file, 'r', encoding='utf-8') as f:
        xml_content = f.read()

    items = parse_rss(xml_content)
    filtered_items = time_filter(items, cutoff_timestamp, window_days)

    try:
        cutoff_dt = datetime.fromisoformat(cutoff_timestamp.replace('+08:00', '').replace('+00:00', ''))
        start_dt = cutoff_dt - timedelta(days=window_days)
        start_str = start_dt.strftime('%Y-%m-%dT%H:%M:%S+08:00')
    except:
        start_str = cutoff_timestamp

    output_data = {
        'source': {
            'name': source_name,
            'url': source_url,
            'feed_url': feed_url,
            'extracted_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00')
        },
        'filter': {
            'cutoff': cutoff_timestamp,
            'window_days': window_days,
            'start': start_str
        },
        'stats': {
            'total': len(items),
            'after_time_filter': len(filtered_items)
        },
        'items': filtered_items
    }

    output_path = f"{output_dir}/{source_name}-raw.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"输出文件: {output_path}")
    print(f"总条目: {len(items)}, 过滤后: {len(filtered_items)}")

if __name__ == '__main__':
    main()
