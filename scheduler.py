import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from stock_analyzer import run_stock_analysis

def initialize_scheduler():
    """Initialize and start the background scheduler"""
    scheduler = BackgroundScheduler()
    
    # Schedule the stock analysis to run at 9:30 AM and 3:30 PM on weekdays (standard market times)
    # These times are in UTC, adjust for your local time zone
    scheduler.add_job(
        run_stock_analysis,
        trigger=CronTrigger(day_of_week='mon-fri', hour='4,10', minute='0'),  # UTC times (9:30 AM IST = 4:00 UTC, 3:30 PM IST = 10:00 UTC)
        id='stock_analysis_job',
        name='Run stock analysis',
        replace_existing=True
    )
    
    # Also add a daily summary job to run after market close
    # scheduler.add_job(
    #     send_daily_summary,  # You would need to implement this function
    #     trigger=CronTrigger(day_of_week='mon-fri', hour='11', minute='0'),  # 4:30 PM IST = 11:00 UTC
    #     id='daily_summary_job',
    #     name='Send daily summary',
    #     replace_existing=True
    # )
    
    try:
        scheduler.start()
        logging.info("Scheduler started successfully")
    except Exception as e:
        logging.error(f"Error starting scheduler: {str(e)}")
    
    return scheduler
