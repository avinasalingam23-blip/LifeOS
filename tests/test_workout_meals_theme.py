from datetime import date,timedelta
import json
import pytest
from lifeos.db import Database
from lifeos.fitness import FitnessCoach
from lifeos.ui import appearance

def test_checkbox_requires_real_sets_and_keeps_performance_on_uncheck(service,db):
    coach=FitnessCoach(service);routine=coach.create_template();day=coach.weekly(routine)[0]['days'][0]
    rid=coach.start(day['id']);exercise=coach.session(rid)['exercises'][0]
    with pytest.raises(ValueError,match='actual sets'):coach.set_exercise_completed(exercise['id'],True)
    coach.save_set(exercise['id'],1,7)
    saved=db.query('SELECT * FROM fitness_sets')
    coach.set_exercise_completed(exercise['id'],False)
    assert coach.session(rid)['exercises'][0]['completion']=='Planned'
    assert db.query('SELECT * FROM fitness_sets')==saved
    with pytest.raises(ValueError):coach.finish(rid)
    coach.set_exercise_completed(exercise['id'],True)
    assert coach.session_summary(rid)['completed_exercises']==1

def test_plan_edits_do_not_change_dated_session_snapshot(service,db):
    coach=FitnessCoach(service);routine=coach.create_template();day=coach.weekly(routine)[0]['days'][0]
    rid=coach.start(day['id']);before=coach.session(rid)
    item=coach.planned(day['id'])[0]
    coach.add_exercise(day['id'],'squat',sets=4,reps=15,weight_kg=5,record_id=item['id'])
    coach.configure_day(routine,'Monday','Future rest',['Back','Biceps'],True,day_id=day['id'])
    assert coach.session(rid)==before
    reopened=Database(db.path)
    assert reopened.one('SELECT name FROM workout_days WHERE id=?',(day['id'],))['name']=='Future rest'
    assert reopened.one('SELECT exercise FROM exercise_logs WHERE id=?',(before['exercises'][0]['id'],))['exercise']==before['exercises'][0]['exercise']
    reopened.close()

def test_meals_separate_date_type_edit_remove_and_restart(service,db):
    food=next(f for f in service.list('foods') if f['name']=='Egg, whole, boiled')
    today=date.today().isoformat();yesterday=(date.today()-timedelta(days=1)).isoformat()
    breakfast=service.log_food(food['id'],100,'g',today,'Breakfast')
    lunch=service.log_food(food['id'],50,'g',today,'Lunch')
    service.log_food(food['id'],200,'g',yesterday,'Dinner')
    report=service.meal_day(today)
    assert list(report['meals'])==['Breakfast','Lunch','Snacks','Dinner']
    assert report['calories']==232.5 and report['protein']==pytest.approx(18.87)
    service.log_food(food['id'],150,'g',today,'Snacks',record_id=lunch)
    assert not service.meal_day(today)['meals']['Lunch']['entries']
    assert service.meal_day(today)['meals']['Snacks']['entries'][0]['quantity']==150
    service.delete('food_logs',breakfast)
    assert service.meal_day(today)['calories']==232.5
    assert service.meal_day(yesterday)['calories']==310
    reopened=Database(db.path)
    assert reopened.one('SELECT COUNT(*) n FROM food_logs')['n']==2
    reopened.close()

def test_terminal_palette_and_original_glass_round_trip():
    from lifeos.ui.glass import composite_glass
    from PIL import Image
    original=appearance.current()
    try:
        appearance.select(appearance.CURRENT)
        source=Image.new('RGB',(80,80),'#aaaaaa')
        before=composite_glass(source,(5,5,75,75))
        appearance.select(appearance.COMMAND)
        assert appearance.palette()==dict(bg='#090B0A',panel='#111713',secondary='#151D18',accent='#70F0A1',
            amber='#D6A85D',text='#E7EEE9',muted='#91A096',border='#2A3B30')
        assert appearance.color('#141414')=='#111713'
        assert composite_glass(source,(5,5,75,75)).getpixel((40,40))==(17,23,19)
        appearance.select(appearance.CURRENT)
        assert composite_glass(source,(5,5,75,75)).tobytes()==before.tobytes()
        with pytest.raises(ValueError):appearance.select('Unsupported theme')
    finally:appearance.select(original)

def test_theme_setting_persists_without_changing_records(service,db):
    rid=service.save('tasks',dict(title='Keep my saved task'))
    previous=db.query('SELECT * FROM goal_history')
    db.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',('theme',json.dumps(appearance.COMMAND)))
    reopened=Database(db.path)
    assert reopened.settings()['theme']==appearance.COMMAND
    assert reopened.one('SELECT title FROM tasks WHERE id=?',(rid,))['title']=='Keep my saved task'
    assert reopened.query('SELECT * FROM goal_history')==previous
    reopened.close()

def test_revision_detects_another_connection_without_changing_rows(db):
    import sqlite3
    before=db.revision()
    with sqlite3.connect(db.path) as other:
        other.execute("INSERT INTO tasks(title,date) VALUES('External saved task',?)",(date.today().isoformat(),))
    after=db.revision()
    assert before[0]==after[0] and before[1]!=after[1]
