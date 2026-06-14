#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import re
import html
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs

# 配置
SOURCE_NAME = "国家数据发展研究院"
SOURCE_URL = "http://localhost:5001/api/rss/MzkzNDkzNjI1NQ=="
FEED_URL = "http://localhost:5001/api/rss/MzkzNDkzNjI1NQ=="
CUTOFF_STR = "2026-06-13T00:10:46+08:00"
WINDOW_DAYS = 1
OUTPUT_DIR = "/Users/quartet/data-elements/reports/2026-06-13"

def parse_date(date_str):
    """解析 RSS 日期为 YYYY-MM-DD 格式"""
    if not date_str:
        return None
    try:
        # 尝试解析 RFC 822/2822 格式
        dt = datetime.strptime(date_str.strip(), "%a, %d %b %Y %H:%M:%S %z")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        try:
            # 尝试 ISO 8601 格式
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return None

def strip_html(text):
    """去除 HTML 标签，只保留纯文本"""
    if not text:
        return ""
    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', ' ', text)
    # 解码 HTML 实体
    text = html.unescape(text)
    # 合并多余空白
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def sanitize_json_string(text):
    """确保字符串中双引号不破坏 JSON"""
    if not text:
        return ""
    # 将未转义的双引号替换为中文引号
    text = text.replace('"', '"')
    return text

def clean_url(url):
    """去除 URL 中的追踪参数"""
    if not url:
        return ""
    url = url.strip()
    try:
        parsed = urlparse(url)
        # 移除常见追踪参数
        query_params = parse_qs(parsed.query)
        tracking_params = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                          'fbclid', 'gclid', 'msclkid'}
        filtered_params = {k: v for k, v in query_params.items() if k.lower() not in tracking_params}
        # 重建 URL
        if filtered_params:
            from urllib.parse import urlencode
            new_query = urlencode(filtered_params, doseq=True)
            url = parsed._replace(query=new_query).geturl()
        else:
            url = parsed._replace(query='').geturl()
    except Exception:
        pass
    return url

def main():
    # 读取 RSS 内容
    import subprocess
    result = subprocess.run([
        'curl', '-s', '-L', '--max-time', '15',
        '-H', 'Accept: application/rss+xml, application/atom+xml, application/xml, text/xml',
        FEED_URL
    ], capture_output=True, text=True)

    if result.returncode != 0 or not result.stdout:
        print(json.dumps({
            "status": "failed",
            "reason": "Failed to fetch RSS feed"
        }, ensure_ascii=False))
        return

    content = result.stdout

    # 解析 XML
    root = ET.fromstring(content)

    # 计算 cutoff 和时间范围
    cutoff_dt = datetime.fromisoformat(CUTOFF_STR)
    start_dt = cutoff_dt - timedelta(days=WINDOW_DAYS)

    # 提取条目
    items = []
    # RSS 2.0: <item> 在 <channel> 下
    channel = root.find('.//channel')
    if channel is not None:
        item_elements = channel.findall('.//item')
    else:
        # Atom 1.0: <entry> 在 <feed> 下
        item_elements = root.findall('.//{http://www.w3.org/2005/Atom}entry')

    total = len(item_elements)

    for item_elem in item_elements[:20]:  # 最多取 20 条
        title_elem = item_elem.find('.//title')
        link_elem = item_elem.find('.//link')
        pubdate_elem = item_elem.find('.//pubDate')
        if pubdate_elem is None:
            pubdate_elem = item_elem.find('.//{http://www.w3.org/2005/Atom}published')
            if pubdate_elem is None:
                pubdate_elem = item_elem.find('.//{http://www.w3.org/2005/Atom}updated')

        desc_elem = item_elem.find('.//description')
        if desc_elem is None:
            desc_elem = item_elem.find('.//{http://www.w3.org/2005/Atom}summary')
            if desc_elem is None:
                desc_elem = item_elem.find('.//{http://www.w3.org/2005/Atom}content')

        title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
        link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
        if link_elem is not None and link_elem.get('href'):
            link = link_elem.get('href').strip()

        # 跳过空 title 或 link
        if not title or not link:
            continue

        # 解析日期
        pub_date_str = pubdate_elem.text.strip() if pubdate_elem is not None and pubdate_elem.text else ""
        pub_date = parse_date(pub_date_str) if pub_date_str else None

        # 时间过滤：丢弃 pubDate 为 None 或不在窗口内的条目
        if pub_date is None:
            continue

        try:
            item_date = datetime.strptime(pub_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if item_date < start_dt or item_date > cutoff_dt:
                continue
        except Exception:
            continue

        # 处理 description
        description = ""
        if desc_elem is not None and desc_elem.text:
            description = strip_html(desc_elem.text)
            description = sanitize_json_string(description)
            if len(description) > 500:
                description = description[:500] + "..."

        # 清洗 link
        link = clean_url(link)

        # 清洗 title（去除零宽空格等特殊字符）
        title = re.sub(r'[​-‍﻿]', '', title)
        title = sanitize_json_string(title)

        items.append({
            "title": title,
            "link": link,
            "pubDate": pub_date,
            "description": description
        })

    # 构建输出 JSON
    output = {
        "source": {
            "name": SOURCE_NAME,
            "url": SOURCE_URL,
            "feed_url": FEED_URL,
            "extracted_at": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S+08:00")
        },
        "filter": {
            "cutoff": CUTOFF_STR,
            "window_days": WINDOW_DAYS,
            "start": start_dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")
        },
        "stats": {
            "total": total,
            "after_time_filter": len(items)
        },
        "items": items
    }

    # 保存文件
    output_path = f"{OUTPUT_DIR}/{SOURCE_NAME}-raw.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "status": "success",
        "output_path": output_path,
        "total": total,
        "filtered": len(items)
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
