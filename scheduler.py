import time
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
import pytz
from database import get_courses_by_day, get_all_courses, get_courses_for_date
from notifier import send_daily_notification, send_weekly_notification, send_course_reminder

# Configuration
TIMEZONE = pytz.timezone('Asia/Shanghai')

# 按顺序排列的星期列表（周一到周日）
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

day_map = {
    "Monday": "周一", "Tuesday": "周二", "Wednesday": "周三",
    "Thursday": "周四", "Friday": "周五", "Saturday": "周六", "Sunday": "周日"
}

# 全局调度器实例
_scheduler = None

def get_scheduler():
    """获取或创建调度器实例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone=TIMEZONE)
    return _scheduler

def job_daily_reminder():
    """
    Runs every day at 9:30 AM to check for TOMORROW's courses.
    Only includes courses with notify_daily=1.
    """
    now = datetime.now(TIMEZONE)
    tomorrow = now + timedelta(days=1)
    tomorrow_day_name = tomorrow.strftime("%A")
    tomorrow_date_str = tomorrow.strftime("%Y-%m-%d")

    # 使用新的函数获取明天的所有课程（包括周期性和一次性）
    courses = get_courses_for_date(tomorrow.date())

    # 过滤出需要每日提醒的课程
    if not courses.empty:
        courses = courses[courses['notify_daily'] == 1]

    if not courses.empty:
        # 使用新的格式化通知接口
        send_daily_notification(courses, tomorrow_day_name, day_map, tomorrow_date_str)
    else:
        print(f"[{now}] No courses with daily notification enabled for tomorrow ({tomorrow_day_name}), no SMS sent.")

def job_weekly_summary_next_week():
    """
    发送下周课程汇总（用于周五提前预览）
    Only includes courses with notify_weekly=1.
    """
    now = datetime.now(TIMEZONE)
    start_date = now + timedelta(days=1)  # 明天开始（周六或下周一）

    courses_by_day = {}
    has_courses = False

    # Loop through next 7 days
    for i in range(7):
        target_date = start_date + timedelta(days=i)
        day_name = target_date.strftime("%A")
        date_str = target_date.strftime("%Y-%m-%d")

        # 使用新的函数获取指定日期的课程
        courses = get_courses_for_date(target_date.date())

        # 过滤出需要周汇总提醒的课程
        if not courses.empty:
            courses = courses[courses['notify_weekly'] == 1]

        courses_by_day[day_name] = courses
        if not courses.empty:
            has_courses = True

    if has_courses:
        # 使用新的格式化通知接口，按固定顺序传递，标记为"下周"
        send_weekly_notification_ordered(courses_by_day, day_map, is_next_week=True)
    else:
        print(f"[{now}] No courses with weekly notification enabled for next week, no SMS sent.")

def job_weekly_summary_this_week():
    """
    发送本周课程汇总（用于周一提醒）
    Only includes courses with notify_weekly=1.
    """
    now = datetime.now(TIMEZONE)
    start_date = now  # 从今天开始（周一）

    courses_by_day = {}
    has_courses = False

    # Loop through this week (7 days from today/Monday)
    for i in range(7):
        target_date = start_date + timedelta(days=i)
        day_name = target_date.strftime("%A")
        date_str = target_date.strftime("%Y-%m-%d")

        # 使用新的函数获取指定日期的课程
        courses = get_courses_for_date(target_date.date())

        # 过滤出需要周汇总提醒的课程
        if not courses.empty:
            courses = courses[courses['notify_weekly'] == 1]

        courses_by_day[day_name] = courses
        if not courses.empty:
            has_courses = True

    if has_courses:
        # 使用新的格式化通知接口，按固定顺序传递，标记为"本周"
        send_weekly_notification_ordered(courses_by_day, day_map, is_next_week=False)
    else:
        print(f"[{now}] No courses with weekly notification enabled for this week, no SMS sent.")

def send_weekly_notification_ordered(courses_by_day, day_map, is_next_week=True):
    """
    按周一到周日的顺序发送每周通知
    
    Args:
        courses_by_day: 按天分组的课程字典
        day_map: 星期映射字典
        is_next_week: 是否是下周（True=下周，False=本周）
    """
    # 创建有序的字典
    ordered_courses = {}
    for day_name in DAY_ORDER:
        if day_name in courses_by_day:
            ordered_courses[day_name] = courses_by_day[day_name]
    
    # 调用通知函数
    from notifier import send_weekly_notification
    send_weekly_notification(ordered_courses, day_map, is_next_week=is_next_week)

def schedule_course_reminders(scheduler):
    """
    为今天的所有课程设置提前提醒（根据课程配置的提前时间）
    这个函数应该每小时运行一次，为当天的课程设置提醒
    Only includes courses with notify_before_start=1.
    """
    now = datetime.now(TIMEZONE)
    today = now.date()
    today_day_name = now.strftime("%A")

    # 使用新的函数获取今天的所有课程
    courses = get_courses_for_date(today)

    if courses.empty:
        print(f"[{now}] 今天没有课程，无需设置提醒")
        return

    # 过滤出需要课前提醒的课程
    courses = courses[courses['notify_before_start'] == 1]

    if courses.empty:
        print(f"[{now}] 没有需要课前提醒的课程")
        return

    # 移除已过期或已设置的提醒（简化处理：每小时重新设置）
    # 实际项目中可以使用 job_id 来管理

    for _, row in courses.iterrows():
        try:
            # 解析课程开始时间
            start_time_str = row['start_time']  # 格式: "HH:MM"
            hour, minute = map(int, start_time_str.split(':'))

            # 获取该课程的提前提醒时间（默认30分钟）
            minutes_before = row.get('notify_minutes_before', 30)
            if pd.isna(minutes_before):
                minutes_before = 30
            else:
                minutes_before = int(minutes_before)

            # 计算提醒时间（根据配置提前）
            course_datetime = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            reminder_datetime = course_datetime - timedelta(minutes=minutes_before)

            # 只设置未来的提醒
            if reminder_datetime > now:
                job_id = f"course_reminder_{row['id']}"

                # 检查是否已存在该提醒
                existing_job = scheduler.get_job(job_id)
                if existing_job:
                    continue  # 已存在，跳过

                # 添加提醒任务
                scheduler.add_job(
                    send_course_reminder,
                    trigger=DateTrigger(run_date=reminder_datetime, timezone=TIMEZONE),
                    args=[row, day_map],
                    id=job_id,
                    replace_existing=True
                )
                print(f"[{now}] 已设置课程提醒: {row['course_name']} at {reminder_datetime.strftime('%H:%M')} (提前{minutes_before}分钟)")
        except Exception as e:
            print(f"[{now}] 设置提醒失败: {row.get('course_name', 'Unknown')} - {e}")

def start_scheduler():
    """启动调度器（用于命令行运行）"""
    scheduler = get_scheduler()
    
    # 检查任务是否已存在，避免重复添加
    existing_jobs = {job.id for job in scheduler.get_jobs()}
    
    # Daily reminder at 9:30 AM
    if 'daily_reminder' not in existing_jobs:
        scheduler.add_job(
            job_daily_reminder,
            CronTrigger(hour=9, minute=30, timezone=TIMEZONE),
            id='daily_reminder'
        )
    
    # Weekly summary on Friday at 15:00 (3 PM) - 下周预览
    if 'weekly_summary_friday' not in existing_jobs:
        scheduler.add_job(
            job_weekly_summary_next_week,
            CronTrigger(day_of_week='fri', hour=15, minute=0, timezone=TIMEZONE),
            id='weekly_summary_friday'
        )

    # Weekly summary on Monday at 9:00 (9 AM) - 本周提醒
    if 'weekly_summary_monday' not in existing_jobs:
        scheduler.add_job(
            job_weekly_summary_this_week,
            CronTrigger(day_of_week='mon', hour=9, minute=0, timezone=TIMEZONE),
            id='weekly_summary_monday'
        )
    
    # 每小时检查一次，为当天的课程设置30分钟前提醒
    if 'schedule_course_reminders' not in existing_jobs:
        scheduler.add_job(
            lambda: schedule_course_reminders(scheduler),
            CronTrigger(minute=0, timezone=TIMEZONE),  # 每小时的第0分钟运行
            id='schedule_course_reminders'
        )
    
    # 启动时立即执行一次（设置当天的提醒）
    schedule_course_reminders(scheduler)
    
    print("Scheduler started. Press Ctrl+C to exit.")
    scheduler.start()
    
    try:
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

def start_scheduler_background():
    """在后台启动调度器（用于 Streamlit 集成）"""
    scheduler = get_scheduler()
    
    # 检查是否已启动
    if scheduler.running:
        print("[Scheduler] 调度器已在运行中")
        return
    
    # 检查任务是否已存在，避免重复添加
    existing_jobs = {job.id for job in scheduler.get_jobs()}
    
    # Daily reminder at 9:30 AM
    if 'daily_reminder' not in existing_jobs:
        scheduler.add_job(
            job_daily_reminder,
            CronTrigger(hour=9, minute=30, timezone=TIMEZONE),
            id='daily_reminder'
        )
    
    # Weekly summary on Friday at 15:00 (3 PM) - 下周预览
    if 'weekly_summary_friday' not in existing_jobs:
        scheduler.add_job(
            job_weekly_summary_next_week,
            CronTrigger(day_of_week='fri', hour=15, minute=0, timezone=TIMEZONE),
            id='weekly_summary_friday'
        )

    # Weekly summary on Monday at 9:00 (9 AM) - 本周提醒
    if 'weekly_summary_monday' not in existing_jobs:
        scheduler.add_job(
            job_weekly_summary_this_week,
            CronTrigger(day_of_week='mon', hour=9, minute=0, timezone=TIMEZONE),
            id='weekly_summary_monday'
        )
    
    # 每小时检查一次，为当天的课程设置30分钟前提醒
    if 'schedule_course_reminders' not in existing_jobs:
        scheduler.add_job(
            lambda: schedule_course_reminders(scheduler),
            CronTrigger(minute=0, timezone=TIMEZONE),
            id='schedule_course_reminders'
        )
    
    # 启动时立即执行一次（设置当天的提醒）
    schedule_course_reminders(scheduler)
    
    print("[Scheduler] 后台调度器已启动")
    scheduler.start()

if __name__ == "__main__":
    start_scheduler()
