import asyncio
import os

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from council import run_council


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "AI Council bot is running. Use /council <question> to run the advisory panel."
    )


async def council_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = " ".join(context.args).strip()
    if not question:
        await update.message.reply_text("Usage: /council <question>")
        return

    await update.message.reply_text("Running council analysis. This can take a minute...")

    try:
        result = await asyncio.to_thread(run_council, question)
        aggregate = result["aggregate"]
        reply = (
            f"Question: {result['question']}\n\n"
            f"CouncilConfidence: {aggregate['council_confidence']}\n"
            f"CouncilRiskScore: {aggregate['council_risk_score']}\n"
            f"LeadingRecommendation: {aggregate['leading_recommendation']}\n\n"
            f"Chairman Decision:\n{result['decision']}"
        )
        await update.message.reply_text(reply[:4096])
    except Exception as exc:
        await update.message.reply_text(f"Council run failed: {exc}")


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("council", council_command))

    app.run_polling()


if __name__ == "__main__":
    main()
