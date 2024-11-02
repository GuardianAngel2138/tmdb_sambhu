import logging
import requests
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import time
import config
from daily_tasks import daily_movie_suggestion

# Initialize MongoDB client and database
client = AsyncIOMotorClient(config.MONGO_URI)
db = client["movie_bot"]
users_collection = db["users"]
movies_collection = db["movies"]

# Initialize Telegram bot and application
bot = Bot(token=config.BOT_TOKEN)
app = Application.builder().token(config.BOT_TOKEN).build()

# Setup logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Fetch detailed movie data from TMDB
def fetch_movie_data():
    """Fetch movie data from TMDB including main actors, director, rating, and where to watch info."""
    url = f"https://api.themoviedb.org/3/movie/now_playing?api_key={config.TMDB_API_KEY}&language=en-US"
    response = requests.get(url)
    movies = response.json().get("results", [])

    movie_data = []
    for movie in movies:
        movie_id = movie["id"]
        details_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={config.TMDB_API_KEY}&language=en-US&append_to_response=credits"
        details_response = requests.get(details_url)
        details = details_response.json()

        actors = ", ".join([actor["name"] for actor in details.get("credits", {}).get("cast", [])[:3]]) or "N/A"
        director = next(
            (crew["name"] for crew in details.get("credits", {}).get("crew", []) if crew["job"] == "Director"), "N/A")
        poster_path = f"https://image.tmdb.org/t/p/w500{details.get('poster_path')}"
        rating = details.get("vote_average", "N/A")

        movie_data.append({
            "title": movie["title"],
            "year": movie["release_date"].split("-")[0],
            "actors": actors,
            "director": director,
            "overview": details.get("overview", "No overview available."),
            "poster_path": poster_path,
            "rating": rating,
            "where_to_watch": "Check streaming platforms"
        })

    return movie_data


# Daily suggestion function to send a movie suggestion to the channel
async def suggest_movie(context: CallbackContext):
    await daily_movie_suggestion(context.bot, config.CHANNEL_ID)


# Send movie updates to the channel as captioned images with rating and button for details
async def send_movie_update(context: CallbackContext):
    movie_updates = fetch_movie_data()
    for movie in movie_updates:
        caption = (
            f"*{movie['title']}* ({movie['year']})\n"
            f"*Actors:* {movie['actors']}\n"
            f"*Director:* {movie['director']}\n"
            f"*Rating:* {movie['rating']}/10\n"
            f"*Where to Watch:* {movie['where_to_watch']}"
        )
        button = InlineKeyboardButton("More Details", callback_data=f"more_details:{movie['title']}")
        reply_markup = InlineKeyboardMarkup([[button]])

        await context.bot.send_photo(
            chat_id=config.CHANNEL_ID,
            photo=movie["poster_path"],
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )


# Callback for handling "More Details" button in channel messages
async def more_details(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    movie_title = query.data.split(":")[1]

    search_url = f"https://api.themoviedb.org/3/search/movie?api_key={config.TMDB_API_KEY}&query={movie_title}"
    search_response = requests.get(search_url)
    search_data = search_response.json()

    if not search_data['results']:
        await context.bot.send_message(chat_id=query.from_user.id, text="Movie details not found.")
        return

    movie = search_data['results'][0]
    overview = movie.get("overview", "No review available for this movie.")
    google_search_url = f"https://www.google.com/search?q={movie_title.replace(' ', '+')}"
    review_text = f"Here's the review of *{movie_title}*:\n{overview}"

    buttons = [[InlineKeyboardButton("Search", url=google_search_url)]]
    reply_markup = InlineKeyboardMarkup(buttons)

    await context.bot.send_message(
        chat_id=query.from_user.id,
        text=review_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )


# Liveness check command restricted to the owner
async def check_bot_liveness(update: Update, context: CallbackContext):
    if update.effective_user.id == int(config.OWNER_ID):
        await update.message.reply_text("Bot is running and alive!")
    else:
        await update.message.reply_text("Unauthorized to check liveness.")


# Fetch new movies from TMDB and store in MongoDB if not already stored
async def fetch_and_store_new_movies():
    url = f"https://api.themoviedb.org/3/movie/now_playing?api_key={config.TMDB_API_KEY}&language=en-US"
    response = requests.get(url)
    movies = response.json().get("results", [])

    new_movies = []
    for movie in movies:
        movie_id = movie["id"]
        existing_movie = await movies_collection.find_one({"id": movie_id})
        if existing_movie:
            continue

        details_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={config.TMDB_API_KEY}&language=en-US&append_to_response=credits"
        details_response = requests.get(details_url)
        details = details_response.json()

        actors = ", ".join([actor["name"] for actor in details.get("credits", {}).get("cast", [])[:3]]) or "N/A"
        director = next(
            (crew["name"] for crew in details.get("credits", {}).get("crew", []) if crew["job"] == "Director"), "N/A")
        poster_path = f"https://image.tmdb.org/t/p/w500{details.get('poster_path')}"
        rating = details.get("vote_average", "N/A")

        new_movie = {
            "id": movie_id,
            "title": movie["title"],
            "year": movie["release_date"].split("-")[0],
            "actors": actors,
            "director": director,
            "overview": details.get("overview", "No overview available."),
            "poster_path": poster_path,
            "rating": rating,
            "where_to_watch": "Check streaming platforms"
        }

        await movies_collection.insert_one(new_movie)
        new_movies.append(new_movie)

    return new_movies


# Periodic function to check for new movies and send updates
async def check_for_new_movies(context: CallbackContext):
    new_movies = await fetch_and_store_new_movies()
    for movie in new_movies:
        caption = (
            f"*{movie['title']}* ({movie['year']})\n"
            f"*Actors:* {movie['actors']}\n"
            f"*Director:* {movie['director']}\n"
            f"*Rating:* {movie['rating']}/10\n"
            f"*Where to Watch:* {movie['where_to_watch']}"
        )
        button = InlineKeyboardButton("More Details", callback_data=f"more_details:{movie['title']}")
        reply_markup = InlineKeyboardMarkup([[button]])

        await context.bot.send_photo(
            chat_id=config.CHANNEL_ID,
            photo=movie["poster_path"],
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )


# Register handlers
app.add_handler(CommandHandler("start", lambda update, context: send_movie_update(context)))
app.add_handler(CommandHandler("suggestion", lambda update, context: suggest_movie(context)))
app.add_handler(CommandHandler("check_liveness", check_bot_liveness))
app.add_handler(CallbackQueryHandler(more_details, pattern="more_details:"))

# Schedule jobs
job_queue = app.job_queue
job_queue.run_repeating(check_for_new_movies, interval=900, first=0)  # Every 15 mins
job_queue.run_daily(suggest_movie, time=time(9, 0))  # Daily at 9 AM

# Run bot
if __name__ == "__main__":
    app.run_polling()
