"""Exact date-scoped aggregates used by the dashboard, charts and progress reviews."""
from datetime import date, timedelta
from .models import NUTRIENTS

def days_between(start,end):
    first,last=date.fromisoformat(start),date.fromisoformat(end)
    if first>last or (last-first).days>3660:
        raise ValueError('Choose an ordered date range of at most ten years.')
    return [(first+timedelta(days=i)).isoformat() for i in range((last-first).days+1)]

class Analytics:
    def __init__(self,db):
        self.db=db

    def summary(self,start,end):
        days_between(start,end)
        params=(start,end)
        dsa=self.db.one("""SELECT COUNT(*) solved, COALESCE(SUM(assistance='Independent'),0) independent,
            COALESCE(SUM(assistance='Hints'),0) hinted, COALESCE(SUM(assistance='Copied'),0) copied
            FROM problems WHERE solved_date BETWEEN ? AND ? AND status IN ('Solved','Revised','Revision due')""",params)
        study=self.db.one('SELECT COALESCE(SUM(minutes),0) actual,COALESCE(SUM(planned_minutes),0) planned FROM study_sessions WHERE date BETWEEN ? AND ?',params)
        workouts=self.db.one("SELECT COUNT(*) total,COALESCE(SUM(status='Completed'),0) completed,COALESCE(SUM(status='Recovery'),0) recovery FROM workouts WHERE date BETWEEN ? AND ?",params)
        tasks=self.db.one("SELECT COUNT(*) total,COALESCE(SUM(status='Completed'),0) completed,COALESCE(SUM(planned_minutes),0) planned,COALESCE(SUM(actual_minutes),0) actual FROM tasks WHERE date BETWEEN ? AND ?",params)
        focus=self.db.one("SELECT COUNT(*) total,COALESCE(SUM(actual_minutes),0) actual,COALESCE(SUM(planned_minutes),0) planned FROM focus_sessions WHERE date BETWEEN ? AND ? AND status IN ('Completed','Interrupted')",params)
        food=self.db.one('SELECT COUNT(*) entries,'+','.join(f'COALESCE(SUM({n}),0) {n},SUM({n} IS NULL) {n}_unknown' for n in NUTRIENTS)+' FROM food_logs WHERE date BETWEEN ? AND ?',params)
        water=self.db.one('SELECT COALESCE(SUM(ml),0) ml FROM water_logs WHERE date BETWEEN ? AND ?',params)
        concepts=self.db.query('SELECT status,COUNT(*) count FROM concepts GROUP BY status')
        due=self.db.query("SELECT c.*,p.name subject FROM concepts c JOIN paths p ON p.id=c.path_id WHERE (c.revision_date!='' AND c.revision_date<=?) OR c.status='Revision due' ORDER BY c.revision_date",(end,))
        revisions=self.db.query("SELECT * FROM problems WHERE (revision_date!='' AND revision_date<=?) OR status='Revision due' ORDER BY revision_date",(end,))
        return dict(dsa=dsa,study=study,workouts=workouts,tasks=tasks,focus=focus,nutrition=food,water=water,
                    concept_status=concepts,concept_revisions=due,dsa_revisions=revisions)

    def daily(self,start,end):
        dates=days_between(start,end)
        dsa={r['date']:r for r in self.db.query("SELECT solved_date date,COUNT(*) solved,SUM(assistance='Independent') independent FROM problems WHERE solved_date BETWEEN ? AND ? AND status IN ('Solved','Revised','Revision due') GROUP BY solved_date",(start,end))}
        food={r['date']:r for r in self.db.query('SELECT date,'+','.join(f'SUM({n}) {n}' for n in NUTRIENTS)+' FROM food_logs WHERE date BETWEEN ? AND ? GROUP BY date',(start,end))}
        water={r['date']:r['ml'] for r in self.db.query('SELECT date,SUM(ml) ml FROM water_logs WHERE date BETWEEN ? AND ? GROUP BY date',(start,end))}
        tasks={r['date']:r for r in self.db.query("SELECT date,COUNT(*) total,SUM(status='Completed') completed FROM tasks WHERE date BETWEEN ? AND ? GROUP BY date",(start,end))}
        focus={r['date']:r for r in self.db.query("SELECT date,SUM(actual_minutes) actual,SUM(planned_minutes) planned FROM focus_sessions WHERE date BETWEEN ? AND ? AND status IN ('Completed','Interrupted') GROUP BY date",(start,end))}
        return [dict(date=d,dsa=dsa.get(d,{'solved':0,'independent':0}),nutrition=food.get(d,{n:0 for n in NUTRIENTS}),
                     water=water.get(d,0),tasks=tasks.get(d,{'total':0,'completed':0}),focus=focus.get(d,{'actual':0,'planned':0}),
                     goals=self.db.goals_on(d)) for d in dates]

    def breakdowns(self,start,end):
        days_between(start,end)
        p=(start,end)
        return {
            'topics':self.db.query("SELECT COALESCE(NULLIF(topic,''),'Unspecified') name,COUNT(*) count FROM problems WHERE solved_date BETWEEN ? AND ? AND status IN ('Solved','Revised','Revision due') GROUP BY topic",p),
            'difficulty':self.db.query("SELECT difficulty name,COUNT(*) count FROM problems WHERE solved_date BETWEEN ? AND ? AND status IN ('Solved','Revised','Revision due') GROUP BY difficulty",p),
            'subjects':self.db.query('SELECT p.name,SUM(s.minutes) actual,SUM(s.planned_minutes) planned FROM study_sessions s JOIN paths p ON p.id=s.path_id WHERE s.date BETWEEN ? AND ? GROUP BY p.id',p),
            'workouts':self.db.query("SELECT date,COUNT(*) count FROM workouts WHERE date BETWEEN ? AND ? AND status='Completed' GROUP BY date ORDER BY date",p),
            'strength':self.db.query("SELECT e.exercise,w.date,MAX(e.weight_kg) weight,SUM(CASE WHEN EXISTS(SELECT 1 FROM fitness_sessions fs WHERE fs.workout_id=w.id) THEN (SELECT COALESCE(SUM(s.weight_kg*s.reps),0) FROM fitness_sets s WHERE s.exercise_log_id=e.id) ELSE e.weight_kg*e.sets*e.reps END) volume,MAX(e.distance_km) distance FROM exercise_logs e JOIN workouts w ON w.id=e.workout_id WHERE w.date BETWEEN ? AND ? AND w.status='Completed' GROUP BY e.exercise,w.date ORDER BY w.date",p),
            'records':self.db.query("SELECT e.exercise,MAX(e.weight_kg) weight,MAX(e.reps) reps,MAX(e.distance_km) distance,MAX(e.duration_min) duration FROM exercise_logs e JOIN workouts w ON w.id=e.workout_id WHERE w.date BETWEEN ? AND ? AND w.status='Completed' GROUP BY e.exercise",p),
            'weight':self.db.query('SELECT date,AVG(weight_kg) weight FROM measurements WHERE date BETWEEN ? AND ? GROUP BY date ORDER BY date',p),
        }

    def dashboard(self,on_date=None):
        day=on_date or date.today().isoformat()
        start=(date.fromisoformat(day)-timedelta(days=6)).isoformat()
        return dict(today=self.summary(day,day),week=self.summary(start,day),goals=self.db.goals_on(day),
            tasks=self.db.query("SELECT * FROM tasks WHERE date<=? AND status NOT IN ('Completed','Skipped') ORDER BY CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END,date LIMIT 8",(day,)),
            paths=self.db.query("SELECT * FROM paths WHERE status!='Understood' ORDER BY CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END LIMIT 6"),
            workouts=self.db.query('SELECT * FROM workouts WHERE date=? ORDER BY id',(day,)))
