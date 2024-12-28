import os
import json
import time
import psutil
from datetime import datetime
from plyer import notification
import schedule
import configparser
from datetime import timedelta
import threading
import sys
from PIL import Image, ImageDraw
from pystray import Icon, MenuItem, Menu


def get_app_path():
    if getattr(sys, 'frozen', False):
        # Running as a bundled exe
        return os.path.dirname(sys.executable)
    else:
        # Running as a script
        return os.path.dirname(os.path.abspath(__file__))
    
# Path to save game data
app_path = get_app_path()
game_data_path = os.path.join(app_path, "game_data.json")
config_path = os.path.join(app_path, "settings.ini")
icon_path = os.path.join(app_path, "icon.ico")  # Path to the icon you want to display
# Check if the game data file exists, if not, create it with a default structure
if not os.path.exists(game_data_path):
    default_data = {
        "games": []
    }
    with open(game_data_path, "w") as f:
        json.dump(default_data, f, indent=4)

def load_config():
    if not os.path.exists(config_path):
        config = configparser.ConfigParser()
        config['DEFAULT'] = {
            'ReminderIntervalMinutes': '30',
            'GameCheckIntervalSeconds': '5'
        }
        with open(config_path, 'w') as configfile:
            config.write(configfile)
    config = configparser.ConfigParser()
    config.read(config_path)
    return [int(config['DEFAULT'].get('ReminderIntervalMinutes', 30)), int(config['DEFAULT'].get('GameCheckIntervalSeconds', 30))]

# Load the current game data from the JSON file
def load_game_data():
    with open(game_data_path, "r") as f:
        return json.load(f)

# Save the updated game data back to the JSON file
def save_game_data(data):
    with open(game_data_path, "w") as f:
        json.dump(data, f, indent=4)

def track_game_activity(games):
    print("Tracking game activity...")
    active_processes = {proc.info['name'].lower() for proc in psutil.process_iter(['name'])}
    for game in games:
        if game['game.exe'].lower() in active_processes:
            game['login_status'] = True
            print(f"{game['game']} is running")
            game['last_login_time'] = str(datetime.now())
        else:
            # Parse last login and reset times
            last_login_time = datetime.strptime(game['last_login_time'].split('.')[0], "%Y-%m-%d %H:%M:%S")
            current_time = datetime.now()

            reset_hour, reset_minute = map(int, game['server_reset_time'].split(':'))
            reset_time_today = current_time.replace(hour=reset_hour, minute=reset_minute, second=0, microsecond=0)

            # Handle reset time crossing midnight
            if reset_time_today > current_time:
                reset_time_today -= timedelta(days=1)

            if last_login_time < reset_time_today:
                game['login_status'] = False
    save_game_data({"games": games})


def check_server_reset_time(game):
    reset_hour, reset_minute = map(int, game['server_reset_time'].split(':'))
    current_time = datetime.now()

    reset_time_today = current_time.replace(hour=reset_hour, minute=reset_minute, second=0, microsecond=0)

    # Handle reset time crossing midnight
    if reset_time_today > current_time:
        reset_time_today -= timedelta(days=1)

    return current_time > reset_time_today and not game['login_status']


# Send a reminder notification to log in
def send_reminder(game):
    print(f"Sending reminder for {game['game']}")
    notification.notify(
        title=f"Reminder: Login to {game['game']}",
        message=f"Don't forget to login to {game['game']}!",
        timeout=10
    )
    

# Task to be scheduled
def scheduled_task_1():
    print("task 1")
    games = load_game_data()['games']
    
    # Track game activity and update login status
    track_game_activity(games)
    
    # Check if any game requires a reminder
    for game in games:
        if game['login_status'] == False:
            send_reminder(game)
        elif check_server_reset_time(game):
            send_reminder(game)
    
    # Save updated data
    save_game_data({"games": games})

def scheduled_task_0():
    print("task 0")
    games = load_game_data()['games']
    track_game_activity(games)


def run_task_in_thread(task):
    task_thread = threading.Thread(target=task)
    task_thread.start()

# Create the tray icon
def create_tray_icon():
    def exit_action(icon, item):
        icon.stop()

    # Create an icon from the .ico file
    icon_image = Image.open(icon_path)

    # Define tray menu
    menu = Menu(MenuItem('Exit', exit_action))

    # Create and run the icon
    icon = Icon("GameReminder", icon_image, menu=menu)
    icon.run()


# Main function
def main():
    # Schedule the task to run every 30 minutes
    ReminderIntervalMinutes, GameCheckIntervalSeconds = load_config()

    schedule.every(GameCheckIntervalSeconds).seconds.do(run_task_in_thread, scheduled_task_0)
    schedule.every(ReminderIntervalMinutes).seconds.do(run_task_in_thread, scheduled_task_1)

     # Create and run the tray icon in a separate thread
    icon_thread = threading.Thread(target=create_tray_icon)
    icon_thread.daemon = True
    icon_thread.start()

    # Run the scheduler continuously
    while True:
        schedule.run_pending()
        time.sleep(1)  # Prevent CPU overuse

if __name__ == "__main__":
    main()