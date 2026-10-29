from lifeos.ui.workout_view import week_completion,workout_totals


def test_week_completion_counts_finished_sessions_not_saved_plans():
    week=[dict(days=[]) for _ in range(7)]
    week[0]['days']=[dict(session=dict(finished_at='2026-10-26T10:00:00'))]
    week[1]['days']=[dict(session=None)]
    week[2]['days']=[dict(session=dict(finished_at=''))]
    week[3]['days']=[dict(session=dict(finished_at='2026-10-29T10:00:00')),dict(session=None)]
    assert week_completion(week)==(1,7)


def test_summary_uses_actual_checks_and_session_targets_after_plan_changes():
    plan=[dict(sets=3,reps=10,duration_min=0,rest_seconds=60)]
    assert workout_totals(plan)==dict(planned=1,completed=0,skipped=0,sets=3,ratio=0,minutes=4.5)
    rows=[dict(target_sets=2,target_reps=8,target_duration=0,rest_seconds=60,completion='Completed'),
          dict(target_sets=1,target_reps=0,target_duration=2,rest_seconds=0,completion='Skipped')]
    summary=workout_totals([],dict(exercises=rows))
    assert summary==dict(planned=2,completed=1,skipped=1,sets=3,ratio=.5,minutes=4.8)
    rows[0]['completion']='Planned'
    assert workout_totals(plan,dict(exercises=rows))['ratio']==0
    assert workout_totals([])['ratio']==0
