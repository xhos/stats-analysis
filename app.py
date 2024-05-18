import os
import pandas as pd
import mysql.connector
import plotly.io as pio
import plotly.express as px
from dotenv import load_dotenv
import dash_bootstrap_components as dbc
from dash import Dash, html, dcc, Output, Input

DEBUG = True
NAME="AbyssStats"
PORT = 8050 # Leave unchanged if you don't know what you're doing

# Feel free to change the theme to any provided by Dash Bootstrap Components
# https://dash-bootstrap-components.opensource.faculty.ai/docs/themes/#available-themes
# But do note that you will need to adjust below colors to match the theme for it to look good
# Some color settings also should be adjusted in the assets/styles.css file

THEME = "MORPH"
# Some themes also have weird support for dark mode, all I can do is to just wish you good luck :)
# Also if you'd like you can send me / open a PR with your theme presets, I'll be happy to add them to the list
 
LIGHT_THEME_GRID_COLOR = "#ced7e5"
LIGHT_TEXT_COLOR = "#000000"
LIGHT_THEME_PLOT_BACKGROUND_COLOR = "#d9e3f1"

DARK_THEME_GRID_COLOR = "#2c3034"
DARK_THEME_TEXT_COLOR = "#ffffff"
DARK_THEME_PLOT_BACKGROUND_COLOR = "#212529"

if DEBUG:
    load_dotenv()
    
HOST = os.getenv('DB_HOST')
USER = os.getenv('DB_USER')
PASSWORD = os.getenv('DB_PASSWORD')
DATABASE = os.getenv('DB_NAME')

pio.templates.default = 'plotly_white'
pio.templates['plotly_white']['layout']['font']['family'] = "Poppins"

stat_type_options = ["broken", "crafted", "custom", "dropped", "killed", "mined", "picked_up", "used"]

def createConnection():
    conn = mysql.connector.connect(
        host=HOST,
        user=USER,
        password=PASSWORD,
        database=DATABASE
    )
    return conn

def getData(stat_type, stat_item, player_name=None, recentOnly=True):
    # Connect to the db
    conn = createConnection()
    cursor = conn.cursor()

    if player_name:
        SQL_Query = f"""
        SELECT * FROM PlayerStats.Player_Stats
        WHERE stat_type = '{stat_type}' AND stat_item = '{stat_item}' AND player_name = '{player_name}'
        """
    else:
        SQL_Query = f"""
        SELECT * FROM PlayerStats.Player_Stats
        WHERE stat_type = '{stat_type}' AND stat_item = '{stat_item}'
        """

    cursor.execute(SQL_Query)
    
    # some smart stuff to get the data from the db
    data = cursor.fetchall()
    df = pd.DataFrame(data, columns=[col[0] for col in cursor.description])
    df = df[(df['stat_type'] == stat_type) & (df['stat_item'] == stat_item)]
    
    if recentOnly:
        # leave only the most recent stat entry for each player
        df = df.sort_values('recorded_at').groupby('player_name').tail(1)
    
    # Close the db connection
    cursor.close()
    conn.close()
    
    return df

def getItemsForStat(stat_type):
    conn = createConnection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT DISTINCT stat_item FROM PlayerStats.Player_Stats WHERE stat_type = '{stat_type}'")

    # Fetch all rows
    rows = cursor.fetchall()

    # Extract the stat items from the rows
    stat_items = [row[0] for row in rows]
    
    # Close the connection
    cursor.close()
    conn.close()
    
    return stat_items



app = Dash(__name__, title=NAME, external_stylesheets=[getattr(dbc.themes, THEME), dbc.icons.FONT_AWESOME])
server = app.server

app.layout = html.Div(
    [
        dbc.NavbarSimple(
            id="navbar",
            children=[
                html.Span(
                    [
                        dbc.Label(className="fa fa-moon", html_for="switch"),
                        dbc.Switch( id="switch", value=True, className="d-inline-block ms-1", persistence=True),
                        dbc.Label(className="fa fa-sun", html_for="switch"),
                    ]
                )
            ],
            brand=NAME,
            brand_href="#",
            color="light",
        ),
        dbc.Container(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Select(
                                id="select-stat-type", # ID
                                options=[{"label": i, "value": i} for i in stat_type_options], # Options
                                value="used", # Default value
                            ),
                        ),
                        dbc.Col(
                            dbc.Select(
                                id="input",
                                options=[],
                                value="sand"
                            )
                        ),
                    ]
                ),
                dcc.Store(id='stat-type-store', data={i: 0 for i in stat_type_options}), 
                html.Br(),
                dbc.Table(id="data-table", bordered=True, striped=True), 
                html.Br(),
                dbc.Select(id="player-select"),
                html.Br(),
                dcc.Graph(id="player-graph"),
            ],
            className="p-5",
        ),
    ]
)

# ------------------------------
# Callbacks
# ------------------------------

app.clientside_callback(
    """
    function(switchOn) {
        document.documentElement.setAttribute("data-bs-theme", switchOn ? "light" : "dark");
        return window.dash_clientside.no_update;
    }
    """,
    Output("switch", "id"),
    Input("switch", "value"),
)


@app.callback(
    Output("navbar", "color"),
    [Input("switch", "value")],
)
def update_navbar_color(switchOn):
    return "light" if switchOn else "dark"


@app.callback(
    Output('stat-type-store', 'data'),
    [Input('select-stat-type', 'value')],
    [Input('stat-type-store', 'data')]
)
def update_store(selected_stat_type, store_data):
    # If a stat type was selected, update the store data
    if selected_stat_type:
        store_data[selected_stat_type] += 1
    # Return the updated or unchanged store data
    return store_data


@app.callback(
    Output("data-table", "children"),
    [Input("select-stat-type", "value"), Input("input", "value")]
)
def update_table(stat_type, stat_item):
    # Fetch the data based on the selected stat type and stat item
    df = getData(stat_type, stat_item, recentOnly=True)

    # Sort by 'stat_value' in descending order and keep only 'player_name' and 'stat_value' columns
    df = df.sort_values('stat_value', ascending=False)[['player_name', 'stat_value']]

    # Rename the columns
    df.columns = ['Name', 'Value']

    # Generate the table header
    table_header = [html.Thead(html.Tr([html.Th(col) for col in df.columns]))]

    # Generate the table body
    table_body = [html.Tbody([html.Tr([html.Td(df.iloc[i][col]) for col in df.columns]) for i in range(len(df))])]

    # Combine the table header and body
    table = table_header + table_body

    return table


@app.callback(
    Output("player-select", "options"),
    Output("player-select", "value"),
    [Input("select-stat-type", "value"), Input("input", "value")]
)
def update_player_select(stat_type, stat_item):
    # Fetch the data based on the selected stat type and stat item
    df = getData(stat_type, stat_item, recentOnly=True)

    # Sort the DataFrame by stat_value in descending order
    df = df.sort_values(by='stat_value', ascending=False)

    # Extract the player names from the DataFrame
    player_names = df['player_name'].unique().tolist()

    # Generate the select options
    options = [{"label": player_name, "value": player_name} for player_name in player_names]

    # Set the player with the highest stat value as the default value
    default_value = player_names[0] if player_names else None

    return options, default_value


@app.callback(
    Output("input", "options"),
    [Input("select-stat-type", "value")]
)
def update_stat_item_options(stat_type):
    # Fetch stat items for the selected stat type
    stat_items = getItemsForStat(stat_type)

    # Generate the select options
    options = [{"label": stat_item, "value": stat_item} for stat_item in stat_items]

    return options


@app.callback(
    Output("player-graph", "figure"),
    [Input("select-stat-type", "value"), Input("input", "value"), Input("player-select", "value"), Input("switch", "value")]
)
def update_player_graph(stat_type, stat_item, player_name, switchOn):
    # Fetch the data for the selected player
    df = getData(stat_type, stat_item, player_name, recentOnly=False)

    # Create a line graph of the player's value over time
    figure = px.line(df, 
        x='recorded_at',
        y='stat_value',
        title=f'Stat Change Over Time for {player_name}',
        labels={'recorded_at':'Time', 'stat_value':'Value'})

    # Update the layout of the figure to use the colors
    if switchOn:
        figure.update_layout(
            plot_bgcolor=LIGHT_THEME_PLOT_BACKGROUND_COLOR,
            paper_bgcolor=LIGHT_THEME_PLOT_BACKGROUND_COLOR,
            font=dict(color=LIGHT_TEXT_COLOR),
            xaxis=dict(gridcolor=LIGHT_THEME_GRID_COLOR),
            yaxis=dict(gridcolor=LIGHT_THEME_GRID_COLOR)
        )
    else:
        figure.update_layout(
            plot_bgcolor=DARK_THEME_PLOT_BACKGROUND_COLOR,
            paper_bgcolor=DARK_THEME_PLOT_BACKGROUND_COLOR,
            font=dict(color=DARK_THEME_TEXT_COLOR),
            xaxis=dict(gridcolor=DARK_THEME_GRID_COLOR),
            yaxis=dict(gridcolor=DARK_THEME_GRID_COLOR)
        )
    return figure

if __name__ == '__main__':
    app.run(debug=DEBUG, port=PORT)