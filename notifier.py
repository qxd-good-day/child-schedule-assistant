import datetime
import json
import sys
import traceback
import requests
import os

# ==================== 通知配置 ====================
# 选择要使用的通知方式: "serverchan" | "aliyun" | "mock"
NOTIFIER_TYPE = os.getenv("NOTIFIER_TYPE", "serverchan")  # 默认使用 Server 酱

# Server 酱配置 (https://sct.ftqq.com/)
# 支持多个 SendKey，实现给多个微信发送通知
# 从环境变量读取，多个 key 用逗号分隔
SERVERCHAN_SENDKEYS = os.getenv("SERVERCHAN_SENDKEYS", "").split(",") if os.getenv("SERVERCHAN_SENDKEYS") else []

# 自定义通知模板配置
NOTIFICATION_CONFIG = {
    # 每日提醒模板
    "daily_title": "📚 明天有{course_count}个课外课",
    "daily_header": "## 📅 明天的课程安排\n\n",
    "daily_course_format": "**{time}** | {name} 📍{location} {pickup_info}\n\n",
    "daily_footer": "\n---\n⏰ 记得按时接送孩子哦~",

    # 每周汇总模板（下周预览）
    "weekly_title": "📊 下周课程预览（共{course_count}节课）",
    "weekly_header": "## 📅 下周课程安排\n\n",
    "weekly_day_format": "### {day}\n",
    "weekly_course_format": "- **{time}** {name} 📍{location} {pickup_info}\n",
    "weekly_course_separator": "\n",  # 课程之间添加空行分隔
    "weekly_footer": "\n---\n💪 新的一周，加油！",

    # 每周汇总模板（本周提醒）
    "this_week_title": "📊 本周课程安排（共{course_count}节课）",
    "this_week_header": "## 📅 本周课程安排\n\n",
    "this_week_footer": "\n---\n💪 本周加油！",

    # 课程开始前提醒模板
    "reminder_title": "⏰ 课程即将开始：{course_name}",
    "reminder_content": "**{course_name}** 将在30分钟后开始\n\n📍 地点：{location}\n🕐 时间：{start_time}\n{pickup_info}\n\n🚗 准备好出发了吗？",

    # 是否使用 Markdown 格式（推荐开启）
    "use_markdown": True,

    # 是否添加课程表链接（如果有的话）
    "schedule_url": None,  # 例如: "https://your-app-url.com"
}

# Aliyun SMS Configuration (备用)
# 从环境变量读取敏感信息
ALIYUN_ACCESS_KEY_ID = os.getenv("ALIYUN_ACCESS_KEY_ID", "")
ALIYUN_ACCESS_KEY_SECRET = os.getenv("ALIYUN_ACCESS_KEY_SECRET", "")
ALIYUN_TEMPLATE_CODE = os.getenv("ALIYUN_TEMPLATE_CODE", "")
ALIYUN_SIGN_NAME = os.getenv("ALIYUN_SIGN_NAME", "")

try:
    from alibabacloud_dysmsapi20170525.client import Client as Dysmsapi20170525Client
    from alibabacloud_tea_openapi import models as open_api_models
    from alibabacloud_dysmsapi20170525 import models as dysmsapi_20170525_models
    HAS_ALIYUN_SDK = True
except ImportError:
    HAS_ALIYUN_SDK = False

def create_client(access_key_id: str, access_key_secret: str) -> Dysmsapi20170525Client:
    """Initialize the Aliyun SMS client."""
    config = open_api_models.Config(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret
    )
    config.endpoint = f'dysmsapi.aliyuncs.com'
    return Dysmsapi20170525Client(config)

def send_serverchan(title, content, sendkey=None, **kwargs):
    """
    使用 Server 酱发送微信推送
    支持给多个微信发送通知

    Args:
        title: 消息标题
        content: 消息内容（支持 Markdown）
        sendkey: Server 酱的 SendKey（单个或列表）
        **kwargs: 额外参数
            - openid: 指定接收用户（多用户场景）
    """
    # 确定要使用的 SendKeys
    if sendkey:
        # 如果传入了单个 sendkey，转换为列表
        keys = [sendkey] if isinstance(sendkey, str) else sendkey
    else:
        # 使用配置的 SendKeys 列表
        keys = SERVERCHAN_SENDKEYS

    if not keys:
        print("[Server 酱] 未配置 SendKey，跳过发送")
        return False

    # 确保 keys 是列表
    if isinstance(keys, str):
        keys = [keys]

    results = []

    for key in keys:
        # 跳过空的或注释掉的 key
        if not key or key.strip().startswith('#'):
            continue

        try:
            url = f"https://sctapi.ftqq.com/{key}.send"
            data = {
                "title": title[:100],  # 标题限制100字符
                "desp": content[:1000]  # 内容限制1000字符
            }

            # 如果有指定接收用户
            if 'openid' in kwargs:
                data['openid'] = kwargs['openid']

            response = requests.post(url, data=data, timeout=10)
            result = response.json()

            if result.get("code") == 0 or result.get("data", {}).get("error") == "SUCCESS":
                print(f"[Server 酱] 推送成功 ({key[:10]}...): {title}")
                results.append(True)
            else:
                print(f"[Server 酱] 推送失败 ({key[:10]}...): {result}")
                results.append(False)

        except Exception as e:
            print(f"[Server 酱] 发送异常 ({key[:10]}...): {e}")
            results.append(False)

    # 只要有一个成功就返回 True
    return any(results)

def format_daily_notification(courses, day_name, day_map, target_date_str=None):
    """
    格式化每日课程提醒（支持 Markdown）

    Args:
        courses: DataFrame 课程数据
        day_name: 星期几（英文）
        day_map: 星期映射字典
        target_date_str: 目标日期字符串 'YYYY-MM-DD'
    """
    config = NOTIFICATION_CONFIG
    course_count = len(courses)

    # 标题 - 直接显示课程名称
    if course_count == 1:
        course_name = courses.iloc[0]['course_name']
        title = f"明天 {course_name}"
    else:
        title = config["daily_title"].format(course_count=course_count)

    # 内容头部
    content = config["daily_header"]

    # 添加日期信息
    if target_date_str:
        content += f"**明天是 {day_map.get(day_name, day_name)} ({target_date_str})**\n\n"
    else:
        content += f"**明天是 {day_map.get(day_name, day_name)}**\n\n"

    # 格式化每个课程
    for _, row in courses.iterrows():
        pickup_info = ""
        if row['pickup_time']:
            pickup_info = f"🚗接娃:{row['pickup_time']}"
        
        # 添加课程类型标识
        course_type_icon = ""
        if row.get('course_type') == 'one_time':
            course_type_icon = "📅 "
        elif row.get('course_type') == 'recurring':
            course_type_icon = "🔁 "

        course_line = config["daily_course_format"].format(
            time=row['start_time'],
            name=f"{course_type_icon}{row['course_name']}",
            location=row['location'],
            pickup_info=pickup_info
        )
        content += course_line

    # 添加页脚
    content += config["daily_footer"]

    # 如果有课程表链接，添加查看链接
    if config.get("schedule_url"):
        content += f"\n\n[📱 查看完整课表]({config['schedule_url']})"

    return title, content

def format_weekly_notification(courses_by_day, day_map, is_next_week=True):
    """
    格式化每周课程汇总（支持 Markdown）
    同一天的多个课程会分开显示，每行一个

    Args:
        courses_by_day: 按天分组的课程字典
        day_map: 星期映射字典
        is_next_week: 是否是下周（True=下周，False=本周）
    """
    config = NOTIFICATION_CONFIG
    total_courses = sum(len(courses) for courses in courses_by_day.values())

    # 根据本周/下周选择不同的模板
    if is_next_week:
        title = config["weekly_title"].format(course_count=total_courses)
        content = config["weekly_header"]
    else:
        title = config["this_week_title"].format(course_count=total_courses)
        content = config["this_week_header"]

    # 格式化每天的课程
    for day_name, courses in courses_by_day.items():
        if not courses.empty:
            content += config["weekly_day_format"].format(day=day_map.get(day_name, day_name))

            # 获取课程数量
            course_count = len(courses)

            for idx, (_, row) in enumerate(courses.iterrows()):
                pickup_info = ""
                if row['pickup_time']:
                    pickup_info = f"(接:{row['pickup_time']})"
                
                # 添加课程类型标识
                course_type_icon = ""
                if row.get('course_type') == 'one_time':
                    course_type_icon = "📅 "
                elif row.get('course_type') == 'recurring':
                    course_type_icon = "🔁 "

                # 格式化单个课程
                course_line = config["weekly_course_format"].format(
                    time=row['start_time'],
                    name=f"{course_type_icon}{row['course_name']}",
                    location=row['location'],
                    pickup_info=pickup_info
                )
                content += course_line

                # 如果不是最后一个课程，添加分隔符（空行）
                if idx < course_count - 1:
                    content += config.get("weekly_course_separator", "\n")

            # 每天结束后添加空行
            content += "\n"

    # 添加页脚（根据本周/下周选择不同的页脚）
    if is_next_week:
        content += config["weekly_footer"]
    else:
        content += config["this_week_footer"]

    # 如果有课程表链接
    if config.get("schedule_url"):
        content += f"\n\n[📱 查看完整课表]({config['schedule_url']})"

    return title, content

def send_aliyun_sms(message, phone_number="18298020072", **kwargs):
    """发送阿里云短信"""
    if not HAS_ALIYUN_SDK:
        print("[阿里云短信] SDK 未安装，跳过发送")
        return False

    try:
        client = create_client(ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET)

        course_count = kwargs.get('course_count', '1')
        content = f"{course_count}个课程"

        template_params = {
            'content': content[:20]
        }

        for key, value in kwargs.items():
            if key not in template_params:
                template_params[key] = str(value)[:20]

        send_sms_request = dysmsapi_20170525_models.SendSmsRequest(
            sign_name=ALIYUN_SIGN_NAME,
            template_code=ALIYUN_TEMPLATE_CODE,
            phone_numbers=phone_number,
            template_param=json.dumps(template_params)
        )

        from alibabacloud_tea_util import models as util_models
        runtime = util_models.RuntimeOptions()

        resp = client.send_sms_with_options(send_sms_request, runtime)

        if resp.body.code != 'OK':
            print(f"[阿里云短信] 发送失败: {resp.body.message} (Code: {resp.body.code})")
            return False
        else:
            print(f"[阿里云短信] 发送成功 to {phone_number}")
            return True

    except Exception as e:
        print(f"[阿里云短信] 发送异常: {e}")
        return False

def send_sms(message, phone_number="18298020072", **kwargs):
    """
    统一的发送接口，根据 NOTIFIER_TYPE 选择发送方式

    Args:
        message: 消息内容（兼容旧接口）
        phone_number: 手机号（用于阿里云短信）
        **kwargs: 额外参数
            - title: 自定义标题（Server 酱）
            - content: 自定义内容（Server 酱）
            - courses: 课程数据（用于格式化）
            - day_name: 星期几
            - day_map: 星期映射
            - is_weekly: 是否是每周汇总
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 总是打印到控制台（用于调试）
    print(f"[{timestamp}] [通知消息]")
    print(f"  内容: {message}")
    if kwargs:
        print(f"  参数: {kwargs}")

    # 根据配置选择发送方式
    if NOTIFIER_TYPE == "serverchan":
        # 如果有预格式化的标题和内容，直接使用
        if 'title' in kwargs and 'content' in kwargs:
            return send_serverchan(kwargs['title'], kwargs['content'])

        # 否则使用旧的方式（从 message 中提取标题）
        lines = message.split('\n')
        title = lines[0] if lines else "课程提醒"
        content = message
        return send_serverchan(title, content)

    elif NOTIFIER_TYPE == "aliyun":
        return send_aliyun_sms(message, phone_number, **kwargs)

    else:  # mock 模式，只打印不发送
        print(f"[{timestamp}] [Mock模式] 仅控制台输出，未发送真实通知")
        return True

# 兼容旧接口
def send_notification(message, **kwargs):
    """兼容旧代码的接口"""
    return send_sms(message, **kwargs)

# 新增：直接发送格式化通知的接口
def send_daily_notification(courses, day_name, day_map, target_date_str=None):
    """发送每日课程提醒（带格式化）
    
    Args:
        courses: DataFrame 课程数据
        day_name: 星期几（英文）
        day_map: 星期映射字典
        target_date_str: 目标日期字符串 'YYYY-MM-DD'
    """
    if NOTIFIER_TYPE == "serverchan":
        title, content = format_daily_notification(courses, day_name, day_map, target_date_str)
        return send_serverchan(title, content)
    else:
        # 其他通知方式使用旧的简单格式
        date_info = f"({target_date_str})" if target_date_str else ""
        msg_lines = [f"【课程提醒】明天({day_map.get(day_name, day_name)}{date_info})的安排："]
        for _, row in courses.iterrows():
            type_icon = "📅" if row.get('course_type') == 'one_time' else "🔁"
            line = f"- {type_icon} {row['start_time']} {row['course_name']} @ {row['location']}"
            if row['pickup_time']:
                line += f" (接娃: {row['pickup_time']})"
            msg_lines.append(line)
        message = "\n".join(msg_lines)
        return send_sms(message, course_count=len(courses))

def send_weekly_notification(courses_by_day, day_map, is_next_week=True):
    """发送每周课程汇总（带格式化）
    
    Args:
        courses_by_day: 按天分组的课程字典
        day_map: 星期映射字典
        is_next_week: 是否是下周（True=下周预览，False=本周安排）
    """
    if NOTIFIER_TYPE == "serverchan":
        title, content = format_weekly_notification(courses_by_day, day_map, is_next_week)
        return send_serverchan(title, content)
    else:
        # 其他通知方式使用旧的简单格式
        if is_next_week:
            msg_lines = ["【下周课程预览】"]
        else:
            msg_lines = ["【本周课程安排】"]
        total_courses = 0
        for day_name, courses in courses_by_day.items():
            if not courses.empty:
                total_courses += len(courses)
                msg_lines.append(f"\n{day_map.get(day_name, day_name)}:")
                for _, row in courses.iterrows():
                    type_icon = "📅" if row.get('course_type') == 'one_time' else "🔁"
                    line = f"  {type_icon} {row['start_time']} {row['course_name']} @ {row['location']}"
                    if row['pickup_time']:
                        line += f" (接: {row['pickup_time']})"
                    msg_lines.append(line)
        message = "\n".join(msg_lines)
        return send_sms(message, course_count=total_courses)

# 新增：课程开始前提醒
def send_course_reminder(course_row, day_map):
    """
    发送单个课程的开始前提醒（提前30分钟）

    Args:
        course_row: Series 单条课程数据
        day_map: 星期映射字典
    """
    config = NOTIFICATION_CONFIG

    # 准备数据
    course_name = course_row['course_name']
    location = course_row['location']
    start_time = course_row['start_time']
    pickup_info = ""

    if course_row['pickup_time']:
        pickup_info = f"🚗 接娃时间：{course_row['pickup_time']}"

    # 格式化标题和内容
    title = config["reminder_title"].format(course_name=course_name)
    content = config["reminder_content"].format(
        course_name=course_name,
        location=location,
        start_time=start_time,
        pickup_info=pickup_info
    )

    # 发送通知
    if NOTIFIER_TYPE == "serverchan":
        return send_serverchan(title, content)
    else:
        # 其他通知方式使用简化格式
        message = f"【课程提醒】{course_name} 将在30分钟后开始，地点：{location}"
        return send_sms(message)
