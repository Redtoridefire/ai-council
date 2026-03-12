import asyncio
import os

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from council import run_council

_TELEGRAM_MAX = 4096


async def _send_long(update: Update, text: str) -> None:
    """Split text into ≤4096-char chunks and send each as a separate message."""
    for i in range(0, len(text), _TELEGRAM_MAX):
        await update.message.reply_text(text[i : i + _TELEGRAM_MAX])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "AI Council bot is running.\n\n"
        "/council <question> — full council analysis\n"
        "/debate <rounds> <question> — council with debate rounds (1-3)\n"
        "/help — show this message"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/council <question> — run the advisory council\n"
        "/debate <rounds> <question> — run with debate rounds, e.g.:\n"
        "  /debate 2 Should we adopt this vendor's AI model?"
    )


async def _run_and_reply(update: Update, question: str, debate_rounds: int = 0) -> None:
    await update.message.reply_text(
        f"Running council analysis{f' ({debate_rounds} debate round(s))' if debate_rounds else ''}... "
        "This can take a minute or two."
    )

    try:
        result = await asyncio.to_thread(run_council, question, "docs", "council_memory.db", debate_rounds)
        aggregate = result["aggregate"]

        summary = (
            f"*Council Summary*\n"
            f"Question: {result['question']}\n\n"
            f"Confidence: {aggregate['council_confidence']}\n"
            f"Risk Score: {aggregate['council_risk_score']}\n"
            f"Leading Recommendation: {aggregate['leading_recommendation']}"
        )
        await update.message.reply_text(summary, parse_mode="Markdown")

        decision_header = "*Chairman Decision*\n"
        await _send_long(update, decision_header + result["decision"])

    except Exception as exc:
        await update.message.reply_text(f"Council run failed: {exc}")


async def council_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = " ".join(context.args).strip()
    if not question:
        await update.message.reply_text("Usage: /council <question>")
        return
    await _run_and_reply(update, question)


async def debate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    if len(args) < 2 or not args[0].isdigit():
        await update.message.reply_text("Usage: /debate <rounds 1-3> <question>")
        return
    rounds = max(1, min(3, int(args[0])))
    question = " ".join(args[1:]).strip()
    if not question:
        await update.message.reply_text("Usage: /debate <rounds 1-3> <question>")
        return
    await _run_and_reply(update, question, debate_rounds=rounds)


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("council", council_command))
    app.add_handler(CommandHandler("debate", debate_command))

    app.run_polling()


if __name__ == "__main__":
    main()
