import json
import sqlite3
from copy import deepcopy
import pytest
from lifeos.db import Database
from lifeos.fitness import FitnessCoach
from lifeos.workout_checklist import WorkoutChecklist,KEY,progress


def test_free_text_targets_muscles_and_checks_persist_without_sessions(db):
    store=WorkoutChecklist(db)
    store.muscles('Monday',['Chest','Back','Chest','Abs'])
    first=store.save_target('Monday','  Push-ups  ','3 \u00d7 15')
    second=store.save_target('Tuesday','Plank','60 seconds')
    store.complete('Monday',first,True)
    store.save_target('Monday','Custom movement','')
    with sqlite3.connect(db.path) as other:
        assert other.execute('SELECT COUNT(*) FROM fitness_sessions').fetchone()[0]==0
        assert other.execute('SELECT COUNT(*) FROM fitness_sets').fetchone()[0]==0
    reopened=Database(db.path)
    saved=WorkoutChecklist(reopened).load()
    assert saved['days']['Monday']['muscles']==['Chest','Back','Abs']
    assert saved['days']['Monday']['targets'][0]==dict(id=first,name='Push-ups',goal='3 \u00d7 15',completed=True)
    assert saved['days']['Tuesday']['targets'][0]['id']==second
    assert not saved['days']['Tuesday']['targets'][0]['completed']
    assert progress(saved['days']['Monday'])==dict(completed=1,total=2,ratio=.5)
    reopened.close()


def test_rename_uncheck_move_delete_and_reset_preserve_plans_and_other_days(db):
    store=WorkoutChecklist(db);a=store.save_target('Monday','A');b=store.save_target('Monday','B','optional')
    c=store.save_target('Tuesday','C');store.complete('Tuesday',c,True)
    store.complete('Monday',a,True);store.save_target('Monday','Renamed','new goal',a)
    assert store.load()['days']['Monday']['targets'][0]['completed']
    store.complete('Monday',a,False);assert progress(store.load()['days']['Monday'])['completed']==0
    store.move('Monday',b,-1);assert [t['id'] for t in store.load()['days']['Monday']['targets']]==[b,a]
    store.complete('Monday',b,True);before=store.load()
    store.reset('Monday');after=store.load()
    expected=deepcopy(before['days']['Monday'])
    for target in expected['targets']:target['completed']=False
    assert after['days']['Monday']==expected
    assert after['days']['Tuesday']==before['days']['Tuesday']
    assert after['history'][0]['targets']==before['days']['Monday']['targets']
    store.reset('Monday');assert len(store.load()['history'])==1
    store.remove('Monday',a);assert [t['id'] for t in store.load()['days']['Monday']['targets']]==[b]
    assert len(store.load()['history'][0]['targets'])==2


def test_legacy_import_is_read_only_until_edit_and_preserves_every_original_record(service,db):
    coach=FitnessCoach(service);rid=coach.create_template()
    day=coach.weekly(rid)[0]['days'][0];session=coach.start(day['id'],coach.weekly(rid)[0]['date'])
    log=coach.session(session)['exercises'][0];coach.save_set(log['id'],1,6)
    tables=['workout_routines','workout_days','planned_exercises','workouts','exercise_logs','fitness_sets','fitness_sessions','settings']
    before={t:db.query('SELECT * FROM '+t) for t in tables}
    schema=db.query('SELECT * FROM sqlite_master ORDER BY name')
    preferences=coach.preferences()
    store=WorkoutChecklist(db);document=store.load()
    assert KEY not in store._preferences()
    assert document['days']['Monday']['targets'][0]['completed']
    assert document['days']['Monday']['targets'][0]['goal']
    assert {t:db.query('SELECT * FROM '+t) for t in tables}==before
    store.save_target('Monday','Anything I choose','As comfortable')
    store.remove('Monday',document['days']['Monday']['targets'][0]['id'])
    assert {t:db.query('SELECT * FROM '+t) for t in tables}==before
    assert db.query('SELECT * FROM sqlite_master ORDER BY name')==schema
    assert {k:v for k,v in coach.preferences().items() if k!=KEY}==preferences
    coach.save_preferences(dict(goal='Maintain fitness'))
    assert store.load()['days']['Monday']['targets'][-1]['name']=='Anything I choose'


def test_drafts_survive_reload_and_commit_clears_them(db):
    store=WorkoutChecklist(db);store.editor('Wednesday','Squats','3 x 20')
    assert WorkoutChecklist(db).load()['days']['Wednesday']['editor']['goal']=='3 x 20'
    rid=store.save_target('Wednesday','Squats','3 x 20')
    assert 'editor' not in store.load()['days']['Wednesday']
    store.editor('Wednesday','Squat hold','30 seconds',rid)
    store.save_target('Wednesday','Squat hold','30 seconds',rid)
    assert len(store.load()['days']['Wednesday']['targets'])==1


def test_validation_rolls_back_and_never_replaces_unknown_saved_document(db):
    store=WorkoutChecklist(db)
    with pytest.raises(ValueError):store.save_target('Monday','   ')
    with pytest.raises(ValueError):store.save_target('Unknown','Target')
    rid=store.save_target('Monday','A')
    before=store.load()
    for action in [lambda:store.complete('Tuesday',rid,True),lambda:store.remove('Tuesday',rid),lambda:store.move('Monday',rid,3),lambda:store.complete('Monday',rid,'yes')]:
        with pytest.raises(ValueError):action()
        assert store.load()==before
    raw=json.dumps({KEY:dict(version=99)})
    db.execute('UPDATE fitness_preferences SET values_json=? WHERE id=1',(raw,))
    with pytest.raises(ValueError):store.save_target('Monday','B')
    assert db.one('SELECT values_json FROM fitness_preferences')['values_json']==raw


def test_independent_connections_keep_each_others_targets_and_preferences(db):
    a=WorkoutChecklist(db);a.save_target('Monday','First')
    other=Database(db.path)
    WorkoutChecklist(other).save_target('Monday','Second')
    a.muscles('Tuesday',['Legs'])
    assert [t['name'] for t in a.load()['days']['Monday']['targets']]==['First','Second']
    assert WorkoutChecklist(other).load()['days']['Tuesday']['muscles']==['Legs']
    other.close()


def test_free_text_checkmarks_are_not_measured_strength_or_report_context(service,db):
    store=WorkoutChecklist(db);rid=store.save_target('Monday','Push-ups','A personal goal')
    store.complete('Monday',rid,True)
    report=FitnessCoach(service).progress_review()
    assert KEY not in report['preferences']
    assert report['workout_totals']['completed']==0 and report['strength']==[]
    assert store.load()['days']['Monday']['targets'][0]['completed']
