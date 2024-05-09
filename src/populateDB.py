import requests
import json
import time

def get_online_players():
    response = requests.get("http://localhost:8081/api/getOnlinePlayerNames")
    player_names = json.loads(response.text)
    return player_names

while True:
    players = get_online_players()
    for player in players:
        print(f'Player: {player}')
    time.sleep(10)