from dash import Dash, html, dcc, Input, Output, State, callback, ALL, ctx, no_update
import sqlite3
import pandas as pd

# The golden rule for multi-page Dash apps: Suppress the exceptions
app = Dash(__name__, suppress_callback_exceptions=True)
server = app.server

# --- Ensure Settings Table Exists ---
conn = sqlite3.connect('golf_trip.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS Settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
''')
cursor.execute("INSERT OR IGNORE INTO Settings (key, value) VALUES ('active_course_id', '1')")
conn.commit()
conn.close()

# --- Helper functions ---
def get_options(query, label_col, value_col):
    conn = sqlite3.connect('golf_trip.db')
    df = pd.read_sql_query(query, conn)
    conn.close()
    return [{'label': row[label_col], 'value': row[value_col]} for _, row in df.iterrows()]

def get_players_df():
    conn = sqlite3.connect('golf_trip.db')
    df = pd.read_sql_query("SELECT * FROM Players", conn)
    conn.close()
    return df

course_options = get_options("SELECT * FROM Courses", 'course_name', 'course_id')
hole_options = [{'label': f'Hole {i}', 'value': i} for i in range(1, 19)]

# --- Layout Builders ---

def build_group_setup_layout():
    players_df = get_players_df()
    player_options = [{'label': row['name'], 'value': row['player_id']} for _, row in players_df.iterrows()]
    
    return html.Div(style={'fontFamily': 'system-ui, sans-serif', 'maxWidth': '500px', 'margin': 'auto', 'padding': '20px'}, children=[
        html.H1("Setup Round", style={'textAlign': 'center', 'marginBottom': '10px'}),
        html.P("Select the players in your specific group:", style={'textAlign': 'center', 'color': '#666', 'marginBottom': '20px'}),
        
        dcc.Dropdown(
            id='group-selector',
            options=player_options,
            multi=True,
            placeholder="Select up to 4 players...",
            style={'marginBottom': '25px'}
        ),
        
        html.Button('Tee Off', id='start-round-btn', n_clicks=0, style={
            'width': '100%', 'padding': '15px', 'backgroundColor': '#28a745', 'color': 'white',
            'border': 'none', 'borderRadius': '8px', 'fontSize': '18px', 'cursor': 'pointer', 'fontWeight': 'bold'
        }),
        
        html.Div(id='setup-error', style={'color': 'red', 'marginTop': '15px', 'textAlign': 'center', 'fontWeight': 'bold'})
    ])

def build_scoring_layout(selected_player_ids):
    conn = sqlite3.connect('golf_trip.db')
    placeholders = ','.join('?' for _ in selected_player_ids)
    df = pd.read_sql_query(f"SELECT * FROM Players WHERE player_id IN ({placeholders})", conn, params=selected_player_ids)
    conn.close()
    
    player_input_rows = []
    for _, row in df.iterrows():
        player_input_rows.append(
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between', 'padding': '10px', 'borderBottom': '1px solid #eee'}, children=[
                html.Label(row['name'], style={'fontWeight': 'bold', 'fontSize': '18px'}),
                dcc.Input(
                    id={'type': 'player-score', 'index': row['player_id']},
                    type='number',
                    placeholder="-",
                    style={'width': '80px', 'padding': '10px', 'fontSize': '18px', 'textAlign': 'center', 'borderRadius': '5px', 'border': '1px solid #ccc'}
                )
            ])
        )

    return html.Div(style={'fontFamily': 'system-ui, sans-serif', 'maxWidth': '500px', 'margin': 'auto', 'padding': '20px'}, children=[
        html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '15px'}, children=[
            html.H2("Live Scoring", style={'margin': '0'}),
            html.Button('Edit Group', id='clear-group-btn', n_clicks=0, style={'padding': '5px 10px', 'backgroundColor': '#dc3545', 'color': 'white', 'border': 'none', 'borderRadius': '4px', 'cursor': 'pointer', 'fontSize': '12px'})
        ]),
        
        dcc.Dropdown(
            id='course-dropdown', options=course_options, disabled=True,
            style={'marginBottom': '20px', 'backgroundColor': '#f0f0f0', 'textAlign': 'center'}
        ),
        
        html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'backgroundColor': '#343a40', 'padding': '15px', 'borderRadius': '8px', 'marginBottom': '20px', 'color': 'white'}, children=[
            html.Button('←', id='prev-hole-btn', n_clicks=0, style={'padding': '10px 15px', 'backgroundColor': '#6c757d', 'color': 'white', 'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer', 'fontWeight': 'bold', 'fontSize': '16px'}),
            html.Div(style={'display': 'flex', 'flexDirection': 'column', 'alignItems': 'center'}, children=[
                dcc.Dropdown(id='hole-dropdown', options=hole_options, value=1, clearable=False, style={'width': '100px', 'color': 'black', 'marginBottom': '5px'}),
                html.Span(id='par-display', style={'fontWeight': 'bold', 'fontSize': '14px', 'color': '#ffc107'})
            ]),
            html.Button('→', id='next-hole-btn', n_clicks=0, style={'padding': '10px 15px', 'backgroundColor': '#28a745', 'color': 'white', 'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer', 'fontWeight': 'bold', 'fontSize': '16px'})
        ]),
        
        html.Div(player_input_rows, style={'backgroundColor': '#f9f9f9', 'borderRadius': '8px', 'padding': '10px', 'marginBottom': '20px'}),
        
        html.Button('Save Group Scores', id='submit-btn', n_clicks=0, style={
            'width': '100%', 'padding': '15px', 'backgroundColor': '#007BFF', 'color': 'white',
            'border': 'none', 'borderRadius': '8px', 'fontSize': '18px', 'cursor': 'pointer', 'fontWeight': 'bold'
        }),
        
        html.Div(id='output-message', style={'marginTop': '20px', 'textAlign': 'center', 'fontWeight': 'bold'})
    ])

admin_layout = html.Div(style={'fontFamily': 'system-ui, sans-serif', 'maxWidth': '500px', 'margin': 'auto', 'padding': '20px'}, children=[
    html.H1("Commissioner Dashboard", style={'textAlign': 'center', 'color': '#D32F2F'}),
    html.Div(style={'backgroundColor': '#f9f9f9', 'padding': '20px', 'borderRadius': '8px', 'border': '1px solid #eee', 'marginBottom': '20px'}, children=[
        html.H3("Set Active Round", style={'marginTop': '0'}),
        dcc.Dropdown(id='admin-course-dropdown', options=course_options, placeholder="Select Active Course", style={'marginBottom': '15px'}),
        html.Button('Update Active Course', id='set-active-course-btn', n_clicks=0, style={'width': '100%', 'padding': '12px', 'backgroundColor': '#D32F2F', 'color': 'white', 'border': 'none', 'borderRadius': '5px', 'fontSize': '16px', 'cursor': 'pointer'}),
        html.Div(id='admin-output-message', style={'marginTop': '15px', 'textAlign': 'center', 'fontWeight': 'bold'})
    ]),
    html.A("← Back to App", href="/", style={'display': 'block', 'textAlign': 'center', 'marginTop': '30px', 'textDecoration': 'none', 'color': '#007BFF', 'fontWeight': 'bold'})
])

# --- Main App Container ---
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='session-group', storage_type='session'),
    html.Div(id='page-content')
])

# --- Back-End Logic ---

# 1. Routing & Layout Rendering
@callback(
    Output('page-content', 'children'),
    Input('url', 'pathname'),
    Input('session-group', 'data')
)
def display_page(pathname, group_data):
    if pathname == '/commissioner':
        return admin_layout
    
    if not group_data:
        return build_group_setup_layout()
    else:
        return build_scoring_layout(group_data)

# 2a. Start Round (Setup Screen Only)
@callback(
    Output('session-group', 'data', allow_duplicate=True),
    Output('setup-error', 'children', allow_duplicate=True),
    Input('start-round-btn', 'n_clicks'),
    State('group-selector', 'value'),
    prevent_initial_call=True
)
def start_round(n_clicks, selected_players):
    if not selected_players or len(selected_players) == 0:
        return no_update, "Please select at least one player to tee off."
    return selected_players, ""

# 2b. Clear Group (Scoring Screen Only)
@callback(
    Output('session-group', 'data', allow_duplicate=True),
    Input('clear-group-btn', 'n_clicks'),
    prevent_initial_call=True
)
def clear_group(n_clicks):
    return None

# 3. Lock Course
@callback(Output('course-dropdown', 'value'), Input('url', 'pathname'))
def set_default_course(pathname):
    if pathname == '/':
        conn = sqlite3.connect('golf_trip.db')
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM Settings WHERE key = 'active_course_id'")
        row = cursor.fetchone()
        conn.close()
        if row: return int(row[0])
    return None

# 4. Update Course (Admin)
@callback(
    Output('admin-output-message', 'children'),
    Input('set-active-course-btn', 'n_clicks'),
    State('admin-course-dropdown', 'value'),
    prevent_initial_call=True
)
def update_active_course(n_clicks, course_id):
    if not course_id: return html.Span("Please select a course.", style={'color': 'red'})
    conn = sqlite3.connect('golf_trip.db')
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO Settings (key, value) VALUES ('active_course_id', ?)", (str(course_id),))
    conn.commit()
    conn.close()
    return html.Span("Active course updated!", style={'color': 'green'})

# 5. Fetch Par & Existing Scores
@callback(
    Output('par-display', 'children'),
    Output({'type': 'player-score', 'index': ALL}, 'value'),
    Input('course-dropdown', 'value'),
    Input('hole-dropdown', 'value'),
    State({'type': 'player-score', 'index': ALL}, 'id')
)
def update_hole_view(course_id, hole_num, player_ids):
    if not course_id or not hole_num:
        return "Par --", [None] * len(player_ids)
        
    conn = sqlite3.connect('golf_trip.db')
    cursor = conn.cursor()
    cursor.execute("SELECT par FROM Course_Holes WHERE course_id = ? AND hole_number = ?", (course_id, hole_num))
    par_row = cursor.fetchone()
    par_text = f"Par {par_row[0]}" if par_row else "Par --"
    
    cursor.execute("SELECT player_id, strokes FROM Scores WHERE course_id = ? AND hole_number = ?", (course_id, hole_num))
    scores_dict = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    
    out_values = []
    for pid_dict in player_ids:
        pid = pid_dict['index']
        out_values.append(scores_dict.get(pid, None))
        
    return par_text, out_values

# 6. Save Group Scores
@callback(
    Output('output-message', 'children'),
    Input('submit-btn', 'n_clicks'),
    State('course-dropdown', 'value'),
    State('hole-dropdown', 'value'),
    State({'type': 'player-score', 'index': ALL}, 'id'),
    State({'type': 'player-score', 'index': ALL}, 'value'),
    prevent_initial_call=True
)
def save_group_scores(n_clicks, course_id, hole, player_ids, player_scores):
    if not course_id or not hole:
        return html.Span("Error: Course and Hole must be selected.", style={'color': 'red'})
        
    conn = sqlite3.connect('golf_trip.db')
    cursor = conn.cursor()
    inserted_count = 0
    for pid_dict, score in zip(player_ids, player_scores):
        pid = pid_dict['index']
        if score is not None and score > 0:
            cursor.execute('DELETE FROM Scores WHERE player_id = ? AND course_id = ? AND hole_number = ?', (pid, course_id, hole))
            cursor.execute('INSERT INTO Scores (player_id, course_id, hole_number, strokes) VALUES (?, ?, ?, ?)', (pid, course_id, hole, score))
            inserted_count += 1
    conn.commit()
    conn.close()
    
    if inserted_count == 0:
        return html.Span("No scores entered.", style={'color': 'orange'})
    return html.Span(f"Saved {inserted_count} scores for Hole {hole}!", style={'color': 'green'})

# 7. Next / Previous Hole Navigation
@callback(
    Output('hole-dropdown', 'value'),
    Output('output-message', 'children', allow_duplicate=True),
    Input('prev-hole-btn', 'n_clicks'),
    Input('next-hole-btn', 'n_clicks'),
    State('hole-dropdown', 'value'),
    prevent_initial_call=True
)
def change_hole(prev_clicks, next_clicks, current_hole):
    triggered_id = ctx.triggered_id
    if triggered_id == 'next-hole-btn' and current_hole < 18:
        return current_hole + 1, ""
    elif triggered_id == 'prev-hole-btn' and current_hole > 1:
        return current_hole - 1, ""
    return current_hole, no_update

if __name__ == '__main__':
    app.run(debug=True, port=8886)
