from flask import Flask, render_template, jsonify
from database import get_recent_activities, get_users
import asyncio

app = Flask(__name__)

# Helper function to run asynchronous functions within an existing event loop
def async_to_sync(coro):
    try:
        # Check if there is already a running event loop
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # If no event loop is running, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@app.route('/')
def dashboard():
    # Use the helper function to run async functions in a synchronous route
    recent_activities = async_to_sync(get_recent_activities(limit=10))
    users = async_to_sync(get_users())
    return render_template('index.html', activities=recent_activities, users=users)

@app.route('/get_recent_activities')
async def recent_activities_endpoint():
    activities = await get_recent_activities(limit=10)
    return jsonify(activities)

@app.route('/get_users')
async def users_endpoint():
    users = await get_users()
    return jsonify(users)

if __name__ == '__main__':
    app.run(debug=True)
