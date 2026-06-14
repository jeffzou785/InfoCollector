#!/usr/bin/env python3
"""
RSS 数据提取器
纯数据获取与清洗，不做任何语义判断
"""

import xml.etree.ElementTree as ET
import re
import json
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

def clean_html(text):
    """去除 HTML 标签，只保留纯文本"""
    if not text:
        return ""
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def clean_url(url):
    """去除 URL 中的追踪参数"""
    if not url:
        return ""
    url = url.strip()
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        clean_params = {}
        for k, v in query_params.items():
            if not k.startswith(('utm_', 'fbclid', 'gclid')):
                clean_params[k] = v
        if clean_params:
            from urllib.parse import urlencode
            query = urlencode(clean_params, doseq=True)
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{query}"
        else:
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except:
        return url

def parse_date(date_str):
    """解析各种日期格式为 YYYY-MM-DD"""
    if not date_str:
        return None
    formats = [
        '%a, %d %b %Y %H:%M:%S %z',
        '%a, %d %b %Y %H:%M:%S %Z',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%d',
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime('%Y-%m-%d')
        except:
            continue
    return None

def truncate_text(text, max_length=500):
    """截断文本到指定长度"""
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def strip_special_chars(text):
    """去除特殊字符"""
    if not text:
        return ""
    text = re.sub(r'[​-‍⁠᠎﻿]', '', text)
    return text.strip()

def extract_rss_items(xml_content, start_date, end_date, max_items=20):
    """从 RSS XML 中提取并过滤条目"""
    items = []
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"XML 解析错误: {e}")
        return items

    for item in root.findall('.//item'):
        if len(items) >= max_items:
            break

        title_elem = item.find('title')
        link_elem = item.find('link')
        desc_elem = item.find('description')
        date_elem = item.find('pubDate')

        title = clean_html(title_elem.text) if title_elem is not None and title_elem.text else ""
        link = clean_url(link_elem.text) if link_elem is not None and link_elem.text else ""
        description = clean_html(desc_elem.text) if desc_elem is not None and desc_elem.text else ""
        pub_date_str = date_elem.text if date_elem is not None and date_elem.text else None

        title = strip_special_chars(title)
        description = truncate_text(description, 500)
        pub_date = parse_date(pub_date_str)

        if not title or not link:
            continue

        if pub_date is None:
            continue

        try:
            item_date = datetime.strptime(pub_date, '%Y-%m-%d')
            if item_date < start_date or item_date > end_date:
                continue
        except:
            continue

        items.append({
            'title': title,
            'link': link,
            'pubDate': pub_date,
            'description': description
        })

    return items

def main():
    source_name = "数据要素市场"
    source_url = "https://www.datafactor.market/"
    feed_url = "http://localhost:5001/api/rss/Mzg2MTg3MDkwNQ=="
    cutoff_str = "2026-06-08T16:30:00+08:00"
    window_days = 1
    work_dir = "/Users/quartet/data-elements/2026-06-08"

    cutoff = datetime.fromisoformat(cutoff_str)
    start = cutoff - timedelta(days=window_days)

    import subprocess
    result = subprocess.run([
        'curl', '-s', '-L', '--max-time', '15',
        '-H', 'Accept: application/rss+xml, application/atom+xml, application/xml, text/xml',
        feed_url
    ], capture_output=True, text=True)

    if result.returncode != 0 or not result.stdout:
        print(f"Feed 获取失败: {result.stderr}")
        return

    xml_content = result.stdout
    total_items = xml_content.count('<item>')

    items = extract_rss_items(xml_content, start, cutoff, max_items=20)

    output = {
        "source": {
            "name": source_name,
            "url": source_url,
            "feed_url": feed_url,
            "extracted_at": datetime.now().isoformat()
        },
        "filter": {
            "cutoff": cutoff_str,
            "window_days": window_days,
            "start": start.isoformat()
        },
        "stats": {
            "total": total_items,
            "after_time_filter": len(items)
        },
        "items": items
    }

    output_path = f"{work_dir}/{source_name}-raw.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"数据提取完成")
    print(f"Feed 总条目: {total_items}")
    print(f"时间过滤后: {len(items)}")
    print(f"输出文件: {output_path}")

if __name__ == "__main__":
    main()
