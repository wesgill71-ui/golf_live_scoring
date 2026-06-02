from dash import Dash, html, dcc, Input, Output, State, callback
import sqlite3
import pandas as pd

app = Dash(__name__, suppress_callback_exceptions=True)
server = app.server

# --- Ensure Settings Table Exists & Initialize ---
conn = sqlite3.connect('golf_trip.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS Settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
''')
# Default to Course 1 if no active course is set yet
cursor.execute("INSERT OR IGNORE INTO Settings (key, value) VALUES ('active_course_id', '1')")
conn.commit()
conn.close()

# --- Helper function ---
def get_options(query, label_col, value_col):
    conn = sqlite3.connect('golf_trip.db')
    df = pd.read_sql_query(query, conn)
    conn.close()
    return [{'label': row[label_col], 'value': row[value_col]} for _, row in df.iterrows()]

player_options = get_options("SELECT * FROM Players", 'name', 'player_id')
course_options = get_options("SELECT * FROM Courses", 'course_name', 'course_id')
hole_options = [{'label': f'Hole {i}', 'value': i} for i in range(1, 19)]

# --- Layout 1: The Public Scoring Screen ---
scoring_layout = html.Div(style={'fontFamily': 'system-ui, sans-serif', 'maxWidth': '500px', 'margin': 'auto', 'padding': '20px'}, children=[
    html.H1("Live Scoring", style={'textAlign': 'center'}),
    
    html.Div([
        html.Label("Player"),
        dcc.Dropdown(id='player-dropdown', options=player_options, placeholder="Select Player", style={'marginBottom': '15px'}),
        
        html.Label("Course"),
        dcc.Dropdown(id='course-dropdown', options=course_options, placeholder="Select Course", style={'marginBottom': '15px'}),
        
        html.Label("Hole"),
        dcc.Dropdown(id='hole-dropdown', options=hole_options, placeholder="Select Hole", style={'marginBottom': '15px'}),
        
        html.Label("Strokes"),
        dcc.Input(id='stroke-input', type='number', placeholder="0", style={'width': '100%', 'padding': '10px', 'marginBottom': '20px', 'fontSize': '18px'}),
        
        html.Button('Submit Score', id='submit-btn', n_clicks=0, style={
            'width': '100%', 'padding': '15px', 'backgroundColor': '#007BFF', 'color': 'white',
            'border': 'none', 'borderRadius': '5px', 'fontSize': '18px', 'cursor': 'pointer'
        }),
    ]),
    
    html.Div(id='output-message', style={'marginTop': '20px', 'textAlign': 'center', 'fontWeight': 'bold'}),
    
    # Subtle admin navigation link
    html.A("Commissioner Setup", href="/commissioner", style={'display': 'block', 'textAlign': 'center', 'marginTop': '40px', 'fontSize': '12px', 'color': '#ccc', 'textDecoration': 'none'})
])

# --- Layout 2: The Hidden Commissioner Screen ---
admin_layout = html.Div(style={'fontFamily': 'system-ui, sans-serif', 'maxWidth': '500px', 'margin': 'auto', 'padding': '20px'}, children=[
    html.H1("Commissioner Dashboard", style={'textAlign': 'center', 'color': '#D32F2F'}),
    
    html.Div(style={'backgroundColor': '#f9f9f9', 'padding': '20px', 'borderRadius': '8px', 'border': '1px solid #eee', 'marginBottom': '20px'}, children=[
        html.H3("Set Active Round", style={'marginTop': '0'}),
        html.P("Select the course currently being played. This will automatically lock it in as the default choice on everyone's scoring screen.", style={'fontSize': '14px', 'color': '#666'}),
        
        dcc.Dropdown(id='admin-course-dropdown', options=course_options, placeholder="Select Active Course", style={'marginBottom': '15px'}),
        
        html.Button('Update Active Course', id='set-active-course-btn', n_clicks=0, style={
            'width': '100%', 'padding': '12px', 'backgroundColor': '#D32F2F', 'color': 'white',
            'border': 'none', 'borderRadius': '5px', 'fontSize': '16px', 'cursor': 'pointer'
        }),
        html.Div(id='admin-output-message', style={'marginTop': '15px', 'textAlign': 'center', 'fontWeight': 'bold'})
    ]),
    
    html.A("← Back to Scoring", href="/", style={'display': 'block', 'textAlign': 'center', 'marginTop': '30px', 'textDecoration': 'none', 'color': '#007BFF', 'fontWeight': 'bold'})
])

# --- Main App Container (Handles the Routing) ---
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])

# --- Back-End Logic ---

# 1. Page Routing
@callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    if pathname == '/commissioner':
        return admin_layout
    return scoring_layout

# 2. Dynamic Default Course Loader (Runs when the scoring page loads)
@callback(
    Output('course-dropdown', 'value'),
    Input('url', 'pathname')
)
def set_default_course(pathname):
    if pathname == '/':
        conn = sqlite3.connect('golf_trip.db')
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM Settings WHERE key = 'active_course_id'")
        row = cursor.fetchone()
        conn.close()
        if row:
            return int(row[0])
    return None

# 3. Save Active Course Selection (Admin Panel)
@callback(
    Output('admin-output-message', 'children'),
    Input('set-active-course-btn', 'n_clicks'),
    State('admin-course-dropdown', 'value'),
    prevent_initial_call=True
)
def update_active_course(n_clicks, course_id):
    if not course_id:
        return html.Span("Please select a course first.", style={'color': 'red'})
    
    conn = sqlite3.connect('golf_trip.db')
    cursor = conn.cursor()
    # REPLACE INTO handles insert or update smoothly if the key already exists
    cursor.execute("REPLACE INTO Settings (key, value) VALUES ('active_course_id', ?)", (str(course_id),))
    conn.commit()
    conn.close()
    
    return html.Span("Active course updated successfully!", style={'color': 'green'})

# 4. Save Score Input (Public Page)
@callback(
    Output('output-message', 'children'),
    Input('submit-btn', 'n_clicks'),
    State('player-dropdown', 'value'),
    State('course-dropdown', 'value'),
    State('hole-dropdown', 'value'),
    State('stroke-input', 'value'),
    prevent_initial_call=True
)
def save_score(n_clicks, player_id, course_id, hole, strokes):
    if not all([player_id, course_id, hole, strokes]):
        return html.Span("Please fill out all fields.", style={'color': 'red'})
    
    conn = sqlite3.connect('golf_trip.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM Scores WHERE player_id = ? AND course_id = ? AND hole_number = ?', (player_id, course_id, hole))
    cursor.execute('INSERT INTO Scores (player_id, course_id, hole_number, strokes) VALUES (?, ?, ?, ?)', (player_id, course_id, hole, strokes))
    conn.commit()
    conn.close()
    
    return html.Span(f"Score saved! {strokes} on Hole {hole}.", style={'color': 'green'})

if __name__ == '__main__':
    app.run(debug=True, port=8888)
