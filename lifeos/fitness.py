"""Deterministic, local fitness operations over existing LifeOS records."""
from datetime import date,datetime,timedelta
import json
import math
import uuid
from .models import WEEKDAYS
from .exercise_library import EXERCISES,MUSCLES,REGIONS,matching

PREFERENCES=dict(goal='Maintain fitness',experience='Beginner',equipment=['Bodyweight'],
                 diet='No preference',restrictions='',budget='Flexible',meals=3,custom_muscles=[])

def number(value,label,minimum=0,maximum=100000,integer=False,optional=False):
    if optional and value in ('',None):
        return None
    try:
        value=float(value)
    except (ValueError,TypeError):
        raise ValueError(label+' must be numeric.') from None
    if not math.isfinite(value) or not minimum<=value<=maximum or (integer and not value.is_integer()):
        raise ValueError(f'{label} must be '+('a whole number ' if integer else '')+f'between {minimum} and {maximum}.')
    return int(value) if integer else value

def readiness(values):
    result={}
    for key,maximum in [('sleep_hours',24),('energy',5),('soreness',10),('fatigue',10)]:
        result[key]=number(values.get(key),key.replace('_',' '),minimum=1 if key=='energy' else 0,maximum=maximum,optional=True)
    result['pain']=str(values.get('pain','No'))
    if result['pain'] not in ('Yes','No'):
        raise ValueError('Choose Yes or No for pain.')
    result['notes']=str(values.get('notes',''))[:2000]
    severe=result['pain']=='Yes' or any((result[k] or 0)>=8 for k in ('fatigue','soreness')) or (result['sleep_hours'] is not None and result['sleep_hours']<4)
    reduced=any((result[k] or 0)>=5 for k in ('fatigue','soreness')) or (result['sleep_hours'] is not None and result['sleep_hours']<6) or (result['energy'] is not None and result['energy']<=2)
    result['recommendation']='Recovery' if severe else 'Reduced' if reduced else 'Normal'
    result['explanation']='Rest or choose a gentle recovery option. Do not train through pain; seek qualified advice for significant or persistent symptoms.' if severe else 'Consider fewer sets and an easier variation; reassess how you feel.' if reduced else 'Use a comfortable workload and stop before form breaks. Missing recovery information is unknown.'
    return result

class FitnessCoach:
    def __init__(self,service):
        self.service,self.db=service,service.db

    def preferences(self):
        saved=self.db.one('SELECT values_json FROM fitness_preferences WHERE id=1')
        return {**PREFERENCES,**(json.loads(saved['values_json']) if saved else {})}

    def save_preferences(self,values):
        result={**self.preferences(),**values}
        if result['experience'] not in ('Beginner','Intermediate','Experienced') or result['diet'] not in ('No preference','Vegetarian','Vegan','Egg-inclusive'):
            raise ValueError('Choose a listed experience and dietary preference.')
        result['meals']=number(result['meals'],'Meals per day',1,8,integer=True)
        result['equipment']=list(dict.fromkeys(['Bodyweight',*result['equipment']]))
        if any(not isinstance(v,str) or len(v)>100 for v in result['equipment']):
            raise ValueError('Equipment names must be short text.')
        result['custom_muscles']=list(dict.fromkeys(str(v).strip()[:60] for v in result['custom_muscles'] if str(v).strip()))
        for key in ('goal','restrictions','budget'):
            result[key]=str(result[key]).strip()
            if len(result[key])>500:
                raise ValueError(key.capitalize()+' must be at most 500 characters.')
        self.db.execute('INSERT OR REPLACE INTO fitness_preferences VALUES(1,?)',(json.dumps(result),))
        return result

    def muscles(self,search=''):
        return [m for m in dict.fromkeys([*MUSCLES,*REGIONS,*self.preferences()['custom_muscles']]) if search.casefold() in m.casefold()]

    def library(self,search='',muscle='',equipment='',category='',available_only=False):
        extras=[json.loads(r['definition']) for r in self.db.query('SELECT definition FROM fitness_custom_exercises ORDER BY key')]
        return matching([*EXERCISES,*extras],search,muscle,equipment,category,self.preferences()['equipment'] if available_only else None)

    def exercise(self,key):
        return next((e for e in self.library() if e['key']==key),None)

    def custom_exercise(self,name,muscles,equipment,instructions,category='Strength'):
        if not name.strip() or not muscles or not instructions.strip():
            raise ValueError('Provide a name, muscle group and instructions.')
        if any(e['name'].casefold()==name.strip().casefold() for e in self.library()):
            raise ValueError('An exercise with that name already exists.')
        key='custom-'+uuid.uuid4().hex[:12]
        definition=dict(key=key,name=name.strip(),primary=list(muscles),secondary=[],equipment=list(equipment) or ['Bodyweight'],
                        instructions=instructions.strip(),category=category,difficulty='Custom',alternatives=[])
        self.db.execute('INSERT INTO fitness_custom_exercises VALUES(?,?)',(key,json.dumps(definition)))
        return key

    def weekly(self,routine_id,on_date=None):
        today=date.fromisoformat(on_date) if isinstance(on_date,str) else on_date or date.today()
        monday=today-timedelta(days=today.weekday())
        days=self.service.list('workout_days',filters={'routine_id':routine_id}) if routine_id else []
        result=[]
        for index,weekday in enumerate(WEEKDAYS):
            on=(monday+timedelta(days=index)).isoformat()
            scheduled=sorted([d for d in days if d['weekday']==weekday],key=lambda d:d['id'])
            entries=[]
            for day in scheduled:
                session=self.db.one('SELECT s.*,w.status FROM fitness_sessions s JOIN workouts w ON w.id=s.workout_id WHERE day_id=? AND session_date=?',(day['id'],on))
                entries.append(dict(**day,exercises=self.planned(day['id']),session=session))
            result.append(dict(weekday=weekday,date=on,days=entries))
        return result

    def planned(self,day_id):
        return self.db.query('SELECT * FROM planned_exercises WHERE day_id=? ORDER BY position,id',(day_id,))

    def configure_day(self,routine_id,weekday,name,muscles,recovery=False,notes='',day_id=None):
        if weekday not in WEEKDAYS:
            raise ValueError('Choose a weekday.')
        if not self.service.get('workout_routines',routine_id):
            raise ValueError('Choose an existing routine.')
        existing=self.service.get('workout_days',day_id) if day_id else None
        if existing and existing['routine_id']!=routine_id:
            raise ValueError('This day belongs to another routine.')
        return self.service.save('workout_days',dict(routine_id=routine_id,weekday=weekday,name=name,
                    muscles=', '.join(muscles),recovery='Yes' if recovery else 'No',notes=notes),day_id)

    def add_exercise(self,day_id,key,sets=2,reps=8,rest_seconds=60,weight_kg=0,resistance='',tempo='',notes='',duration_min=0,record_id=None):
        exercise=self.exercise(key)
        if not exercise or not self.service.get('workout_days',day_id):
            raise ValueError('Choose an exercise and a scheduled day.')
        values=dict(day_id=day_id,exercise=exercise['name'],equipment=', '.join(exercise['equipment']),
            sets=number(sets,'Sets',1,30,True),reps=number(reps,'Repetitions',0,500,True),
            weight_kg=number(weight_kg,'External load (kg)',0,1000),duration_min=number(duration_min,'Duration',0,1440),
            distance_km=0,notes=str(notes)[:3000])
        rest=number(rest_seconds,'Rest (seconds)',0,900,True)
        if record_id:
            old=self.service.get('planned_exercises',record_id)
            if not old or old['day_id']!=day_id:
                raise ValueError('The selected exercise is not in this day.')
        rid=self.service.save('planned_exercises',values,record_id)
        position=self.db.one('SELECT COALESCE(MAX(position),0) p FROM planned_exercises WHERE day_id=?',(day_id,))['p']+1
        self.db.execute('UPDATE planned_exercises SET library_key=?,rest_seconds=?,tempo=?,resistance=?,position=CASE WHEN ? THEN position ELSE ? END WHERE id=?',
                        (key,rest,str(tempo)[:80],str(resistance)[:100],bool(record_id),position,rid))
        return rid

    def reorder(self,day_id,ids):
        expected={r['id'] for r in self.planned(day_id)}
        if len(ids)!=len(expected) or set(ids)!=expected:
            raise ValueError('Exercise order must contain each planned exercise exactly once.')
        with self.db.transaction() as conn:
            conn.executemany('UPDATE planned_exercises SET position=? WHERE id=?',[(i,rid) for i,rid in enumerate(ids)])

    def create_template(self,six_days=False):
        name='Editable six-day split' if six_days else 'Editable balanced three-day plan'
        existing=self.service.list('workout_routines',filters={'name':name})
        if existing:
            return existing[0]['id']
        preferences=self.preferences()
        if six_days and preferences['experience']=='Beginner':
            raise ValueError('The three-day template is the starting option for beginners. Choose experience and recovery needs before a six-day split.')
        routine=self.service.save('workout_routines',dict(name=name,split='Custom',days_per_week=6 if six_days else 3,
                location='Gym' if 'Gym' in preferences['equipment'] else 'Home',notes='Editable starting template. Recovery is part of training; adapt to your experience and available equipment.'))
        groups=[('Push: chest, shoulders & triceps',['Chest','Shoulders','Triceps'],['wall-pushup','wall-slide','band-triceps']),
                ('Pull: back & biceps',['Back','Biceps'],['band-row','band-curl']),
                ('Legs & glutes',['Quadriceps','Hamstrings','Glutes'],['chair-squat','glute-bridge','calf-raise']),
                ('Upper body',['Chest','Back','Shoulders'],['incline-pushup','band-row']),
                ('Legs & core',['Quadriceps','Glutes','Core/abs'],['squat','dead-bug']),
                ('Full body & conditioning',['Chest','Back','Quadriceps','Core/abs'],['wall-pushup','chair-squat','walk']),
                ('Recovery & mobility',[],['cat-cow','ankle-mobility'])]
        available={e['key'] for e in self.library(available_only=True)}
        with self.db.transaction():
            for i,(title,muscles,keys) in enumerate(groups):
                recovery=i==6 or (not six_days and i in (1,3,5))
                if not six_days and i==4:
                    title,muscles,keys='Pull & whole-body practice',['Back','Biceps','Quadriceps'],['band-row','chair-squat','bird-dog']
                if recovery:
                    title,muscles,keys='Recovery & comfortable mobility',[],['walk','cat-cow']
                day_id=self.configure_day(routine,WEEKDAYS[i],title,muscles,recovery,
                    'Alternates training and recovery to manage workload. Adjust this editable plan to how you recover.' if not six_days else 'Editable split distributes muscle groups across the week. Swap or rest when recovery requires it.')
                for key in keys:
                    if key in available:
                        e=self.exercise(key)
                        duration=5 if e['category']=='Cardio' else 2 if e['category'] in ('Mobility','Stretching') else 0
                        self.add_exercise(day_id,key,sets=1 if recovery else 2,reps=0 if duration else 8,duration_min=duration)
        return routine

    def start(self,day_id,on_date=None,reported=None,mode='Normal'):
        on_date=on_date or date.today().isoformat()
        if date.fromisoformat(on_date)>date.today():
            raise ValueError('Future workouts can be planned, but actual performance cannot be logged in advance.')
        day=self.service.get('workout_days',day_id)
        if not day:
            raise ValueError('Choose a scheduled workout.')
        existing=self.db.one('SELECT workout_id FROM fitness_sessions WHERE day_id=? AND session_date=?',(day_id,on_date))
        if existing:
            return existing['workout_id']
        report=readiness(reported or {})
        if mode not in ('Normal','Reduced','Recovery'):
            raise ValueError('Choose normal, reduced or recovery.')
        if report['recommendation']=='Recovery' and mode!='Recovery':
            raise ValueError(report['explanation']+' Choose Recovery to continue.')
        if report['recommendation']=='Reduced' and mode=='Normal':
            raise ValueError(report['explanation']+' Choose Reduced or Recovery.')
        if day['recovery']=='Yes':
            mode='Recovery'
        planned=self.planned(day_id)
        if not planned and mode!='Recovery':
            raise ValueError('Add exercises before starting a training session, or choose Recovery.')
        if mode!='Recovery':
            available={e['key'] for e in self.library(available_only=True)}
            missing=[e['exercise'] for e in planned if e['library_key'] and e['library_key'] not in available]
            if missing:
                raise ValueError('Required equipment is not selected for: '+', '.join(missing)+'. Update coach equipment or choose suitable alternatives before starting.')
        with self.db.transaction() as conn:
            rid=conn.execute('INSERT INTO workouts(routine_id,name,date,status,muscles,notes) VALUES(?,?,?,?,?,?)',
                        (day['routine_id'],day['name'],on_date,'In progress',day['muscles'],day['notes'])).lastrowid
            conn.execute('INSERT INTO fitness_sessions(workout_id,day_id,session_date,started_at,readiness_json,recovery_option) VALUES(?,?,?,?,?,?)',
                         (rid,day_id,on_date,datetime.now().isoformat(),json.dumps(report),mode))
            for item in planned:
                e=self.exercise(item['library_key'])
                if mode=='Recovery' and (report['pain']=='Yes' or not e or e['category'] not in ('Cardio','Mobility','Stretching')):
                    continue
                data={k:v for k,v in item.items() if k not in ('id','day_id')}
                target_sets=max(1,item['sets']//2) if mode=='Reduced' else item['sets']
                data.update(workout_id=rid,target_sets=target_sets,target_reps=item['reps'],target_duration=item['duration_min'],
                            sets=0,reps=0,duration_min=0,distance_km=0,completion='Planned')
                conn.execute(f"INSERT INTO exercise_logs({','.join(data)}) VALUES({','.join('?' for _ in data)})",tuple(data.values()))
        return rid

    def session(self,rid):
        session=self.db.one('SELECT * FROM fitness_sessions WHERE workout_id=?',(rid,))
        if not session:
            raise ValueError('Choose a coaching session.')
        return dict(**self.service.get('workouts',rid),coaching=session,
                    exercises=self.db.query('SELECT * FROM exercise_logs WHERE workout_id=? ORDER BY position,id',(rid,)))

    def save_set(self,log_id,set_no,reps=0,weight_kg=0,resistance='',variation='',rir=None,notes='',duration_min=0,distance_km=0):
        log=self.service.get('exercise_logs',log_id)
        if not log or not self.db.one('SELECT workout_id FROM fitness_sessions WHERE workout_id=?',(log['workout_id'],)):
            raise ValueError('Choose an exercise in a coaching session.')
        values=(log_id,number(set_no,'Set number',1,100,True),number(reps,'Reps',0,1000,True),number(weight_kg,'Load (kg)',0,1000),
            str(resistance).strip()[:100],str(variation).strip()[:100],number(rir,'Reps in reserve',0,10,optional=True),
            number(duration_min,'Duration (minutes)',0,1440),number(distance_km,'Distance (km)',0,500),str(notes)[:2000])
        if values[2]==0 and values[7]==0 and values[8]==0:
            raise ValueError('Log actual repetitions, time or distance; use Skip for an unperformed exercise.')
        with self.db.transaction() as conn:
            conn.execute('INSERT INTO fitness_sets(exercise_log_id,set_no,reps,weight_kg,resistance,variation,rir,duration_min,distance_km,notes) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(exercise_log_id,set_no) DO UPDATE SET reps=excluded.reps,weight_kg=excluded.weight_kg,resistance=excluded.resistance,variation=excluded.variation,rir=excluded.rir,duration_min=excluded.duration_min,distance_km=excluded.distance_km,notes=excluded.notes',values)
            aggregate=conn.execute('SELECT COUNT(*),MAX(reps),MAX(weight_kg),SUM(duration_min),SUM(distance_km) FROM fitness_sets WHERE exercise_log_id=?',(log_id,)).fetchone()
            conn.execute("UPDATE exercise_logs SET sets=?,reps=?,weight_kg=?,duration_min=?,distance_km=?,completion='Completed',skip_reason='' WHERE id=?",(*aggregate,log_id))
            conn.execute("UPDATE workouts SET status='Completed' WHERE id=? AND status='Skipped' AND EXISTS(SELECT 1 FROM fitness_sessions WHERE workout_id=? AND finished_at!='' AND recovery_option!='Recovery')",(log['workout_id'],log['workout_id']))

    def delete_set(self,set_id):
        row=self.db.one('SELECT s.*,e.workout_id FROM fitness_sets s JOIN exercise_logs e ON e.id=s.exercise_log_id WHERE s.id=?',(set_id,))
        if not row:
            raise ValueError('Choose an existing saved set.')
        with self.db.transaction() as conn:
            conn.execute('DELETE FROM fitness_sets WHERE id=?',(set_id,))
            aggregate=conn.execute('SELECT COUNT(*),COALESCE(MAX(reps),0),COALESCE(MAX(weight_kg),0),COALESCE(SUM(duration_min),0),COALESCE(SUM(distance_km),0) FROM fitness_sets WHERE exercise_log_id=?',(row['exercise_log_id'],)).fetchone()
            completion='Completed' if aggregate[0] else 'Skipped'
            conn.execute('UPDATE exercise_logs SET sets=?,reps=?,weight_kg=?,duration_min=?,distance_km=?,completion=?,skip_reason=? WHERE id=?',(*aggregate,completion,'' if aggregate[0] else 'Corrected: no performed sets remain',row['exercise_log_id']))
            conn.execute("UPDATE workouts SET status='Skipped' WHERE id=? AND status='Completed' AND NOT EXISTS(SELECT 1 FROM exercise_logs WHERE workout_id=? AND completion='Completed')",(row['workout_id'],row['workout_id']))

    def skip(self,log_id,reason):
        log=self.service.get('exercise_logs',log_id)
        if not log or not self.db.one('SELECT workout_id FROM fitness_sessions WHERE workout_id=?',(log['workout_id'],)):
            raise ValueError('Choose an exercise in a coaching session.')
        if not str(reason).strip():
            raise ValueError('Record why this exercise was skipped.')
        if self.db.one('SELECT id FROM fitness_sets WHERE exercise_log_id=?',(log_id,)):
            raise ValueError('This exercise has saved sets. Keep it as partially completed instead of marking it skipped.')
        self.db.execute("UPDATE exercise_logs SET completion='Skipped',skip_reason=? WHERE id=?",(str(reason).strip()[:1000],log_id))

    def set_exercise_completed(self,log_id,completed):
        log=self.service.get('exercise_logs',log_id)
        if not log:
            raise ValueError('Choose an existing session exercise.')
        session=self.session(log['workout_id'])
        if session['coaching']['finished_at']:
            raise ValueError('This workout is finished. Correct saved sets in session history instead.')
        if completed and not self.db.one('SELECT id FROM fitness_sets WHERE exercise_log_id=?',(log_id,)):
            raise ValueError('Log your actual sets before marking the exercise complete.')
        self.db.execute('UPDATE exercise_logs SET completion=?,skip_reason=? WHERE id=?',
            ('Completed' if completed else 'Planned','',log_id))

    def finish(self,rid,review=''):
        session=self.session(rid)
        if session['coaching']['finished_at']:
            return self.session_summary(rid)
        if any(e['completion'] not in ('Completed','Skipped') for e in session['exercises']):
            raise ValueError('Log actual sets or record a skip reason for each exercise before finishing.')
        if not session['exercises'] and session['coaching']['recovery_option']!='Recovery':
            raise ValueError('Add exercises to the plan before starting a training session.')
        with self.db.transaction() as conn:
            conn.execute("UPDATE fitness_sessions SET finished_at=?,review=? WHERE workout_id=? AND finished_at=''",(datetime.now().isoformat(),str(review)[:3000],rid))
            status='Recovery' if session['coaching']['recovery_option']=='Recovery' else 'Completed' if any(e['completion']=='Completed' for e in session['exercises']) else 'Skipped'
            conn.execute('UPDATE workouts SET status=? WHERE id=?',(status,rid))
        return self.session_summary(rid)

    def session_summary(self,rid):
        session=self.session(rid)
        sets=self.db.one('SELECT COUNT(*) count,COALESCE(SUM(s.reps),0) reps FROM fitness_sets s JOIN exercise_logs e ON e.id=s.exercise_log_id WHERE e.workout_id=?',(rid,))
        return dict(workout_id=rid,name=session['name'],date=session['date'],status=session['status'],
                    planned_exercises=len(session['exercises']),completed_exercises=sum(e['completion']=='Completed' for e in session['exercises']),
                    skipped_exercises=sum(e['completion']=='Skipped' for e in session['exercises']),planned_sets=sum(e['target_sets'] for e in session['exercises']),
                    completed_sets=sets['count'],total_reps=sets['reps'])

    def strength(self,key,start=None,end=None):
        end=end or date.today().isoformat()
        start=start or (date.fromisoformat(end)-timedelta(days=29)).isoformat()
        from .analytics import days_between
        days_between(start,end)
        rows=self.db.query("SELECT w.date,w.id workout_id,e.exercise,s.* FROM fitness_sets s JOIN exercise_logs e ON e.id=s.exercise_log_id JOIN workouts w ON w.id=e.workout_id WHERE e.library_key=? AND w.status='Completed' AND w.date BETWEEN ? AND ? ORDER BY w.date,w.id,s.set_no",(key,start,end))
        grouped={}
        for row in rows:
            signature=(row['workout_id'],row['variation'],row['resistance'],row['weight_kg'])
            aggregate=grouped.setdefault(signature,dict(date=row['date'],workout_id=row['workout_id'],variation=row['variation'],resistance=row['resistance'],weight_kg=row['weight_kg'],sets=0,total_reps=0,best_reps=0,rir=[]))
            aggregate['sets']+=1
            aggregate['total_reps']+=row['reps']
            aggregate['best_reps']=max(aggregate['best_reps'],row['reps'])
            if row['rir'] is not None:
                aggregate['rir'].append(row['rir'])
        points=list(grouped.values())
        definition=self.exercise(key)
        legacy=self.db.query("SELECT w.date,e.exercise,e.sets,e.reps,e.weight_kg FROM exercise_logs e JOIN workouts w ON w.id=e.workout_id WHERE w.status='Completed' AND w.date BETWEEN ? AND ? AND LOWER(e.exercise)=? AND NOT EXISTS(SELECT 1 FROM fitness_sessions fs WHERE fs.workout_id=w.id) ORDER BY w.date,e.id",(start,end,definition['name'].lower() if definition else key.lower()))
        suggestion='Log at least two completed sessions with the same variation, load, resistance and set count for a fair comparison.'
        change=None
        if len(points)>=2:
            current=points[-1]
            previous=next((p for p in reversed(points[:-1]) if p['workout_id']!=current['workout_id'] and all(p[k]==current[k] for k in ('variation','resistance','weight_kg','sets'))),None)
            if previous:
                change=current['total_reps']-previous['total_reps']
                if change>0 and current['rir'] and min(current['rir'])>=2:
                    suggestion='More recorded repetitions at the same setup with reserve reported. If recovery is good, optionally add one repetition to one set; keep other variables steady.'
                elif change<0:
                    suggestion='Repetitions declined at the same setup. Review sleep, soreness and fatigue; repeat an easier workload or take recovery if needed.'
                elif change==0:
                    suggestion='Recorded repetitions are unchanged in the latest comparable sessions. Repeat with controlled form; two equal sessions alone do not establish a stall.'
                else:
                    suggestion='Recorded repetitions increased. Repeat this workload; log reps in reserve and recovery before considering progression.'
        stalled=False
        weekly=dict(previous_best_reps=None,current_best_reps=None,change=None)
        if points:
            latest=points[-1]
            comparable=[p for p in points if all(p[k]==latest[k] for k in ('variation','resistance','weight_kg','sets'))]
            recent=comparable[-3:]
            stalled=len(recent)==3 and len({p['date'] for p in recent})==3 and len({p['total_reps'] for p in recent})==1
            if stalled:
                suggestion='Repetition totals are unchanged across three comparable logged dates. This may be a plateau; check technique, sleep and recovery before an optional small change.'
            split=(date.fromisoformat(end)-timedelta(days=6)).isoformat()
            previous_start=(date.fromisoformat(end)-timedelta(days=13)).isoformat()
            past=[p['best_reps'] for p in comparable if previous_start<=p['date']<split]
            current=[p['best_reps'] for p in comparable if split<=p['date']<=end]
            weekly=dict(previous_date_range=[previous_start,(date.fromisoformat(split)-timedelta(days=1)).isoformat()],
                        current_date_range=[split,end],previous_best_reps=max(past) if past else None,
                        current_best_reps=max(current) if current else None,
                        change=max(current)-max(past) if past and current else None)
            recovery=self.db.one('SELECT readiness_json FROM fitness_sessions WHERE workout_id=?',(latest['workout_id'],))
            if recovery:
                report=json.loads(recovery['readiness_json'])
                if report.get('recommendation') in ('Recovery','Reduced'):
                    suggestion='Reported recovery limits take priority over progression. '+report.get('explanation','Repeat a lighter workload or recover.')
        return dict(date_range=[start,end],exercise_key=key,points=points,rep_change=change,weekly_comparison=weekly,
                    possible_plateau=stalled,recommendation=suggestion,
                    legacy_aggregate_points=legacy,
                    scope='Actual logged sets from completed coaching sessions only; legacy aggregate records remain available separately. No measured 1RM is inferred.')

    def body_trend(self,start,end):
        from .analytics import days_between
        days_between(start,end)
        rows=self.db.query('SELECT * FROM measurements WHERE date BETWEEN ? AND ? ORDER BY date,id',(start,end))
        days={}
        for row in rows:
            days.setdefault(row['date'],[]).append(row['weight_kg'])
        points=[dict(date=d,weight_kg=sum(v)/len(v),entries=len(v)) for d,v in days.items()]
        return dict(date_range=[start,end],measurements=rows,weight_points=points,
                    change_kg=points[-1]['weight_kg']-points[0]['weight_kg'] if len(points)>=2 else None,
                    scope='Actual measurement entries; daily points average same-day weights. Calculated change is not muscle growth or body-fat percentage.')

    def nutrition_review(self,start,end):
        from .analytics import Analytics
        daily=Analytics(self.db).daily(start,end)
        counts={r['date']:r['n'] for r in self.db.query('SELECT date,COUNT(*) n FROM food_logs WHERE date BETWEEN ? AND ? GROUP BY date',(start,end))}
        for day in daily:
            day['nutrition']['entries']=counts.get(day['date'],0)
        # Zero logs mean unknown intake, not a measured zero-calorie day.
        logged=[d for d in daily if d['nutrition']['entries']]
        return dict(date_range=[start,end],days=len(daily),logged_days=len(logged),missing_days=len(daily)-len(logged),
            calories=sum(d['nutrition']['calories'] for d in logged),protein=sum(d['nutrition']['protein'] for d in logged),
            calorie_target_days=sum(d['goals']['calories']>0 and d['nutrition']['calories']>=d['goals']['calories'] for d in logged),
            protein_target_days=sum(d['goals']['protein']>0 and d['nutrition']['protein']>=d['goals']['protein'] for d in logged),
            daily=[dict(date=d['date'],entries=d['nutrition']['entries'],calories=d['nutrition']['calories'],protein=d['nutrition']['protein'],calorie_goal=d['goals']['calories'],protein_goal=d['goals']['protein']) for d in daily],
            uncertainty='Logged totals only; partial days and unlogged meals are unknown. Targets are user-set; reaching or exceeding one is not proof of an appropriate intake.')

    def meal_suggestions(self):
        preferences=self.preferences()
        blocked=[v.strip().casefold() for v in preferences['restrictions'].replace(';',',').split(',') if v.strip()]
        aliases={'dairy':['milk','yogurt','curd','butter','cheese','paneer'],
                 'gluten':['wheat','barley','rye','chapati'],
                 'nuts':['peanut','groundnut','almond','cashew','walnut'],
                 'eggs':['egg']}
        blocked+=[term for restriction in list(blocked) for term in aliases.get(restriction,[])]
        meat=['chicken','fish','beef','pork','mutton','lamb','meat','gelatin','prawn','shrimp']
        if preferences['diet']=='Vegan':
            blocked+=['egg','milk','yogurt','curd','butter','cheese','paneer','honey',*meat]
        elif preferences['diet']=='Vegetarian':
            blocked+=['egg',*meat]
        elif preferences['diet']=='Egg-inclusive':
            blocked+=meat
        foods=[f for f in self.service.list('foods') if not any(v in (f['name']+' '+f['notes']).casefold() for v in blocked)]
        # Suggestions reference real library records, without invented portions or totals.
        order=['lentil','chickpea','idli','sambar','chapati','rice','egg','yogurt','spinach','banana']
        return list({f['id']:f for term in order for f in foods if term in f['name'].casefold()}.values())[:8]

    def progress_review(self,end=None,routine_id=None):
        end=end or date.today().isoformat()
        start=(date.fromisoformat(end)-timedelta(days=29)).isoformat()
        routines=self.service.list('workout_routines',filters={'active':'Yes'})
        routine_id=routine_id if routine_id and self.service.get('workout_routines',routine_id) else routines[0]['id'] if routines else None
        weekly=self.weekly(routine_id,end) if routine_id else []
        exercise_keys=[r['library_key'] for r in self.db.query("SELECT DISTINCT library_key FROM exercise_logs WHERE library_key!='' ORDER BY id DESC LIMIT 8")]
        body=self.body_trend(start,end)
        strengths=[self.strength(k,start,end) for k in exercise_keys]
        for item in strengths:
            item['points']=item['points'][-8:]
            item['legacy_aggregate_points']=item['legacy_aggregate_points'][-5:]
        library=[dict(key=e['key'],name=e['name'],muscles=e['primary'],equipment=e['equipment'],difficulty=e['difficulty']) for e in self.library(available_only=True) if not (self.preferences()['experience']=='Beginner' and e['difficulty']=='Advanced')]
        report=dict(kind='fitness_coach',date_range=[start,end],preferences=self.preferences(),weekly_schedule=weekly,
            strength=strengths,body=dict(weight_points=body['weight_points'],change_kg=body['change_kg'],scope=body['scope']),
            nutrition=self.nutrition_review(start,end),available_exercises=library,
            recent_recovery=self.db.query('SELECT session_date,readiness_json,recovery_option,review FROM fitness_sessions WHERE session_date BETWEEN ? AND ? ORDER BY session_date DESC LIMIT 5',(start,end)),
            missing=['Unlogged food, sets and recovery are unknown.','No body-fat or muscle-growth measurement is available.','Recommendations do not change the saved plan.'])
        # Checklist storage shares the preferences row, but is not measured
        # strength evidence or relevant to this bounded historical report.
        report['preferences'].pop('weekly_workout_checklist',None)
        report['workout_totals']=self.db.one("SELECT COUNT(*) total,COALESCE(SUM(status='Completed'),0) completed,COALESCE(SUM(status='Recovery'),0) recovery,COALESCE(SUM(status='In progress'),0) in_progress FROM workouts WHERE date BETWEEN ? AND ?",(start,end))
        report['today_plan']=[dict(name=entry['name'],muscles=entry['muscles'],recovery=entry['recovery'],why=entry['notes'][:180],
            exercises=[{k:e[k] for k in ('exercise','library_key','sets','reps','rest_seconds','equipment')} for e in entry['exercises'][:6]])
            for day in weekly if day['date']==end for entry in day['days'][:2]]
        report['preferences']['custom_muscles']=report['preferences']['custom_muscles'][:15]
        report['preferences']['equipment']=report['preferences']['equipment'][:10]
        for recovery in report['recent_recovery']:
            values=json.loads(recovery['readiness_json'])
            values['notes']=str(values.get('notes',''))[:180]
            recovery['readiness_json']=values
            recovery['review']=recovery['review'][:220]
        # The schedule is a current plan, not completed history. Keep instructions
        # and personal free text bounded for a compact local progress report.
        for day in report['weekly_schedule']:
            for entry in day['days']:
                entry['exercises']=[{k:e[k] for k in ('exercise','library_key','sets','reps','rest_seconds','equipment')} for e in entry['exercises'][:6]]
                entry['notes']=entry['notes'][:180]
                entry.pop('session',None)
        report['scope']='Exact calculations within stated date range; recent examples/library/schedule may be abbreviated. A plan is not evidence of completed exercise.'
        while len(json.dumps(report,ensure_ascii=False))>8500:
            candidates=[(library,4),(strengths,0),(report['weekly_schedule'],0),
                        (report['recent_recovery'],0),(report['nutrition']['daily'],7),(report['body']['weight_points'],2)]
            eligible=[rows for rows,minimum in candidates if len(rows)>minimum]
            if not eligible:
                break
            max(eligible,key=lambda rows:len(json.dumps(rows,ensure_ascii=False))).pop(0)
        return report

    def review_text(self,end=None,routine_id=None):
        """Explain calculated progress and missing history from local records."""
        report=self.progress_review(end,routine_id)
        nutrition,body=report['nutrition'],report['body']
        change=('Not enough measurements to calculate weight change.' if body['change_kg'] is None
                else f"Calculated weight change: {body['change_kg']:+.2f} kg.")
        plans='\n'.join(p['name']+' - '+(p['muscles'] or 'Recovery / mobility')+'\n'+
            ', '.join(e['exercise'] for e in p['exercises']) for p in report['today_plan'])
        workouts=report['workout_totals']
        return (f"Date range: {' to '.join(report['date_range'])}\n"
            f"Saved plan for {report['date_range'][1]}: {plans or 'No saved workout scheduled in the selected routine.'}\n"
            f"{workouts['completed']} completed workouts; {workouts['recovery']} recovery sessions in range.\n"
            f"{change}\nNutrition: {nutrition['logged_days']} / {nutrition['days']} days have food entries; "
            f"{nutrition['missing_days']} days missing. Protein target reached in logged totals on "
            f"{nutrition['protein_target_days']} days.\nUnlogged meals and recovery are unknown. Targets are user-set.\n"+
            '\n'.join(s['exercise_key']+': '+s['recommendation'] for s in report['strength']))
