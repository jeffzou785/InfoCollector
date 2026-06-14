#!/usr/bin/env python3
"""RSS 数据提取器 - BAT大数据架构"""
import json
import re
import sys
from datetime import datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs

class HTMLTextExtractor(HTMLParser):
    """提取纯文本，去除 HTML 标签"""
    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):
        self.text.append(data)

    def get_text(self):
        return ''.join(self.text).strip()

def clean_html(text):
    """去除 HTML 标签，提取纯文本"""
    if not text:
        return ""
    # 去除 CDATA 包裹
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
    # 使用 HTML 解析器提取文本
    parser = HTMLTextExtractor()
    try:
        parser.feed(text)
        return parser.get_text()
    except:
        # 回退：简单去除标签
        text = re.sub(r'<[^>]+>', '', text)
        return text.strip()

def clean_text(text):
    """清洗文本：去除零宽空格等特殊字符"""
    if not text:
        return ""
    # 去除零宽空格
    text = re.sub(r'[​‌‍﻿]', '', text)
    # 去除首尾空白
    text = text.strip()
    return text

def safe_json_string(text):
    """确保字符串是 JSON 安全的，替换双引号"""
    if not text:
        return ""
    # 将双引号替换为单引号
    text = text.replace('"', "'")
    return text

def clean_link(url):
    """去除链接中的追踪参数"""
    if not url:
        return ""
    url = url.strip()
    try:
        parsed = urlparse(url)
        # 去除 utm_* 参数
        query_params = parse_qs(parsed.query)
        filtered_params = {k: v for k, v in query_params.items()
                          if not k.startswith('utm_')}
        if filtered_params:
            from urllib.parse import urlencode
            new_query = urlencode(filtered_params, doseq=True)
            url = parsed._replace(query=new_query).geturl()
        else:
            url = parsed._replace(query='').geturl()
    except:
        pass
    return url

def parse_date(date_str):
    """解析日期字符串为 YYYY-MM-DD 格式"""
    if not date_str:
        return None
    # 尝试多种日期格式
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

def parse_rss(xml_content, cutoff_date, start_date):
    """解析 RSS 2.0 格式"""
    items = []

    # 提取所有 item
    item_pattern = re.compile(r'<item>(.*?)</item>', re.DOTALL)
    for item_match in item_pattern.finditer(xml_content):
        item_xml = item_match.group(1)

        # 提取标题
        title_match = re.search(r'<title>(.*?)</title>', item_xml, re.DOTALL)
        title = clean_text(clean_html(title_match.group(1))) if title_match else ""

        # 提取链接
        link_match = re.search(r'<link>(.*?)</link>', item_xml, re.DOTALL)
        link = clean_link(link_match.group(1)) if link_match else ""

        # 提取描述
        desc_match = re.search(r'<description>(.*?)</description>', item_xml, re.DOTALL)
        description = clean_html(desc_match.group(1)) if desc_match else ""

        # 提取日期
        pubdate_match = re.search(r'<pubDate>(.*?)</pubDate>', item_xml, re.DOTALL)
        pubdate = parse_date(pubdate_match.group(1)) if pubdate_match else None

        # 跳过空标题或空链接
        if not title or not link:
            continue

        # 时间过滤
        if pubdate:
            try:
                item_date = datetime.strptime(pubdate, '%Y-%m-%d').date()
                if not (start_date <= item_date <= cutoff_date):
                    continue
            except:
                continue
        else:
            # pubDate 为 null 的直接丢弃
            continue

        # 截断描述
        if len(description) > 500:
            description = description[:500] + "..."

        # JSON 安全处理
        title = safe_json_string(title)
        description = safe_json_string(description)

        items.append({
            'title': title,
            'link': link,
            'pubDate': pubdate,
            'description': description
        })

        # 最多保留 20 条
        if len(items) >= 20:
            break

    return items

def main():
    # 参数
    source_name = "BAT大数据架构"
    source_url = "http://localhost:5001/api/rss/MzkwNzE5NDM5Nw=="
    feed_url = "http://localhost:5001/api/rss/MzkwNzE5NDM5Nw=="
    cutoff_str = "2026-06-12T00:10:31+08:00"
    window_days = 1
    work_dir = "/Users/quartet/data-elements/reports/2026-06-12"

    # 解析时间
    try:
        cutoff_dt = datetime.fromisoformat(cutoff_str)
        cutoff_date = cutoff_dt.date()
    except:
        print(f"错误：无法解析截止时间 {cutoff_str}", file=sys.stderr)
        sys.exit(1)

    start_dt = cutoff_dt - timedelta(days=window_days)
    start_date = start_dt.date()

    # 读取 RSS 内容
    curl_file = "/Users/quartet/.claude/projects/-Users-quartet-data-elements/aea8e7f7-50fb-49a3-9f0f-b9a467a1ea1d/tool-results/biqyb420t.txt"
    try:
        with open(curl_file, 'r', encoding='utf-8') as f:
            xml_content = f.read()
    except:
        print(f"错误：无法读取 RSS 内容", file=sys.stderr)
        sys.exit(1)

    # 解析 RSS
    items = parse_rss(xml_content, cutoff_date, start_date)

    # 统计总数（不含时间过滤）
    total_pattern = re.compile(r'<item>', re.IGNORECASE)
    total_count = len(total_pattern.findall(xml_content))

    # 构建输出
    output = {
        'source': {
            'name': source_name,
            'url': source_url,
            'feed_url': feed_url,
            'extracted_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00')
        },
        'filter': {
            'cutoff': cutoff_str,
            'window_days': window_days,
            'start': start_dt.strftime('%Y-%m-%dT%H:%M:%S+08:00')
        },
        'stats': {
            'total': total_count,
            'after_time_filter': len(items)
        },
        'items': items
    }

    # 输出文件
    output_file = f"{work_dir}/{source_name}-raw.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 打印结果
    print(f"✅ {source_name} 数据提取完成")
    print(f"\n📊 统计:")
    print(f"- Feed 总条目: {total_count}")
    print(f"- 时间过滤后: {len(items)}")
    print(f"\n📁 输出文件: {output_file}")

if __name__ == '__main__':
    main()
