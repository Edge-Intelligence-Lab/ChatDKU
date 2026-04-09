#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import psycopg2
from psycopg2.extras import execute_values
from bs4 import BeautifulSoup
from datetime import datetime, date
from dateutil import parser  # 需要安装 python-dateutil

# ========== 配置 ==========
DATA_ROOT = "/datapool/chat_dku_advising_test/event_data"
# 从环境变量获取数据库连接（确保已设置 PG_INGEST_URI）
DATABASE_URL = os.getenv("PG_INGEST_URI", "postgresql://chatdku_retrieval:securepassword123@localhost:5432/chatdku_ingestion")

# ========== 辅助函数 ==========
def find_index_html(page_dir):
    """递归查找 index.html"""
    for root, dirs, files in os.walk(page_dir):
        if 'index.html' in files:
            return os.path.join(root, 'index.html')
    return None

def parse_event_date(date_str):
    """解析日期字符串，返回 date 对象"""
    if not date_str:
        return None
    # ISO 格式
    if 'T' in date_str:
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.date()
        except:
            pass
    # 长格式 "Thursday, April 9, 2026"
    match = re.search(r'(\w+,\s+\w+\s+\d{1,2},\s+\d{4})', date_str)
    if match:
        try:
            return datetime.strptime(match.group(1), '%A, %B %d, %Y').date()
        except:
            try:
                return datetime.strptime(match.group(1), '%A, %b %d, %Y').date()
            except:
                pass
    # 使用 dateutil 模糊解析
    try:
        return parser.parse(date_str, fuzzy=True).date()
    except:
        return None

def parse_event_time(time_str):
    """将 '9:00am' 转为 '09:00:00' 格式，或返回原始字符串"""
    if not time_str:
        return None
    time_str = time_str.strip()
    # 尝试解析 12 小时制
    try:
        dt = datetime.strptime(time_str, '%I:%M%p')
        return dt.time().strftime('%H:%M:%S')
    except:
        # 如果已经是 24 小时制或其它格式，直接返回（后续可调整）
        return time_str

def extract_events_from_html(html_path):
    """从列表页 HTML 提取事件列表（与你之前代码一致）"""
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'lxml')

    events = []
    rows = soup.find_all('div', class_='views-row')
    for row in rows:
        # 标题和链接
        title_tag = row.find('h2', class_='field-content')
        if not title_tag:
            continue
        a_tag = title_tag.find('a')
        if not a_tag:
            continue
        title = a_tag.get_text().strip()
        url = a_tag.get('href')
        if url and not url.startswith('http'):
            url = 'https://calendar.dukekunshan.edu.cn' + url

        # 日期时间
        time_tags = row.find_all('time')
        start_date = None
        start_time = None
        end_time = None
        if len(time_tags) >= 2:
            start_dt = time_tags[0].get('datetime')
            end_dt = time_tags[1].get('datetime')
            if start_dt:
                start_date = parse_event_date(start_dt)
                if 'T' in start_dt:
                    time_part = start_dt.split('T')[1].split('+')[0].split('-')[0]
                    start_time = parse_event_time(time_part)
            if end_dt and 'T' in end_dt:
                time_part = end_dt.split('T')[1].split('+')[0].split('-')[0]
                end_time = parse_event_time(time_part)
        elif len(time_tags) == 1:
            dt_str = time_tags[0].get('datetime')
            if dt_str:
                start_date = parse_event_date(dt_str)
                if 'T' in dt_str:
                    time_part = dt_str.split('T')[1].split('+')[0].split('-')[0]
                    start_time = parse_event_time(time_part)
        else:
            # 从文本中尝试解析
            text = row.get_text()
            match = re.search(r'(\w+,\s+\w+\s+\d{1,2},\s+\d{4})\s*\|\s*(\d{1,2}:\d{2}(?:am|pm))', text, re.IGNORECASE)
            if match:
                start_date = parse_event_date(match.group(1))
                start_time = parse_event_time(match.group(2))
        if not start_date:
            continue

        # 地点
        location = None
        loc_span = row.find('span', class_='icon locale')
        if loc_span:
            location = loc_span.get_text().strip()
        else:
            loc_a = row.find('a', href=re.compile(r'maps\.app\.goo\.gl'))
            if loc_a:
                location = loc_a.get_text().strip()

        # Sponsor
        sponsor = None
        sponsor_div = row.find('div', class_='sponsor')
        if sponsor_div:
            sponsor = re.sub(r'^Sponsor:\s*', '', sponsor_div.get_text().strip())

        # Open to
        open_to = None
        audience_label = row.find('strong', string=re.compile(r'Open to:', re.IGNORECASE))
        if audience_label:
            audience_span = audience_label.find_next('span', class_='legend')
            if audience_span:
                open_to = audience_span.get_text().strip()
            else:
                parent = audience_label.find_parent('div')
                if parent:
                    open_to = parent.get_text().replace('Open to:', '').strip()

        # Speaker
        speaker = None
        speaker_span = row.find('span', class_='icon speaker')
        if speaker_span:
            speaker = speaker_span.get_text().strip()

        events.append({
            'title': title,
            'url': url,
            'date': start_date,
            'start_time': start_time,
            'end_time': end_time,
            'location': location,
            'sponsor': sponsor,
            'open_to': open_to,
            'speaker': speaker,
        })
    return events

# ========== 主流程 ==========
def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 可选：清空旧数据（每周全量更新）
    cur.execute("TRUNCATE TABLE weekly_events;")
    print("已清空 weekly_events 表")

    all_events = []
    # 遍历 page_0 到 page_6
    for page_num in range(0, 7):
        page_dir = os.path.join(DATA_ROOT, f'page_{page_num}')
        if not os.path.isdir(page_dir):
            continue
        html_file = find_index_html(page_dir)
        if not html_file:
            print(f"警告: 未在 {page_dir} 找到 index.html")
            continue
        print(f"处理: {html_file}")
        events = extract_events_from_html(html_file)
        all_events.extend(events)

    # 批量插入
    insert_sql = """
        INSERT INTO weekly_events 
        (title, event_date, start_time, end_time, location, sponsor, open_to, speaker, url)
        VALUES %s
    """
    values = []
    for ev in all_events:
        values.append((
            ev['title'],
            ev['date'],
            ev['start_time'],
            ev['end_time'],
            ev['location'],
            ev['sponsor'],
            ev['open_to'],
            ev['speaker'],
            ev['url']
        ))
    execute_values(cur, insert_sql, values)
    conn.commit()
    cur.close()
    conn.close()
    print(f"成功插入 {len(values)} 条事件到 weekly_events 表")

if __name__ == "__main__":
    main()