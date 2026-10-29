from datetime import date,datetime,timedelta
import sqlite3
import pytest
from lifeos.analytics import Analytics,days_between
from lifeos.db import Database
from lifeos.service import Service

TODAY=date.today().isoformat()

def test_independence_and_date_scoping(db,service):
    for assistance in ('Independent','Hints','Copied'):
        service.save('problems',dict(name=assistance,status='Solved',solved_date=TODAY,assistance=assistance))
    service.save('problems',dict(name='unsolved'))
    totals=Analytics(db).summary(TODAY,TODAY)['dsa']
    assert totals=={'solved':3,'independent':1,'hinted':1,'copied':1}

def test_goal_history_survives_restart(db):
    db.save_settings({'calories':2100,'dsa_target':3},effective_date='2026-01-01')
    db.save_settings({'calories':2300,'dsa_target':5},effective_date='2026-02-01')
    assert db.goals_on('2026-01-10')['calories']==2100
    assert db.goals_on('2026-02-10')['dsa_target']==5
    other=Database(db.path)
    assert other.settings()['calories']==2300
    assert other.goals_on('2026-01-10')['dsa_target']==3
    other.close()

def test_analytics_respects_completed_workouts_and_unknown_nutrients(db,service):
    w=service.save('workouts',dict(name='Strength',status='Completed'))
    p=service.save('workouts',dict(name='Future plan',status='Planned'))
    service.save('exercise_logs',dict(workout_id=w,exercise='Press',weight_kg=25,sets=3,reps=8))
    service.save('exercise_logs',dict(workout_id=p,exercise='Press',weight_kg=50))
    groups=Analytics(db).breakdowns(TODAY,TODAY)
    assert groups['records'][0]['weight']==25
    assert groups['strength'][0]['volume']==600
    urad=next(f for f in service.list('foods','Black gram') if f['name'].startswith('Black gram'))
    service.log_food(urad['id'],100,'g',TODAY,'Lunch')
    totals=Analytics(db).summary(TODAY,TODAY)['nutrition']
    assert totals['calcium_mg_unknown']==1
    assert totals['calories']==341

def test_date_range_validation():
    with pytest.raises(ValueError):
        days_between('2026-02-01','2026-01-01')
    with pytest.raises(ValueError):
        days_between('1900-01-01','2026-01-01')

def test_focus_timer_pause_restart_resume_and_finish(db,service):
    rid=service.start_timer('Algorithms',25)
    before=service.active_timer()
    assert service.timer_remaining(before,datetime.fromisoformat(before['started_at'])+timedelta(seconds=60))==1440
    db.execute('UPDATE focus_sessions SET started_at=? WHERE id=?',((datetime.now()-timedelta(seconds=30)).isoformat(),rid))
    service.timer_action('pause')
    paused=service.active_timer()
    assert 1468<paused['remaining_seconds']<1471
    other=Database(db.path)
    resumed=Service(other)
    assert resumed.active_timer()['status']=='Paused'
    resumed.timer_action('resume')
    resumed.timer_action('finish')
    assert resumed.active_timer() is None
    final=resumed.get('focus_sessions',rid)
    assert final['status']=='Interrupted'
    assert .48<final['actual_minutes']<.55
    other.close()

def test_running_timer_expiry_after_restart_and_no_duplicate(service,db):
    rid=service.start_timer('Short focus',1)
    with pytest.raises(ValueError):
        service.start_timer('Second',25)
    db.execute('UPDATE focus_sessions SET started_at=? WHERE id=?',((datetime.now()-timedelta(seconds=90)).isoformat(),rid))
    assert service.timer_remaining(service.active_timer())==0
    service.timer_action('finish')
    assert service.get('focus_sessions',rid)['actual_minutes']==1
    assert service.get('focus_sessions',rid)['status']=='Completed'

def test_active_timer_cannot_be_edited_or_deleted(service):
    rid=service.start_timer('Focus',25)
    with pytest.raises(ValueError):
        service.delete('focus_sessions',rid)
    with pytest.raises(ValueError):
        service.save('focus_sessions',{'title':'Change'},rid)
