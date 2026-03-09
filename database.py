import sqlite3
import pandas as pd
from datetime import datetime

DB_FILE = "schedule.db"

def init_db():
    """Initialize the database with the courses table."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            course_name TEXT NOT NULL,
            location TEXT,
            pickup_time TEXT,
            notes TEXT,
            course_type TEXT DEFAULT 'recurring',
            course_date TEXT,
            end_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_course(day, start, end, name, location, pickup, notes="", course_type="recurring", course_date=None, end_date=None, notify_daily=1, notify_weekly=1, notify_before_start=0, notify_minutes_before=30):
    """Add a single course to the database."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO courses (day_of_week, start_time, end_time, course_name, location, pickup_time, notes, course_type, course_date, end_date, notify_daily, notify_weekly, notify_before_start, notify_minutes_before)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (day, start, end, name, location, pickup, notes, course_type, course_date, end_date, notify_daily, notify_weekly, notify_before_start, notify_minutes_before))
    conn.commit()
    conn.close()

def get_all_courses():
    """Retrieve all courses as a pandas DataFrame."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM courses", conn)
    conn.close()
    # Sort by day and time (custom sort for days)
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    df['day_of_week'] = pd.Categorical(df['day_of_week'], categories=days_order, ordered=True)
    df = df.sort_values(['day_of_week', 'start_time'])
    return df

def delete_course(course_id):
    """Delete a course by ID."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM courses WHERE id=?", (course_id,))
    conn.commit()
    conn.close()

def update_course(course_id, day, start, end, name, location, pickup, notes="", course_type="recurring", course_date=None, end_date=None, notify_daily=1, notify_weekly=1, notify_before_start=0, notify_minutes_before=30):
    """Update a course by ID."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        UPDATE courses 
        SET day_of_week = ?, start_time = ?, end_time = ?, course_name = ?, 
            location = ?, pickup_time = ?, notes = ?, course_type = ?, course_date = ?, end_date = ?,
            notify_daily = ?, notify_weekly = ?, notify_before_start = ?, notify_minutes_before = ?
        WHERE id = ?
    ''', (day, start, end, name, location, pickup, notes, course_type, course_date, end_date, notify_daily, notify_weekly, notify_before_start, notify_minutes_before, course_id))
    conn.commit()
    conn.close()

def get_course_by_id(course_id):
    """Get a single course by ID."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM courses WHERE id = ?", conn, params=(course_id,))
    conn.close()
    if not df.empty:
        return df.iloc[0]
    return None

def get_courses_by_day(day_name, target_date=None):
    """Get courses for a specific day (e.g., 'Monday').
    
    Args:
        day_name: 星期几（英文）
        target_date: 目标日期字符串 'YYYY-MM-DD'，用于过滤一次性课程
    """
    conn = sqlite3.connect(DB_FILE)
    
    if target_date:
        # 获取周期性课程 + 该日期的一次性课程
        query = '''
            SELECT * FROM courses 
            WHERE day_of_week = ? 
            AND (
                course_type = 'recurring' 
                OR (course_type = 'one_time' AND course_date = ?)
            )
        '''
        df = pd.read_sql_query(query, conn, params=(day_name, target_date))
    else:
        # 只获取周期性课程（兼容旧逻辑）
        query = '''
            SELECT * FROM courses 
            WHERE day_of_week = ? 
            AND course_type = 'recurring'
        '''
        df = pd.read_sql_query(query, conn, params=(day_name,))
    
    conn.close()
    if not df.empty:
        df = df.sort_values('start_time')
    return df

def get_courses_for_date(date_obj):
    """获取指定日期的所有课程（包括周期性和一次性）
    
    Args:
        date_obj: datetime.date 对象
    """
    from datetime import datetime
    
    day_name = date_obj.strftime("%A")
    date_str = date_obj.strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_FILE)
    
    # 获取周期性课程（检查是否在有效期内）
    # 和该日期的一次性课程
    query = '''
        SELECT * FROM courses 
        WHERE (
            course_type = 'recurring' 
            AND day_of_week = ?
            AND (end_date IS NULL OR end_date >= ?)
        )
        OR (
            course_type = 'one_time' 
            AND course_date = ?
        )
    '''
    df = pd.read_sql_query(query, conn, params=(day_name, date_str, date_str))
    conn.close()
    
    if not df.empty:
        df = df.sort_values('start_time')
    return df

def get_upcoming_one_time_courses(days=7):
    """获取未来几天内的一次性课程
    
    Args:
        days: 未来几天
    """
    from datetime import datetime, timedelta
    
    today = datetime.now().date()
    end_date = today + timedelta(days=days)
    
    conn = sqlite3.connect(DB_FILE)
    query = '''
        SELECT * FROM courses 
        WHERE course_type = 'one_time' 
        AND course_date >= ? 
        AND course_date <= ?
        ORDER BY course_date, start_time
    '''
    df = pd.read_sql_query(query, conn, params=(today.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))
    conn.close()
    return df

def seed_initial_data():
    """Seed the database with the user's provided image data."""
    # Check if empty first
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM courses")
    count = cursor.fetchone()[0]
    conn.close()
    
    if count > 0:
        return

    # Data from the user's image
    # Mapping Chinese days to English for consistency in logic, or keep Chinese? 
    # User asked for "Monday" etc in the table, but the image has "周一". 
    # Let's store as "Monday" but display as "周一" in UI, or store "周一". 
    # Storing standard English days makes sorting/date logic easier.
    
    initial_courses = [
        ("Monday", "16:30", "17:30", "小主持人", "幼儿园", "17:30", "", "recurring", None, None),
        ("Tuesday", "16:30", "17:30", "体适能", "中安创谷", "16:00", "", "recurring", None, None),
        ("Wednesday", "16:30", "17:30", "科学小实验", "幼儿园", "17:30", "", "recurring", None, None),
        ("Thursday", "16:40", "17:30", "舞蹈", "西子曼城超市", "16:00", "", "recurring", None, None),
        ("Friday", "16:30", "17:30", "体适能", "中安创谷", "16:00", "", "recurring", None, None),
        ("Saturday", "10:50", "11:50", "乐高", "高新银泰3楼吉姆", "", "", "recurring", None, None),
        ("Sunday", "10:30", "12:00", "绘画", "Y15栋201", "", "", "recurring", None, None),
        ("Sunday", "17:40", "18:30", "舞蹈", "西子曼城超市", "", "", "recurring", None, None)
    ]

    for course in initial_courses:
        add_course(*course)

def migrate_db():
    """迁移数据库，添加新课程类型字段"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 检查是否需要迁移
    c.execute("PRAGMA table_info(courses)")
    columns = [col[1] for col in c.fetchall()]
    
    if 'course_type' not in columns:
        # 添加新字段
        c.execute("ALTER TABLE courses ADD COLUMN course_type TEXT DEFAULT 'recurring'")
        c.execute("ALTER TABLE courses ADD COLUMN course_date TEXT")
        c.execute("ALTER TABLE courses ADD COLUMN end_date TEXT")
        conn.commit()
        print("[Database] 已迁移数据库，添加课程类型字段")
    
    # 添加通知配置字段
    if 'notify_daily' not in columns:
        c.execute("ALTER TABLE courses ADD COLUMN notify_daily INTEGER DEFAULT 1")
        c.execute("ALTER TABLE courses ADD COLUMN notify_weekly INTEGER DEFAULT 1")
        c.execute("ALTER TABLE courses ADD COLUMN notify_before_start INTEGER DEFAULT 0")
        c.execute("ALTER TABLE courses ADD COLUMN notify_minutes_before INTEGER DEFAULT 30")
        conn.commit()
        print("[Database] 已迁移数据库，添加通知配置字段")
    
    conn.close()

if __name__ == "__main__":
    init_db()
    migrate_db()
    seed_initial_data()
    print("Database initialized and seeded.")
