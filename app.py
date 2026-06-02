from dash import Dash, html, dcc, Input, Output, State, callback
import sqlite3
import pandas as pd

app = Dash(__name__)
server = app.server # Required for Railway

# --- Helper function to pull database data ---
def get_options(query, label_col, value_col):
    conn = sqlite3.connect('golf_trip.db')
    df = pd.read_sql_query(query, conn)
    conn.close()
    return [{'label': row[label_col], 'value': row[value_col]} for _, row in df.iterrows()]

# Pull our initial dropdown lists
player_options = get_options("SELECT * FROM Players", 'name', 'player_id')
course_options = get_options("SELECT * FROM Courses", 'course_name', 'course_id')
hole_options = [{'label': f'Hole {i}', 'value': i} for i in range(1, 19)]

# --- Front-End Layout ---
app.layout = html.Div(style={'fontFamily': 'system-ui, sans-serif', 'maxWidth': '500px', 'margin': 'auto', 'padding': '20px'}, children=[
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
    
    html.Div(id='output-message', style={'marginTop': '20px', 'textAlign': 'center', 'fontWeight': 'bold'})
])

# --- Back-End Logic ---
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
    
    # Delete any existing score for this exact player/course/hole to prevent duplicates if someone makes a correction
    cursor.execute('''
        DELETE FROM Scores 
        WHERE player_id = ? AND course_id = ? AND hole_number = ?
    ''', (player_id, course_id, hole))
    
    # Insert the new score
    cursor.execute('''
        INSERT INTO Scores (player_id, course_id, hole_number, strokes)
        VALUES (?, ?, ?, ?)
    ''', (player_id, course_id, hole, strokes))
    
    conn.commit()
    conn.close()
    
    return html.Span(f"Score saved! {strokes} on Hole {hole}.", style={'color': 'green'})

if __name__ == '__main__':
    app.run(debug=True)
