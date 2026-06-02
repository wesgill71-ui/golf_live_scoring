import sqlite3

def setup_complete_database():
    # Connect to database file
    conn = sqlite3.connect('golf_trip.db')
    cursor = conn.cursor()

    print("Creating database tables...")
    
    # 1. Create Players Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Players (
        player_id INTEGER PRIMARY KEY,
        name TEXT,
        handicap REAL
    )
    ''')

    # 2. Create Courses Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Courses (
        course_id INTEGER PRIMARY KEY,
        course_name TEXT,
        par_total INTEGER
    )
    ''')

    # 3. Create Course_Holes Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Course_Holes (
        hole_id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER,
        hole_number INTEGER,
        par INTEGER,
        stroke_index INTEGER,
        FOREIGN KEY(course_id) REFERENCES Courses(course_id)
    )
    ''')

    # 4. Create Scores Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Scores (
        score_id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id INTEGER,
        course_id INTEGER,
        hole_number INTEGER,
        strokes INTEGER,
        FOREIGN KEY(player_id) REFERENCES Players(player_id),
        FOREIGN KEY(course_id) REFERENCES Courses(course_id)
    )
    ''')

    # --- INSERT PLAYERS ---
    print("Populating player profiles...")
    players_data = [
        (1, 'Wes', -2.0), # Storing + handicaps as negative numbers for straightforward net score logic
        (2, 'Matt', 10.0),
        (3, 'Jim', 15.0)
    ]
    cursor.executemany('INSERT OR IGNORE INTO Players VALUES (?, ?, ?)', players_data)

    # --- INSERT COURSES ---
    print("Populating course details...")
    courses_data = [
        (1, "Oak Bay", 72),  # Update "Course 1" to actual name if desired
        (2, "The Rock", 71),
        (3, "South Muskoka", 71)   # Update "Course 3" to actual name if desired
    ]
    cursor.executemany('INSERT OR IGNORE INTO Courses VALUES (?, ?, ?)', courses_data)

    # --- INSERT HOLE DATA ---
    print("Populating hole-by-hole scorecards...")
    
    # Clear out any existing hole records to prevent duplication if re-run
    cursor.execute('DELETE FROM Course_Holes')

    all_holes = [
        # === COURSE 1 ===
        # Front 9
        (1, 1, 4, 11), (1, 2, 4, 3), (1, 3, 4, 9),
        (1, 4, 4, 13), (1, 5, 4, 17), (1, 6, 3, 5),
        (1, 7, 5, 15), (1, 8, 3, 7), (1, 9, 5, 1),
        # Back 9
        (1, 10, 5, 14), (1, 11, 3, 8), (1, 12, 4, 6),
        (1, 13, 3, 10), (1, 14, 4, 4), (1, 15, 4, 2),
        (1, 16, 4, 16), (1, 17, 4, 12), (1, 18, 5, 18),

        # === COURSE 2: THE ROCK ===
        # Front 9
        (2, 1, 5, 7), (2, 2, 3, 15), (2, 3, 4, 5),
        (2, 4, 4, 11), (2, 5, 3, 17), (2, 6, 4, 3),
        (2, 7, 4, 9), (2, 8, 3, 13), (2, 9, 5, 1),
        # Back 9
        (2, 10, 4, 10), (2, 11, 3, 16), (2, 12, 4, 8),
        (2, 13, 4, 6), (2, 14, 4, 14), (2, 15, 4, 12),
        (2, 16, 5, 2), (2, 17, 3, 18), (2, 18, 5, 4),

        # === COURSE 3 ===
        # Front 9
        (3, 1, 4, 5), (3, 2, 4, 11), (3, 3, 4, 1),
        (3, 4, 3, 15), (3, 5, 5, 7), (3, 6, 4, 3),
        (3, 7, 4, 13), (3, 8, 3, 17), (3, 9, 4, 9),
        # Back 9
        (3, 10, 4, 10), (3, 11, 5, 14), (3, 12, 3, 18),
        (3, 13, 4, 2), (3, 14, 4, 6), (3, 15, 3, 16),
        (3, 16, 5, 12), (3, 17, 4, 4), (3, 18, 4, 8)
    ]

    cursor.executemany('''
        INSERT INTO Course_Holes (course_id, hole_number, par, stroke_index) 
        VALUES (?, ?, ?, ?)
    ''', all_holes)

    conn.commit()
    conn.close()
    print("\nInitialization complete! 'golf_trip.db' is fully configured and ready.")

if __name__ == '__main__':
    setup_complete_database()
