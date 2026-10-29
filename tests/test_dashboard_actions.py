from types import SimpleNamespace
from lifeos.ui.dashboard import Dashboard

def test_dashboard_checkbox_writes_and_reverses_actual_task_status(service):
    rid=service.save('tasks',{'title':'Review a concept'})
    refreshed=[]
    board=SimpleNamespace(app=SimpleNamespace(service=service),refresh_data=lambda:refreshed.append(True))
    original=service.get('tasks',rid)
    Dashboard.toggle_task(board,original)
    assert service.get('tasks',rid)['status']=='Completed'
    assert original['status']=='To do'
    Dashboard.toggle_task(board,service.get('tasks',rid))
    assert service.get('tasks',rid)['status']=='To do'
    assert len(refreshed)==2

def test_focus_card_uses_the_same_duration_for_display_and_start(service,db):
    app=SimpleNamespace(service=service,db=db,timer_minutes=SimpleNamespace(get=lambda:'12'),timer_title=SimpleNamespace(get=lambda:'Practice'))
    board=SimpleNamespace(app=app,draw=lambda:None)
    board.configured_duration=lambda:Dashboard.configured_duration(board)
    assert board.configured_duration()==12
    Dashboard.focus_toggle(board)
    assert service.active_timer()['planned_minutes']==12
    Dashboard.focus_toggle(board)
    assert service.active_timer()['status']=='Paused'
    Dashboard.focus_toggle(board)
    assert service.active_timer()['status']=='Running'
