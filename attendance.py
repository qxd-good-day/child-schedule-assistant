import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from database import DB_FILE

# ==================== 出勤记录模块 ====================

def init_attendance_db():
    """初始化出勤记录数据库表"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 出勤记录表
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            attendance_date DATE NOT NULL,
            status TEXT NOT NULL DEFAULT 'attended',
            check_in_time TEXT,
            check_out_time TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE,
            UNIQUE(course_id, attendance_date)
        )
    ''')
    
    # 创建索引以提高查询性能
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_attendance_date 
        ON attendance(attendance_date)
    ''')
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_attendance_course 
        ON attendance(course_id)
    ''')
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_attendance_status 
        ON attendance(status)
    ''')
    
    conn.commit()
    conn.close()

def record_attendance(course_id, attendance_date, status='attended', 
                      check_in_time=None, check_out_time=None, notes=""):
    """
    记录课程出勤情况
    
    Args:
        course_id: 课程ID
        attendance_date: 出勤日期 (YYYY-MM-DD)
        status: 出勤状态 - 'attended'(已上), 'absent'(缺勤), 'leave'(请假), 'cancelled'(课程取消)
        check_in_time: 签到时间 (可选)
        check_out_time: 签退时间 (可选)
        notes: 备注
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 检查是否已存在记录
    c.execute('''
        SELECT id FROM attendance 
        WHERE course_id = ? AND attendance_date = ?
    ''', (course_id, attendance_date))
    
    existing = c.fetchone()
    
    if existing:
        # 更新现有记录
        c.execute('''
            UPDATE attendance 
            SET status = ?, check_in_time = ?, check_out_time = ?, notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE course_id = ? AND attendance_date = ?
        ''', (status, check_in_time, check_out_time, notes, course_id, attendance_date))
    else:
        # 插入新记录
        c.execute('''
            INSERT INTO attendance 
            (course_id, attendance_date, status, check_in_time, check_out_time, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (course_id, attendance_date, status, check_in_time, check_out_time, notes))
    
    conn.commit()
    conn.close()
    return True

def get_attendance_by_date(date):
    """获取某一天的出勤记录"""
    conn = sqlite3.connect(DB_FILE)
    query = '''
        SELECT a.*, c.course_name, c.location, c.start_time, c.end_time, c.day_of_week
        FROM attendance a
        JOIN courses c ON a.course_id = c.id
        WHERE a.attendance_date = ?
        ORDER BY c.start_time
    '''
    df = pd.read_sql_query(query, conn, params=(date,))
    conn.close()
    return df

def get_attendance_by_course(course_id, start_date=None, end_date=None):
    """获取某课程的出勤记录"""
    conn = sqlite3.connect(DB_FILE)
    
    query = '''
        SELECT a.*, c.course_name, c.location
        FROM attendance a
        JOIN courses c ON a.course_id = c.id
        WHERE a.course_id = ?
    '''
    params = [course_id]
    
    if start_date:
        query += ' AND a.attendance_date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND a.attendance_date <= ?'
        params.append(end_date)
    
    query += ' ORDER BY a.attendance_date DESC'
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def get_attendance_by_date_range(start_date, end_date):
    """获取日期范围内的出勤记录"""
    conn = sqlite3.connect(DB_FILE)
    query = '''
        SELECT a.*, c.course_name, c.location, c.start_time, c.end_time, c.day_of_week
        FROM attendance a
        JOIN courses c ON a.course_id = c.id
        WHERE a.attendance_date BETWEEN ? AND ?
        ORDER BY a.attendance_date DESC, c.start_time
    '''
    df = pd.read_sql_query(query, conn, params=(start_date, end_date))
    conn.close()
    return df

def get_all_attendance(limit=100):
    """获取所有出勤记录"""
    conn = sqlite3.connect(DB_FILE)
    query = '''
        SELECT a.*, c.course_name, c.location, c.start_time, c.end_time, c.day_of_week
        FROM attendance a
        JOIN courses c ON a.course_id = c.id
        ORDER BY a.attendance_date DESC, c.start_time
        LIMIT ?
    '''
    df = pd.read_sql_query(query, conn, params=(limit,))
    conn.close()
    return df

def delete_attendance_record(record_id):
    """删除出勤记录"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM attendance WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()
    return True

# ==================== 统计分析功能 ====================

def get_attendance_stats_by_course(course_id=None, start_date=None, end_date=None):
    """
    获取出勤统计信息
    
    Returns:
        dict: 包含各种出勤状态的统计
    """
    conn = sqlite3.connect(DB_FILE)
    
    query = '''
        SELECT 
            c.course_name,
            a.status,
            COUNT(*) as count
        FROM attendance a
        JOIN courses c ON a.course_id = c.id
        WHERE 1=1
    '''
    params = []
    
    if course_id:
        query += ' AND a.course_id = ?'
        params.append(course_id)
    if start_date:
        query += ' AND a.attendance_date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND a.attendance_date <= ?'
        params.append(end_date)
    
    query += ' GROUP BY c.course_name, a.status'
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    # 转换为统计字典
    stats = {}
    for _, row in df.iterrows():
        course = row['course_name']
        if course not in stats:
            stats[course] = {'attended': 0, 'absent': 0, 'leave': 0, 'cancelled': 0, 'total': 0}
        stats[course][row['status']] = row['count']
        stats[course]['total'] += row['count']
    
    # 计算出勤率
    for course in stats:
        total = stats[course]['total']
        if total > 0:
            attended = stats[course]['attended']
            stats[course]['attendance_rate'] = round(attended / total * 100, 2)
        else:
            stats[course]['attendance_rate'] = 0
    
    return stats

def get_monthly_attendance_stats(year=None, month=None):
    """获取月度出勤统计"""
    if year is None:
        year = datetime.now().year
    if month is None:
        month = datetime.now().month
    
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    
    conn = sqlite3.connect(DB_FILE)
    query = '''
        SELECT 
            a.status,
            COUNT(*) as count
        FROM attendance a
        WHERE a.attendance_date >= ? AND a.attendance_date < ?
        GROUP BY a.status
    '''
    df = pd.read_sql_query(query, conn, params=(start_date, end_date))
    conn.close()
    
    stats = {'attended': 0, 'absent': 0, 'leave': 0, 'cancelled': 0, 'total': 0}
    for _, row in df.iterrows():
        stats[row['status']] = row['count']
        stats['total'] += row['count']
    
    if stats['total'] > 0:
        stats['attendance_rate'] = round(stats['attended'] / stats['total'] * 100, 2)
    else:
        stats['attendance_rate'] = 0
    
    return stats

def get_weekly_attendance_trend(weeks=8):
    """获取最近几周的出勤趋势"""
    conn = sqlite3.connect(DB_FILE)
    
    # 计算最近几周的起始日期
    end_date = datetime.now().date()
    start_date = end_date - timedelta(weeks=weeks)
    
    query = '''
        SELECT 
            strftime('%Y-%W', a.attendance_date) as week,
            a.status,
            COUNT(*) as count
        FROM attendance a
        WHERE a.attendance_date >= ? AND a.attendance_date <= ?
        GROUP BY week, a.status
        ORDER BY week
    '''
    df = pd.read_sql_query(query, conn, params=(start_date, end_date))
    conn.close()
    
    # 整理数据
    weeks_data = {}
    for _, row in df.iterrows():
        week = row['week']
        if week not in weeks_data:
            weeks_data[week] = {'attended': 0, 'absent': 0, 'leave': 0, 'cancelled': 0, 'total': 0}
        weeks_data[week][row['status']] = row['count']
        weeks_data[week]['total'] += row['count']
    
    # 计算每周出勤率
    for week in weeks_data:
        total = weeks_data[week]['total']
        if total > 0:
            weeks_data[week]['attendance_rate'] = round(weeks_data[week]['attended'] / total * 100, 2)
        else:
            weeks_data[week]['attendance_rate'] = 0
    
    return weeks_data

def get_course_attendance_ranking(start_date=None, end_date=None, limit=10):
    """获取课程出勤率排名"""
    conn = sqlite3.connect(DB_FILE)
    
    query = '''
        SELECT 
            c.course_name,
            c.day_of_week,
            COUNT(CASE WHEN a.status = 'attended' THEN 1 END) as attended_count,
            COUNT(*) as total_count
        FROM attendance a
        JOIN courses c ON a.course_id = c.id
        WHERE 1=1
    '''
    params = []
    
    if start_date:
        query += ' AND a.attendance_date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND a.attendance_date <= ?'
        params.append(end_date)
    
    query += '''
        GROUP BY c.id, c.course_name
        HAVING total_count > 0
        ORDER BY (attended_count * 1.0 / total_count) DESC
        LIMIT ?
    '''
    params.append(limit)
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if not df.empty:
        df['attendance_rate'] = (df['attended_count'] / df['total_count'] * 100).round(2)
    
    return df

def get_upcoming_courses_without_record(days=7):
    """获取未来几天还没有出勤记录的课程（用于提醒记录）"""
    conn = sqlite3.connect(DB_FILE)
    
    today = datetime.now().date()
    future_date = today + timedelta(days=days)
    
    # 获取未来几天的日期列表
    date_list = []
    current = today
    while current <= future_date:
        date_list.append(current)
        current += timedelta(days=1)
    
    # 获取所有课程
    courses_df = pd.read_sql_query("SELECT * FROM courses", conn)
    
    # 获取已有记录的日期和课程组合
    existing_records = pd.read_sql_query('''
        SELECT course_id, attendance_date 
        FROM attendance 
        WHERE attendance_date >= ? AND attendance_date <= ?
    ''', conn, params=(today, future_date))
    
    conn.close()
    
    # 找出没有记录的课程
    weekday_map = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    missing_records = []
    
    for date in date_list:
        weekday = weekday_map[date.weekday()]
        day_courses = courses_df[courses_df['day_of_week'] == weekday]
        
        for _, course in day_courses.iterrows():
            # 检查是否已有记录
            existing = existing_records[
                (existing_records['course_id'] == course['id']) & 
                (existing_records['attendance_date'] == date.strftime('%Y-%m-%d'))
            ]
            
            if existing.empty:
                missing_records.append({
                    'date': date,
                    'course_id': course['id'],
                    'course_name': course['course_name'],
                    'start_time': course['start_time'],
                    'location': course['location']
                })
    
    return pd.DataFrame(missing_records)

# 状态标签映射
STATUS_LABELS = {
    'attended': '✅ 已上课',
    'absent': '❌ 缺勤',
    'leave': '📝 请假',
    'cancelled': '🚫 课程取消'
}

STATUS_COLORS = {
    'attended': '#10b981',
    'absent': '#ef4444',
    'leave': '#f59e0b',
    'cancelled': '#6b7280'
}

def get_status_label(status):
    """获取状态的中文标签"""
    return STATUS_LABELS.get(status, status)

def get_status_color(status):
    """获取状态对应的颜色"""
    return STATUS_COLORS.get(status, '#6b7280')
