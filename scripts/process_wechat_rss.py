#!/usr/bin/env python3
"""
微信公众号 RSS 处理脚本
从微信 API 获取文章并转换为标准 RSS 格式
"""
import json
import subprocess
import re
import html
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def fetch_articles(fakeid):
    """从微信 API 获取文章列表"""
    result = subprocess.run([
        'curl', '-s', '-L', '--max-time', '15',
        f'http://localhost:5001/api/public/articles?fakeid={fakeid}'
    ], capture_output=True, text=True)

    if result.returncode != 0 or not result.stdout:
        return None

    try:
        data = json.loads(result.stdout)
        if data.get('success'):
            return data['data']['articles']
    except json.JSONDecodeError:
        pass

    return None

def clean_html(text):
    """去除 HTML 标签，只保留纯文本"""
    if not text:
        return ""

    # 移除 CDATA 包裹
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)

    # 移除所有 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)

    # 解码 HTML 实体
    text = html.unescape(text)

    # 移除多余空白
    text = re.sub(r'\s+', ' ', text).strip()

    # 截断至 500 字符
    if len(text) > 500:
        text = text[:500] + "..."

    return text

def clean_title(title):
    """清理标题"""
    if not title:
        return ""

    # 移除 CDATA 包裹
    title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title, flags=re.DOTALL)

    # 解码 HTML 实体
    title = html.unescape(title)

    # 移除首尾空白和特殊字符
    title = title.strip()
    title = re.sub(r'[​-‍﻿]', '', title)  # 零宽字符

    return title

def clean_link(link):
    """清理链接"""
    if not link:
        return ""

    link = link.strip()

    # 去除追踪参数
    parsed = urlparse(link)
    query_params = parse_qs(parsed.query)

    # 保留的参数
    clean_params = {}
    for key in ['s', 'p', 'id', 'v', 'article_id']:
        if key in query_params:
            clean_params[key] = query_params[key]

    # 重构 URL
    clean_query = urlencode(clean_params, doseq=True)
    clean_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        clean_query,
        ''  # 移除 fragment
    ))

    return clean_url

def timestamp_to_date(timestamp):
    """将时间戳转换为 YYYY-MM-DD 格式"""
    if not timestamp:
        return None

    try:
        dt = datetime.fromtimestamp(timestamp, tz=timezone(timedelta(hours=8)))
        return dt.strftime('%Y-%m-%d')
    except (ValueError, TypeError, OSError):
        return None

def process_articles(articles, cutoff_date, start_date):
    """处理文章列表，进行时间过滤和清洗"""
    items = []

    for article in articles:
        title = clean_title(article.get('title', ''))
        link = clean_link(article.get('link', ''))
        description = clean_html(article.get('digest', ''))

        # 使用 update_time 作为发布时间
        pub_date = timestamp_to_date(article.get('update_time'))

        # 跳过标题或链接为空的条目
        if not title or not link:
            continue

        # 时间过滤
        if pub_date:
            try:
                item_date = datetime.strptime(pub_date, '%Y-%m-%d').date()
                if item_date < start_date or item_date > cutoff_date:
                    continue
            except (ValueError, TypeError):
                continue
        else:
            continue  # 无日期则跳过

        items.append({
            'title': title,
            'link': link,
            'pubDate': pub_date,
            'description': description
        })

        # 最多保留 20 条
        if len(items) >= 20:
            break

    return items

def main():
    """主函数"""
    # 配置参数
    source_name = '国家数据局'
    source_url = 'https://www.ndata.gov.cn/'
    feed_url = 'http://localhost:5001/api/rss/MzkzMTU5MDA3OQ=='
    fakeid = 'MzkzMTU5MDA3OQ=='
    cutoff_str = '2026-06-04T10:00:00+0800'
    window_days = 1
    work_dir = '/Users/quartet/data-elements/2026-06-04'

    # 计算时间范围
    if '+0800' in cutoff_str:
        cutoff_str = cutoff_str.replace('+0800', '+08:00')

    try:
        cutoff_dt = datetime.fromisoformat(cutoff_str)
        cutoff_dt = cutoff_dt.astimezone(timezone(timedelta(hours=8)))
        cutoff_date = cutoff_dt.date()
        start_dt = cutoff_dt - timedelta(days=window_days)
        start_date = start_dt.date()
    except ValueError as e:
        print(f"时间解析错误: {e}")
        return

    print(f"时间范围: {start_date} 至 {cutoff_date}")

    # 获取文章列表
    print(f"正在获取 {source_name} 的文章...")
    articles = fetch_articles(fakeid)

    if not articles:
        print(f"无法获取 {source_name} 的文章")
        return

    print(f"获取到 {len(articles)} 篇文章")

    # 处理文章
    items = process_articles(articles, cutoff_date, start_date)

    # 构建输出
    output = {
        "source": {
            "name": source_name,
            "url": source_url,
            "feed_url": feed_url,
            "extracted_at": datetime.now(timezone(timedelta(hours=8))).isoformat()
        },
        "filter": {
            "cutoff": cutoff_str,
            "window_days": window_days,
            "start": start_dt.isoformat() + "+08:00"
        },
        "stats": {
            "total": len(articles),
            "after_time_filter": len(items)
        },
        "items": items
    }

    # 保存文件
    from pathlib import Path
    Path(work_dir).mkdir(parents=True, exist_ok=True)

    output_path = f"{work_dir}/{source_name}-raw.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {source_name} 数据提取完成")
    print(f"\n📊 统计:")
    print(f"- Feed 总条目: {len(articles)}")
    print(f"- 时间过滤后: {len(items)}")
    print(f"\n📁 输出文件: {output_path}")

if __name__ == "__main__":
    main()