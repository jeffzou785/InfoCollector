#!/usr/bin/env python3
"""RSS 数据提取脚本 - 单个信息源处理"""
import xml.etree.ElementTree as ET
import json
import re
import html
from datetime import datetime, timedelta, timezone
import sys

def strip_html(text):
    """去除 HTML 标签，只保留纯文本"""
    if not text:
        return ""
    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    # 解码 HTML 实体
    text = html.unescape(text)
    # 去除多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def clean_link(url):
    """去除链接中的追踪参数"""
    if not url:
        return ""
    url = url.strip()
    # 去除常见的追踪参数
    cleaned = re.sub(r'[?&](utm_source|utm_medium|utm_campaign|utm_content|utm_term|referrer|source|ref)=[^&]*', '', url)
    # 清理可能的残留 ? 或 &
    cleaned = re.sub(r'[?&]$', '', cleaned)
    return cleaned

def clean_title(title):
    """清理标题"""
    if not title:
        return ""
    # 去除零宽空格等特殊字符
    title = re.sub(r'[​‌‍‎‏‪‫‬‭‮⁠﻿]', '', title)
    title = title.strip()
    # JSON 安全处理：将双引号替换为中文引号
    title = title.replace('"', '"')
    title = title.replace('"', '"')
    return title

def parse_date(date_str):
    """解析日期字符串为 YYYY-MM-DD 格式"""
    if not date_str:
        return None
    try:
        # 尝试解析 RFC 2822 格式 (RSS 常用)
        date_str = date_str.strip()
        # 处理时区
        if '+' in date_str or 'GMT' in date_str or 'UTC' in date_str:
            # 简单处理：直接解析并提取日期部分
            dt = datetime.strptime(date_str.split('+')[0].split('Z')[0].strip().replace('GMT', '').replace('UTC', '').strip(),
                                    '%a, %d %b %Y %H:%M:%S')
        else:
            dt = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S')
        return dt.strftime('%Y-%m-%d')
    except:
        try:
            # 尝试 ISO 8601 格式 (Atom 常用)
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d')
        except:
            return None

def truncate_description(text, max_length=500):
    """截断描述文本"""
    if not text:
        return ""
    text = strip_html(text)
    if len(text) > max_length:
        text = text[:max_length].rstrip()
        # 确保在单词边界截断
        if ' ' in text:
            text = ' '.join(text.split()[:-1]) + '...'
    # JSON 安全处理：将双引号替换为中文引号
    text = text.replace('"', '"')
    text = text.replace('"', '"')
    return text

def parse_rss_xml(xml_content, source_name, source_url, feed_url, cutoff_timestamp, window_days):
    """解析 RSS XML 内容"""
    root = ET.fromstring(xml_content)

    # 计算时间范围
    cutoff_dt = datetime.fromisoformat(cutoff_timestamp.replace('+08:00', ''))
    if cutoff_dt.tzinfo is None:
        cutoff_dt = cutoff_dt.replace(tzinfo=timezone(timedelta(hours=8)))
    start_dt = cutoff_dt - timedelta(days=window_days)

    # 查找 channel (RSS 2.0)
    channel = root.find('.//channel')
    if channel is None:
        # 尝试 Atom 格式
        channel = root
    items = []

    # RSS 2.0: <item>
    for item in channel.findall('.//item'):
        title_elem = item.find('./title')
        link_elem = item.find('./link')
        desc_elem = item.find('./description')
        date_elem = item.find('./pubDate')

        title = clean_title(title_elem.text if title_elem is not None else "")
        link = clean_link(link_elem.text if link_elem is not None else "")
        pub_date = parse_date(date_elem.text if date_elem is not None else "")
        description = truncate_description(desc_elem.text if desc_elem is not None else "")

        if not title or not link:
            continue

        # 时间过滤
        if pub_date:
            try:
                item_date = datetime.strptime(pub_date, '%Y-%m-%d')
                item_date = item_date.replace(tzinfo=timezone.utc)
                # 统一到 UTC 进行比较
                start_utc = start_dt.astimezone(timezone.utc)
                cutoff_utc = cutoff_dt.astimezone(timezone.utc)
                if item_date < start_utc or item_date > cutoff_utc:
                    continue
            except Exception as e:
                print(f"日期解析错误: {pub_date}, 错误: {e}", file=sys.stderr)
                continue
        else:
            continue

        items.append({
            "title": title,
            "link": link,
            "pubDate": pub_date,
            "description": description
        })

    # Atom: <entry>
    if not items:
        for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
            title_elem = entry.find('.//{http://www.w3.org/2005/Atom}title')
            link_elem = entry.find('.//{http://www.w3.org/2005/Atom}link')
            desc_elem = entry.find('.//{http://www.w3.org/2005/Atom}summary')
            date_elem = entry.find('.//{http://www.w3.org/2005/Atom}published') or entry.find('.//{http://www.w3.org/2005/Atom}updated')

            title = clean_title(title_elem.text if title_elem is not None else "")
            link = clean_link(link_elem.get('href') if link_elem is not None else "")
            pub_date = parse_date(date_elem.text if date_elem is not None else "")
            description = truncate_description(desc_elem.text if desc_elem is not None else "")

            if not title or not link:
                continue

            # 时间过滤
            if pub_date:
                try:
                    item_date = datetime.strptime(pub_date, '%Y-%m-%d')
                    item_date = item_date.replace(tzinfo=timezone.utc)
                    start_utc = start_dt.astimezone(timezone.utc)
                    cutoff_utc = cutoff_dt.astimezone(timezone.utc)
                    if item_date < start_utc or item_date > cutoff_utc:
                        continue
                except:
                    continue
            else:
                continue

            items.append({
                "title": title,
                "link": link,
                "pubDate": pub_date,
                "description": description
            })

    # 最多保留 20 条
    items = items[:20]

    # 构建 JSON 结构
    result = {
        "source": {
            "name": source_name,
            "url": source_url,
            "feed_url": feed_url,
            "extracted_at": datetime.now(timezone(timedelta(hours=8))).isoformat()
        },
        "filter": {
            "cutoff": cutoff_timestamp,
            "window_days": window_days,
            "start": start_dt.isoformat()
        },
        "stats": {
            "total": len(items),
            "after_time_filter": len(items)
        },
        "items": items
    }

    return result

if __name__ == "__main__":
    # 从命令行参数读取
    if len(sys.argv) < 8:
        print("Usage: python parse_single_rss.py <xml_file> <source_name> <source_url> <feed_url> <cutoff_timestamp> <window_days> <output_dir>")
        sys.exit(1)

    xml_file = sys.argv[1]
    source_name = sys.argv[2]
    source_url = sys.argv[3]
    feed_url = sys.argv[4]
    cutoff_timestamp = sys.argv[5]
    window_days = int(sys.argv[6])
    output_dir = sys.argv[7]

    # 读取 XML 内容
    with open(xml_file, 'r', encoding='utf-8') as f:
        xml_content = f.read()

    # 解析 RSS
    result = parse_rss_xml(xml_content, source_name, source_url, feed_url, cutoff_timestamp, window_days)

    # 保存 JSON
    output_file = f"{output_dir}/{source_name}-raw.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ {source_name} 数据提取完成")
    print(f"\n📊 统计:")
    print(f"- Feed 总条目: {result['stats']['total']}")
    print(f"- 时间过滤后: {result['stats']['after_time_filter']}")
    print(f"\n📁 输出文件: {output_file}")
