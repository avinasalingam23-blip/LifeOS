"""Domain operations and validation for locally saved records."""
from __future__ import annotations
import csv
import math
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from .models import ENTITIES, NUTRIENTS, WEEKDAYS, defaults_for
from .nutrition import calculate, seed_foods, recipe_nutrients

class Service:
    def __init__(self, db):
        self.db = db
        seed_foods(db)

    def get(self, table, record_id):
        self.entity(table)
        return self.db.one(f'SELECT * FROM {table} WHERE id=?', (record_id,))

    def entity(self, table):
        if table not in ENTITIES:
            raise ValueError('Unknown record type.')
        return ENTITIES[table]

    def list(self, table, search='', filters=None):
        entity = self.entity(table)
        fields = {r['name'] for r in self.db.query(f'PRAGMA table_info({table})')}
        clauses, values = [], []
        if search:
            clauses.append('('+' OR '.join(f'CAST({f} AS TEXT) LIKE ?' for f in fields if f!='id')+')')
            values += ['%'+search+'%']*(len(fields)-1)
        for key, value in (filters or {}).items():
            if key not in fields:
                raise ValueError('Unknown filter.')
            if value is not None and value != '':
                clauses.append(f'{key}=?')
                values.append(value)
        where = ' WHERE '+' AND '.join(clauses) if clauses else ''
        return self.db.query(f'SELECT * FROM {table}{where} ORDER BY id DESC', values)

    def validate(self, table, values):
        result = {}
        entity = self.entity(table)
        for f in entity.fields:
            value = values.get(f.key, defaults_for(table)[f.key])
            if isinstance(value,str) and f.kind not in ('code','memo'):
                value = value.strip()
            if value is None or value == '':
                if f.required:
                    raise ValueError(f'{f.label} is required.')
                result[f.key] = None if f.kind in ('number','int','ref') else ''
                continue
            if f.kind in ('number','int'):
                try:
                    value = float(value)
                except (ValueError,TypeError):
                    raise ValueError(f'{f.label} must be a number.') from None
                if not math.isfinite(value) or value<f.minimum or (f.maximum is not None and value>f.maximum):
                    raise ValueError(f'{f.label} must be at least {f.minimum}' + (f' and at most {f.maximum}.' if f.maximum is not None else '.'))
                if f.kind=='int':
                    if not value.is_integer():
                        raise ValueError(f'{f.label} must be a whole number.')
                    value = int(value)
            if f.kind=='date':
                try:
                    if date.fromisoformat(value).isoformat()!=value:
                        raise ValueError()
                except (ValueError, TypeError):
                    raise ValueError(f'{f.label} must be a real date in YYYY-MM-DD format.') from None
            if f.kind=='time':
                try:
                    if datetime.strptime(value,'%H:%M').strftime('%H:%M')!=value:
                        raise ValueError()
                except ValueError:
                    raise ValueError('Reminder time must use 24-hour HH:MM format.') from None
            if f.kind=='choice' and value not in f.choices:
                raise ValueError(f'Choose a valid {f.label.lower()}.')
            if f.kind=='ref':
                try:
                    value=int(value)
                except (ValueError,TypeError):
                    raise ValueError(f'Choose a {f.label.lower()} first.') from None
                if not self.get(f.ref,value):
                    raise ValueError(f'{f.label} no longer exists. Refresh and select it again.')
            result[f.key] = value
        if table=='problems':
            if result['url'] and urlparse(result['url']).scheme not in ('http','https'):
                raise ValueError('Problem URL must begin with https:// or http://.')
            if result['status'] in ('Solved','Revised') and not result['solved_date']:
                raise ValueError('Enter a solution date for a solved problem.')
            if result['solved_date'] and result['solved_date'] < result['attempt_date']:
                raise ValueError('Solution date cannot be before the attempt date.')
        if table=='concepts':
            score, maximum = result['quiz_score'],result['quiz_max']
            if (score is None)!=(maximum is None) or (maximum is not None and (maximum<=0 or score>maximum)):
                raise ValueError('Provide both a quiz score and a positive maximum; score cannot exceed maximum.')
        if table=='study_sessions' and result['concept_id']:
            if self.get('concepts',result['concept_id'])['path_id']!=result['path_id']:
                raise ValueError('The selected concept belongs to a different subject.')
        if table=='daily_routines':
            days=[v.strip() for v in result['weekdays'].split(',')]
            if not days or any(v not in WEEKDAYS for v in days):
                raise ValueError('Enter full weekday names separated by commas, for example Monday,Wednesday,Friday.')
            result['weekdays']=','.join(dict.fromkeys(days))
        return result

    def save(self, table, values, record_id=None):
        entity=self.entity(table)
        if entity.readonly:
            raise ValueError('Use the food logger to save calculated food entries.')
        if table=='focus_sessions' and record_id:
            existing=self.get(table,record_id)
            if existing and existing['status'] in ('Running','Paused'):
                raise ValueError('Pause or finish this session using the timer controls.')
        data=self.validate(table,values)
        if table=='workouts' and record_id and self.db.one('SELECT workout_id FROM fitness_sessions WHERE workout_id=?',(record_id,)):
            existing=self.get(table,record_id)
            if data['status']!=existing['status'] or data['routine_id']!=existing['routine_id']:
                raise ValueError('Coaching session status is controlled by actual set logging and Finish Workout. Its original routine link is preserved.')
            # Date corrections must keep weekly completion and history consistent.
            with self.db.transaction() as conn:
                conn.execute(f"UPDATE workouts SET {','.join(k+'=?' for k in data)} WHERE id=?",(*data.values(),record_id))
                conn.execute('UPDATE fitness_sessions SET session_date=? WHERE workout_id=?',(data['date'],record_id))
            return record_id
        return self._write(table,data,record_id)

    def _write(self,table,data,record_id=None):
        if record_id:
            if not self.get(table,record_id):
                raise ValueError('This record was removed. Refresh the list.')
            self.db.execute(f"UPDATE {table} SET {','.join(k+'=?' for k in data)} WHERE id=?",(*data.values(),record_id))
            return record_id
        return self.db.execute(f"INSERT INTO {table} ({','.join(data)}) VALUES ({','.join('?' for _ in data)})",tuple(data.values()))

    def delete(self,table,record_id):
        self.entity(table)
        if table=='focus_sessions' and (self.get(table,record_id) or {}).get('status') in ('Running','Paused'):
            raise ValueError('Finish the active timer before deleting it.')
        self.db.execute(f'DELETE FROM {table} WHERE id=?',(record_id,))

    def label(self,table,row):
        name=row.get('name') or row.get('title') or row.get('exercise') or str(row['id'])
        prefix=''
        if table=='concepts':
            parent=self.get('paths',row['path_id'])
            prefix=(parent['name']+' / ') if parent else ''
        if table=='workout_days':
            routine=self.get('workout_routines',row['routine_id'])
            prefix=(routine['name']+' / ' if routine else '')+row['weekday']+' / '
        if table=='workouts':
            prefix=row['date']+' / '
        if table=='foods':
            name += ' ['+row['preparation']+']'
        return f"{prefix}{name}  ·  #{row['id']}"

    def log_food(self,food_id,quantity,unit,day,meal,notes='',record_id=None):
        food=self.get('foods',food_id)
        if not food:
            raise ValueError('Choose a food from the library.')
        date.fromisoformat(day)
        if meal not in ('Breakfast','Lunch','Dinner','Snacks'):
            raise ValueError('Choose a valid meal.')
        nutrients=calculate(food,quantity,unit)
        data=dict(food_id=food_id,name=food['name']+' ['+food['preparation']+']',date=day,meal=meal,
                  quantity=float(quantity),unit=unit,**nutrients,source=food['source'],approximate=food['approximate'],notes=notes)
        return self._write('food_logs',data,record_id)

    def meal_day(self,on_date):
        date.fromisoformat(on_date)
        rows=self.db.query('SELECT * FROM food_logs WHERE date=? ORDER BY id',(on_date,))
        meals={name:dict(entries=[],calories=0,protein=0,unknown_calories=0,unknown_protein=0)
               for name in ('Breakfast','Lunch','Snacks','Dinner')}
        for row in rows:
            group=meals[row['meal']]
            group['entries'].append(row)
            for key in ('calories','protein'):
                if row[key] is None: group['unknown_'+key]+=1
                else: group[key]+=row[key]
        return dict(date=on_date,meals=meals,**{key:sum(m[key] for m in meals.values())
            for key in ('calories','protein','unknown_calories','unknown_protein')})

    def save_recipe(self,name,ingredients,final_grams,serving_g=None,cup_g=None):
        if not name.strip():
            raise ValueError('Give the recipe a name.')
        records=[]
        for food_id,grams in ingredients:
            food=self.get('foods',food_id)
            if not food or not math.isfinite(float(grams)) or grams<=0:
                raise ValueError('Each ingredient needs an existing food and positive grams.')
            records.append((food,grams))
        if not math.isfinite(float(final_grams)):
            raise ValueError('Final cooked weight must be finite.')
        totals=recipe_nutrients(records,final_grams)
        description='; '.join(f"{g:g} g {f['name']}" for f,g in records)
        return self.save('foods',dict(name=name,preparation='Recipe',source='Calculated recipe from source-labelled library ingredients',
                    approximate='Yes',serving_g=serving_g,cup_g=cup_g,**totals,
                    notes=f'Ingredients: {description}. Final yield: {final_grams:g} g. Water changes weight, not calories.'))

    def plan_workout(self,day_id,on_date):
        date.fromisoformat(on_date)
        scheduled=self.get('workout_days',day_id)
        if not scheduled:
            raise ValueError('Select a scheduled day first.')
        with self.db.transaction() as conn:
            workout_id=conn.execute('INSERT INTO workouts(routine_id,name,date,status,muscles,notes) VALUES (?,?,?,?,?,?)',
                (scheduled['routine_id'],scheduled['name'],on_date,'Recovery' if scheduled['recovery']=='Yes' else 'Planned',scheduled['muscles'],scheduled['notes'])).lastrowid
            if scheduled['recovery']!='Yes':
                for exercise in self.list('planned_exercises',filters={'day_id':day_id}):
                    data={k:v for k,v in exercise.items() if k not in ('id','day_id')}
                    data['workout_id']=workout_id
                    conn.execute(f"INSERT INTO exercise_logs ({','.join(data)}) VALUES ({','.join('?' for _ in data)})",tuple(data.values()))
        return workout_id

    def generate_tasks(self,on_date=None):
        on_date=on_date or date.today().isoformat()
        weekday=date.fromisoformat(on_date).strftime('%A')
        count=0
        with self.db.transaction() as conn:
            for routine in self.list('daily_routines',filters={'active':'Yes'}):
                if weekday in routine['weekdays'].split(','):
                    cursor=conn.execute('INSERT OR IGNORE INTO tasks(title,date,priority,status,planned_minutes,kind,notes,routine_id) VALUES (?,?,?,?,?,?,?,?)',
                        (routine['title'],on_date,routine['priority'],'To do',routine['planned_minutes'],routine['kind'],'Routine reminder: '+routine['time'],routine['id']))
                    count+=cursor.rowcount
        return count

    def active_timer(self):
        return self.db.one("SELECT * FROM focus_sessions WHERE status IN ('Running','Paused') LIMIT 1")

    def timer_remaining(self,timer,now=None):
        if timer['status']=='Running':
            elapsed=max(0,((now or datetime.now())-datetime.fromisoformat(timer['started_at'])).total_seconds())
            return max(0,timer['remaining_seconds']-elapsed)
        return timer['remaining_seconds']

    def start_timer(self,title,minutes):
        if self.active_timer():
            raise ValueError('Finish the current focus session before starting another.')
        minutes=float(minutes)
        if not title.strip() or not math.isfinite(minutes) or not 0.1<=minutes<=1440:
            raise ValueError('Give the session a title and duration between 0.1 and 1440 minutes.')
        return self._write('focus_sessions',dict(title=title.strip(),date=date.today().isoformat(),planned_minutes=minutes,
            actual_minutes=0,status='Running',started_at=datetime.now().isoformat(),remaining_seconds=minutes*60,notes='Timed session'))

    def timer_action(self,action):
        timer=self.active_timer()
        if not timer:
            return None
        remaining=self.timer_remaining(timer)
        if action=='pause':
            status='Paused'
        elif action=='resume':
            status='Running'
        elif action=='finish':
            status='Completed' if remaining<=0 else 'Interrupted'
        else:
            raise ValueError('Unknown timer action.')
        actual=max(0,timer['planned_minutes']-remaining/60)
        self.db.execute('UPDATE focus_sessions SET status=?,remaining_seconds=?,actual_minutes=?,started_at=? WHERE id=?',
                        (status,remaining,actual,datetime.now().isoformat(),timer['id']))
        return timer['id']

    def export_csv(self,table,destination,rows=None):
        self.entity(table)
        rows=self.list(table) if rows is None else rows
        fields=[r['name'] for r in self.db.query(f'PRAGMA table_info({table})')]
        with Path(destination).open('w',encoding='utf-8-sig',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=fields)
            writer.writeheader()
            for row in rows:
                # Spreadsheet formula protection; original text stays unchanged in SQLite.
                writer.writerow({k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v) for k,v in row.items()})
