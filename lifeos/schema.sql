CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS goal_history (effective_date TEXT PRIMARY KEY, values_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS problems (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, platform TEXT DEFAULT '', url TEXT DEFAULT '',
 topic TEXT DEFAULT '', subtopic TEXT DEFAULT '', difficulty TEXT DEFAULT 'Medium',
 attempt_date TEXT NOT NULL, solved_date TEXT DEFAULT '', status TEXT DEFAULT 'Attempted',
 revision_date TEXT DEFAULT '', minutes REAL DEFAULT 0 CHECK(minutes>=0), attempts INTEGER DEFAULT 1 CHECK(attempts>=1),
 assistance TEXT DEFAULT 'Independent', approach TEXT DEFAULT '', time_complexity TEXT DEFAULT '',
 space_complexity TEXT DEFAULT '', notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS solutions (
 id INTEGER PRIMARY KEY, problem_id INTEGER NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
 title TEXT NOT NULL, language TEXT DEFAULT 'Python', created_date TEXT NOT NULL, code TEXT DEFAULT '', notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS paths (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '', goal TEXT DEFAULT '',
 priority TEXT DEFAULT 'Medium', target_minutes REAL DEFAULT 0, target_period TEXT DEFAULT 'Weekly',
 deadline TEXT DEFAULT '', status TEXT DEFAULT 'Learning');
CREATE TABLE IF NOT EXISTS concepts (
 id INTEGER PRIMARY KEY, path_id INTEGER NOT NULL REFERENCES paths(id) ON DELETE CASCADE,
 name TEXT NOT NULL, topic TEXT DEFAULT '', subtopic TEXT DEFAULT '', prerequisites TEXT DEFAULT '',
 status TEXT DEFAULT 'Not started', understanding INTEGER DEFAULT 0 CHECK(understanding BETWEEN 0 AND 5),
 revision_date TEXT DEFAULT '', notes TEXT DEFAULT '', exercises TEXT DEFAULT '', code TEXT DEFAULT '',
 quiz_score REAL, quiz_max REAL);
CREATE TABLE IF NOT EXISTS study_sessions (
 id INTEGER PRIMARY KEY, path_id INTEGER NOT NULL REFERENCES paths(id) ON DELETE CASCADE,
 concept_id INTEGER REFERENCES concepts(id) ON DELETE SET NULL, date TEXT NOT NULL,
 minutes REAL NOT NULL CHECK(minutes>=0), planned_minutes REAL DEFAULT 0 CHECK(planned_minutes>=0), notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS workout_routines (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, split TEXT DEFAULT 'Custom', location TEXT DEFAULT 'Home',
 days_per_week INTEGER DEFAULT 3 CHECK(days_per_week BETWEEN 0 AND 7), active TEXT DEFAULT 'Yes', notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS workout_days (
 id INTEGER PRIMARY KEY, routine_id INTEGER NOT NULL REFERENCES workout_routines(id) ON DELETE CASCADE,
 weekday TEXT NOT NULL, name TEXT NOT NULL, muscles TEXT DEFAULT '', recovery TEXT DEFAULT 'No', notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS planned_exercises (
 id INTEGER PRIMARY KEY, day_id INTEGER NOT NULL REFERENCES workout_days(id) ON DELETE CASCADE,
 exercise TEXT NOT NULL, equipment TEXT DEFAULT '', sets INTEGER DEFAULT 3, reps INTEGER DEFAULT 10,
 weight_kg REAL DEFAULT 0, duration_min REAL DEFAULT 0, distance_km REAL DEFAULT 0, notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS workouts (
 id INTEGER PRIMARY KEY, routine_id INTEGER REFERENCES workout_routines(id) ON DELETE SET NULL,
 name TEXT NOT NULL, date TEXT NOT NULL, status TEXT DEFAULT 'Planned', muscles TEXT DEFAULT '', notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS exercise_logs (
 id INTEGER PRIMARY KEY, workout_id INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
 exercise TEXT NOT NULL, equipment TEXT DEFAULT '', sets INTEGER DEFAULT 3, reps INTEGER DEFAULT 10,
 weight_kg REAL DEFAULT 0, duration_min REAL DEFAULT 0, distance_km REAL DEFAULT 0, notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS foods (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, preparation TEXT DEFAULT 'Cooked', source TEXT NOT NULL,
 approximate TEXT DEFAULT 'Yes', serving_g REAL, cup_g REAL, density REAL,
 calories REAL NOT NULL, protein REAL NOT NULL, carbs REAL NOT NULL, fat REAL NOT NULL,
 fibre REAL, sugar REAL, calcium_mg REAL, iron_mg REAL, sodium_mg REAL, potassium_mg REAL,
 notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS food_logs (
 id INTEGER PRIMARY KEY, food_id INTEGER REFERENCES foods(id) ON DELETE SET NULL,
 name TEXT NOT NULL, date TEXT NOT NULL, meal TEXT DEFAULT 'Breakfast', quantity REAL NOT NULL,
 unit TEXT NOT NULL, grams REAL NOT NULL, calories REAL NOT NULL, protein REAL NOT NULL,
 carbs REAL NOT NULL, fat REAL NOT NULL, fibre REAL, sugar REAL, calcium_mg REAL, iron_mg REAL,
 sodium_mg REAL, potassium_mg REAL, source TEXT NOT NULL, approximate TEXT DEFAULT 'Yes', notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS water_logs (id INTEGER PRIMARY KEY, date TEXT NOT NULL, ml REAL NOT NULL CHECK(ml>0), notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS measurements (
 id INTEGER PRIMARY KEY, date TEXT NOT NULL, weight_kg REAL NOT NULL CHECK(weight_kg>0),
 waist_cm REAL, chest_cm REAL, hips_cm REAL, notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS daily_routines (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, weekdays TEXT DEFAULT 'Monday,Tuesday,Wednesday,Thursday,Friday',
 time TEXT DEFAULT '09:00', kind TEXT DEFAULT 'Personal', planned_minutes REAL DEFAULT 25,
 priority TEXT DEFAULT 'Medium', active TEXT DEFAULT 'Yes');
CREATE TABLE IF NOT EXISTS tasks (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, date TEXT NOT NULL, deadline TEXT DEFAULT '',
 priority TEXT DEFAULT 'Medium', status TEXT DEFAULT 'To do', planned_minutes REAL DEFAULT 25,
 actual_minutes REAL DEFAULT 0, kind TEXT DEFAULT 'Personal', notes TEXT DEFAULT '',
 routine_id INTEGER REFERENCES daily_routines(id) ON DELETE SET NULL, UNIQUE(routine_id,date));
CREATE TABLE IF NOT EXISTS focus_sessions (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, date TEXT NOT NULL, planned_minutes REAL NOT NULL,
 actual_minutes REAL DEFAULT 0, status TEXT DEFAULT 'Completed', started_at TEXT DEFAULT '',
 remaining_seconds REAL DEFAULT 0, notes TEXT DEFAULT '');
CREATE INDEX IF NOT EXISTS problems_date ON problems(solved_date);
CREATE INDEX IF NOT EXISTS study_date ON study_sessions(date);
CREATE INDEX IF NOT EXISTS food_date ON food_logs(date);
CREATE INDEX IF NOT EXISTS workouts_date ON workouts(date);
CREATE INDEX IF NOT EXISTS tasks_date ON tasks(date);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_timer ON focus_sessions((1)) WHERE status IN ('Running','Paused');
