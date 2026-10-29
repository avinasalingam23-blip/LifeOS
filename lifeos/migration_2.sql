-- Additive fitness coaching metadata. Existing columns and rows are retained.
ALTER TABLE planned_exercises ADD COLUMN library_key TEXT NOT NULL DEFAULT '';
ALTER TABLE planned_exercises ADD COLUMN position INTEGER NOT NULL DEFAULT 0;
ALTER TABLE planned_exercises ADD COLUMN rest_seconds INTEGER NOT NULL DEFAULT 60;
ALTER TABLE planned_exercises ADD COLUMN tempo TEXT NOT NULL DEFAULT '';
ALTER TABLE planned_exercises ADD COLUMN resistance TEXT NOT NULL DEFAULT '';
ALTER TABLE exercise_logs ADD COLUMN library_key TEXT NOT NULL DEFAULT '';
ALTER TABLE exercise_logs ADD COLUMN position INTEGER NOT NULL DEFAULT 0;
ALTER TABLE exercise_logs ADD COLUMN rest_seconds INTEGER NOT NULL DEFAULT 60;
ALTER TABLE exercise_logs ADD COLUMN tempo TEXT NOT NULL DEFAULT '';
ALTER TABLE exercise_logs ADD COLUMN resistance TEXT NOT NULL DEFAULT '';
ALTER TABLE exercise_logs ADD COLUMN completion TEXT NOT NULL DEFAULT 'Legacy';
ALTER TABLE exercise_logs ADD COLUMN skip_reason TEXT NOT NULL DEFAULT '';
ALTER TABLE exercise_logs ADD COLUMN target_sets INTEGER NOT NULL DEFAULT 0;
ALTER TABLE exercise_logs ADD COLUMN target_reps INTEGER NOT NULL DEFAULT 0;
ALTER TABLE exercise_logs ADD COLUMN target_duration REAL NOT NULL DEFAULT 0;
ALTER TABLE measurements ADD COLUMN arm_cm REAL;
ALTER TABLE measurements ADD COLUMN thigh_cm REAL;
ALTER TABLE measurements ADD COLUMN photo_path TEXT NOT NULL DEFAULT '';
ALTER TABLE measurements ADD COLUMN sleep_hours REAL;
ALTER TABLE measurements ADD COLUMN energy INTEGER;
ALTER TABLE measurements ADD COLUMN soreness INTEGER;
ALTER TABLE measurements ADD COLUMN fatigue INTEGER;
ALTER TABLE measurements ADD COLUMN pain TEXT NOT NULL DEFAULT '';
CREATE TABLE fitness_preferences(id INTEGER PRIMARY KEY CHECK(id=1),values_json TEXT NOT NULL);
CREATE TABLE fitness_custom_exercises(key TEXT PRIMARY KEY,definition TEXT NOT NULL);
CREATE TABLE fitness_sessions(
 workout_id INTEGER PRIMARY KEY REFERENCES workouts(id) ON DELETE CASCADE,
 day_id INTEGER REFERENCES workout_days(id) ON DELETE SET NULL,
 session_date TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT NOT NULL DEFAULT '',
 readiness_json TEXT NOT NULL,review TEXT NOT NULL DEFAULT '',recovery_option TEXT NOT NULL DEFAULT 'Normal',
 UNIQUE(day_id,session_date));
CREATE TABLE fitness_sets(
 id INTEGER PRIMARY KEY,exercise_log_id INTEGER NOT NULL REFERENCES exercise_logs(id) ON DELETE CASCADE,
 set_no INTEGER NOT NULL CHECK(set_no>0),reps INTEGER NOT NULL CHECK(reps>=0),
 weight_kg REAL NOT NULL DEFAULT 0 CHECK(weight_kg>=0),resistance TEXT NOT NULL DEFAULT '',
 variation TEXT NOT NULL DEFAULT '',rir REAL CHECK(rir BETWEEN 0 AND 10),
 duration_min REAL NOT NULL DEFAULT 0 CHECK(duration_min>=0),
 distance_km REAL NOT NULL DEFAULT 0 CHECK(distance_km>=0),notes TEXT NOT NULL DEFAULT '',
 UNIQUE(exercise_log_id,set_no));
CREATE INDEX fitness_sets_exercise ON fitness_sets(exercise_log_id);
CREATE INDEX fitness_sessions_date ON fitness_sessions(session_date);
