#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
from datetime import datetime, date, timedelta
from bs4 import BeautifulSoup
import psycopg2
from psycopg2.extras import execute_values

# ========== 配置 ==========
DATA_ROOT = "/datapool/chat_dku_advising/event_homepage"  # 改为学长的正式路径
DATABASE_URL = os.getenv("PG_INGEST_URI", "postgresql://chatdku_retrieval:securepassword123@localhost:5432/chatdku_ingestion")

def get_current_week_range():
    """返回本周的周一和周日日期（基于当前系统日期）"""
    today = date.today()
    # 周一是一周的开始（weekday=0 是周一）
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    return start_of_week, end_of_week

def find_index_html(page_dir):
    for root, dirs, files in os.walk(page_dir):
        if 'index.html' in files:
            return os.path.join(root, 'index.html')
    return None

def parse_event_date(date_str):
    if not date_str:
        return None
    if 'T' in date_str:
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.date()
        except:
            pass
    match = re.search(r'(\w+,\s+\w+\s+\d{1,2},\s+\d{4})', date_str)
    if match:
        try:
            dt = datetime.strptime(match.group(1), '%A, %B %d, %Y')
            return dt.date()
        except:
            try:
                dt = datetime.strptime(match.group(1), '%A, %b %d, %Y')
                return dt.date()
            except:
                pass
    try:
        from dateutil import parser
        dt = parser.parse(date_str, fuzzy=True)
        return dt.date()
    except:
        return None

def parse_event_time(time_str):
    if not time_str:
        return None
    time_str = time_str.strip()
    try:
        dt = datetime.strptime(time_str, '%I:%M%p')
        return dt.time().strftime('%H:%M:%S')
    except:
        return time_str

def extract_events_from_html(html_path):
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'lxml')
    events = []
    rows = soup.find_all('div', class_='views-row')
    for row in rows:
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

        time_tags = row.find_all('time')
        start_date = None
        end_date = None
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
            if end_dt:
                end_date = parse_event_date(end_dt)
                if 'T' in end_dt:
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
            text = row.get_text()
            match = re.search(r'(\w+,\s+\w+\s+\d{1,2},\s+\d{4})\s*\|\s*(\d{1,2}:\d{2}(?:am|pm))', text, re.IGNORECASE)
            if match:
                start_date = parse_event_date(match.group(1))
                start_time = parse_event_time(match.group(2))
        if not start_date:
            continue

        location = None
        loc_span = row.find('span', class_='icon locale')
        if loc_span:
            location = loc_span.get_text().strip()
        else:
            loc_a = row.find('a', href=re.compile(r'maps\.app\.goo\.gl'))
            if loc_a:
                location = loc_a.get_text().strip()

        sponsor = None
        sponsor_div = row.find('div', class_='sponsor')
        if sponsor_div:
            sponsor = re.sub(r'^Sponsor:\s*', '', sponsor_div.get_text().strip())

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

def main():
    # 自动获取本周的周一和周日
    week_start, week_end = get_current_week_range()
    print(f"当前周范围: {week_start} 至 {week_end}")

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 清空旧数据
    cur.execute("TRUNCATE TABLE weekly_events;")
    print("已清空 weekly_events 表")

    # 遍历所有页面
    all_events = []
    for page_num in range(0, 7):
        page_dir = os.path.join(DATA_ROOT, f'page_{page_num}')
        if not os.path.isdir(page_dir):
            print(f"警告: 目录不存在 {page_dir}")
            continue
        html_file = find_index_html(page_dir)
        if not html_file:
            print(f"警告: 在 {page_dir} 下未找到 index.html")
            continue
        print(f"处理: {html_file}")
        events = extract_events_from_html(html_file)
        # 只保留本周范围内的活动
        for ev in events:
            if week_start <= ev['date'] <= week_end:
                all_events.append(ev)

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
    if values:
        execute_values(cur, insert_sql, values)
        conn.commit()
        print(f"成功插入 {len(values)} 条事件到 weekly_events 表")
    else:
        print("本周没有找到任何事件")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()