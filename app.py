import streamlit as st
import pandas as pd
import os
import threading
import time
from datetime import datetime, timedelta, date
from database import init_db, add_course, get_all_courses, delete_course, seed_initial_data, migrate_db, update_course, get_course_by_id
from ai_processor import extract_schedule_from_image, extract_schedule_from_text, mock_extract_schedule
from scheduler import job_daily_reminder, job_weekly_summary_next_week, job_weekly_summary_this_week, start_scheduler_background
from attendance import (
    init_attendance_db, record_attendance, get_attendance_by_date,
    get_attendance_by_course, get_attendance_by_date_range, get_all_attendance,
    delete_attendance_record, get_attendance_stats_by_course, get_monthly_attendance_stats,
    get_weekly_attendance_trend, get_course_attendance_ranking, get_upcoming_courses_without_record,
    get_status_label, get_status_color, STATUS_LABELS
)

# Page Config - 艾莎公主冰雪主题
st.set_page_config(
    page_title="❄️ 艾莎公主课程表 ❄️",
    page_icon="👑",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 全局CSS样式 - 艾莎公主冰雪主题
st.markdown("""
<style>
/* 导入字体 - 添加优雅的迪士尼风格字体 */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&family=Quicksand:wght@400;600;700&display=swap');

/* 全局字体 */
* {
    font-family: 'Quicksand', 'Noto Sans SC', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* 隐藏默认头部 */
[data-testid="stHeader"] {
    display: none !important;
}

/* 主容器样式 - 冰雪奇缘蓝紫渐变 */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #1a3a5c 0%, #2d5a87 30%, #4a90c6 60%, #87CEEB 100%);
    min-height: 100vh;
    background-attachment: fixed;
}

/* 内容区域 */
.block-container {
    padding: 1rem !important;
    max-width: 1200px;
}

/* 卡片通用样式 - 冰雪水晶效果 */
.stCard {
    background: rgba(255, 255, 255, 0.92);
    border-radius: 20px;
    padding: 1.5rem;
    box-shadow: 0 8px 32px rgba(74, 144, 198, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.6);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.5);
}

/* 移动端适配 */
@media (max-width: 768px) {
    .block-container {
        padding: 0.75rem !important;
    }
    
    .main-title {
        font-size: 1.75rem !important;
    }
    
    .subtitle {
        font-size: 0.9rem !important;
    }
    
    /* 课程表网格 */
    .schedule-grid {
        grid-template-columns: 50px repeat(7, 1fr) !important;
        gap: 2px !important;
        font-size: 0.65rem !important;
    }
    
    .schedule-header {
        padding: 6px 2px !important;
        font-size: 0.6rem !important;
    }
    
    .schedule-time-slot {
        padding: 6px 2px !important;
        font-size: 0.6rem !important;
    }
    
    .schedule-cell {
        padding: 4px 2px !important;
        min-height: 55px !important;
    }
    
    .cell-course-name {
        font-size: 0.6rem !important;
    }
    
    /* 统计卡片 */
    .stat-card {
        padding: 0.75rem !important;
    }
    
    .stat-number {
        font-size: 1.5rem !important;
    }
    
    /* 按钮 */
    .stButton > button {
        font-size: 0.9rem !important;
        padding: 0.6rem 1.2rem !important;
    }
    
    /* 标签页 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px !important;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 0.5rem 0.75rem !important;
        font-size: 0.8rem !important;
    }
}

/* 触摸优化 */
.stButton > button, .stSelectbox > div, .stTextInput > div {
    min-height: 44px !important;
}

/* 滚动条美化 */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}

::-webkit-scrollbar-track {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 3px;
}

::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.3);
    border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.5);
}
</style>
""", unsafe_allow_html=True)

# 默认使用阿里云 DashScope API Key
DEFAULT_DASHSCOPE_API_KEY = "sk-505d451414fc484685dd98f359e978d9"
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL_TEXT = "qwen-max-latest"
DEFAULT_MODEL_IMAGE = "qwen-vl-max-latest"

# Initialize DB
if 'db_initialized' not in st.session_state:
    init_db()
    migrate_db()  # 迁移数据库添加新字段
    init_attendance_db()
    st.session_state['db_initialized'] = True

# 启动后台调度器（只启动一次）
if 'scheduler_started' not in st.session_state:
    scheduler_thread = threading.Thread(target=start_scheduler_background, daemon=True)
    scheduler_thread.start()
    st.session_state['scheduler_started'] = True
    print("[App] 后台调度器已启动")

# 星期顺序和映射
WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_MAP = {
    "Monday": "周一", "Tuesday": "周二", "Wednesday": "周三",
    "Thursday": "周四", "Friday": "周五", "Saturday": "周六", "Sunday": "周日"
}

def load_css():
    st.markdown("""
    <style>
    /* 主标题样式 - 艾莎公主冰雪风格 */
    .main-title {
        text-align: center;
        color: white;
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0.5rem 0;
        text-shadow: 0 0 20px rgba(135, 206, 235, 0.8), 0 0 40px rgba(74, 144, 198, 0.6), 0 2px 10px rgba(0, 0, 0, 0.3);
        letter-spacing: 2px;
        font-family: 'Quicksand', sans-serif;
    }
    
    .subtitle {
        text-align: center;
        color: rgba(255, 255, 255, 0.9);
        font-size: 1.1rem;
        margin-bottom: 1.5rem;
        font-weight: 500;
        text-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
    }
    
    /* 内容卡片 - 冰雪水晶 */
    .content-card {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(230, 245, 255, 0.95) 100%);
        border-radius: 24px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 8px 32px rgba(74, 144, 198, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.8);
        border: 2px solid rgba(255, 255, 255, 0.6);
    }
    
    /* 课程表网格样式 - 冰雪奇缘风格 */
    .schedule-grid {
        display: grid;
        grid-template-columns: 60px repeat(7, 1fr);
        gap: 4px;
        background: rgba(255, 255, 255, 0.3);
        border-radius: 20px;
        padding: 12px;
        font-size: 0.85rem;
        overflow-x: auto;
        border: 2px solid rgba(255, 255, 255, 0.4);
        box-shadow: 0 4px 20px rgba(74, 144, 198, 0.2);
    }
    
    .schedule-header {
        background: linear-gradient(135deg, #4a90c6 0%, #87CEEB 50%, #B0E0E6 100%);
        color: white;
        padding: 10px 4px;
        text-align: center;
        font-weight: 700;
        font-size: 0.85rem;
        border-radius: 12px;
        text-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.5);
    }
    
    .schedule-time-slot {
        background: linear-gradient(135deg, rgba(74, 144, 198, 0.15) 0%, rgba(135, 206, 235, 0.2) 100%);
        padding: 10px 4px;
        text-align: center;
        font-weight: 600;
        color: #2d5a87;
        font-size: 0.8rem;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.3);
    }
    
    .schedule-cell {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(240, 248, 255, 0.95) 100%);
        padding: 8px 4px;
        min-height: 65px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        text-align: center;
        border-radius: 12px;
        transition: all 0.2s ease;
        border: 1px solid rgba(255, 255, 255, 0.6);
        box-shadow: 0 2px 8px rgba(74, 144, 198, 0.1);
    }
    
    .schedule-cell:hover {
        transform: translateY(-2px) scale(1.02);
        box-shadow: 0 6px 20px rgba(74, 144, 198, 0.25);
        border-color: rgba(135, 206, 235, 0.8);
    }
    
    /* 课程颜色 - 艾莎公主冰雪配色 */
    .course-color-0 { background: linear-gradient(135deg, #E3F2FD 0%, #BBDEFB 100%); border: 1px solid #90CAF9; }
    .course-color-1 { background: linear-gradient(135deg, #F3E5F5 0%, #E1BEE7 100%); border: 1px solid #CE93D8; }
    .course-color-2 { background: linear-gradient(135deg, #E0F7FA 0%, #B2EBF2 100%); border: 1px solid #80DEEA; }
    .course-color-3 { background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%); border: 1px solid #A5D6A7; }
    .course-color-4 { background: linear-gradient(135deg, #FFF3E0 0%, #FFE0B2 100%); border: 1px solid #FFCC80; }
    .course-color-5 { background: linear-gradient(135deg, #FCE4EC 0%, #F8BBD9 100%); border: 1px solid #F48FB1; }
    .course-color-6 { background: linear-gradient(135deg, #E1F5FE 0%, #B3E5FC 100%); border: 1px solid #81D4FA; }
    .course-color-7 { background: linear-gradient(135deg, #EDE7F6 0%, #D1C4E9 100%); border: 1px solid #B39DDB; }
    .course-color-8 { background: linear-gradient(135deg, #E0F2F1 0%, #B2DFDB 100%); border: 1px solid #80CBC4; }
    .course-color-9 { background: linear-gradient(135deg, #FFF8E1 0%, #FFECB3 100%); border: 1px solid #FFE082; }
    
    .cell-course-name {
        font-weight: 600;
        color: #2d3748;
        font-size: 0.8rem;
        line-height: 1.2;
    }
    
    .cell-course-time {
        color: #4a5568;
        font-size: 0.7rem;
        margin-top: 2px;
    }
    
    .cell-course-location {
        color: #718096;
        font-size: 0.65rem;
        margin-top: 1px;
    }
    
    /* 统计卡片 - 艾莎公主冰雪风格 */
    .stat-card {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(230, 245, 255, 0.95) 100%);
        border-radius: 20px;
        padding: 1.25rem;
        text-align: center;
        box-shadow: 0 6px 20px rgba(74, 144, 198, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.8);
        border: 2px solid rgba(255, 255, 255, 0.6);
        transition: transform 0.2s ease;
    }
    
    .stat-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(74, 144, 198, 0.3);
    }
    
    .stat-number {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #4a90c6 0%, #87CEEB 50%, #B0E0E6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        text-shadow: 0 2px 4px rgba(74, 144, 198, 0.2);
    }
    
    .stat-label {
        color: #5a7a9a;
        font-size: 0.9rem;
        font-weight: 600;
        margin-top: 0.25rem;
    }
    
    /* 按钮样式 - 艾莎公主冰雪风格 */
    .stButton > button {
        border-radius: 16px !important;
        font-weight: 700 !important;
        background: linear-gradient(135deg, #4a90c6 0%, #87CEEB 50%, #B0E0E6 100%) !important;
        color: white !important;
        border: 2px solid rgba(255, 255, 255, 0.5) !important;
        box-shadow: 0 4px 15px rgba(74, 144, 198, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.3) !important;
        transition: all 0.2s ease !important;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2) !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 25px rgba(74, 144, 198, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.4) !important;
        background: linear-gradient(135deg, #5aa0d6 0%, #97d4f5 50%, #c0f0f6 100%) !important;
    }
    
    [data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, #E1BEE7 0%, #CE93D8 50%, #BA68C8 100%) !important;
        box-shadow: 0 4px 15px rgba(206, 147, 216, 0.4) !important;
    }
    
    [data-testid="stBaseButton-primary"]:hover {
        box-shadow: 0 6px 25px rgba(206, 147, 216, 0.5) !important;
        background: linear-gradient(135deg, #f1cee7 0%, #dea3e8 50%, #ca78d8 100%) !important;
    }
    
    /* 侧边栏样式 - 冰雪主题 */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(230, 245, 255, 0.98) 100%) !important;
        border-right: 2px solid rgba(135, 206, 235, 0.3);
    }
    
    .sidebar-title {
        font-size: 1.2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #4a90c6 0%, #87CEEB 50%, #B0E0E6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem;
        text-shadow: 0 2px 4px rgba(74, 144, 198, 0.1);
    }
    
    /* 标签页样式 - 艾莎公主冰雪风格 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(255, 255, 255, 0.15);
        padding: 0.5rem;
        border-radius: 16px;
        margin-bottom: 1rem;
        border: 1px solid rgba(255, 255, 255, 0.3);
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 12px;
        padding: 0.75rem 1.25rem;
        font-weight: 600;
        color: rgba(255, 255, 255, 0.8);
        background: transparent;
        transition: all 0.2s ease;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(230, 245, 255, 0.95) 100%) !important;
        color: #4a90c6 !important;
        box-shadow: 0 4px 15px rgba(74, 144, 198, 0.3) !important;
        border: 1px solid rgba(135, 206, 235, 0.5);
    }
    
    /* 空状态样式 */
    .empty-state {
        text-align: center;
        padding: 3rem;
        color: rgba(255, 255, 255, 0.7);
    }
    
    .empty-state-icon {
        font-size: 4rem;
        margin-bottom: 1rem;
        opacity: 0.5;
    }
    
    /* 信息卡片 - 冰雪水晶 */
    .info-card {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.15) 0%, rgba(135, 206, 235, 0.1) 100%);
        border-radius: 16px;
        padding: 1rem 1.5rem;
        margin-bottom: 1rem;
        border-left: 4px solid rgba(135, 206, 235, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.3);
        box-shadow: 0 4px 15px rgba(74, 144, 198, 0.15);
    }
    
    .info-card h4 {
        color: white;
        margin: 0 0 0.25rem 0;
        font-size: 1.1rem;
        font-weight: 600;
        text-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
    }
    
    .info-card p {
        color: rgba(255, 255, 255, 0.9);
        margin: 0;
        font-size: 0.9rem;
    }
    
    /* 移动端适配 */
    @media (max-width: 768px) {
        .main-title {
            font-size: 1.75rem !important;
        }
        
        .schedule-grid {
            grid-template-columns: 45px repeat(7, 1fr);
            gap: 2px;
            padding: 8px;
        }
        
        .schedule-header {
            padding: 6px 2px;
            font-size: 0.65rem;
        }
        
        .schedule-time-slot {
            padding: 6px 2px;
            font-size: 0.6rem;
        }
        
        .schedule-cell {
            padding: 4px 2px;
            min-height: 50px;
        }
        
        .cell-course-name {
            font-size: 0.6rem;
        }
        
        .stat-card {
            padding: 0.75rem;
        }
        
        .stat-number {
            font-size: 1.5rem;
        }
        
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px;
            padding: 0.3rem;
        }
        
        .stTabs [data-baseweb="tab"] {
            padding: 0.5rem 0.75rem;
            font-size: 0.8rem;
        }
    }
    
    /* 表单样式优化 - 冰雪主题 */
    .stTextInput > div > div > input,
    .stSelectbox > div > div > select,
    .stTimeInput > div > div > input {
        border-radius: 12px !important;
        border: 2px solid rgba(135, 206, 235, 0.3) !important;
        background: rgba(255, 255, 255, 0.95) !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stSelectbox > div > div > select:focus {
        border-color: #87CEEB !important;
        box-shadow: 0 0 0 4px rgba(135, 206, 235, 0.2) !important;
    }
    
    /* 复选框样式 */
    .stCheckbox > div > div > div {
        background: rgba(255, 255, 255, 0.9) !important;
        border-radius: 6px !important;
    }
    
    /* 数字输入框 */
    .stNumberInput > div > div > input {
        border-radius: 12px !important;
        border: 2px solid rgba(135, 206, 235, 0.3) !important;
    }
    
    /* 文本域 */
    .stTextArea > div > div > textarea {
        border-radius: 12px !important;
        border: 2px solid rgba(135, 206, 235, 0.3) !important;
        background: rgba(255, 255, 255, 0.95) !important;
    }
    </style>
    """, unsafe_allow_html=True)

def main():
    load_css()

    # 艾莎公主主题标题区域
    st.markdown("""
    <div style="text-align: center; padding: 1.5rem 0;">
        <div style="font-size: 4rem; margin-bottom: 0.5rem; animation: sparkle 2s infinite;">👑❄️👑</div>
        <h1 class="main-title">❄️ 艾莎公主课程表 ❄️</h1>
        <p class="subtitle">✨ 让魔法陪伴孩子的学习之旅 ✨</p>
    </div>
    <style>
    @keyframes sparkle {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.8; transform: scale(1.1); }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 移动端检测 - 使用底部导航栏，桌面端使用侧边栏
    st.markdown("""
    <style>
    /* 底部导航栏样式 - 仅移动端显示 */
    @media (max-width: 768px) {
        .mobile-nav {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: linear-gradient(135deg, #fff5f5 0%, #ffe0e0 100%);
            border-top: 2px solid #fecdd3;
            padding: 8px 0;
            z-index: 9999;
            display: flex;
            justify-content: space-around;
            align-items: center;
            box-shadow: 0 -4px 12px rgba(255, 154, 158, 0.2);
        }
        .mobile-nav-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 4px 8px;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 0.7rem;
            color: #666;
        }
        .mobile-nav-item.active {
            background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%);
            color: white;
            transform: scale(1.05);
        }
        .mobile-nav-icon {
            font-size: 1.3rem;
            margin-bottom: 2px;
        }
        /* 为主内容添加底部padding，避免被导航栏遮挡 */
        .main .block-container {
            padding-bottom: 80px !important;
        }
    }
    @media (min-width: 769px) {
        .mobile-nav {
            display: none !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 使用session_state存储当前页面
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "📊 查看课表"
    
    # 底部导航栏（移动端）
    nav_items = [
        ("📊", "课表", "📊 查看课表"),
        ("➕", "添加", "➕ 添加课程"),
        ("📋", "出勤", "📋 出勤记录"),
        ("📈", "分析", "📈 出勤分析"),
    ]
    
    # 创建底部导航
    nav_cols = st.columns(4)
    for i, (icon, label, page_name) in enumerate(nav_items):
        with nav_cols[i]:
            is_active = st.session_state.current_page == page_name
            btn_type = "primary" if is_active else "secondary"
            if st.button(f"{icon}\n{label}", key=f"nav_{i}", type=btn_type, use_container_width=True):
                st.session_state.current_page = page_name
                st.rerun()
    
    # 侧边栏（桌面端）- 添加更多选项
    with st.sidebar:
        st.markdown('<div class="sidebar-title">🧭 功能导航</div>', unsafe_allow_html=True)
        sidebar_page = st.radio(
            "选择功能",
            ["📊 查看课表", "➕ 添加课程", "📋 出勤记录", "📈 出勤分析", "🔔 通知测试"],
            label_visibility="collapsed",
            index=["📊 查看课表", "➕ 添加课程", "📋 出勤记录", "📈 出勤分析", "🔔 通知测试"].index(st.session_state.current_page) if st.session_state.current_page in ["📊 查看课表", "➕ 添加课程", "📋 出勤记录", "📈 出勤分析", "🔔 通知测试"] else 0
        )
        # 同步侧边栏和底部导航
        if sidebar_page != st.session_state.current_page:
            st.session_state.current_page = sidebar_page
            st.rerun()
    
    page = st.session_state.current_page
    
    # 默认使用已配置的 DashScope API Key（不在页面显示）
    api_key = DEFAULT_DASHSCOPE_API_KEY
    base_url = DEFAULT_BASE_URL
    model_text = DEFAULT_MODEL_TEXT
    model_image = DEFAULT_MODEL_IMAGE

    # 通知设置（已默认配置为 Server 酱，不在页面显示）
    import notifier
    notifier.NOTIFIER_TYPE = "serverchan"

    if page == "📊 查看课表":
        show_schedule_page()
    elif page == "➕ 添加课程":
        show_add_course_page(api_key, base_url, model_text, model_image)
    elif page == "📋 出勤记录":
        show_attendance_page()
    elif page == "📈 出勤分析":
        show_attendance_analysis_page()
    elif page == "🔔 通知测试":
        show_notification_test_page()

def show_schedule_page():
    df = get_all_courses()
    
    # 统计信息
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{len(df)}</div>
            <div class="stat-label">总课程数</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        unique_days = df['day_of_week'].nunique() if not df.empty else 0
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{unique_days}</div>
            <div class="stat-label">上课天数</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        weekend_courses = len(df[df['day_of_week'].isin(['Saturday', 'Sunday'])]) if not df.empty else 0
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{weekend_courses}</div>
            <div class="stat-label">周末课程</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    if df.empty:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">📚</div>
            <h3 style="margin-bottom: 0.5rem;">暂无课程安排</h3>
            <p>快去"添加课程"页面创建你的第一张课程表吧！</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # 课程表网格布局
        html = ['<div class="schedule-grid">']
        
        # 表头
        html.append('<div class="schedule-header">时间</div>')
        for day in WEEKDAY_ORDER:
            html.append(f'<div class="schedule-header">{WEEKDAY_MAP[day]}</div>')
        
        # 获取所有课程按时间分组
        all_courses_by_time = {}
        for day in WEEKDAY_ORDER:
            day_courses = df[df['day_of_week'] == day]
            for _, course in day_courses.iterrows():
                time_key = f"{course['start_time']}"
                if time_key not in all_courses_by_time:
                    all_courses_by_time[time_key] = {}
                all_courses_by_time[time_key][day] = course
        
        # 按时间排序
        sorted_times = sorted(all_courses_by_time.keys())
        
        # 为每个课程名称分配颜色索引
        course_names = df['course_name'].unique()
        course_color_map = {name: idx % 10 for idx, name in enumerate(course_names)}
        
        # 生成每一行
        for time_key in sorted_times:
            html.append(f'<div class="schedule-time-slot">{time_key}</div>')
            for day in WEEKDAY_ORDER:
                if day in all_courses_by_time[time_key]:
                    course = all_courses_by_time[time_key][day]
                    color_idx = course_color_map.get(course['course_name'], 0)
                    color_class = f"course-color-{color_idx}"
                    location = course['location'][:4] + '..' if len(course['location']) > 4 else course['location']
                    html.append(f'''<div class="schedule-cell {color_class}">
                        <div class="cell-course-name">{course['course_name']}</div>
                        <div class="cell-course-time">{course['start_time']}-{course['end_time'][:5]}</div>
                        {f'<div class="cell-course-location">{location}</div>' if location else ''}
                    </div>''')
                else:
                    html.append('<div class="schedule-cell"></div>')
        
        html.append('</div>')
        st.markdown(''.join(html), unsafe_allow_html=True)
        
        # 管理课程部分
        st.markdown("---")
        st.subheader("✏️ 管理课程")
        
        display_df = df.copy()
        
        # 添加课程类型标识
        def format_course_display(x):
            day = WEEKDAY_MAP.get(x['day_of_week'], x['day_of_week'])
            name = x['course_name']
            time = x['start_time']
            type_icon = "📅" if x.get('course_type') == 'one_time' else "🔁"
            date_info = f" ({x['course_date']})" if pd.notna(x.get('course_date')) and x.get('course_type') == 'one_time' else ""
            return f"{type_icon} {day} {time} - {name}{date_info}"
        
        display_df["display_text"] = display_df.apply(format_course_display, axis=1)
        
        # 修改课程功能
        st.markdown("**修改课程**")
        col1, col2 = st.columns([3, 1])
        with col1:
            course_to_edit = st.selectbox(
                "选择要修改的课程",
                display_df["display_text"].tolist(),
                label_visibility="collapsed",
                key="edit_select"
            )
        with col2:
            if st.button("✏️ 修改课程", use_container_width=True):
                if course_to_edit:
                    selected_course = display_df[display_df["display_text"] == course_to_edit].iloc[0]
                    st.session_state['editing_course'] = selected_course.to_dict()
                    st.rerun()
        
        # 显示编辑表单
        if 'editing_course' in st.session_state:
            st.markdown("---")
            st.markdown("**编辑课程信息**")
            course = st.session_state['editing_course']
            
            with st.form("edit_course_form"):
                # 课程类型选择
                course_type = st.radio(
                    "课程类型",
                    options=["recurring", "one_time"],
                    format_func=lambda x: "🔁 周期重复" if x == "recurring" else "📅 一次性/临时",
                    horizontal=True,
                    index=0 if course.get('course_type') == 'recurring' else 1
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    day = st.selectbox(
                        "星期", 
                        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                        index=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(course['day_of_week'])
                    )
                    course_name = st.text_input("课程名称", value=course['course_name'])
                    location = st.text_input("地点", value=course['location'] if course['location'] else "")
                with col2:
                    start_time = st.text_input("开始时间 (HH:MM)", value=course['start_time'])
                    end_time = st.text_input("结束时间 (HH:MM)", value=course['end_time'])
                    pickup_time = st.text_input("接娃时间 (HH:MM)", value=course['pickup_time'] if course['pickup_time'] else "")
                
                # 根据课程类型显示不同字段
                if course_type == "one_time":
                    course_date_val = course.get('course_date')
                    if course_date_val and pd.notna(course_date_val):
                        try:
                            course_date = st.date_input("课程日期", value=datetime.strptime(course_date_val, "%Y-%m-%d").date())
                        except:
                            course_date = st.date_input("课程日期", value=date.today())
                    else:
                        course_date = st.date_input("课程日期", value=date.today())
                    end_date = None
                else:
                    col1, col2 = st.columns(2)
                    with col1:
                        end_date_val = course.get('end_date')
                        enable_end_date = st.checkbox("设置结束日期", value=end_date_val is not None and pd.notna(end_date_val))
                    with col2:
                        if enable_end_date:
                            if end_date_val and pd.notna(end_date_val):
                                try:
                                    end_date = st.date_input("结束日期", value=datetime.strptime(end_date_val, "%Y-%m-%d").date())
                                except:
                                    end_date = st.date_input("结束日期", value=date.today() + timedelta(days=90))
                            else:
                                end_date = st.date_input("结束日期", value=date.today() + timedelta(days=90))
                        else:
                            end_date = None
                    course_date = None
                
                notes = st.text_area("备注", value=course['notes'] if course['notes'] else "")

                # 通知配置
                st.markdown("---")
                st.markdown("**🔔 通知配置**")

                notify_daily = st.checkbox("📅 每日提醒（前一天通知）", value=bool(course.get('notify_daily', 1)))
                notify_weekly = st.checkbox("📊 周汇总提醒", value=bool(course.get('notify_weekly', 1)))
                notify_before_start = st.checkbox("⏰ 课前提醒", value=bool(course.get('notify_before_start', 0)))

                if notify_before_start:
                    notify_minutes_before = st.number_input(
                        "提前多少分钟提醒",
                        min_value=5,
                        max_value=120,
                        value=int(course.get('notify_minutes_before', 30)),
                        step=5
                    )
                else:
                    notify_minutes_before = 30

                col1, col2 = st.columns(2)
                with col1:
                    submitted = st.form_submit_button("💾 保存修改", use_container_width=True)
                with col2:
                    cancelled = st.form_submit_button("❌ 取消", use_container_width=True)

                if submitted:
                    # 处理日期格式
                    course_date_str = course_date.strftime("%Y-%m-%d") if course_date else None
                    end_date_str = end_date.strftime("%Y-%m-%d") if end_date else None

                    update_course(
                        course['id'],
                        day, start_time, end_time, course_name, location, pickup_time,
                        notes, course_type, course_date_str, end_date_str,
                        int(notify_daily), int(notify_weekly), int(notify_before_start), int(notify_minutes_before)
                    )
                    del st.session_state['editing_course']
                    st.success("✅ 课程修改成功！")
                    st.rerun()

                if cancelled:
                    del st.session_state['editing_course']
                    st.rerun()
        
        # 删除课程功能
        st.markdown("---")
        st.markdown("**删除课程**")
        col1, col2 = st.columns([3, 1])
        with col1:
            course_to_delete = st.selectbox(
                "选择要删除的课程",
                display_df["display_text"].tolist(),
                label_visibility="collapsed",
                key="delete_select"
            )
        with col2:
            if st.button("🗑️ 删除课程", use_container_width=True, type="primary"):
                if course_to_delete:
                    selected_course = display_df[display_df["display_text"] == course_to_delete].iloc[0]
                    course_id = int(selected_course['id'])
                    delete_course(course_id)
                    st.success("✅ 课程删除成功！")
                    st.rerun()

def show_add_course_page(api_key, base_url, model_text, model_image):
    st.markdown("<h2 style='text-align: center; margin-bottom: 1.5rem;'>🎯 添加新课程</h2>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📸 AI 图片识别", "📝 AI 文本提取", "✍️ 手动添加"])
    
    with tab1:
        st.markdown("""
        <div class="info-card">
            <h4>📸 上传课程表图片</h4>
            <p>支持 JPG、PNG 格式，AI 将自动识别课程信息</p>
        </div>
        """, unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader("选择图片", type=["jpg", "jpeg", "png"], label_visibility="collapsed")
        
        if uploaded_file is not None:
            col1, col2 = st.columns([1, 2])
            with col1:
                st.image(uploaded_file, caption="上传的图片", use_container_width=True)
            with col2:
                if st.button("🚀 开始识别", use_container_width=True):
                    with st.spinner("🤖 AI 正在识别中..."):
                        if api_key:
                            result = extract_schedule_from_image(uploaded_file, api_key, base_url, model_image)
                        else:
                            time.sleep(1)
                            result = mock_extract_schedule()
                    st.session_state['ai_result'] = result
                    st.success("✅ 识别完成！")
    
    with tab2:
        st.markdown("""
        <div class="info-card">
            <h4>📝 粘贴课程文本</h4>
            <p>将课程信息粘贴到下方，AI 将自动提取结构化数据</p>
        </div>
        """, unsafe_allow_html=True)
        
        text_input = st.text_area("课程文本", height=150, placeholder="例如：\n周一 16:30-17:30 小主持人\n周二 16:30-17:30 体适能")
        
        if st.button("🚀 开始提取", use_container_width=True):
            if text_input:
                with st.spinner("🤖 AI 正在分析中..."):
                    if api_key:
                        result = extract_schedule_from_text(text_input, api_key, base_url, model_text)
                    else:
                        time.sleep(1)
                        result = mock_extract_schedule()
                st.session_state['ai_result'] = result
                st.success("✅ 提取完成！")
            else:
                st.error("请输入文本内容。")
    
    with tab3:
        st.markdown("""
        <div class="info-card">
            <h4>✍️ 手动录入</h4>
            <p>手动填写课程信息</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("manual_add_form"):
            # 课程类型选择
            course_type = st.radio(
                "课程类型",
                options=["recurring", "one_time"],
                format_func=lambda x: "🔁 周期重复" if x == "recurring" else "📅 一次性/临时",
                horizontal=True
            )
            
            col1, col2 = st.columns(2)
            with col1:
                day = st.selectbox("星期", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
                course_name = st.text_input("课程名称")
                location = st.text_input("地点")
            with col2:
                start_time = st.text_input("开始时间 (HH:MM)", value="16:30")
                end_time = st.text_input("结束时间 (HH:MM)", value="17:30")
                pickup_time = st.text_input("接娃时间 (HH:MM)", value="17:30")
            
            # 根据课程类型显示不同字段
            if course_type == "one_time":
                course_date = st.date_input("课程日期", value=date.today())
                end_date = None
            else:
                col1, col2 = st.columns(2)
                with col1:
                    enable_end_date = st.checkbox("设置结束日期", value=False)
                with col2:
                    if enable_end_date:
                        end_date = st.date_input("结束日期", value=date.today() + timedelta(days=90))
                    else:
                        end_date = None
                course_date = None
            
            notes = st.text_area("备注")

            # 通知配置
            st.markdown("---")
            st.markdown("**🔔 通知配置**")

            notify_daily = st.checkbox("📅 每日提醒（前一天通知）", value=True)
            notify_weekly = st.checkbox("📊 周汇总提醒", value=True)
            notify_before_start = st.checkbox("⏰ 课前提醒", value=False)

            if notify_before_start:
                notify_minutes_before = st.number_input(
                    "提前多少分钟提醒",
                    min_value=5,
                    max_value=120,
                    value=30,
                    step=5
                )
            else:
                notify_minutes_before = 30

            submitted = st.form_submit_button("💾 保存课程", use_container_width=True)
            if submitted:
                # 处理日期格式
                course_date_str = course_date.strftime("%Y-%m-%d") if course_date else None
                end_date_str = end_date.strftime("%Y-%m-%d") if end_date else None

                add_course(day, start_time, end_time, course_name, location, pickup_time, notes, course_type, course_date_str, end_date_str, int(notify_daily), int(notify_weekly), int(notify_before_start), int(notify_minutes_before))

                type_label = "一次性" if course_type == "one_time" else "周期重复"
                st.success(f"✅ 已添加 {type_label} 课程: {course_name}")
    
    # 显示 AI 识别结果
    if 'ai_result' in st.session_state:
        st.divider()
        st.subheader("📝 AI 识别结果确认")
        process_ai_result(st.session_state['ai_result'])

def process_ai_result(result):
    if "error" in result:
        st.error(f"❌ 识别失败: {result['error']}")
        return

    if "courses" in result:
        courses = result["courses"]
        st.write("请在下方表格中修改确认信息，然后点击保存。")
        
        df_preview = pd.DataFrame(courses)
        
        # 确保所有必要列存在
        if 'course_type' not in df_preview.columns:
            df_preview['course_type'] = 'recurring'
        if 'course_date' not in df_preview.columns:
            df_preview['course_date'] = None
        if 'end_date' not in df_preview.columns:
            df_preview['end_date'] = None
            
        edited_df = st.data_editor(df_preview, num_rows="dynamic", key="editor_ai")
        
        if st.button("💾 确认并保存所有课程", use_container_width=True):
            count = 0
            for index, row in edited_df.iterrows():
                add_course(
                    row.get("day_of_week", "Monday"),
                    row.get("start_time", "00:00"),
                    row.get("end_time", "00:00"),
                    row.get("course_name", "Unknown"),
                    row.get("location", ""),
                    row.get("pickup_time", ""),
                    row.get("notes", ""),
                    row.get("course_type", "recurring"),
                    row.get("course_date") if pd.notna(row.get("course_date")) else None,
                    row.get("end_date") if pd.notna(row.get("end_date")) else None
                )
                count += 1
            st.success(f"✅ 已成功保存 {count} 个课程到数据库！")
            del st.session_state['ai_result']
            st.rerun()

def show_notification_test_page():
    st.markdown("""
    <div class="info-card">
        <h4>🔔 通知功能测试</h4>
        <p>这里可以手动触发通知逻辑，用于测试消息是否能正常发送。</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div style="background: rgba(255,255,255,0.1); padding: 1.25rem; border-radius: 12px; margin-bottom: 1rem;">
            <h4 style="margin: 0 0 0.5rem 0; color: white;">📅 每日提醒</h4>
            <p style="margin: 0; color: rgba(255,255,255,0.8); font-size: 0.875rem;">模拟发送明天的课程提醒</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("📨 发送明日提醒", use_container_width=True):
            with st.spinner("正在发送..."):
                import io
                from contextlib import redirect_stdout
                f = io.StringIO()
                with redirect_stdout(f):
                    job_daily_reminder()
                output = f.getvalue()
            st.success("✅ 执行完成")
            st.text_area("执行日志", output, height=150)

    with col2:
        st.markdown("""
        <div style="background: rgba(255,255,255,0.1); padding: 1.25rem; border-radius: 12px; margin-bottom: 1rem;">
            <h4 style="margin: 0 0 0.5rem 0; color: white;">📊 每周汇总</h4>
            <p style="margin: 0; color: rgba(255,255,255,0.8); font-size: 0.875rem;">模拟发送本周/下周的课程汇总</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("📨 发送下周汇总（周五）", use_container_width=True):
            with st.spinner("正在发送..."):
                import io
                from contextlib import redirect_stdout
                f = io.StringIO()
                with redirect_stdout(f):
                    job_weekly_summary_next_week()
                output = f.getvalue()
            st.success("✅ 执行完成")
            st.text_area("执行日志", output, height=150)
        if st.button("📨 发送本周汇总（周一）", use_container_width=True):
            with st.spinner("正在发送..."):
                import io
                from contextlib import redirect_stdout
                f = io.StringIO()
                with redirect_stdout(f):
                    job_weekly_summary_this_week()
                output = f.getvalue()
            st.success("✅ 执行完成")
            st.text_area("执行日志", output, height=150)

def show_attendance_page():
    """出勤记录页面"""
    st.markdown("<h2 style='text-align: center; margin-bottom: 1rem;'>📋 出勤记录</h2>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📝 记录出勤", "📅 按日期查看", "📚 按课程查看"])
    
    with tab1:
        show_record_attendance()
    
    with tab2:
        show_attendance_by_date()
    
    with tab3:
        show_attendance_by_course()

def show_record_attendance():
    """记录出勤表单"""
    st.markdown("""
    <div class="info-card">
        <h4>📝 记录出勤情况</h4>
        <p>记录孩子每次课程的出勤状态</p>
    </div>
    """, unsafe_allow_html=True)
    
    df = get_all_courses()
    if df.empty:
        st.warning("⚠️ 请先添加课程")
        return
    
    # 创建课程选择列表
    df['display'] = df.apply(
        lambda x: f"{WEEKDAY_MAP.get(x['day_of_week'], x['day_of_week'])} {x['start_time']} - {x['course_name']}", axis=1
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        selected_course_display = st.selectbox("选择课程", df['display'].tolist())
        selected_course = df[df['display'] == selected_course_display].iloc[0]
        course_id = int(selected_course['id'])
        
        # 默认选择今天
        attendance_date = st.date_input("日期", value=date.today())
    
    with col2:
        status = st.selectbox(
            "出勤状态",
            options=list(STATUS_LABELS.keys()),
            format_func=lambda x: STATUS_LABELS[x]
        )
        
        check_in_time = st.text_input("签到时间 (可选)", placeholder="例如: 16:25")
        check_out_time = st.text_input("签退时间 (可选)", placeholder="例如: 17:30")
    
    notes = st.text_area("备注", placeholder="记录一些特殊情况...")
    
    if st.button("💾 保存记录", use_container_width=True, type="primary"):
        try:
            result = record_attendance(
                course_id=course_id,
                attendance_date=attendance_date.strftime('%Y-%m-%d'),
                status=status,
                check_in_time=check_in_time if check_in_time else None,
                check_out_time=check_out_time if check_out_time else None,
                notes=notes
            )
            if result:
                st.success(f"✅ 已记录: {selected_course['course_name']} - {STATUS_LABELS[status]}")
                st.balloons()
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ 保存失败，请重试")
        except Exception as e:
            st.error(f"❌ 保存出错: {str(e)}")

def show_attendance_by_date():
    """按日期查看出勤记录"""
    st.markdown("""
    <div class="info-card">
        <h4>📅 按日期查看</h4>
        <p>查看某一天的出勤情况</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        view_date = st.date_input("选择日期", value=date.today(), key="view_date")
    
    attendance_df = get_attendance_by_date(view_date.strftime('%Y-%m-%d'))
    
    if attendance_df.empty:
        st.info(f"📭 {view_date} 暂无出勤记录")
        
        # 显示当天的课程提醒
        weekday = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][view_date.weekday()]
        courses_df = get_all_courses()
        day_courses = courses_df[courses_df['day_of_week'] == weekday]
        
        if not day_courses.empty:
            st.markdown("**📚 当天有以下课程：**")
            for _, course in day_courses.iterrows():
                st.markdown(f"- {course['start_time']} {course['course_name']} @ {course['location']}")
    else:
        st.markdown(f"**📊 {view_date} 出勤记录：**")
        
        # 显示记录表格
        display_df = attendance_df.copy()
        display_df['status_label'] = display_df['status'].apply(get_status_label)
        display_df['星期'] = display_df['day_of_week'].map(WEEKDAY_MAP)
        
        st.dataframe(
            display_df[['course_name', '星期', 'start_time', 'location', 'status_label', 'notes']],
            column_config={
                'course_name': '课程名称',
                'start_time': '时间',
                'location': '地点',
                'status_label': '状态',
                'notes': '备注'
            },
            use_container_width=True,
            hide_index=True
        )
        
        # 删除记录功能
        st.markdown("---")
        st.subheader("🗑️ 删除记录")
        
        record_to_delete = st.selectbox(
            "选择要删除的记录",
            display_df.apply(lambda x: f"{x['course_name']} - {x['attendance_date']}", axis=1).tolist(),
            label_visibility="collapsed"
        )
        
        if st.button("🗑️ 删除选中记录", use_container_width=True):
            selected_record = display_df[display_df.apply(
                lambda x: f"{x['course_name']} - {x['attendance_date']}" == record_to_delete, axis=1
            )].iloc[0]
            delete_attendance_record(int(selected_record['id']))
            st.success("✅ 记录已删除")
            st.rerun()

def show_attendance_by_course():
    """按课程查看出勤记录"""
    st.markdown("""
    <div class="info-card">
        <h4>📚 按课程查看</h4>
        <p>查看某门课程的历史出勤记录</p>
    </div>
    """, unsafe_allow_html=True)
    
    df = get_all_courses()
    if df.empty:
        st.warning("⚠️ 请先添加课程")
        return
    
    df['display'] = df.apply(
        lambda x: f"{WEEKDAY_MAP.get(x['day_of_week'], x['day_of_week'])} {x['start_time']} - {x['course_name']}", axis=1
    )
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        selected_course_display = st.selectbox("选择课程", df['display'].tolist(), key="course_select")
        selected_course = df[df['display'] == selected_course_display].iloc[0]
        course_id = int(selected_course['id'])
    
    with col2:
        start_date = st.date_input("开始日期", value=date.today() - timedelta(days=30))
    
    with col3:
        end_date = st.date_input("结束日期", value=date.today())
    
    attendance_df = get_attendance_by_course(
        course_id,
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d')
    )
    
    if attendance_df.empty:
        st.info(f"📭 {selected_course['course_name']} 在选定时间段内暂无记录")
    else:
        # 统计信息
        stats = get_attendance_stats_by_course(
            course_id,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        if selected_course['course_name'] in stats:
            course_stats = stats[selected_course['course_name']]
            
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("总次数", course_stats['total'])
            with col2:
                st.metric("✅ 已上", course_stats['attended'])
            with col3:
                st.metric("❌ 缺勤", course_stats['absent'])
            with col4:
                st.metric("📝 请假", course_stats['leave'])
            with col5:
                st.metric("出勤率", f"{course_stats['attendance_rate']}%")
        
        # 显示记录表格
        st.markdown("**📋 详细记录：**")
        display_df = attendance_df.copy()
        display_df['status_label'] = display_df['status'].apply(get_status_label)
        
        st.dataframe(
            display_df[['attendance_date', 'status_label', 'check_in_time', 'check_out_time', 'notes']],
            column_config={
                'attendance_date': '日期',
                'status_label': '状态',
                'check_in_time': '签到时间',
                'check_out_time': '签退时间',
                'notes': '备注'
            },
            use_container_width=True,
            hide_index=True
        )

def show_attendance_analysis_page():
    """出勤分析页面"""
    st.markdown("<h2 style='text-align: center; margin-bottom: 1rem;'>📈 出勤分析</h2>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📊 月度统计", "📈 趋势分析", "🏆 课程排名"])
    
    with tab1:
        show_monthly_stats()
    
    with tab2:
        show_trend_analysis()
    
    with tab3:
        show_course_ranking()

def show_monthly_stats():
    """月度统计"""
    st.markdown("""
    <div class="info-card">
        <h4>📊 月度出勤统计</h4>
        <p>查看每月的出勤情况汇总</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        year = st.selectbox("年份", [2024, 2025, 2026], index=1)
    with col2:
        month = st.selectbox("月份", list(range(1, 13)), index=datetime.now().month - 1)
    
    stats = get_monthly_attendance_stats(year, month)
    
    if stats['total'] == 0:
        st.info(f"📭 {year}年{month}月暂无出勤记录")
    else:
        # 显示统计卡片
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("总次数", stats['total'])
        with col2:
            st.metric("✅ 已上", stats['attended'])
        with col3:
            st.metric("❌ 缺勤", stats['absent'])
        with col4:
            st.metric("📝 请假", stats['leave'])
        with col5:
            st.metric("出勤率", f"{stats['attendance_rate']}%")
        
        # 饼图展示
        import plotly.graph_objects as go
        
        labels = ['已上课', '缺勤', '请假', '课程取消']
        values = [stats['attended'], stats['absent'], stats['leave'], stats['cancelled']]
        colors = ['#10b981', '#ef4444', '#f59e0b', '#6b7280']
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker_colors=colors
        )])
        fig.update_layout(
            title=f"{year}年{month}月出勤分布",
            showlegend=True,
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)

def show_trend_analysis():
    """趋势分析"""
    st.markdown("""
    <div class="info-card">
        <h4>📈 出勤趋势</h4>
        <p>查看最近几周的出勤率变化趋势</p>
    </div>
    """, unsafe_allow_html=True)
    
    weeks = st.slider("选择周数", min_value=4, max_value=16, value=8)
    trend_data = get_weekly_attendance_trend(weeks)
    
    if not trend_data:
        st.info("📭 暂无足够的数据进行分析")
    else:
        import plotly.graph_objects as go
        
        weeks_list = sorted(trend_data.keys())
        rates = [trend_data[w]['attendance_rate'] for w in weeks_list]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=weeks_list,
            y=rates,
            mode='lines+markers',
            name='出勤率',
            line=dict(color='#667eea', width=3),
            marker=dict(size=8)
        ))
        fig.update_layout(
            title=f"最近{weeks}周出勤率趋势",
            xaxis_title="周",
            yaxis_title="出勤率 (%)",
            yaxis_range=[0, 100],
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 显示详细数据
        st.markdown("**📋 详细数据：**")
        trend_df = pd.DataFrame([
            {
                '周': w,
                '出勤率': f"{trend_data[w]['attendance_rate']}%",
                '已上': trend_data[w]['attended'],
                '缺勤': trend_data[w]['absent'],
                '请假': trend_data[w]['leave'],
                '总计': trend_data[w]['total']
            }
            for w in weeks_list
        ])
        st.dataframe(trend_df, use_container_width=True, hide_index=True)

def show_course_ranking():
    """课程排名"""
    st.markdown("""
    <div class="info-card">
        <h4>🏆 课程出勤率排名</h4>
        <p>查看各门课程的出勤率排名</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("开始日期", value=date.today() - timedelta(days=90), key="rank_start")
    with col2:
        end_date = st.date_input("结束日期", value=date.today(), key="rank_end")
    
    ranking_df = get_course_attendance_ranking(
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d')
    )
    
    if ranking_df.empty:
        st.info("📭 暂无数据")
    else:
        ranking_df['星期'] = ranking_df['day_of_week'].map(WEEKDAY_MAP)
        ranking_df['排名'] = range(1, len(ranking_df) + 1)
        
        st.dataframe(
            ranking_df[['排名', 'course_name', '星期', 'attended_count', 'total_count', 'attendance_rate']],
            column_config={
                'course_name': '课程名称',
                'attended_count': '已上次数',
                'total_count': '总次数',
                'attendance_rate': st.column_config.NumberColumn('出勤率', format="%.1f%%")
            },
            use_container_width=True,
            hide_index=True
        )
        
        # 柱状图
        import plotly.graph_objects as go
        
        fig = go.Figure(data=[
            go.Bar(
                x=ranking_df['course_name'],
                y=ranking_df['attendance_rate'],
                marker_color='#667eea'
            )
        ])
        fig.update_layout(
            title="课程出勤率对比",
            xaxis_title="课程",
            yaxis_title="出勤率 (%)",
            yaxis_range=[0, 100],
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
