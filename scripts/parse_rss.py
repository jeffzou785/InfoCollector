#!/usr/bin/env python3
"""
RSS Feed 解析器
获取 RSS Feed，清洗数据，执行时间过滤，输出标准化的 JSON 文件
使用 feedparser 库以支持各种 RSS/Atom 格式
"""

import sys
import json
import re
import time
from datetime import datetime, timedelta
from time import struct_time
import feedparser
from html.parser import HTMLParser

class HTMLStripper(HTMLParser):
    """HTML 标签去除器"""
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []

    def handle_data(self, d):
        self.text.append(d)

    def get_data(self):
        return ''.join(self.text)

def strip_html(html):
    """去除 HTML 标签"""
    if not html:
        return ""
    stripper = HTMLStripper()
    stripper.feed(html)
    return stripper.get_data()

def clean_text(text):
    """清洗文本：去除首尾空白、零宽字符等"""
    if not text:
        return ""
    # 去除零宽字符
    text = re.sub(r'[​-‍⁠᠎﻿]', '', text)
    # 去除首尾空白
    text = text.strip()
    return text

def clean_url(url):
    """清洗 URL：去除追踪参数"""
    if not url:
        return ""
    url = url.strip()
    # 去除常见的追踪参数
    url = re.sub(r'[?&](utm_[^&]*|ref_[^&]*|fbclid[^&]*|gclid[^&]*)', '', url)
    # 去除可能残留的 ? 或 &
    url = re.sub(r'[?&]$', '', url)
    return url

def parse_feed(xml_content, source_name, source_url, feed_url, cutoff_timestamp, window_days):
    """解析 RSS/Atom feed（统一处理）"""
    # 使用 feedparser 解析
    feed = feedparser.parse(xml_content)

    # 计算时间范围（正确处理时区）
    # 输入的时间戳是北京时间 (+08:00)
    # cutoff_timestamp 格式: "2026-05-29T15:00:00+08:00"

    # 保存原始时间戳用于输出
    original_cutoff = cutoff_timestamp

    if '+08:00' in cutoff_timestamp or '+0800' in cutoff_timestamp:
        # 北京时间，减去 8 小时得到 UTC
        cutoff_str = cutoff_timestamp.replace('+08:00', '').replace('+0800', '').replace('T', ' ')
        cutoff_dt = datetime.fromisoformat(cutoff_str)
        cutoff_dt = cutoff_dt - timedelta(hours=8)
    else:
        # 假设是 UTC
        cutoff_str = cutoff_timestamp.replace('+00:00', '').replace('+0000', '').replace('T', ' ').replace('Z', '')
        cutoff_dt = datetime.fromisoformat(cutoff_str)
        cutoff_dt = cutoff_dt.replace(tzinfo=None)

    start_dt = cutoff_dt - timedelta(days=window_days)

    # 提取所有条目
    items = []
    for entry in feed.entries:
        # 提取标题
        title = clean_text(getattr(entry, 'title', ''))

        # 提取链接
        link = clean_url(getattr(entry, 'link', ''))

        if not title or not link:
            continue

        # 提取发布日期
        pub_date_str = None
        pub_date_dt = None
        date_field = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
        if date_field:
            # feedparser 已经解析为 struct_time
            try:
                dt = datetime.fromtimestamp(time.mktime(date_field))
                pub_date_str = dt.strftime('%Y-%m-%d')
                pub_date_dt = dt  # 保留完整时间用于过滤
            except:
                pass

        # 时间过滤
        if pub_date_dt:
            if pub_date_dt < start_dt or pub_date_dt > cutoff_dt:
                continue
        else:
            # 日期为 null 的直接丢弃
            continue

        # 提取描述
        desc_text = ""
        description = getattr(entry, 'description', '') or getattr(entry, 'summary', '')
        if description:
            desc_text = strip_html(description)
            desc_text = clean_text(desc_text)
            # 截断至 500 字符
            if len(desc_text) > 500:
                desc_text = desc_text[:500]

        items.append({
            'title': title,
            'link': link,
            'pubDate': pub_date_str,
            'description': desc_text
        })

    # 最多保留 20 条
    items = items[:20]

    return {
        'source': {
            'name': source_name,
            'url': source_url,
            'feed_url': feed_url,
            'extracted_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00')
        },
        'filter': {
            'cutoff': original_cutoff,
            'window_days': window_days,
            'start': (datetime.fromisoformat(original_cutoff.replace('+08:00', '').replace('+0800', '').replace('T', ' ')) - timedelta(days=window_days)).strftime('%Y-%m-%dT%H:%M:%S+08:00')
        },
        'stats': {
            'total': len(feed.entries),
            'after_time_filter': len(items)
        },
        'items': items
    }

def main():
    # 从命令行参数读取配置
    if len(sys.argv) < 7:
        print("Usage: python parse_rss.py <source_name> <source_url> <feed_url> <cutoff_timestamp> <window_days> <output_dir> <input_file>", file=sys.stderr)
        sys.exit(1)

    source_name = sys.argv[1]
    source_url = sys.argv[2]
    feed_url = sys.argv[3]
    cutoff_timestamp = sys.argv[4]
    window_days = int(sys.argv[5])
    output_dir = sys.argv[6]
    input_file = sys.argv[7] if len(sys.argv) > 7 else None

    # 读取 XML 内容
    if input_file:
        with open(input_file, 'r', encoding='utf-8') as f:
            xml_content = f.read()
    else:
        xml_content = sys.stdin.read()

    # 解析
    result = parse_feed(xml_content, source_name, source_url, feed_url, cutoff_timestamp, window_days)

    # 输出 JSON
    output_file = f"{output_dir}/{source_name}-raw.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"RSS feed parsed successfully")
    print(f"Total items: {result['stats']['total']}")
    print(f"After time filter: {result['stats']['after_time_filter']}")
    print(f"Output file: {output_file}")

if __name__ == '__main__':
    main()
