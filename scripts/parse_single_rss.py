#!/usr/bin/env python3
"""
单条 RSS Feed 解析脚本
输入：XML 内容、时间过滤参数
输出：标准化的 JSON 结构
"""

import sys
import json
import re
from datetime import datetime, timedelta
from html import unescape
import xml.etree.ElementTree as ET

def strip_html(text):
    """去除 HTML 标签，保留纯文本"""
    if not text:
        return ""
    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    # 去除 CDATA 包裹
    text = text.replace('<![CDATA[', '').replace(']]>', '')
    # 解码 HTML 实体
    text = unescape(text)
    # 去除多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def safe_json_str(text):
    """确保字符串是 JSON 安全的（处理双引号）"""
    if not text:
        return ""
    # 将双引号替换为中文引号或单引号
    text = text.replace('"', '"')
    text = text.replace('"', '"')
    return text

def clean_link(url):
    """清理链接，移除追踪参数"""
    if not url:
        return ""
    url = url.strip()
    # 移除常见的追踪参数
    params_to_remove = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content']
    try:
        from urllib.parse import urlparse, parse_qs, urlunparse
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        filtered_params = {k: v for k, v in query_params.items() if k not in params_to_remove}
        # 重建 URL
        new_query = '&'.join(f"{k}={v[0]}" for k, v in filtered_params.items())
        parsed = parsed._replace(query=new_query)
        url = urlunparse(parsed)
    except:
        pass
    return url

def parse_date(date_str):
    """解析日期字符串为 YYYY-MM-DD 格式"""
    if not date_str:
        return None
    try:
        # 尝试解析 RFC 2822 格式（Tue, 09 Jun 2026 09:00:00 +0000）
        date_obj = datetime.strptime(date_str.strip(), '%a, %d %b %Y %H:%M:%S %z')
        return date_obj.strftime('%Y-%m-%d')
    except:
        try:
            # 尝试解析 ISO 8601 格式
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return date_obj.strftime('%Y-%m-%d')
        except:
            return None

def parse_rss_items(xml_content):
    """解析 RSS 2.0 格式的 items"""
    items = []
    try:
        root = ET.fromstring(xml_content)
        # RSS 2.0: items 在 channel 下
        channel = root.find('.//channel')
        if channel is not None:
            item_elements = channel.findall('.//item')
        else:
            item_elements = root.findall('.//item')

        for item_elem in item_elements:
            try:
                title = item_elem.find('.//title')
                link = item_elem.find('.//link')
                desc = item_elem.find('.//description')
                pub_date = item_elem.find('.//pubDate')

                title_text = strip_html(title.text if title is not None and title.text else "")
                link_text = clean_link(link.text if link is not None and link.text else "")
                desc_text = strip_html(desc.text if desc is not None and desc.text else "")
                pub_date_text = parse_date(pub_date.text if pub_date is not None and pub_date.text else "")

                # 跳过 title 或 link 为空的条目
                if not title_text or not link_text:
                    continue

                # 截断 description 至 500 字符
                if len(desc_text) > 500:
                    desc_text = desc_text[:500]

                # JSON 安全处理
                title_text = safe_json_str(title_text)
                desc_text = safe_json_str(desc_text)

                items.append({
                    'title': title_text,
                    'link': link_text,
                    'pubDate': pub_date_text,
                    'description': desc_text
                })
            except:
                continue
    except Exception as e:
        print(f"XML 解析错误: {e}", file=sys.stderr)
    return items

def filter_by_time(items, cutoff_str, window_days):
    """根据时间窗口过滤条目"""
    cutoff = datetime.fromisoformat(cutoff_str.replace('Z', '+00:00'))
    start_time = cutoff - timedelta(days=window_days)

    filtered = []
    for item in items:
        pub_date_str = item.get('pubDate')
        if not pub_date_str:
            continue  # 丢弃 pubDate 为 null 的条目

        try:
            pub_date = datetime.strptime(pub_date_str, '%Y-%m-%d')
            # 转为 UTC 进行比较（简单处理，假设都是 UTC）
            if start_time.date() <= pub_date.date() <= cutoff.date():
                filtered.append(item)
        except:
            continue

    return filtered[:20]  # 最多保留 20 条

def main():
    if len(sys.argv) < 5:
        print("用法: parse_single_rss.py <xml_file> <source_name> <source_url> <feed_url> <cutoff> <window_days> <output_dir>", file=sys.stderr)
        sys.exit(1)

    xml_file = sys.argv[1]
    source_name = sys.argv[2]
    source_url = sys.argv[3]
    feed_url = sys.argv[4]
    cutoff = sys.argv[5]
    window_days = int(sys.argv[6])
    output_dir = sys.argv[7]

    # 读取 XML 内容
    with open(xml_file, 'r', encoding='utf-8') as f:
        xml_content = f.read()

    # 解析 items
    items = parse_rss_items(xml_content)

    # 时间过滤
    filtered_items = filter_by_time(items, cutoff, window_days)

    # 计算时间范围
    cutoff_dt = datetime.fromisoformat(cutoff.replace('Z', '+00:00'))
    start_dt = cutoff_dt - timedelta(days=window_days)

    # 构建输出结构
    output = {
        'source': {
            'name': source_name,
            'url': source_url,
            'feed_url': feed_url,
            'extracted_at': datetime.now().astimezone().isoformat()
        },
        'filter': {
            'cutoff': cutoff,
            'window_days': window_days,
            'start': start_dt.astimezone().isoformat()
        },
        'stats': {
            'total': len(items),
            'after_time_filter': len(filtered_items)
        },
        'items': filtered_items
    }

    # 输出 JSON
    output_path = f"{output_dir}/{source_name}-raw.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ {source_name} 数据提取完成")
    print(f"\n📊 统计:")
    print(f"- Feed 总条目: {len(items)}")
    print(f"- 时间过滤后: {len(filtered_items)}")
    print(f"\n📁 输出文件: {output_path}")

if __name__ == '__main__':
    main()
