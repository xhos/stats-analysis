import os
from dotenv import load_dotenv # type: ignore
from dash import Dash, html, dash_table, dcc, callback, Output, Input # type: ignore
import mysql.connector # type: ignore
import pandas as pd # type: ignore
import plotly.express as px # type: ignore
import dash_bootstrap_components as dbc # type: ignore
from dash import html # type: ignore
import plotly.io as pio # type: ignore

pio.templates.default = 'plotly_white'
pio.templates['plotly_white']['layout']['font']['family'] = "Poppins"

load_dotenv()
HOST = os.getenv('DB_HOST')
USER = os.getenv('DB_USER')
PASSWORD = os.getenv('DB_PASSWORD')
DATABASE = os.getenv('DB_NAME')

THEME = "MORPH"

BACKGROUND_COLOR = "#d9e3f1"
TEXT_COLOR = "#000000"

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
    data = cursor.fetchall()

    df = pd.DataFrame(data, columns=[col[0] for col in cursor.description])
    df = df[(df['stat_type'] == stat_type) & (df['stat_item'] == stat_item)]
    
    if recentOnly:
        df = df.sort_values('recorded_at').groupby('player_name').tail(1)
    
    # Close the db connection
    cursor.close()
    conn.close()
    
    return df

def get_stat_items_for_type(stat_type):
    conn = createConnection()
    cursor = conn.cursor()

    # Execute the query
    cursor.execute(f"SELECT DISTINCT stat_item FROM PlayerStats.Player_Stats WHERE stat_type = '{stat_type}'")

    # Fetch all rows
    rows = cursor.fetchall()

    # Close the connection
    conn.close()

    # Extract the stat items from the rows
    stat_items = [row[0] for row in rows]
    
    cursor.close()
    conn.close()
    
    return stat_items

app = Dash(__name__, title="AbyssStats", external_stylesheets=[getattr(dbc.themes, THEME), dbc.icons.FONT_AWESOME])

color_mode_switch =  html.Span(
    [
        dbc.Label(className="fa fa-moon", html_for="switch"),
        dbc.Switch( id="switch", value=True, className="d-inline-block ms-1", persistence=True),
        dbc.Label(className="fa fa-sun", html_for="switch"),
    ]
)

app.layout = html.Div(
    [
        dbc.NavbarSimple(
            id="navbar",
            children=[
                color_mode_switch,  # Add the theme switcher here
            ],
            brand="AbyssStats (ака я делал это неделю хуй знает зачем)",
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
                                options=[],  # Options will be populated by the callback
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
    stat_items = get_stat_items_for_type(stat_type)

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
    figure = px.line(df, x='recorded_at', y='stat_value', title=f'Stat Change Over Time for {player_name}')

    # Update the layout of the figure to use the colors
    if switchOn:
        figure.update_layout(
            plot_bgcolor=BACKGROUND_COLOR,
            paper_bgcolor=BACKGROUND_COLOR,
            font=dict(color=TEXT_COLOR),
            xaxis=dict(gridcolor="#ced7e5"),  # Change grid color here
            yaxis=dict(gridcolor="#ced7e5")  # Change grid color here
        )
    else:
        figure.update_layout(
            plot_bgcolor="#212529",
            paper_bgcolor="#212529",
            font=dict(color="#ffffff"),
            xaxis=dict(gridcolor="#2c3034"),  # Change grid color here
            yaxis=dict(gridcolor="#2c3034")  # Change grid color here
        )
    return figure

if __name__ == '__main__':
    app.run(debug=True)