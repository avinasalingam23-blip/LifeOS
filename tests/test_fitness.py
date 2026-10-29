from datetime import date,timedelta
import json
import sqlite3
from pathlib import Path
import pytest
from lifeos.fitness import FitnessCoach,readiness
from lifeos.exercise_library import EXERCISES,BY_KEY,MUSCLES
from lifeos.db import Database

@pytest.fixture
def coach(service):
    return FitnessCoach(service)

def plan(coach):
    routine=coach.create_template()
    day=coach.weekly(routine)[0]['days'][0]
    return day['id']

def complete(coach,day,on_date,reps=8,rir=3):
    rid=coach.start(day,on_date)
    for item in coach.session(rid)['exercises']:
        for i in range(item['target_sets']):
            coach.save_set(item['id'],i+1,reps,rir=rir)
    coach.finish(rid,'Controlled form')
    return rid

def test_libraries_unique_mappings_search_and_equipment(coach):
    assert len(EXERCISES)>=30
    assert len({e['key'] for e in EXERCISES})==len(EXERCISES)
    assert len({e['name'].casefold() for e in EXERCISES})==len(EXERCISES)
    for e in EXERCISES:
        assert set(e['primary']+e['secondary'])<=set(MUSCLES)
        assert all(key in BY_KEY for key in e['alternatives'])
        assert e['instructions']
    assert all('Back' in e['primary']+e['secondary'] for e in coach.library(muscle='Lats'))
    assert coach.library('pull-up',equipment='Pull-up bar')
    assert all(e['equipment']==['Bodyweight'] for e in coach.library(available_only=True))
    assert all(e['category']=='Mobility' for e in coach.library(category='Mobility'))

def test_weekly_seven_days_empty_and_editable_template(coach):
    assert len(coach.weekly(None))==7
    assert all(not d['days'] for d in coach.weekly(None))
    routine=coach.create_template()
    week=coach.weekly(routine)
    assert [d['weekday'] for d in week]==['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    assert all(len(d['days'])==1 for d in week)
    assert sum(d['days'][0]['recovery']=='No' for d in week)==3
    assert coach.create_template()==routine
    assert len(coach.service.list('workout_routines'))==1
    sunday=week[-1]['days'][0]
    coach.configure_day(routine,'Sunday','My recovery',[],True,'Custom notes',sunday['id'])
    assert coach.service.get('workout_days',sunday['id'])['name']=='My recovery'

def test_library_selection_plan_order_replacement_and_persistence(coach):
    day=plan(coach)
    a=coach.add_exercise(day,'band-row',sets=3,reps=10,rest_seconds=75,resistance='light band',tempo='2-1-2')
    b=coach.add_exercise(day,'dead-bug')
    ids=[e['id'] for e in coach.planned(day)]
    coach.reorder(day,list(reversed(ids)))
    assert [e['id'] for e in coach.planned(day)]==list(reversed(ids))
    coach.add_exercise(day,'wall-pushup',record_id=a)
    assert coach.service.get('planned_exercises',a)['exercise']=='Wall push-up'
    with pytest.raises(ValueError):
        coach.reorder(day,[a,b])
    reopened=Database(coach.db.path)
    assert reopened.one('SELECT library_key FROM planned_exercises WHERE id=?',(b,))['library_key']=='dead-bug'
    reopened.close()

def test_invalid_plan_input_does_not_partially_write(coach):
    day=plan(coach)
    before=coach.planned(day)
    with pytest.raises(ValueError):
        coach.add_exercise(day,'squat',rest_seconds=-1)
    assert coach.planned(day)==before

def test_finish_idempotent_actual_sets_and_restart(coach):
    day=plan(coach)
    rid=coach.start(day)
    assert coach.start(day)==rid
    session=coach.session(rid)
    with pytest.raises(ValueError,match='Log actual'):
        coach.finish(rid)
    first=session['exercises'][0]
    coach.save_set(first['id'],1,8,resistance='bodyweight',variation='wall',rir=3)
    coach.save_set(first['id'],1,9,resistance='bodyweight',variation='wall',rir=2)
    for exercise in session['exercises'][1:]:
        coach.skip(exercise['id'],'Recovery priority today')
    summary=coach.finish(rid,'Felt comfortable')
    assert summary['completed_sets']==1 and summary['total_reps']==9
    assert summary['skipped_exercises']==len(session['exercises'])-1
    rows=coach.db.query('SELECT * FROM fitness_sets')
    assert coach.finish(rid,'Duplicate click')==summary
    assert coach.db.query('SELECT * FROM fitness_sets')==rows
    assert coach.db.one('SELECT review FROM fitness_sessions WHERE workout_id=?',(rid,))['review']=='Felt comfortable'
    reopened=Database(coach.db.path)
    assert reopened.one('SELECT status FROM workouts WHERE id=?',(rid,))['status']=='Completed'
    assert reopened.one('SELECT COUNT(*) n FROM fitness_sessions')['n']==1
    reopened.close()

@pytest.mark.parametrize('report,mode',[
    ({'pain':'Yes'},'Recovery'),({'fatigue':9},'Recovery'),({'sleep_hours':3},'Recovery'),
    ({'soreness':6},'Reduced'),({'energy':2},'Reduced'),({'sleep_hours':8,'energy':4},'Normal')])
def test_readiness_safely_reduces_workload(report,mode):
    assert readiness(report)['recommendation']==mode

def test_pain_blocks_normal_and_recovery_never_prescribes_training(coach):
    day=plan(coach)
    with pytest.raises(ValueError,match='Recovery'):
        coach.start(day,reported={'pain':'Yes'})
    rid=coach.start(day,reported={'pain':'Yes'},mode='Recovery')
    assert coach.session(rid)['exercises']==[]
    assert coach.finish(rid)['status']=='Recovery'

def test_strength_comparisons_require_same_setup(coach):
    day=plan(coach)
    yesterday=(date.today()-timedelta(days=7)).isoformat()
    complete(coach,day,yesterday,8)
    complete(coach,day,date.today().isoformat(),9)
    result=coach.strength('wall-pushup')
    assert result['rep_change']==2
    assert 'one repetition' in result['recommendation']
    latest=coach.session(coach.start(day))['exercises'][0]
    coach.save_set(latest['id'],1,9,weight_kg=2)
    assert coach.strength('wall-pushup')['rep_change'] is None

def test_missing_data_not_fabricated_and_nutrition_uses_logged_totals(coach):
    today=date.today().isoformat()
    start=(date.today()-timedelta(days=6)).isoformat()
    report=coach.nutrition_review(start,today)
    assert report['logged_days']==0 and report['missing_days']==7
    assert coach.body_trend(start,today)['change_kg'] is None
    assert coach.strength('pullup')['rep_change'] is None
    food=next(f for f in coach.service.list('foods') if f['name']=='Egg, whole, boiled')
    coach.service.log_food(food['id'],100,'g',today,'Breakfast')
    report=coach.nutrition_review(start,today)
    assert report['calories']==155 and report['protein']==12.58
    assert report['logged_days']==1 and report['missing_days']==6

def test_weight_daily_average_and_calculated_change(coach):
    before=(date.today()-timedelta(days=7)).isoformat()
    today=date.today().isoformat()
    coach.service.save('measurements',dict(date=before,weight_kg=70,arm_cm=30))
    coach.service.save('measurements',dict(date=today,weight_kg=71))
    coach.service.save('measurements',dict(date=today,weight_kg=72))
    report=coach.body_trend(before,today)
    assert report['change_kg']==1.5
    assert report['weight_points'][-1]['entries']==2

def test_preferences_and_custom_muscles_and_diet(coach):
    coach.save_preferences(dict(diet='Vegan',custom_muscles=['My custom group'],restrictions='peanut',meals=4,budget='Low'))
    assert 'My custom group' in coach.muscles('custom')
    assert not any('egg' in f['name'].lower() for f in coach.meal_suggestions())
    key=coach.custom_exercise('My gentle movement',['My custom group'],['Bodyweight'],'Comfortable range')
    assert coach.library(muscle='My custom group')[0]['key']==key
    with pytest.raises(ValueError,match='already exists'):
        coach.custom_exercise('My gentle movement',['Chest'],[],'Repeat')

def test_fitness_progress_review_bounded_no_learning_or_photo_contents(coach):
    day=plan(coach)
    complete(coach,day,date.today().isoformat())
    context=coach.progress_review()
    assert context['kind']=='fitness_coach'
    assert context['strength'][0]['points']
    assert 'paths' not in context
    assert context['date_range'][1]==date.today().isoformat()
    assert len(json.dumps(context))<15000
    assert all('key' in e for e in context['available_exercises'])

def test_v1_migration_preserves_original_rows_and_old_backup_restore(tmp_path):
    legacy=tmp_path/'v1.sqlite3'
    schema=(Path(__file__).parents[1]/'lifeos'/'schema.sql').read_text()
    with sqlite3.connect(legacy) as conn:
        conn.executescript(schema+'\nPRAGMA user_version=1;')
        conn.execute("INSERT INTO workout_routines(id,name) VALUES(17,'Keep routine')")
        conn.execute("INSERT INTO measurements(id,date,weight_kg,notes) VALUES(9,'2026-10-01',72,'Keep notes')")
    original=legacy.read_bytes()
    db=Database(tmp_path/'current.sqlite3')
    db.restore(legacy)
    assert db.one('SELECT name FROM workout_routines WHERE id=17')['name']=='Keep routine'
    assert db.one('SELECT notes,weight_kg FROM measurements WHERE id=9')==dict(notes='Keep notes',weight_kg=72)
    assert db.one('PRAGMA user_version')['user_version']==2
    assert legacy.read_bytes()==original
    assert db.query('PRAGMA foreign_key_check')==[]
    db.close()

def test_set_volume_is_exact_for_unequal_reps_and_loads(coach):
    from lifeos.analytics import Analytics
    day=plan(coach)
    rid=coach.start(day)
    items=coach.session(rid)['exercises']
    coach.save_set(items[0]['id'],1,10,weight_kg=5)
    coach.save_set(items[0]['id'],2,7,weight_kg=10)
    for e in items[1:]:
        coach.skip(e['id'],'Not performed')
    coach.finish(rid)
    today=date.today().isoformat()
    row=next(r for r in Analytics(coach.db).breakdowns(today,today)['strength'] if r['exercise']==items[0]['exercise'])
    assert row['volume']==120

def test_weekly_comparison_and_possible_plateau_need_comparable_dates(coach):
    day=plan(coach)
    for offset in (12,8,1):
        complete(coach,day,(date.today()-timedelta(days=offset)).isoformat(),8)
    result=coach.strength('wall-pushup')
    assert result['possible_plateau'] is True
    assert result['weekly_comparison']['change']==0

def test_future_actual_session_and_empty_training_are_rejected(coach):
    day=plan(coach)
    with pytest.raises(ValueError,match='advance'):
        coach.start(day,(date.today()+timedelta(days=1)).isoformat())
    for item in coach.planned(day):
        coach.service.delete('planned_exercises',item['id'])
    with pytest.raises(ValueError,match='Add exercises'):
        coach.start(day)
    assert coach.db.query('SELECT * FROM fitness_sessions')==[]

def test_fitness_review_and_tracking_work_offline(coach,monkeypatch):
    import socket
    import subprocess
    def forbidden(*args,**kwargs):
        pytest.fail('A local progress review must not connect to a provider or run a model')
    monkeypatch.setattr(socket.socket,'connect',forbidden)
    monkeypatch.setattr(subprocess,'run',forbidden)
    day=plan(coach)
    before=coach.db.conn.total_changes
    report=coach.progress_review()
    assert report['strength']==[]
    text=coach.review_text()
    assert 'Not enough measurements' in text and '30 days missing' in text
    assert coach.db.conn.total_changes==before
    rid=complete(coach,day,date.today().isoformat())
    assert coach.session(rid)['status']=='Completed'
    assert coach.progress_review()['workout_totals']['completed']==1
    assert '1 completed workouts' in coach.review_text()


def test_equipment_required_before_start_and_legacy_history_is_separate(coach):
    day=plan(coach)
    coach.add_exercise(day,'pullup')
    with pytest.raises(ValueError,match='equipment'):
        coach.start(day)
    rid=coach.service.save('workouts',dict(name='Older workout',status='Completed'))
    coach.service.save('exercise_logs',dict(workout_id=rid,exercise='Wall push-up',sets=3,reps=8))
    result=coach.strength('wall-pushup')
    assert len(result['legacy_aggregate_points'])==1
    assert result['points']==[] and result['rep_change'] is None

def test_large_fitness_review_is_bounded_and_unknown_targets_are_not_achievements(coach):
    day=plan(coach)
    for i in range(15):
        on=(date.today()-timedelta(days=i)).isoformat()
        rid=complete(coach,day,on)
        coach.db.execute('UPDATE fitness_sessions SET review=? WHERE workout_id=?',('Long note '*300,rid))
    context=coach.progress_review()
    assert len(json.dumps(context,ensure_ascii=False))<=8500
    assert context['nutrition']['days']==30

def test_session_metadata_corrections_preserve_status_and_routine_links(coach):
    day=plan(coach)
    rid=complete(coach,day,date.today().isoformat())
    row=coach.service.get('workouts',rid)
    row['name']='Corrected session title'
    row['date']=(date.today()-timedelta(days=1)).isoformat()
    coach.service.save('workouts',row,rid)
    assert coach.session(rid)['coaching']['session_date']==row['date']
    row['status']='Planned'
    with pytest.raises(ValueError,match='Finish Workout'):
        coach.service.save('workouts',row,rid)
    assert coach.service.get('workouts',rid)['status']=='Completed'

def test_deleting_incorrect_sets_recalculates_real_totals(coach):
    day=plan(coach)
    rid=complete(coach,day,date.today().isoformat())
    sets=coach.db.query('SELECT id FROM fitness_sets ORDER BY id')
    before=coach.session_summary(rid)['completed_sets']
    coach.delete_set(sets[0]['id'])
    assert coach.session_summary(rid)['completed_sets']==before-1
    for row in sets[1:]:
        coach.delete_set(row['id'])
    assert coach.session_summary(rid)['status']=='Skipped'
    item=coach.session(rid)['exercises'][0]
    coach.save_set(item['id'],1,5)
    assert coach.session_summary(rid)['status']=='Completed'
