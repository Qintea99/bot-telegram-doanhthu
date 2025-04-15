import logging
import re
import pytz
import pandas as pd
from datetime import datetime
from telegram import Update, ChatMember
from telegram.ext import (
    ApplicationBuilder, ContextTypes,
    CommandHandler, MessageHandler, filters
)

# ========== THIẾT LẬP ==========
TOKEN = "7886580250:AAEyJmSd3Wid94ib3Q8JAp88KjOIreuYOAQ"

logging.basicConfig(level=logging.INFO)
data = {
    'orders': [],
    'withdrawals': [],
    'total_income': 0,
    'total_orders': 0,
    'total_withdrawn': 0
}

def get_now():
    return datetime.now(pytz.timezone("Asia/Ho_Chi_Minh"))

# ========== CÔNG CỤ ==========
def parse_money(text):
    match = re.search(r"=\s*([\d.,]+)(k)?", text.lower())
    if not match:
        return None
    num = match.group(1).replace(',', '')
    money = float(num) * 1000 if match.group(2) == 'k' else float(num)
    return int(money)

def parse_withdraw(text):
    match = re.match(r"-\s*([\d.,]+)(k)?", text.lower())
    if not match:
        return None
    num = match.group(1).replace(',', '')
    money = float(num) * 1000 if match.group(2) == 'k' else float(num)
    return int(money)

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]

async def send_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = get_now().strftime("%d/%m/%Y %H:%M")
    message = (
        f"📅 Ngày: {now}\n"
        f"📦 Số đơn: {data['total_orders']}\n"
        f"💰 Doanh thu: {data['total_income']:,}đ\n"
        f"💸 Đã rút: {data['total_withdrawn']:,}đ"
    )
    await update.message.reply_text(message)

# ========== CÁC LỆNH ==========
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Chỉ admin mới có quyền reset.")
        return
    data['orders'].clear()
    data['withdrawals'].clear()
    data['total_income'] = 0
    data['total_orders'] = 0
    data['total_withdrawn'] = 0
    await update.message.reply_text("✅ Đã reset toàn bộ dữ liệu.")

async def undo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not data['orders']:
        await update.message.reply_text("❌ Không còn đơn nào để undo.")
        return
    last = data['orders'].pop()
    data['total_income'] -= last['amount']
    data['total_orders'] -= 1
    await send_stats(update, context)

async def export_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not data['orders'] and not data['withdrawals']:
        await update.message.reply_text("❌ Không có dữ liệu để xuất.")
        return
    df_orders = pd.DataFrame(data['orders'])
    df_withdraw = pd.DataFrame(data['withdrawals'])
    with pd.ExcelWriter("doanh_thu.xlsx") as writer:
        if not df_orders.empty:
            df_orders.to_excel(writer, sheet_name="Đơn hàng", index=False)
        if not df_withdraw.empty:
            df_withdraw.to_excel(writer, sheet_name="Tiền đã rút", index=False)
    await context.bot.send_document(chat_id=update.effective_chat.id, document=open("doanh_thu.xlsx", "rb"))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "=" in text:
        amount = parse_money(text)
        if amount:
            data['orders'].append({'amount': amount, 'time': get_now()})
            data['total_income'] += amount
            data['total_orders'] += 1
            await send_stats(update, context)
    elif text.strip().startswith("-"):
        if not await is_admin(update, context):
            await update.message.reply_text("❌ Chỉ admin mới được rút tiền.")
            return
        amount = parse_withdraw(text)
        if amount:
            data['withdrawals'].append({'amount': amount, 'time': get_now()})
            data['total_withdrawn'] += amount
            await send_stats(update, context)

# ========== MAIN ==========
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("undo", undo))
    app.add_handler(CommandHandler("stats", send_stats))
    app.add_handler(CommandHandler("export", export_excel))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
