import sqlite3
from datetime import date
import pytest
from lifeos.db import Database
from lifeos.service import Service
from lifeos.models import defaults_for

TODAY=date.today().isoformat()

def test_dynamic_subject_and_solution_persist(db,service):
    assert service.list('paths')==[]
    path=service.save('paths',{'name':'Compiler design','target_minutes':120})
    concept=service.save('concepts',{'path_id':path,'name':'LR parsing','notes':'Confused about lookahead','understanding':2})
    service.save('study_sessions',{'path_id':path,'concept_id':concept,'minutes':37,'planned_minutes':30})
    problem=service.save('problems',{'name':'括号 parser','topic':'Stacks','status':'Solved','solved_date':TODAY})
    code='def parse(text):\n    return "λ" in text\n'
    v1=service.save('solutions',{'problem_id':problem,'title':'First attempt','code':code})
    v2=service.save('solutions',{'problem_id':problem,'title':'Optimized','code':'# O(n)\npass'})
    reopened=Database(db.path)
    other=Service(reopened)
    assert other.get('paths',path)['name']=='Compiler design'
    assert other.get('solutions',v1)['code']==code
    assert len(other.list('solutions',filters={'problem_id':problem}))==2
    assert other.get('concepts',concept)['status']=='Not started'
    reopened.close()

def test_update_search_filter_and_delete(service):
    p=service.save('problems',{'name':"O'Brien's two sum",'platform':'Custom','topic':'Array'})
    assert len(service.list('problems',search="O'Brien"))==1
    assert service.list('problems',search="' OR 1=1 --")==[]
    assert len(service.list('problems',filters={'topic':'Array'}))==1
    row=service.get('problems',p)
    row['name']='Three sum'
    service.save('problems',row,p)
    assert service.get('problems',p)['name']=='Three sum'
    service.save('solutions',{'problem_id':p,'title':'Attempt','code':'pass'})
    service.delete('problems',p)
    assert service.list('solutions')==[]

@pytest.mark.parametrize('values',[
    {'name':''},{'name':'x','minutes':-1},{'name':'x','minutes':'nan'},
    {'name':'x','attempts':1.5},{'name':'x','attempts':0},
    {'name':'x','url':'javascript:alert(1)'},{'name':'x','status':'Solved'},
    {'name':'x','attempt_date':'2026-02-30'}, {'name':'x','difficulty':'Impossible'},
    {'name':'x','attempt_date':'2026-10-20','solved_date':'2026-10-19'},
])
def test_problem_validation(service,values):
    with pytest.raises(ValueError):
        service.save('problems',values)

def test_references_and_quiz_validation(service):
    a=service.save('paths',{'name':'Algebra'})
    b=service.save('paths',{'name':'Japanese'})
    c=service.save('concepts',{'path_id':a,'name':'Rings'})
    with pytest.raises(ValueError,match='different subject'):
        service.save('study_sessions',{'path_id':b,'concept_id':c,'minutes':10})
    with pytest.raises(ValueError):
        service.save('concepts',{'path_id':a,'name':'x','quiz_score':9,'quiz_max':8})
    with pytest.raises(ValueError):
        service.save('concepts',{'path_id':999,'name':'x'})
    with pytest.raises(ValueError):
        service.save('concepts',{'path_id':a,'name':'x','understanding':6})

def test_workout_snapshot_survives_plan_changes_and_deletion(service):
    routine=service.save('workout_routines',{'name':'Custom Upper','split':'Upper/Lower'})
    day=service.save('workout_days',{'routine_id':routine,'weekday':'Monday','name':'Upper A','muscles':'Chest, back'})
    exercise=service.save('planned_exercises',{'day_id':day,'exercise':'Dumbbell press','weight_kg':12})
    workout=service.plan_workout(day,TODAY)
    old=service.get('planned_exercises',exercise)
    old['weight_kg']=16
    service.save('planned_exercises',old,exercise)
    assert service.list('exercise_logs',filters={'workout_id':workout})[0]['weight_kg']==12
    service.delete('workout_routines',routine)
    assert service.get('workouts',workout)['name']=='Upper A'
    assert service.get('workouts',workout)['routine_id'] is None
    assert service.list('exercise_logs')[0]['weight_kg']==12

def test_recovery_day_has_no_planned_exercises(service):
    routine=service.save('workout_routines',{'name':'Flexible'})
    day=service.save('workout_days',{'routine_id':routine,'name':'Rest','recovery':'Yes'})
    service.save('planned_exercises',{'day_id':day,'exercise':'Should not be copied'})
    workout=service.plan_workout(day,TODAY)
    assert service.get('workouts',workout)['status']=='Recovery'
    assert not service.list('exercise_logs')

def test_routines_generate_once_and_remain_editable(service):
    routine=service.save('daily_routines',{'title':'Review concepts','weekdays':date.today().strftime('%A'),'time':'19:30'})
    assert service.generate_tasks()==1
    assert service.generate_tasks()==0
    task=service.list('tasks')[0]
    task['status']='Completed'
    service.save('tasks',task,task['id'])
    service.delete('daily_routines',routine)
    assert service.list('tasks')[0]['status']=='Completed'
    with pytest.raises(ValueError):
        service.save('daily_routines',{'title':'Bad','weekdays':'Mon'})
    with pytest.raises(ValueError):
        service.save('daily_routines',{'title':'Bad','time':'25:00'})

def test_csv_preserves_code_and_escapes_spreadsheet_formulas(service,tmp_path):
    import csv
    service.save('paths',{'name':'=DANGEROUS()','description':'Line one\nLine two'})
    target=tmp_path/'export.csv'
    service.export_csv('paths',target)
    with target.open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    assert rows[0]['name']=="'=DANGEROUS()"
    assert rows[0]['description']=='Line one\nLine two'

def test_unknown_entities_and_filters_are_rejected(service):
    with pytest.raises(ValueError):
        service.list('problems; DROP TABLE settings')
    with pytest.raises(ValueError):
        service.list('problems',filters={'id OR 1=1':'x'})

def test_manual_session_never_completes_concepts(service):
    path=service.save('paths',{'name':'New subject'})
    concept=service.save('concepts',{'path_id':path,'name':'Core idea','status':'Needs practice'})
    service.save('study_sessions',{'path_id':path,'concept_id':concept,'minutes':120})
    assert service.get('concepts',concept)['status']=='Needs practice'
