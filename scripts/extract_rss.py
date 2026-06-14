#!/usr/bin/env python3
"""RSS 数据提取器 - 获取、清洗、时间过滤、输出 JSON"""
import xml.etree.ElementTree as ET
import json
import re
import sys
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

def strip_html(text):
    """去除 HTML 标签，只保留纯文本"""
    if not text:
        return ""
    # 移除 CDATA 包裹
    text = re.sub(r'<!\[CDATA\[|\]\]>', '', text)
    # 移除所有 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    # 移除 HTML 实体
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#39;', "'", text)
    # 去除多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def make_json_safe(text):
    """确保文本对 JSON 安全，将双引号替换为中文引号或单引号"""
    if not text:
        return ""
    # 将双引号 " 替换为中文双引号 ""（或单引号）
    text = text.replace('"', ''')
    return text

def clean_url(url):
    """去除 URL 中的追踪参数"""
    if not url:
        return ""
    url = url.strip()
    try:
        parsed = urlparse(url)
        # 移除常见的追踪参数
        tracking_params = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                          'source', 'medium', 'campaign', 'ref', 'referrer', 'share'}
        query_params = parse_qs(parsed.query)
        filtered_params = {k: v for k, v in query_params.items() if k not in tracking_params}

        # 重构 URL
        if filtered_params:
            from urllib.parse import urlencode
            new_query = urlencode(filtered_params, doseq=True)
            return parsed._replace(query=new_query).geturl()
        else:
            return parsed._replace(query='').geturl()
    except:
        return url

def parse_date(date_str):
    """解析各种日期格式为 YYYY-MM-DD"""
    if not date_str:
        return None

    date_str = date_str.strip()

    # 常见日期格式
    formats = [
        '%a, %d %b %Y %H:%M:%S %z',  # RFC 2822
        '%a, %d %b %Y %H:%M:%S',      # RFC 2822 无时区
        '%Y-%m-%dT%H:%M:%S%z',        # ISO 8601
        '%Y-%m-%dT%H:%M:%SZ',         # ISO 8601 UTC
        '%Y-%m-%d',                   # 简单日期
        '%Y%m%d',                     # 紧凑日期
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except:
            continue

    # 尝试其他清理方式
    # 移除时区信息重试
    date_str = re.sub(r'\s*[+-]\d{4}$', '', date_str)
    date_str = re.sub(r'\s*GMT$', '', date_str, flags=re.IGNORECASE)

    for fmt in formats[:3]:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except:
            continue

    return None

def parse_rss(xml_content, cutoff_date, window_days):
    """解析 RSS 2.0 Feed"""
    items = []

    try:
        root = ET.fromstring(xml_content)

        # 查找所有 item 元素
        for item in root.findall('.//item'):
            title_elem = item.find('title')
            link_elem = item.find('link')
            desc_elem = item.find('description')
            date_elem = item.find('pubDate')

            # 提取字段
            title = strip_html(title_elem.text) if title_elem is not None and title_elem.text else ""
            link = clean_url(link_elem.text) if link_elem is not None and link_elem.text else ""
            description = strip_html(desc_elem.text) if desc_elem is not None and desc_elem.text else ""
            pub_date_str = date_elem.text if date_elem is not None and date_elem.text else None

            # 跳过空字段
            if not title or not link:
                continue

            # 解析日期
            pub_date = parse_date(pub_date_str)
            if not pub_date:
                continue  # 丢弃无法解析日期的条目

            # 截断描述
            description = description[:500]

            # JSON 安全处理
            title = make_json_safe(title)
            description = make_json_safe(description)

            items.append({
                'title': title,
                'link': link,
                'pubDate': pub_date,
                'description': description
            })

    except Exception as e:
        print(f"解析 RSS 失败: {e}", file=sys.stderr)

    return items

def parse_atom(xml_content, cutoff_date, window_days):
    """解析 Atom Feed"""
    items = []

    try:
        root = ET.fromstring(xml_content)

        # Atom 命名空间
        ns = {'atom': 'http://www.w3.org/2005/Atom'}

        # 查找所有 entry 元素
        for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
            title_elem = entry.find('{http://www.w3.org/2005/Atom}title')
            link_elem = entry.find('{http://www.w3.org/2005/Atom}link')
            desc_elem = entry.find('{http://www.w3.org/2005/Atom}summary')
            date_elem = entry.find('{http://www.w3.org/2005/Atom}published')
            if date_elem is None:
                date_elem = entry.find('{http://www.w3.org/2005/Atom}updated')

            # 提取字段
            title = strip_html(title_elem.text) if title_elem is not None and title_elem.text else ""
            link = link_elem.get('href') if link_elem is not None else ""
            link = clean_url(link)
            description = strip_html(desc_elem.text) if desc_elem is not None and desc_elem.text else ""
            pub_date_str = date_elem.text if date_elem is not None and date_elem.text else None

            # 跳过空字段
            if not title or not link:
                continue

            # 解析日期
            pub_date = parse_date(pub_date_str)
            if not pub_date:
                continue

            # 截断描述
            description = description[:500]

            # JSON 安全处理
            title = make_json_safe(title)
            description = make_json_safe(description)

            items.append({
                'title': title,
                'link': link,
                'pubDate': pub_date,
                'description': description
            })

    except Exception as e:
        print(f"解析 Atom 失败: {e}", file=sys.stderr)

    return items

def time_filter(items, cutoff_date_str, window_days):
    """根据时间窗口过滤条目"""
    # 解析截止日期
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

    # 最多保留 20 条
    return filtered[:20]

def extract_from_rss_file(xml_file_path, source_name, source_url, feed_url, cutoff_timestamp, window_days, output_dir):
    """从 RSS 文件提取数据"""
    # 读取 XML 文件
    with open(xml_file_path, 'r', encoding='utf-8') as f:
        xml_content = f.read()

    # 检测格式并解析
    items = []
    if '<rss' in xml_content or '<channel>' in xml_content:
        items = parse_rss(xml_content, cutoff_timestamp, window_days)
    elif '<feed' in xml_content or '<entry>' in xml_content:
        items = parse_atom(xml_content, cutoff_timestamp, window_days)

    # 时间过滤
    filtered_items = time_filter(items, cutoff_timestamp, window_days)

    # 计算时间范围
    try:
        cutoff_dt = datetime.fromisoformat(cutoff_timestamp.replace('+08:00', '').replace('+00:00', ''))
        start_dt = cutoff_dt - timedelta(days=window_days)
        start_str = start_dt.strftime('%Y-%m-%dT%H:%M:%S+08:00')
    except:
        start_str = cutoff_timestamp

    # 构建输出数据
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

    # 输出 JSON 文件
    output_path = f"{output_dir}/{source_name}-raw.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    return output_path, len(items), len(filtered_items)

if __name__ == '__main__':
    # 从环境变量或参数获取配置
    xml_file = sys.argv[1]
    source_name = sys.argv[2]
    source_url = sys.argv[3]
    feed_url = sys.argv[4]
    cutoff_timestamp = sys.argv[5]
    window_days = int(sys.argv[6])
    output_dir = sys.argv[7]

    output_path, total, filtered = extract_from_rss_file(
        xml_file, source_name, source_url, feed_url,
        cutoff_timestamp, window_days, output_dir
    )

    print(f"输出文件: {output_path}")
    print(f"总条目: {total}, 过滤后: {filtered}")
