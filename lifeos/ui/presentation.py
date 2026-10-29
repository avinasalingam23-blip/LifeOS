"""Small read-only projections for everyday lists; entity metadata stays complete."""
from datetime import date,timedelta

COLUMNS={
    'problems':('name','topic','difficulty','status'),
    'solutions':('title','problem_id','language','created_date'),
    'paths':('name','priority','deadline','status'),
    'concepts':('name','path_id','status','understanding'),
    'study_sessions':('date','path_id','minutes'),
    'workout_routines':('name','split','days_per_week','active'),
    'workout_days':('weekday','name','recovery'),
    'planned_exercises':('exercise','sets','reps','weight_kg'),
    'workouts':('date','name','status'),
    'exercise_logs':('exercise','workout_id','sets','reps'),
    'food_logs':('name','meal','date','calories'),
    'foods':('name','preparation','calories','protein'),
    'water_logs':('date','ml'),
    'measurements':('date','weight_kg','waist_cm'),
    'tasks':('title','date','priority','status'),
    'daily_routines':('title','time','active'),
    'focus_sessions':('title','date','actual_minutes','status'),
}
HEADINGS={'minutes':'Study (min)','actual_minutes':'Actual (min)','created_date':'Date',
          'weight_kg':'Weight (kg)','waist_cm':'Waist (cm)','calories':'kcal',
          'protein':'Protein (g)','days_per_week':'Days / week','recovery':'Recovery',
          'understanding':'Confidence','ml':'Water (ml)','path_id':'Subject',
          'problem_id':'Problem','workout_id':'Workout','time':'Reminder'}
PRIMARY={'problems':'Add problem','solutions':'Add version','paths':'Add Subject','concepts':'Add concept',
         'study_sessions':'Log study','workout_routines':'Add routine','workout_days':'Add day',
         'planned_exercises':'Add exercise','workouts':'Log workout','exercise_logs':'Log exercise',
         'food_logs':'Add food','foods':'Add food','water_logs':'Log water','measurements':'Add measurement',
         'tasks':'Add task','daily_routines':'Add routine','focus_sessions':'Log focus'}

def subject_progress(service,subject,today=None):
    """Actual dated study vs target, or self-assessed concept understanding."""
    today=today or date.today()
    start=today if subject['target_period']=='Daily' else today-timedelta(days=6)
    minutes=service.db.one('SELECT COALESCE(SUM(minutes),0) value FROM study_sessions WHERE path_id=? AND date BETWEEN ? AND ?',
                         (subject['id'],start.isoformat(),today.isoformat()))['value']
    concepts=service.list('concepts',filters={'path_id':subject['id']})
    target=subject['target_minutes']
    if target:
        return min(1,minutes/target),f"{minutes:g} / {target:g} min · "+('today' if subject['target_period']=='Daily' else 'last 7 days')
    ratio=sum(c['understanding'] for c in concepts)/(5*len(concepts)) if concepts else 0
    return ratio,(f'{sum(c["status"]=="Understood" for c in concepts)} / {len(concepts)} concepts understood' if concepts else 'No concepts yet')

def compact_value(key,value,row):
    if value is None or value=='':
        return '—'
    if key=='understanding':
        return f'{value:g} / 5'
    if isinstance(value,float):
        return f'{value:,.1f}'.removesuffix('.0')
    if key=='name' and 'quantity' in row:
        return f"{value} · {row['quantity']:g} {row['unit']}"
    return str(value)
