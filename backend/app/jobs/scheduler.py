# score = 0.7*s_base + 0.3*hourly_component
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.ml.train_model import train_all_residents

async def run_training():

    print("start training")
    await train_all_residents()
    print("training finished")

def start():

    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        lambda: asyncio.create_task(run_training()),
        trigger="cron",
        hour=4,
        minute=0
    )

    scheduler.start()

    print("scheduler started")

    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    start()