"""Shared form metadata: UI and service validation use the same domain rules."""
from dataclasses import dataclass, field
from datetime import date

@dataclass
class Field:
    key: str
    label: str
    kind: str = 'text'
    default: object = ''
    required: bool = False
    choices: tuple = ()
    ref: str = ''
    minimum: float = 0
    maximum: float | None = None
    help: str = ''

def text(key, label, required=False, default='', **kw):
    return Field(key, label, default=default, required=required, **kw)
def choice(key, label, values, default=None):
    return Field(key, label, 'choice', default or values[0], choices=tuple(values))
def num(key, label, default=0, required=True, minimum=0, maximum=None, integer=False):
    return Field(key, label, 'int' if integer else 'number', default, required, minimum=minimum, maximum=maximum)
def day(key='date', label='Date', required=True):
    return Field(key, label, 'date', 'TODAY' if required else '', required, help='YYYY-MM-DD')
def memo(key, label, code=False):
    return Field(key, label, 'code' if code else 'memo')
def ref(key, label, table, required=True):
    return Field(key, label, 'ref', '', required, ref=table)

@dataclass
class Entity:
    title: str
    fields: list[Field]
    columns: tuple[str, ...]
    hint: str = ''
    readonly: bool = False

LEARNING_STATUS = ['Not started', 'Learning', 'Needs practice', 'Understood', 'Revision due']
PRIORITY = ['High', 'Medium', 'Low']
WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
NUTRIENTS = ('calories', 'protein', 'carbs', 'fat', 'fibre', 'sugar', 'calcium_mg', 'iron_mg', 'sodium_mg', 'potassium_mg')
EXERCISE_FIELDS = [text('exercise','Exercise',True), text('equipment','Equipment'),
    num('sets','Sets',3,integer=True), num('reps','Reps per set',10,integer=True),
    num('weight_kg','Weight (kg)'), num('duration_min','Duration (minutes)'),
    num('distance_km','Distance (km)'), memo('notes','Notes / individual sets')]
ENTITIES = {
 'problems': Entity('Problems', [
    text('name','Problem name',True),text('platform','Platform'),text('url','Problem URL'),
    text('topic','Topic'),text('subtopic','Subtopic'),choice('difficulty','Difficulty',['Easy','Medium','Hard']),
    day('attempt_date','Latest attempt date'),day('solved_date','Solution date',False),
    choice('status','Status',['Attempted','Solved','Revision due','Revised']),day('revision_date','Next revision',False),
    num('minutes','Total time (minutes)'),num('attempts','Number of attempts',1,minimum=1,integer=True),
    choice('assistance','Solved with',['Independent','Hints','Copied']),memo('approach','Explanation and approach'),
    text('time_complexity','Time complexity'),text('space_complexity','Space complexity'),memo('notes','Personal notes')],
    ('name','topic','difficulty','status','assistance','solved_date','revision_date'),
    'Save a problem, then add as many solution versions as you need in Solution versions. Copied and hinted solves are excluded from independent totals.'),
 'solutions': Entity('Solution versions', [ref('problem_id','Problem','problems'),text('title','Version title',True),
    choice('language','Language',['Python','Java','C++','JavaScript','SQL','Other']),day('created_date','Version date'),
    memo('code','Code solution',True),memo('notes','Version explanation')],('problem_id','title','language','created_date'),
    'Keep initial and optimized approaches as separate versions. Code supports undo, syntax highlighting and Copy.'),
 'paths': Entity('Subjects', [text('name','Subject name',True),memo('description','Description'),memo('goal','Learning goal'),
    choice('priority','Priority',PRIORITY),num('target_minutes','Study target (minutes; 0 = no target)'),
    choice('target_period','Target period',['Weekly','Daily']),day('deadline','Deadline',False),
    choice('status','Status',LEARNING_STATUS)],('name','priority','target_minutes','target_period','deadline','status'),
    'Create any subject. Add its concepts and record study sessions in the adjoining tabs.'),
 'concepts': Entity('Concepts', [ref('path_id','Subject','paths'),text('name','Concept name',True),text('topic','Topic'),
    text('subtopic','Subtopic'),memo('prerequisites','Prerequisite concepts'),choice('status','Status',LEARNING_STATUS),
    num('understanding','Understanding (0 = new, 5 = confident)',0,maximum=5,integer=True),day('revision_date','Next revision',False),
    memo('notes','Notes and difficulties'),memo('exercises','Exercises and results'),memo('code','Code',True),
    num('quiz_score','Quiz score',None,required=False),num('quiz_max','Quiz maximum',None,required=False)],
    ('path_id','name','topic','status','understanding','revision_date'),
    'Completion is your decision. Use notes, prerequisites and difficulties to guide your next study session.'),
 'study_sessions': Entity('Study sessions', [ref('path_id','Subject','paths'),ref('concept_id','Concept (optional)','concepts',False),
    day(),num('minutes','Actual study (minutes)',25),num('planned_minutes','Planned study (minutes)',25),memo('notes','Session notes')],
    ('date','path_id','concept_id','minutes','planned_minutes'), 'Record actual learning time; logging time never automatically marks a concept understood.'),
 'workout_routines': Entity('Routines', [text('name','Routine name',True),choice('split','Split',['Custom','Push/Pull/Legs','Upper/Lower','Full Body']),
    choice('location','Location',['Home','Gym','Home + Gym']),num('days_per_week','Training days per week',3,maximum=7,integer=True),
    choice('active','Active',['Yes','No']),memo('notes','Routine notes')],('name','split','location','days_per_week','active'),
    'Create a routine and its schedule. Changing a routine never changes existing workout history.'),
 'workout_days': Entity('Weekly schedule', [ref('routine_id','Routine','workout_routines'),choice('weekday','Weekday',WEEKDAYS),
    text('name','Day name',True),text('muscles','Muscle groups'),choice('recovery','Recovery day',['No','Yes']),memo('notes','Notes')],
    ('routine_id','weekday','name','muscles','recovery'), 'Recovery days are supported. Use Plan scheduled day to copy a day and its exercises into history.'),
 'planned_exercises': Entity('Planned exercises', [ref('day_id','Scheduled day','workout_days')] + EXERCISE_FIELDS,
    ('day_id','exercise','sets','reps','weight_kg'), 'Exercise names and equipment are entirely customizable. Weights are stored in kilograms.'),
 'workouts': Entity('Workout history', [ref('routine_id','Routine (optional)','workout_routines',False),text('name','Workout name',True),day(),
    choice('status','Status',['Planned','In progress','Completed','Skipped','Recovery']),text('muscles','Muscle groups'),memo('notes','Notes')],
    ('date','name','status','muscles'), 'Log performance under Exercise history and mark the workout Completed when finished.'),
 'exercise_logs': Entity('Exercise history', [ref('workout_id','Workout','workouts')] + EXERCISE_FIELDS,
    ('workout_id','exercise','sets','reps','weight_kg','duration_min','distance_km'),
    'Personal records and strength charts use completed workouts only. Create separate rows for sets with different weights or reps.'),
 'foods': Entity('Food library', [text('name','Food name',True),choice('preparation','Preparation',['Cooked','Raw','As sold','Recipe']),
    text('source','Source / recipe calculation',True),choice('approximate','Approximate',['Yes','No']),
    num('serving_g','One piece / serving (g)',None,required=False,minimum=0.01),
    num('cup_g','One cup (g)',None,required=False,minimum=0.01),num('density','Density (g per ml)',None,required=False,minimum=0.01),
    *[num(n, n.replace('_',' ').capitalize() + (' per 100 g' if n.endswith('_mg') or n=='calories' else ' (g per 100 g)'),
          0 if n in NUTRIENTS[:4] else None, required=n in NUTRIENTS[:4]) for n in NUTRIENTS],memo('notes','Food notes / ingredients')],
    ('name','preparation','calories','protein','carbs','fat','source'),
    'All nutrients are per 100 g. Blank micronutrients mean unknown, never zero. Add homemade foods from weighed ingredients and final cooked weight.'),
 'food_logs': Entity('Food diary', [],('date','meal','name','quantity','unit','calories','protein','carbs','fat'),
    'Nutrition is calculated from the selected food and quantity. Library edits never rewrite previous meals.',True),
 'water_logs': Entity('Water', [day(),num('ml','Water (ml)',250,minimum=1),memo('notes','Notes')],('date','ml','notes')),
 'measurements': Entity('Body measurements', [day(),num('weight_kg','Weight (kg)',70,minimum=1),
    num('waist_cm','Waist (cm)',None,False,minimum=1),num('chest_cm','Chest (cm)',None,False,minimum=1),
    num('hips_cm','Hips (cm)',None,False,minimum=1),num('arm_cm','Arm (cm)',None,False,minimum=1),
    num('thigh_cm','Thigh (cm)',None,False,minimum=1),text('photo_path','Progress photo reference (local path; optional)'),
    num('sleep_hours','Sleep (hours)',None,False,maximum=24),num('energy','Energy (1–5)',None,False,minimum=1,maximum=5,integer=True),
    num('soreness','Soreness (0–10)',None,False,maximum=10,integer=True),num('fatigue','Fatigue (0–10)',None,False,maximum=10,integer=True),
    choice('pain','Pain reported',['','No','Yes']),memo('notes','Notes')],('date','weight_kg','waist_cm','chest_cm','hips_cm')),
 'tasks': Entity('Daily tasks', [text('title','Task title',True),day(),day('deadline','Deadline',False),choice('priority','Priority',PRIORITY),
    choice('status','Status',['To do','In progress','Completed','Skipped']),num('planned_minutes','Planned time (minutes)',25),
    num('actual_minutes','Actual time (minutes)'),choice('kind','Category',['Personal','Learning','Workout','Work','Health']),memo('notes','Notes')],
    ('date','title','priority','status','deadline','planned_minutes','actual_minutes'), 'Filter by date, category, status or priority. Dates are YYYY-MM-DD.'),
 'daily_routines': Entity('Daily routines', [text('title','Routine task',True),text('weekdays','Weekdays (comma separated)',True,','.join(WEEKDAYS[:5])),
    Field('time','Reminder time','time','09:00',True),choice('kind','Category',['Personal','Learning','Workout','Work','Health']),
    num('planned_minutes','Planned time (minutes)',25),choice('priority','Priority',PRIORITY),choice('active','Active',['Yes','No'])],
    ('title','weekdays','time','kind','active'), 'Generate today’s tasks at any time. Each routine creates at most one task per day. Reminders appear while LifeOS is open.'),
 'focus_sessions': Entity('Focus history', [text('title','Focus / study title',True),day(),num('planned_minutes','Planned time (minutes)',25,minimum=0.1),
    num('actual_minutes','Actual time (minutes)',25),choice('status','Status',['Completed','Interrupted']),memo('notes','Notes')],
    ('date','title','planned_minutes','actual_minutes','status'), 'Add manual focus history here. Use the persistent timer above to start, pause, resume and finish timed sessions.'),
}

def defaults_for(table):
    return {f.key: date.today().isoformat() if f.default == 'TODAY' else f.default for f in ENTITIES[table].fields}
