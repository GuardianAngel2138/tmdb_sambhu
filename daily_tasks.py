from telegram.constants import ParseMode
import config

# Daily movie suggestion task
async def daily_movie_suggestion(bot, chat_id=config.CHANNEL_ID):
    # Fetch a random movie suggestion
    movie = await movies_collection.aggregate([{"$sample": {"size": 1}}]).to_list(1)
    movie = movie[0] if movie else None

    if movie:
        # Format the suggestion message
        text = f"*Today's Movie Suggestion:*\n*{movie['title']}* ({movie['year']})"
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
