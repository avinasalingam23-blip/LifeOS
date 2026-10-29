"""Persistent weekly checklists; earlier plans, sessions and measured sets stay intact."""
from copy import deepcopy
from datetime import date,datetime,timedelta
import json
import uuid
from .models import WEEKDAYS

KEY='weekly_workout_checklist'


def progress(day):
    total=len(day['targets'])
    completed=sum(t['completed'] for t in day['targets'])
    return dict(completed=completed,total=total,ratio=completed/total if total else 0)


class WorkoutChecklist:
    """A small versioned document in the existing fitness_preferences JSON row.

    Reads do not modify a profile. The first edit saves a copy of earlier plans;
    no original workout row is updated or removed, and ticks never invent sets.
    Every operation reloads under SQLite's write lock before changing its field.
    """
    def __init__(self,db):
        self.db=db

    def _preferences(self):
        row=self.db.one('SELECT values_json FROM fitness_preferences WHERE id=1')
        return json.loads(row['values_json']) if row else {}

    def _legacy(self):
        document=dict(version=1,days={d:dict(muscles=[],targets=[]) for d in WEEKDAYS},history=[])
        routine=self.db.one("SELECT id FROM workout_routines WHERE active='Yes' ORDER BY id DESC LIMIT 1")
        if not routine: routine=self.db.one('SELECT id FROM workout_routines ORDER BY id DESC LIMIT 1')
        if not routine:return document
        document['source_routine_id']=routine['id']
        monday=date.today()-timedelta(days=date.today().weekday())
        for row in self.db.query('SELECT * FROM workout_days WHERE routine_id=? ORDER BY id',(routine['id'],)):
            if row['weekday'] not in WEEKDAYS:continue
            day=document['days'][row['weekday']]
            day['muscles']=list(dict.fromkeys([*day['muscles'],*['Abs' if m.strip()=='Core/abs' else m.strip() for m in row['muscles'].split(',') if m.strip()]]))
            on=(monday+timedelta(days=WEEKDAYS.index(row['weekday']))).isoformat()
            session=self.db.one('SELECT workout_id FROM fitness_sessions WHERE day_id=? AND session_date=?',(row['id'],on))
            logs=self.db.query('SELECT * FROM exercise_logs WHERE workout_id=?',(session['workout_id'],)) if session else []
            for target in self.db.query('SELECT * FROM planned_exercises WHERE day_id=? ORDER BY position,id',(row['id'],)):
                goal=[]
                if target['sets'] and target['reps']:goal.append(f"{target['sets']} x {target['reps']}")
                if target['duration_min']:goal.append(f"{target['duration_min']:g} min")
                if target['weight_kg']:goal.append(f"{target['weight_kg']:g} kg")
                if target['resistance']:goal.append(target['resistance'])
                if target['notes']:goal.append(target['notes'])
                matches=[r for r in logs if all(r[k]==target[k] for k in ('exercise','library_key','position'))]
                completed=len(matches)==1 and matches[0]['completion']=='Completed'
                day['targets'].append(dict(id='legacy-'+str(target['id']),name=target['exercise'],
                    goal=' / '.join(goal),completed=bool(completed)))
        return document

    def _document(self,preferences):
        document=preferences.get(KEY)
        if document is None:return self._legacy()
        if not isinstance(document,dict) or document.get('version')!=1 or set(document.get('days',{}))!=set(WEEKDAYS):
            raise ValueError('The saved workout checklist has an unsupported format. Restore a known backup; the saved value has not been replaced.')
        for day in document['days'].values():
            if not isinstance(day,dict) or not isinstance(day.get('muscles'),list) or not isinstance(day.get('targets'),list):
                raise ValueError('The saved workout checklist is invalid and has not been replaced.')
            ids=set()
            for target in day['targets']:
                if not isinstance(target,dict) or not all(isinstance(target.get(k),str) for k in ('id','name','goal')) or type(target.get('completed')) is not bool or target['id'] in ids:
                    raise ValueError('A saved checklist target is invalid and has not been replaced.')
                ids.add(target['id'])
        return document

    def load(self):
        return deepcopy(self._document(self._preferences()))

    def _edit(self,weekday,change):
        if weekday not in WEEKDAYS:raise ValueError('Choose Monday through Sunday.')
        with self.db.transaction() as conn:
            conn.execute('BEGIN IMMEDIATE')
            preferences=self._preferences()
            document=self._document(preferences)
            result=change(document['days'][weekday],document)
            preferences[KEY]=document
            conn.execute('INSERT OR REPLACE INTO fitness_preferences(id,values_json) VALUES(1,?)',(json.dumps(preferences,ensure_ascii=False),))
        return result

    def muscles(self,weekday,selected):
        values=list(dict.fromkeys(str(m).strip() for m in selected if str(m).strip()))
        if len(values)>50 or any(len(m)>100 for m in values):raise ValueError('Use up to 50 short muscle-group names.')
        self._edit(weekday,lambda day,doc:day.update(muscles=values))

    @staticmethod
    def _text(name,goal):
        name,goal=str(name).strip(),str(goal).strip()
        if not name:raise ValueError('Enter an exercise or workout target name.')
        if len(name)>200 or len(goal)>2000:raise ValueError('Use a name up to 200 characters and goal up to 2,000 characters.')
        return name,goal

    @staticmethod
    def _target(day,target_id):
        target=next((t for t in day['targets'] if t['id']==target_id),None)
        if not target:raise ValueError('Select a target from this day.')
        return target

    def save_target(self,weekday,name,goal='',target_id=None):
        name,goal=self._text(name,goal)
        def change(day,document):
            if target_id:
                target=self._target(day,target_id);target.update(name=name,goal=goal)
                day.pop('editor',None)
                return target_id
            if len(day['targets'])>=500:raise ValueError('Use up to 500 targets per day.')
            rid=uuid.uuid4().hex
            day['targets'].append(dict(id=rid,name=name,goal=goal,completed=False))
            day.pop('editor',None)
            return rid
        return self._edit(weekday,change)

    def complete(self,weekday,target_id,completed):
        if type(completed) is not bool:raise ValueError('Completion must be checked or unchecked.')
        self._edit(weekday,lambda day,doc:self._target(day,target_id).update(completed=completed))

    def remove(self,weekday,target_id):
        def change(day,document):
            day['targets'].remove(self._target(day,target_id))
            if day.get('editor',{}).get('target_id')==target_id:day.pop('editor',None)
        self._edit(weekday,change)

    def editor(self,weekday,name,goal,target_id=None):
        if len(name)>200 or len(goal)>2000:raise ValueError('Use a name up to 200 characters and goal up to 2,000 characters.')
        value=dict(name=name,goal=goal,target_id=target_id)
        current=self.load()['days'][weekday].get('editor',dict(name='',goal='',target_id=None))
        if current==value:return
        def change(day,document):
            if target_id:self._target(day,target_id)
            if name or goal:day['editor']=value
            else:day.pop('editor',None)
        self._edit(weekday,change)

    def move(self,weekday,target_id,direction):
        if direction not in (-1,1):raise ValueError('Move one position up or down.')
        def change(day,document):
            index=day['targets'].index(self._target(day,target_id));other=index+direction
            if 0<=other<len(day['targets']):day['targets'][index],day['targets'][other]=day['targets'][other],day['targets'][index]
        self._edit(weekday,change)

    def reset(self,weekday):
        """Caller asks confirmation. Archive a snapshot; only checkboxes reset."""
        def change(day,document):
            if not any(t['completed'] for t in day['targets']):return
            document['history'].append(dict(id=uuid.uuid4().hex,weekday=weekday,
                saved_at=datetime.now().isoformat(timespec='seconds'),**deepcopy(day)))
            for target in day['targets']:target['completed']=False
        self._edit(weekday,change)
