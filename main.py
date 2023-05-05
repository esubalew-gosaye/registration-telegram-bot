import logging
import os
import sqlite3
import pandas as pd

from typing import Dict

import dataset
from openpyxl import load_workbook

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

CHOOSING, TYPING_REPLY, TYPING_CHOICE = range(3)

reply_keyboard = [
    ["ሙሉ ስም", "ባች/አመት", 'ዲፓርትመንት'],
    ['የአገልግሎት ክፍል', "ሌላ ተጨማሪ..."],
    ["መዝግብ"]
]
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, is_persistent=True)


def facts_to_str(user_data: Dict[str, str]) -> str:
    """Helper function for formatting the gathered user info."""
    facts = [f"{key} - {value}" for key, value in user_data.items()]
    return "\n".join(facts).join(["\n", "\n"])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask user for input."""
    await update.message.reply_text(
        'እንኳን ደህና መጡ፤ መምረጥ የሚፈልጉትን አባል መረጃ ከታች የሚመጣውን Button ' +
        'በመንካት መረጃውን በትክክል ይሙሉት ሲጨርሱ መዝግብ የሚለውን Button ተጭነው ይመዝግቡ።',
        reply_markup=markup,
    )

    return CHOOSING


async def regular_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask the user for info about the selected predefined choice."""
    text = update.message.text
    context.user_data["choice"] = text
    await update.message.reply_text(f"እባኮ የተማሪውን {text.lower()} ያስገቡ!")

    return TYPING_REPLY


async def received_information(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    text = update.message.text
    if text == "ሌላ ተጨማሪ...":
        text = "ተጨማሪ መረጃ"
    category = user_data["choice"]
    user_data[category] = text
    del user_data["choice"]

    await update.message.reply_text(
        "እናመሰግናለን! እስካሁን ያስገቡት መረጃ እነዚህ ናቸው:"
        f"\n{'-' * 60}"
        f"{facts_to_str(user_data)} {'-' * 60}\nሌላ መጨመር ወይም መቀየር ከፈለጉ እንደገና መርጠው ማስተካከል ይችላሉ"
        ,
        reply_markup=markup,
    )

    return CHOOSING


# Setup for the dataset to write in db
db = dataset.connect('sqlite:///memo.db')
table = db['nominated']


def insert_to_db(**kwargs):
    table.insert(dict(
        full_name=kwargs.get("name", ""),
        batch=kwargs.get("batch", ""),
        department=kwargs.get("dep", ""),
        service=kwargs.get("service", ""),
        description=kwargs.get("desc", "")
    ))
    # for user in db['nominated']:
    #     print(user['full_name'], user['batch'], user['department'], user['service'], user['description'])


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data
    # write_to_xl(
    #     name=user_data.get("ሙሉ ስም", ""),
    #     batch=user_data.get("ባች/አመት", ""),
    #     dep=user_data.get("ዲፓርትመንት", ""),
    #     service=user_data.get("የአገልግሎት ክፍል", ""),
    #     desc=user_data.get("ሌላ ተጨማሪ...", "")
    # )

    insert_to_db(
        name=user_data.get("ሙሉ ስም", ""),
        batch=user_data.get("ባች/አመት", ""),
        dep=user_data.get("ዲፓርትመንት", ""),
        service=user_data.get("የአገልግሎት ክፍል", ""),
        desc=user_data.get("ሌላ ተጨማሪ...", "")
    )

    if "choice" in user_data:
        del user_data["choice"]

    await update.message.reply_text(
        f"{user_data.get('ሙሉ ስም', '')} በተሳካ ሁኔታ ተመዝግቧል! ሌላ ለመጠቆም /start ነክተው ይጀምሩ።",
        reply_markup=ReplyKeyboardRemove(),
    )

    user_data.clear()
    return ConversationHandler.END


async def secret_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    authorized_users = [579497835]
    if update.message.chat_id in authorized_users:
        conn = sqlite3.connect('memo.db')
        df = pd.read_sql_query("SELECT * FROM nominated", conn)
        df.to_excel('mydata.xlsx', index=False)
        conn.close()
        await update.message.reply_document('mydata.xlsx')
    else:
        await update.message.reply_text("You are not eligable to do so.")


def main():
    application = Application.builder().token("6125105157:AAF8N-gKuINPFP_bu6mfz_0lQTUnPeKTyIc").build()

    application.add_handler(CommandHandler("export", secret_command))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [
                MessageHandler(
                    filters.Regex("^(ባች/አመት|ሙሉ ስም|የአገልግሎት ክፍል|ዲፓርትመንት|ሌላ ተጨማሪ...)$"), regular_choice
                ),
            ],
            TYPING_CHOICE: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^መዝግብ$")), regular_choice
                )
            ],
            TYPING_REPLY: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^መዝግብ$")),
                    received_information,
                )
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^መዝግብ$"), done)],
    )

    application.add_handler(conv_handler)

    application.run_polling()


if __name__ == "__main__":
    main()
