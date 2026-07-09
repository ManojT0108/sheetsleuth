"""Deploy + exercise the SheetSleuth agent pipeline on a RocketRide server.

Uses ROCKETRIDE_URI / ROCKETRIDE_APIKEY from .env — point them at the local
engine for dev or at RocketRide Cloud (api.rocketride.ai) for the mandatory
production deployment. Same .pipe file either way; that's the whole point.
"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[1] / ".env")

from rocketride import RocketRideClient          # noqa: E402
from rocketride.schema import Question           # noqa: E402

QUESTIONS = [
    "Which findings in workbook 'lumeo-analytics-fy2026-demo-cbd38864' are "
    "CONFIRMED, and what is the measured dollar impact of each?",
]


async def main():
    client = RocketRideClient()
    await client.connect()
    print("connected to RocketRide server")
    result = await client.use(
        filepath=str(Path(__file__).parent / "sheetsleuth_agent.pipe"))
    token = result["token"]
    print(f"pipeline running, token={token}")

    for qtext in QUESTIONS if len(sys.argv) < 2 else [" ".join(sys.argv[1:])]:
        q = Question()
        q.addQuestion(qtext)
        resp = await client.chat(token=token, question=q)
        answers = resp.get("answers") or []
        print(f"\nQ: {qtext}\nA: {answers[0] if answers else resp}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
