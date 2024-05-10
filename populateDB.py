import requests
import json
import time
import os
from dotenv import load_dotenv
import mysql.connector

# Load environment variables from .env file
load_dotenv()

# Get database connection details from environment variables
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = 'PlayerStats'

# Sleep time between each call to populate_db
SLEEP_TIME = 60*60

# https://github.com/misode/mcmeta/blob/registries/item/data.json
with open('data/items.json', 'r') as file:
    items = json.load(file)

# https://github.com/misode/mcmeta/blob/registries/custom_stat/data.json
with open('data/custom_stats.json', 'r') as file:
    custom_stats = json.load(file)

# https://github.com/misode/mcmeta/blob/registries/entity_type/data.json
with open('data/entities.json', 'r') as file:
    entities = json.load(file)

# https://github.com/misode/mcmeta/blob/registries/stat_type/data.json
stats_map = {
    "broken": "items",
    "crafted": "items",
    "custom": "custom_stat",
    "dropped": "items",
    "killed": "entities",
    "kill_by": "entities",
    "mined": "items",
    "picked_up": "items",
    "used": "items"
}

# Returns a list of online player names
def getOnlinePlayers():
    response = requests.get("http://localhost:8081/api/getOnlinePlayerNames")
    player_names = json.loads(response.text)
    return player_names

# Returns a value of the stat in question
def getStatValue(playername, stattype, item):
    url = f"http://localhost:8081/api/executeCommand?command=stats%20query%20{playername}%20minecraft:{stattype}%20minecraft:{item}"
    response = requests.get(url)
    return {f"{stattype}:{item}": response.json()}

# YES
def getAllStats(playername):
    results = {}
    for stattype, stattype_value in stats_map.items():
        if stattype_value == "items":
            for item in items:
                results.update(getStatValue(playername, stattype, item))
        elif stattype_value == "custom_stat":
            for stat in custom_stats:
                results.update(getStatValue(playername, stattype, stat))
        elif stattype_value == "entities":
            for entity in entities:
                results.update(getStatValue(playername, stattype, entity))
    return results


# Returns a list of all custom stats for a player
def getAllCustomStats(playername):
    results = []
    for stat in custom_stats:
        url = f"http://localhost:8081/api/executeCommand?command=stats%20query%20{playername}%20minecraft:custom%20{stat}"
        response = requests.get(url)
        results.append(response.json())
    return results

# Returns the level of the player
def get_xp_value(playername):
    url = f"http://localhost:8081/api/executeCommand?command=xp%20query%20{playername}%20levels"
    response = requests.get(url)
    return response.json()

def populate_db():
    try:
        mydb = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT,
            database=DB_NAME
        )
        # Create a cursor object
        mycursor = mydb.cursor()

        players = getOnlinePlayers()
        for player in players:
            stats = getAllStats(player)
            xp_level = get_xp_value(player)

            # Insert the player into the Players table
            sql = "INSERT IGNORE INTO Players (player_name) VALUES (%s)"
            val = (player,)
            mycursor.execute(sql, val)
            mydb.commit()

            # Insert a record into the Player_Online table
            sql = "INSERT INTO Player_Online (player_name) VALUES (%s)"
            val = (player,)
            mycursor.execute(sql, val)
            mydb.commit()

            # Insert the stats into the Player_Stats table
            for stat, value in stats.items():
                # Skip if the value of the stat is zero
                if value == 0:
                    continue

                stat_type, stat_item = stat.split(":")
                
                # Fetch the latest recorded value for this stat
                sql = "SELECT stat_value FROM Player_Stats WHERE player_name = %s AND stat_type = %s AND stat_item = %s ORDER BY recorded_at DESC LIMIT 1"
                val = (player, stat_type, stat_item)
                mycursor.execute(sql, val)
                result = mycursor.fetchone()
                
                # If the new stat value is the same as the latest recorded value, skip the insertion
                if result is not None and value == result[0]:
                    continue
                
                sql = "INSERT INTO Player_Stats (player_name, stat_type, stat_item, stat_value) VALUES (%s, %s, %s, %s)"
                val = (player, stat_type, stat_item, value)
                mycursor.execute(sql, val)
                mydb.commit()

        # Insert the XP level into the Player_XP table
        sql = "INSERT INTO Player_XP (player_name, xp_level, recorded_at) VALUES (%s, %s, NOW())"
        val = (player, xp_level)
        mycursor.execute(sql, val)
        mydb.commit()
    except mysql.connector.Error as err:
        print(f"Something went wrong: {err}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        
while True:
    populate_db()
    time.sleep(SLEEP_TIME)