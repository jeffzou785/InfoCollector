#!/usr/bin/env python3
"""RSS 数据提取脚本 - 获取RSS Feed并执行时间过滤，输出标准化JSON"""

import sys
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET
import requests

def extract_rss_data(
    source_name: str,
    source_url: str,
    feed_url: str,
    cutoff_timestamp: str,
    window_days: int,
    work_dir: str
):
    """执行RSS数据提取与过滤"""

    # 解析时间参数
    try:
        cutoff_dt = datetime.fromisoformat(cutoff_timestamp.replace('+08:00', ''))
    except:
        cutoff_dt = datetime.strptime(cutoff_timestamp, '%Y-%m-%dT%H:%M:%S')

    start_dt = cutoff_dt - timedelta(days=window_days)

    # 获取RSS内容
    try:
        response = requests.get(feed_url, timeout=15, headers={
            'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml'
        })
        response.raise_for_status()
        raw_content = response.text
    except Exception as e:
        return False, f"RSS Feed获取失败: {e}"

    # 解析XML
    try:
        root = ET.fromstring(raw_content)
    except ET.ParseError as e:
        return False, f"XML解析失败: {e}"

    # 提取items（支持RSS 2.0和Atom格式）
    items = []
    rss_items = root.findall('.//item')  # RSS 2.0
    atom_entries = root.findall('.//{http://www.w3.org/2005/Atom}entry')  # Atom

    all_items = rss_items if rss_items else atom_entries

    for elem in all_items:
        try:
            # 提取标题 - 支持直接迭代子元素
            title = ''
            link = ''

            # 直接迭代子元素以避免 find() 方法的潜在问题
            for child in elem:
                child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag

                if child_tag == 'title' and child.text and not title:
                    title = child.text.strip()
                elif child_tag == 'link':
                    # link 可能是文本或属性
                    if child.text:
                        link = child.text.strip()
                    elif 'href' in child.attrib:
                        link = child.attrib['href'].strip()

            # 跳过空标题或链接
            if not title or not link:
                continue

            # 提取链接
            link_elem = elem.find('link')
            if link_elem is not None:
                link = link_elem.text if link_elem.text else link_elem.get('href', '')
            else:
                link_elem = elem.find('{http://www.w3.org/2005/Atom}link')
                link = link_elem.get('href', '') if link_elem is not None else ''

            link = link.strip()

            # 跳过空标题或链接
            if not title or not link:
                continue

            # 提取发布日期 - 继续迭代子元素
            pub_date_str = ''
            description = ''

            for child in elem:
                child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag

                if child_tag == 'pubDate' and child.text and not pub_date_str:
                    pub_date_str = child.text.strip()
                elif child_tag in ['published', 'updated'] and child.text and not pub_date_str:
                    pub_date_str = child.text.strip()
                elif child_tag in ['description', 'summary', 'content'] and child.text and not description:
                    description = child.text

            # 解析日期为YYYY-MM-DD格式
            pub_date = None
            if pub_date_str:
                try:
                    # 尝试解析RFC 2822格式（如 "Tue, 09 Jun 2026 15:58:34 +0000"）
                    pub_dt = datetime.strptime(pub_date_str[:25].strip(), '%a, %d %b %Y %H:%M:%S')
                    pub_date = pub_dt.strftime('%Y-%m-%d')
                except Exception as e:
                    try:
                        # 尝试ISO格式
                        pub_dt = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                        pub_date = pub_dt.strftime('%Y-%m-%d')
                    except Exception as e2:
                        pub_date = None

            # 提取描述
            desc_elem = elem.find('description') or elem.find('summary') or elem.find('{http://www.w3.org/2005/Atom}summary') or elem.find('content')
            description = desc_elem.text if desc_elem is not None and desc_elem.text else ''

            # 清洗描述
            if description:
                # 去除HTML标签
                description = re.sub(r'<[^>]+>', ' ', description)
                # 去除CDATA包裹
                description = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', description, flags=re.DOTALL)
                # 去除多余空白
                description = re.sub(r'\s+', ' ', description).strip()
                # 截断至500字符
                description = description[:500]

            # JSON安全处理：替换双引号为中文引号
            title = title.replace('"', '"').replace('"', '"')
            description = description.replace('"', '"').replace('"', '"')

            items.append({
                'title': title,
                'link': link,
                'pubDate': pub_date,
                'description': description
            })

        except Exception as e:
            # 跳过解析失败的条目
            continue

    total_count = len(items)

    # 时间硬过滤
    filtered_items = []
    start_date = start_dt.strftime('%Y-%m-%d')
    cutoff_date = cutoff_dt.strftime('%Y-%m-%d')

    for item in items:
        pub_date = item.get('pubDate')
        if not pub_date:
            continue  # 丢弃无日期的条目

        # 检查是否在时间窗口内（包含边界）
        if start_date <= pub_date <= cutoff_date:
            filtered_items.append(item)

    # 限制最多20条
    filtered_items = filtered_items[:20]
    after_filter_count = len(filtered_items)

    # 构建输出JSON
    output = {
        "source": {
            "name": source_name,
            "url": source_url,
            "feed_url": feed_url,
            "extracted_at": datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00')
        },
        "filter": {
            "cutoff": cutoff_timestamp,
            "window_days": window_days,
            "start": start_dt.isoformat() + '+08:00'
        },
        "stats": {
            "total": total_count,
            "after_time_filter": after_filter_count
        },
        "items": filtered_items
    }

    # 输出文件
    output_file = Path(work_dir) / f'{source_name}-raw.json'
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return True, str(output_file)


if __name__ == '__main__':
    if len(sys.argv) != 7:
        print(f"Usage: extract_rss_data.py <source_name> <source_url> <feed_url> <cutoff> <window_days> <work_dir>")
        print(f"Got {len(sys.argv)} args: {sys.argv}")
        sys.exit(1)

    success, result = extract_rss_data(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        sys.argv[4],
        int(sys.argv[5]),
        sys.argv[6]
    )

    if success:
        print(f"SUCCESS: {result}")
    else:
        print(f"ERROR: {result}")
        sys.exit(1)
