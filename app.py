from dash import Dash, html, dcc, Input, Output, State, callback, ALL, ctx, no_update
import sqlite3
import pandas as pd

app = Dash(__name__, suppress_callback_exceptions=True)
server = app.server

# --- Ensure Settings Table Exists & Initialize Defaults ---
conn = sqlite3.connect('golf_trip.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS Settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
''')
cursor.execute("INSERT OR IGNORE INTO Settings (key, value) VALUES ('active_course_id', '1')")
cursor.execute("INSERT OR IGNORE INTO Settings (key, value) VALUES ('tournament_format', 'Stroke Play')")

# Attempt silent migration (will fail gracefully if DB is locked)
try:
    cursor.execute("PRAGMA table_info(Course_Holes)")
    columns = [info[1] for info in cursor.fetchall()]
    if columns and 'handicap' not in columns:
        cursor.execute("ALTER TABLE Course_Holes ADD COLUMN handicap INTEGER DEFAULT 18")
except Exception:
    pass

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

def get_pops(player_hcp, hole_hcp):
    try:
        hcp = float(player_hcp)
        hhcp = int(hole_hcp)
    except (ValueError, TypeError):
        return 0
        
    if hcp >= 0:
        return int(hcp // 18) + (1 if hhcp <= (hcp % 18) else 0)
    else:
        abs_hcp = abs(hcp)
        return -(int(abs_hcp // 18) + (1 if hhcp > (18 - (abs_hcp % 18)) else 0))

def get_pops_symbol(pops):
    if pops > 0: return " " + ("•" * pops)
    if pops < 0: return " " + ("+" * abs(pops))
    return ""

course_options = get_options("SELECT * FROM Courses", 'course_name', 'course_id')
hole_options = [{'label': f'Hole {i}', 'value': i} for i in range(1, 19)]

format_options = [
    {'label': 'Stroke Play (Gross)', 'value': 'Stroke Play'},
    {'label': 'Net Stroke Play', 'value': 'Net Stroke Play'},
    {'label': 'Stableford (Net)', 'value': 'Stableford'}
]

# --- Layout Builders ---

def build_group_setup_layout():
    players_df = get_players_df()
    player_options = [{'label': row['name'], 'value': row['player_id']} for _, row in players_df.iterrows()]
    
    return html.Div(style={'fontFamily': 'system-ui, sans-serif', 'maxWidth': '500px', 'margin': 'auto', 'padding': '20px'}, children=[
        html.H1("Setup Round", style={'textAlign': 'center', 'marginBottom': '10px'}),
        html.P("Select the players in your cart:", style={'textAlign': 'center', 'color': '#666', 'marginBottom': '20px'}),
        
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
        
        html.Div(id='setup-error', style={'color': 'red', 'marginTop': '15px', 'textAlign': 'center', 'fontWeight': 'bold'}),
        
        html.Div(style={'display': 'none'}, children=[
            html.Button(id='clear-group-btn'),
            html.Button(id='show-leaderboard-btn'),
            html.Button(id='hide-leaderboard-btn'),
            html.Button(id='show-scorecard-btn'),
            html.Button(id='hide-scorecard-btn'),
            html.Button(id='prev-hole-btn'),
            html.Button(id='next-hole-btn'),
            html.Button(id='submit-btn')
        ])
    ])

def build_scoring_layout(selected_player_ids, start_hole, active_view):
    conn = sqlite3.connect('golf_trip.db')
    placeholders = ','.join('?' for _ in selected_player_ids)
    df = pd.read_sql_query(f"SELECT * FROM Players WHERE player_id IN ({placeholders})", conn, params=selected_player_ids)
    conn.close()
    
    player_input_rows = []
    for _, row in df.iterrows():
        player_input_rows.append(
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between', 'padding': '10px', 'borderBottom': '1px solid #eee'}, children=[
                html.Label(row['name'], id={'type': 'player-label', 'index': row['player_id']}, style={'fontWeight': 'bold', 'fontSize': '18px'}),
                dcc.Input(
                    id={'type': 'player-score', 'index': row['player_id']},
                    type='number',
                    placeholder="-",
                    style={'width': '80px', 'padding': '10px', 'fontSize': '18px', 'textAlign': 'center', 'borderRadius': '5px', 'border': '1px solid #ccc'}
                )
            ])
        )

    scoring_display = 'block' if active_view == 'scoring' else 'none'
    leaderboard_display = 'block' if active_view == 'leaderboard' else 'none'
    scorecard_display = 'block' if active_view == 'scorecard' else 'none'

    scoring_ui = html.Div(id='scoring-ui-container', style={'display': scoring_display}, children=[
        html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'backgroundColor': '#343a40', 'padding': '15px', 'borderRadius': '8px', 'marginBottom': '20px', 'color': 'white'}, children=[
            html.Button('←', id='prev-hole-btn', n_clicks=0, style={'padding': '10px 15px', 'backgroundColor': '#6c757d', 'color': 'white', 'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer', 'fontWeight': 'bold', 'fontSize': '16px'}),
            html.Div(style={'display': 'flex', 'flexDirection': 'column', 'alignItems': 'center'}, children=[
                dcc.Dropdown(id='hole-dropdown', options=hole_options, value=start_hole, clearable=False, style={'width': '100px', 'color': 'black', 'marginBottom': '5px'}),
                html.Span(id='par-display', style={'fontWeight': 'bold', 'fontSize': '14px', 'color': '#ffc107'})
            ]),
            html.Button('→', id='next-hole-btn', n_clicks=0, style={'padding': '10px 15px', 'backgroundColor': '#28a745', 'color': 'white', 'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer', 'fontWeight': 'bold', 'fontSize': '16px'})
        ]),
        
        html.Div(player_input_rows, style={'backgroundColor': '#f9f9f9', 'borderRadius': '8px', 'padding': '10px', 'marginBottom': '20px'}),
        
        html.Button('Save Group Scores', id='submit-btn', n_clicks=0, style={
            'width': '100%', 'padding': '15px', 'backgroundColor': '#007BFF', 'color': 'white',
            'border': 'none', 'borderRadius': '8px', 'fontSize': '18px', 'cursor': 'pointer', 'fontWeight': 'bold'
        }),
        
        html.Div(id='output-message', style={'marginTop': '10px', 'marginBottom': '20px', 'textAlign': 'center', 'fontWeight': 'bold'}),
        
        html.Button('🏆 View Leaderboard', id='show-leaderboard-btn', n_clicks=0, style={
            'width': '100%', 'padding': '15px', 'backgroundColor': '#17a2b8', 'color': 'white',
            'border': 'none', 'borderRadius': '8px', 'fontSize': '18px', 'cursor': 'pointer', 'fontWeight': 'bold'
        }),
        html.Button('📋 View Scorecard', id='show-scorecard-btn', n_clicks=0, style={
            'width': '100%', 'padding': '15px', 'backgroundColor': '#6f42c1', 'color': 'white',
            'border': 'none', 'borderRadius': '8px', 'fontSize': '18px', 'cursor': 'pointer', 'fontWeight': 'bold', 'marginTop': '10px'
        }),
    ])

    leaderboard_ui = html.Div(id='leaderboard-ui-container', style={'display': leaderboard_display}, children=[
        html.Button('← Back to Scoring', id='hide-leaderboard-btn', n_clicks=0, style={
            'width': '100%', 'padding': '10px', 'backgroundColor': '#6c757d', 'color': 'white',
            'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer', 'fontWeight': 'bold', 'marginBottom': '20px'
        }),
        html.Div(id='leaderboard-container')
    ])

    scorecard_ui = html.Div(id='scorecard-ui-container', style={'display': scorecard_display}, children=[
        html.Button('← Back to Scoring', id='hide-scorecard-btn', n_clicks=0, style={
            'width': '100%', 'padding': '10px', 'backgroundColor': '#6c757d', 'color': 'white',
            'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer', 'fontWeight': 'bold', 'marginBottom': '20px'
        }),
        html.Div(id='scorecard-container', style={'overflowX': 'auto'})
    ])

    return html.Div(style={'fontFamily': 'system-ui, sans-serif', 'maxWidth': '500px', 'margin': 'auto', 'padding': '20px'}, children=[
        html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '15px'}, children=[
            html.H2("Live Scoring", style={'margin': '0'}),
            html.Button('Edit Group', id='clear-group-btn', n_clicks=0, style={'padding': '5px 10px', 'backgroundColor': '#dc3545', 'color': 'white', 'border': 'none', 'borderRadius': '4px', 'cursor': 'pointer', 'fontSize': '12px'})
        ]),
        
        dcc.Dropdown(
            id='course-dropdown', options=course_options, disabled=True,
            style={'marginBottom': '20px', 'backgroundColor': '#f0f0f0', 'textAlign': 'center'}
        ),
        
        scoring_ui,
        leaderboard_ui,
        scorecard_ui
    ])

admin_layout = html.Div(style={'fontFamily': 'system-ui, sans-serif', 'maxWidth': '500px', 'margin': 'auto', 'padding': '20px'}, children=[
    html.H1("Commissioner Dashboard", style={'textAlign': 'center', 'color': '#D32F2F'}),
    
    html.Div(style={'backgroundColor': '#f9f9f9', 'padding': '20px', 'borderRadius': '8px', 'border': '1px solid #eee', 'marginBottom': '20px'}, children=[
        html.H3("Active Course", style={'marginTop': '0', 'marginBottom': '10px'}),
        dcc.Dropdown(id='admin-course-dropdown', options=course_options, placeholder="Select Active Course", style={'marginBottom': '25px'}),
        html.H3("Tournament Format", style={'marginTop': '0', 'marginBottom': '10px'}),
        dcc.Dropdown(id='admin-format-dropdown', options=format_options, placeholder="Select Format", style={'marginBottom': '25px'}),
        html.Button('Lock In Settings', id='save-settings-btn', n_clicks=0, style={'width': '100%', 'padding': '12px', 'backgroundColor': '#007BFF', 'color': 'white', 'border': 'none', 'borderRadius': '5px', 'fontSize': '16px', 'cursor': 'pointer', 'fontWeight': 'bold'}),
        html.Div(id='admin-output-message', style={'marginTop': '15px', 'textAlign': 'center', 'fontWeight': 'bold'})
    ]),
    
    html.Div(style={'backgroundColor': '#e9ecef', 'padding': '20px', 'borderRadius': '8px', 'border': '1px solid #ced4da', 'marginBottom': '20px'}, children=[
        html.H3("Course Handicaps (Stroke Index)", style={'marginTop': '0', 'marginBottom': '10px'}),
        html.P("Select an active course above to load its 18 holes.", style={'fontSize': '14px', 'color': '#666', 'marginBottom': '15px'}),
        html.Div(id='admin-handicap-container'),
        html.Button('Save Hole Handicaps', id='save-handicaps-btn', n_clicks=0, style={'width': '100%', 'padding': '12px', 'backgroundColor': '#28a745', 'color': 'white', 'border': 'none', 'borderRadius': '5px', 'fontSize': '16px', 'cursor': 'pointer', 'fontWeight': 'bold', 'marginTop': '15px', 'display': 'none'}),
        html.Div(id='admin-handicap-output-message', style={'marginTop': '15px', 'textAlign': 'center', 'fontWeight': 'bold'})
    ]),
    
    html.Div(style={'backgroundColor': '#fff5f5', 'padding': '20px', 'borderRadius': '8px', 'border': '1px solid #ffcdd2', 'marginBottom': '20px'}, children=[
        html.H3("Danger Zone", style={'marginTop': '0', 'marginBottom': '10px', 'color': '#D32F2F'}),
        html.P("Testing complete? Clear out all scores from the database to start fresh.", style={'fontSize': '14px', 'color': '#666', 'marginBottom': '15px'}),
        
        dcc.ConfirmDialogProvider(
            children=html.Button('⚠️ Wipe All Scores', style={'width': '100%', 'padding': '12px', 'backgroundColor': 'transparent', 'color': '#D32F2F', 'border': '2px solid #D32F2F', 'borderRadius': '5px', 'fontSize': '16px', 'cursor': 'pointer', 'fontWeight': 'bold'}),
            id='reset-tournament-provider',
            message='Are you sure you want to completely wipe all player scores? This CANNOT be undone!'
        ),
        html.Div(id='reset-output-message', style={'marginTop': '15px', 'textAlign': 'center', 'fontWeight': 'bold'})
    ]),
    
    html.A("← Back to App", href="/", style={'display': 'block', 'textAlign': 'center', 'marginTop': '30px', 'textDecoration': 'none', 'color': '#007BFF', 'fontWeight': 'bold'})
])

# --- Main App Container ---
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='session-group', storage_type='local'),
    dcc.Store(id='session-hole', storage_type='local'),
    dcc.Store(id='session-view', storage_type='local'),
    html.Div(id='page-content')
])

# --- Back-End Logic ---

@callback(
    Output('page-content', 'children'),
    Input('url', 'pathname'),
    Input('session-group', 'data'),
    State('session-hole', 'data'),
    State('session-view', 'data')
)
def display_page(pathname, group_data, hole_data, view_data):
    if pathname == '/commissioner':
        return admin_layout
    if not group_data:
        return build_group_setup_layout()
    else:
        current_hole = int(hole_data) if hole_data else 1
        active_view = view_data if view_data else 'scoring'
        return build_scoring_layout(group_data, current_hole, active_view)

@callback(
    Output('admin-course-dropdown', 'value'),
    Output('admin-format-dropdown', 'value'),
    Input('url', 'pathname')
)
def load_admin_defaults(pathname):
    if pathname == '/commissioner':
        conn = sqlite3.connect('golf_trip.db')
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM Settings WHERE key = 'active_course_id'")
        course_row = cursor.fetchone()
        cursor.execute("SELECT value FROM Settings WHERE key = 'tournament_format'")
        format_row = cursor.fetchone()
        conn.close()
        return (int(course_row[0]) if course_row else None, format_row[0] if format_row else None)
    return no_update, no_update

@callback(
    Output('admin-output-message', 'children'),
    Input('save-settings-btn', 'n_clicks'),
    State('admin-course-dropdown', 'value'),
    State('admin-format-dropdown', 'value'),
    prevent_initial_call=True
)
def save_tournament_settings(n_clicks, course_id, format_val):
    if not n_clicks: return no_update
    if not course_id or not format_val:
        return html.Span("Please select both a course and a format.", style={'color': 'red'})
    conn = sqlite3.connect('golf_trip.db')
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO Settings (key, value) VALUES ('active_course_id', ?)", (str(course_id),))
    cursor.execute("REPLACE INTO Settings (key, value) VALUES ('tournament_format', ?)", (str(format_val),))
    conn.commit()
    conn.close()
    return html.Span("Tournament settings locked in!", style={'color': 'green'})

# --- CRITICAL FIX: Graceful fallback if database is locked ---
@callback(
    Output('admin-handicap-container', 'children'),
    Output('save-handicaps-btn', 'style'),
    Input('admin-course-dropdown', 'value'),
    prevent_initial_call=True
)
def load_course_handicaps(course_id):
    if not course_id:
        return "", {'display': 'none'}

    conn = sqlite3.connect('golf_trip.db')
    
    try:
        df = pd.read_sql_query("SELECT hole_number, par, handicap FROM Course_Holes WHERE course_id = ? ORDER BY hole_number", conn, params=(course_id,))
    except Exception:
        # If the handicap column still doesn't exist, build it dynamically for the screen
        df = pd.read_sql_query("SELECT hole_number, par FROM Course_Holes WHERE course_id = ? ORDER BY hole_number", conn, params=(course_id,))
        df['handicap'] = df['hole_number']

    conn.close()

    if df.empty:
        return html.Div("No hole data found for this course.", style={'color': 'red'}), {'display': 'none'}

    inputs = []
    for _, row in df.iterrows():
        # THE FIX: Force Pandas np.int64 types into standard Python integers
        h_num = int(row['hole_number'])
        h_par = int(row['par']) if pd.notnull(row['par']) else '-'
        h_hcp = int(row['handicap']) if pd.notnull(row['handicap']) else h_num

        inputs.append(html.Div(style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between', 'padding': '8px 5px', 'borderBottom': '1px solid #ddd'}, children=[
            html.Label(f"Hole {h_num} (Par {h_par})", style={'fontWeight': 'bold'}),
            dcc.Input(
                id={'type': 'hole-hcp-input', 'index': h_num}, # Dash will now perfectly accept this integer
                type='number', value=h_hcp, min=1, max=18,
                style={'width': '70px', 'padding': '8px', 'textAlign': 'center', 'borderRadius': '4px', 'border': '1px solid #ccc'}
            )
        ]))

    layout = html.Div(inputs, style={'backgroundColor': 'white', 'padding': '15px', 'borderRadius': '5px', 'border': '1px solid #ccc', 'maxHeight': '350px', 'overflowY': 'auto'})
    btn_style = {'width': '100%', 'padding': '12px', 'backgroundColor': '#28a745', 'color': 'white', 'border': 'none', 'borderRadius': '5px', 'fontSize': '16px', 'cursor': 'pointer', 'fontWeight': 'bold', 'marginTop': '15px', 'display': 'block'}

    return layout, btn_style

# --- CRITICAL FIX: Brute force column creation on save ---
@callback(
    Output('admin-handicap-output-message', 'children'),
    Input('save-handicaps-btn', 'n_clicks'),
    State('admin-course-dropdown', 'value'),
    State({'type': 'hole-hcp-input', 'index': ALL}, 'id'),
    State({'type': 'hole-hcp-input', 'index': ALL}, 'value'),
    prevent_initial_call=True
)
def save_hole_handicaps(n_clicks, course_id, hole_ids, hole_hcps):
    if not n_clicks or not course_id: return no_update

    conn = sqlite3.connect('golf_trip.db')
    cursor = conn.cursor()

    # Brute force the column generation if it failed earlier
    try:
        cursor.execute("ALTER TABLE Course_Holes ADD COLUMN handicap INTEGER DEFAULT 18")
    except Exception:
        pass

    for h_dict, hcp in zip(hole_ids, hole_hcps):
        h_num = h_dict['index']
        try:
            hcp_val = int(hcp)
            cursor.execute("UPDATE Course_Holes SET handicap = ? WHERE course_id = ? AND hole_number = ?", (hcp_val, course_id, h_num))
        except (ValueError, TypeError):
            pass

    conn.commit()
    conn.close()

    return html.Span("Hole handicaps successfully saved!", style={'color': 'green'})

@callback(
    Output('reset-output-message', 'children'),
    Input('reset-tournament-provider', 'submit_n_clicks'),
    prevent_initial_call=True
)
def execute_database_wipe(submit_n_clicks):
    if submit_n_clicks:
        conn = sqlite3.connect('golf_trip.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM Scores')
        conn.commit()
        conn.close()
        return html.Span("Database wiped! All scores are back to 0.", style={'color': 'green'})
    return no_update

@callback(
    Output('scoring-ui-container', 'style'),
    Output('leaderboard-ui-container', 'style'),
    Output('scorecard-ui-container', 'style'),
    Output('session-view', 'data'),
    Input('show-leaderboard-btn', 'n_clicks'),
    Input('hide-leaderboard-btn', 'n_clicks'),
    Input('show-scorecard-btn', 'n_clicks'),
    Input('hide-scorecard-btn', 'n_clicks'),
    prevent_initial_call=True
)
def toggle_views(show_lb, hide_lb, show_sc, hide_sc):
    if not ctx.triggered_id: return no_update, no_update, no_update, no_update
    t_id = ctx.triggered_id
    if t_id == 'show-leaderboard-btn':
        return {'display': 'none'}, {'display': 'block'}, {'display': 'none'}, 'leaderboard'
    elif t_id == 'show-scorecard-btn':
        return {'display': 'none'}, {'display': 'none'}, {'display': 'block'}, 'scorecard'
    elif t_id in ['hide-leaderboard-btn', 'hide-scorecard-btn']:
        return {'display': 'block'}, {'display': 'none'}, {'display': 'none'}, 'scoring'
    return no_update, no_update, no_update, no_update

@callback(
    Output('session-group', 'data', allow_duplicate=True),
    Output('session-hole', 'data', allow_duplicate=True),
    Output('session-view', 'data', allow_duplicate=True),
    Output('setup-error', 'children', allow_duplicate=True),
    Input('start-round-btn', 'n_clicks'),
    State('group-selector', 'value'),
    prevent_initial_call=True
)
def start_round(n_clicks, selected_players):
    if not n_clicks: return no_update, no_update, no_update, no_update
    if not selected_players or len(selected_players) == 0:
        return no_update, no_update, no_update, "Please select at least one player to tee off."
    return selected_players, 1, 'scoring', ""

@callback(
    Output('session-group', 'data', allow_duplicate=True),
    Output('session-hole', 'data', allow_duplicate=True),
    Output('session-view', 'data', allow_duplicate=True),
    Input('clear-group-btn', 'n_clicks'),
    prevent_initial_call=True
)
def clear_group(n_clicks):
    if not n_clicks: return no_update, no_update, no_update
    return None, 1, 'scoring'

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

@callback(
    Output('par-display', 'children'),
    Output({'type': 'player-score', 'index': ALL}, 'value'),
    Output({'type': 'player-label', 'index': ALL}, 'children'),
    Input('course-dropdown', 'value'),
    Input('hole-dropdown', 'value'),
    State({'type': 'player-score', 'index': ALL}, 'id')
)
def update_hole_view(course_id, hole_num, player_ids):
    if not course_id or not hole_num:
        return "Par --", [None] * len(player_ids), [no_update] * len(player_ids)
        
    conn = sqlite3.connect('golf_trip.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT par, handicap FROM Course_Holes WHERE course_id = ? AND hole_number = ?", (course_id, hole_num))
        hole_data = cursor.fetchone()
        par_val, hole_hcp = hole_data if hole_data else (None, hole_num)
    except Exception:
        cursor.execute("SELECT par FROM Course_Holes WHERE course_id = ? AND hole_number = ?", (course_id, hole_num))
        hole_data = cursor.fetchone()
        par_val = hole_data[0] if hole_data else None
        hole_hcp = hole_num

    par_text = f"Par {par_val}" if par_val else "Par --"
    
    cursor.execute("SELECT player_id, strokes FROM Scores WHERE course_id = ? AND hole_number = ?", (course_id, hole_num))
    scores_dict = {row[0]: row[1] for row in cursor.fetchall()}
    
    df_players = pd.read_sql_query("SELECT player_id, name, handicap FROM Players", conn)
    conn.close()
    
    player_dict = df_players.set_index('player_id').to_dict('index')
    
    out_scores = []
    out_labels = []
    
    for pid_dict in player_ids:
        pid = pid_dict['index']
        out_scores.append(scores_dict.get(pid, None))
        
        p_data = player_dict.get(pid, {})
        base_name = p_data.get('name', 'Player')
        p_hcp = p_data.get('handicap', 0)
        
        pops = get_pops(p_hcp, hole_hcp)
        
        if pops > 0:
            out_labels.append(f"{base_name} ({pops} pop{'s' if pops > 1 else ''})")
        elif pops < 0:
            out_labels.append(f"{base_name} ({abs(pops)} giveback)")
        else:
            out_labels.append(base_name)
        
    return par_text, out_scores, out_labels

@callback(
    Output('hole-dropdown', 'value'),
    Output('output-message', 'children', allow_duplicate=True),
    Input('submit-btn', 'n_clicks'),
    Input('prev-hole-btn', 'n_clicks'),
    Input('next-hole-btn', 'n_clicks'),
    State('course-dropdown', 'value'),
    State('hole-dropdown', 'value'),
    State({'type': 'player-score', 'index': ALL}, 'id'),
    State({'type': 'player-score', 'index': ALL}, 'value'),
    prevent_initial_call=True
)
def handle_scoring_and_navigation(save_clicks, prev_clicks, next_clicks, course_id, current_hole, player_ids, player_scores):
    triggered_id = ctx.triggered_id
    if not triggered_id: return no_update, no_update
    
    inserted_count = 0
    if course_id and current_hole:
        conn = sqlite3.connect('golf_trip.db')
        cursor = conn.cursor()
        for pid_dict, score in zip(player_ids, player_scores):
            pid = pid_dict['index']
            try:
                val = int(score)
                if val > 0:
                    cursor.execute('DELETE FROM Scores WHERE player_id = ? AND course_id = ? AND hole_number = ?', (pid, course_id, current_hole))
                    cursor.execute('INSERT INTO Scores (player_id, course_id, hole_number, strokes) VALUES (?, ?, ?, ?)', (pid, course_id, current_hole, val))
                    inserted_count += 1
            except (TypeError, ValueError):
                pass
        conn.commit()
        conn.close()

    current_hole = int(current_hole) if current_hole else 1
    
    if triggered_id == 'next-hole-btn' and current_hole < 18:
        return current_hole + 1, ""
    elif triggered_id == 'prev-hole-btn' and current_hole > 1:
        return current_hole - 1, ""
    elif triggered_id == 'submit-btn':
        if inserted_count == 0:
            return no_update, html.Span("No valid scores entered.", style={'color': 'orange'})
        return no_update, html.Span(f"Saved {inserted_count} scores for Hole {current_hole}!", style={'color': 'green'})
    
    return no_update, no_update

@callback(
    Output('session-hole', 'data', allow_duplicate=True),
    Input('hole-dropdown', 'value'),
    prevent_initial_call=True
)
def save_current_hole(hole_val):
    if hole_val is None: return no_update
    return int(hole_val)

@callback(
    Output('leaderboard-container', 'children'),
    Input('course-dropdown', 'value'),
    Input('submit-btn', 'n_clicks'),
    Input('show-leaderboard-btn', 'n_clicks')
)
def render_live_leaderboard(course_id, submit_clicks, view_clicks):
    if not course_id: return html.Div()
        
    conn = sqlite3.connect('golf_trip.db')
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM Settings WHERE key = 'tournament_format'")
    format_row = cursor.fetchone()
    current_format = format_row[0] if format_row else "Stroke Play"
    
    df_scores = pd.read_sql_query("SELECT player_id, hole_number, strokes FROM Scores WHERE course_id = ?", conn, params=(course_id,))
    df_players = pd.read_sql_query("SELECT player_id, name, handicap as player_hcp FROM Players", conn)
    
    try:
        df_holes = pd.read_sql_query("SELECT hole_number, par, handicap as hole_hcp FROM Course_Holes WHERE course_id = ?", conn, params=(course_id,))
    except Exception:
        df_holes = pd.read_sql_query("SELECT hole_number, par FROM Course_Holes WHERE course_id = ?", conn, params=(course_id,))
        df_holes['hole_hcp'] = df_holes['hole_number']
        
    conn.close()
    
    if df_scores.empty: return html.Div("No scores posted yet.", style={'textAlign': 'center', 'color': '#666'})

    df = df_scores.merge(df_players, on='player_id').merge(df_holes, on='hole_number')
    df['player_hcp'] = pd.to_numeric(df['player_hcp'], errors='coerce').fillna(0)
    df['hole_hcp'] = pd.to_numeric(df['hole_hcp'], errors='coerce').fillna(18)
    
    def calculate_stats(row):
        pops = get_pops(row['player_hcp'], row['hole_hcp'])
        net_strokes = row['strokes'] - pops
        points = max(0, 2 - (net_strokes - row['par']))
        return pd.Series([net_strokes, points])
        
    df[['net_strokes', 'stableford_points']] = df.apply(calculate_stats, axis=1)
    
    lb_df = df.groupby('player_id').agg(
        name=('name', 'first'), total_strokes=('strokes', 'sum'), total_par=('par', 'sum'),
        total_net=('net_strokes', 'sum'), total_points=('stableford_points', 'sum'), holes_played=('hole_number', 'count')
    ).reset_index()
    
    lb_df['to_par_gross'] = lb_df['total_strokes'] - lb_df['total_par']
    lb_df['to_par_net'] = lb_df['total_net'] - lb_df['total_par']

    if current_format == 'Stableford':
        lb_df = lb_df.sort_values(by=['total_points', 'to_par_gross'], ascending=[False, True])
        score_col, header_title = 'total_points', "Points"
    elif current_format == 'Net Stroke Play':
        lb_df = lb_df.sort_values(by=['to_par_net', 'to_par_gross'], ascending=[True, True])
        score_col, header_title = 'to_par_net', "Net To Par"
    else:
        lb_df = lb_df.sort_values(by=['to_par_gross', 'total_points'], ascending=[True, False])
        score_col, header_title = 'to_par_gross', "To Par"

    table_rows = [html.Tr(style={'backgroundColor': '#343a40', 'color': 'white', 'textAlign': 'left'}, children=[
        html.Th("Pos", style={'padding': '10px'}), html.Th("Player", style={'padding': '10px'}),
        html.Th(header_title, style={'padding': '10px', 'textAlign': 'center'}), html.Th("Thru", style={'padding': '10px', 'textAlign': 'center'})
    ])]
    
    for index, (_, row) in enumerate(lb_df.iterrows()):
        score_val = row[score_col]
        if current_format == 'Stableford':
            display_score, score_color = str(int(score_val)), "black"
        else:
            if score_val == 0: display_score, score_color = "E", "black"
            elif score_val > 0: display_score, score_color = f"+{int(score_val)}", "red"
            else: display_score, score_color = f"{int(score_val)}", "green"
                
        row_color = "#f9f9f9" if index % 2 == 0 else "white"
        table_rows.append(html.Tr(style={'backgroundColor': row_color, 'borderBottom': '1px solid #ddd'}, children=[
            html.Td(f"{index + 1}", style={'padding': '10px', 'fontWeight': 'bold'}), html.Td(row['name'], style={'padding': '10px'}),
            html.Td(display_score, style={'padding': '10px', 'textAlign': 'center', 'color': score_color, 'fontWeight': 'bold'}),
            html.Td(row['holes_played'], style={'padding': '10px', 'textAlign': 'center', 'color': '#666'})
        ]))

    return html.Div(style={'marginTop': '10px'}, children=[
        html.H3(f"Live Leaderboard ({current_format})", style={'textAlign': 'center', 'marginBottom': '15px'}),
        html.Table(style={'width': '100%', 'borderCollapse': 'collapse', 'boxShadow': '0 2px 5px rgba(0,0,0,0.1)'}, children=table_rows)
    ])

@callback(
    Output('scorecard-container', 'children'),
    Input('course-dropdown', 'value'),
    Input('submit-btn', 'n_clicks'),
    Input('show-scorecard-btn', 'n_clicks')
)
def render_live_scorecard(course_id, submit_clicks, view_clicks):
    if not course_id: return html.Div()
        
    conn = sqlite3.connect('golf_trip.db')
    
    df_players = pd.read_sql_query("SELECT player_id, name, handicap as player_hcp FROM Players", conn)
    df_scores = pd.read_sql_query("SELECT player_id, hole_number, strokes FROM Scores WHERE course_id = ?", conn, params=(course_id,))
    
    try:
        df_holes = pd.read_sql_query("SELECT hole_number, par, handicap as hole_hcp FROM Course_Holes WHERE course_id = ? ORDER BY hole_number", conn, params=(course_id,))
    except Exception:
        df_holes = pd.read_sql_query("SELECT hole_number, par FROM Course_Holes WHERE course_id = ? ORDER BY hole_number", conn, params=(course_id,))
        df_holes['hole_hcp'] = df_holes['hole_number']
        
    conn.close()
    
    if df_players.empty or df_holes.empty: return html.Div()
    
    header_cols = [html.Th("HOLE", style={'padding': '8px', 'minWidth': '80px', 'backgroundColor': '#343a40', 'color': 'white'})]
    par_cols = [html.Th("PAR", style={'padding': '8px', 'backgroundColor': '#f0f0f0'})]
    hcp_cols = [html.Th("HCP", style={'padding': '8px', 'backgroundColor': '#f0f0f0'})]
    
    out_par, in_par = 0, 0
    hole_data_dict = df_holes.set_index('hole_number').to_dict('index')
    
    def add_summary_col(h_list, p_list, hc_list, label, par_val):
        h_list.append(html.Th(label, style={'padding': '8px', 'backgroundColor': '#343a40', 'color': 'white'}))
        p_list.append(html.Th(par_val, style={'padding': '8px', 'backgroundColor': '#e9ecef'}))
        hc_list.append(html.Th("", style={'padding': '8px', 'backgroundColor': '#e9ecef'}))

    for i in range(1, 10):
        h_data = hole_data_dict.get(i, {'par': '-', 'hole_hcp': '-'})
        if h_data['par'] != '-': out_par += int(h_data['par'])
        header_cols.append(html.Th(str(i), style={'padding': '8px', 'backgroundColor': '#343a40', 'color': 'white'}))
        par_cols.append(html.Th(h_data['par'], style={'padding': '8px', 'backgroundColor': '#f0f0f0'}))
        hcp_cols.append(html.Th(h_data['hole_hcp'], style={'padding': '8px', 'backgroundColor': '#f0f0f0', 'fontSize': '12px'}))
    
    add_summary_col(header_cols, par_cols, hcp_cols, "OUT", out_par)
    
    for i in range(10, 19):
        h_data = hole_data_dict.get(i, {'par': '-', 'hole_hcp': '-'})
        if h_data['par'] != '-': in_par += int(h_data['par'])
        header_cols.append(html.Th(str(i), style={'padding': '8px', 'backgroundColor': '#343a40', 'color': 'white'}))
        par_cols.append(html.Th(h_data['par'], style={'padding': '8px', 'backgroundColor': '#f0f0f0'}))
        hcp_cols.append(html.Th(h_data['hole_hcp'], style={'padding': '8px', 'backgroundColor': '#f0f0f0', 'fontSize': '12px'}))
        
    add_summary_col(header_cols, par_cols, hcp_cols, "IN", in_par)
    add_summary_col(header_cols, par_cols, hcp_cols, "TOT", out_par + in_par)

    table_rows = [
        html.Tr(header_cols),
        html.Tr(par_cols, style={'borderBottom': '1px solid #ddd'}),
        html.Tr(hcp_cols, style={'borderBottom': '2px solid #343a40'})
    ]

    for _, player in df_players.iterrows():
        p_id = player['player_id']
        p_name = player['name']
        p_hcp = player['player_hcp']
        
        p_scores = df_scores[df_scores['player_id'] == p_id].set_index('hole_number')['strokes'].to_dict()
        p_cols = [html.Td(html.Strong(p_name), style={'padding': '8px', 'borderRight': '1px solid #ddd'})]
        
        out_score, in_score = 0, 0
        
        def process_hole_score(hole_num):
            h_data = hole_data_dict.get(hole_num, {'hole_hcp': 18})
            pops = get_pops(p_hcp, h_data['hole_hcp'])
            dots = get_pops_symbol(pops)
            
            score = p_scores.get(hole_num)
            if score:
                display = html.Span([str(int(score)), html.Span(dots, style={'color': '#D32F2F'})])
                return int(score), html.Td(display, style={'padding': '8px', 'textAlign': 'center', 'border': '1px solid #eee'})
            else:
                return 0, html.Td(html.Span(dots, style={'color': '#ccc'}), style={'padding': '8px', 'textAlign': 'center', 'border': '1px solid #eee'})

        for i in range(1, 10):
            score, ui_cell = process_hole_score(i)
            out_score += score
            p_cols.append(ui_cell)
            
        p_cols.append(html.Td(str(out_score) if out_score > 0 else "-", style={'padding': '8px', 'textAlign': 'center', 'fontWeight': 'bold', 'backgroundColor': '#f9f9f9'}))
        
        for i in range(10, 19):
            score, ui_cell = process_hole_score(i)
            in_score += score
            p_cols.append(ui_cell)
            
        p_cols.append(html.Td(str(in_score) if in_score > 0 else "-", style={'padding': '8px', 'textAlign': 'center', 'fontWeight': 'bold', 'backgroundColor': '#f9f9f9'}))
        p_cols.append(html.Td(str(out_score + in_score) if (out_score + in_score) > 0 else "-", style={'padding': '8px', 'textAlign': 'center', 'fontWeight': 'bold', 'backgroundColor': '#e2e3e5'}))
        
        table_rows.append(html.Tr(p_cols, style={'borderBottom': '1px solid #ddd'}))

    return html.Div([
        html.H3("Live Scorecard", style={'textAlign': 'center', 'marginBottom': '10px'}),
        html.Table(style={'borderCollapse': 'collapse', 'width': '100%', 'textAlign': 'center'}, children=table_rows)
    ])

if __name__ == '__main__':
    app.run(debug=True, port=8885)
