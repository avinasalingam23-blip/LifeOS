from datetime import date
import pytest
from lifeos.nutrition import calculate,parse_food_text

def food(service,term):
    return next(f for f in service.list('foods',term) if term.lower() in f['name'].lower())

def test_known_sample_foods(service):
    egg=calculate(food(service,'Egg, whole'),2,'piece')
    assert egg['grams']==100
    assert egg['calories']==155
    assert egg['protein']==pytest.approx(12.58)
    chicken=calculate(food(service,'Chicken breast, roasted'),150,'g')
    assert chicken['calories']==247.5
    assert chicken['protein']==pytest.approx(46.53)
    rice=calculate(food(service,'Rice, white, cooked'),1,'cup')
    assert rice['calories']==pytest.approx(205.4)
    milk=calculate(food(service,'Milk, whole'),250,'ml')
    assert milk['grams']==257.5
    assert milk['calories']==pytest.approx(157.075)

@pytest.mark.parametrize('text,quantity,unit,term',[
    ('2 eggs',2,'piece','egg'),('150 g chicken',150,'g','chicken'),
    ('1 cup cooked rice',1,'cup','cooked rice'),('250 ml milk',250,'ml','milk'),
    ('0.5 kg lentils',0.5,'kg','lentils')])
def test_phrase_parse(text,quantity,unit,term):
    assert parse_food_text(text)==(quantity,unit,term)

def test_ambiguous_composite_requires_clarification():
    with pytest.raises(ValueError,match='separately'):
        parse_food_text('3 idlis with sambar')

@pytest.mark.parametrize('qty',[0,-1,float('nan'),float('inf'),100001])
def test_invalid_quantity(service,qty):
    with pytest.raises(ValueError):
        calculate(food(service,'Egg'),qty,'piece')

def test_unknown_portions_and_micronutrients(service):
    chicken=food(service,'Chicken breast, raw')
    with pytest.raises(ValueError,match='Enter grams'):
        calculate(chicken,1,'cup')
    urad=food(service,'Black gram')
    assert calculate(urad,50,'g')['calcium_mg'] is None

def test_meal_snapshot_is_immutable_after_library_edit(service):
    egg=food(service,'Egg')
    logged=service.log_food(egg['id'],2,'piece',date.today().isoformat(),'Breakfast')
    egg['calories']=999
    service.save('foods',egg,egg['id'])
    assert service.get('food_logs',logged)['calories']==155
    service.delete('foods',egg['id'])
    assert service.get('food_logs',logged)['calories']==155
    assert service.get('food_logs',logged)['food_id'] is None

def test_recipe_accounts_for_oil_and_final_water_weight(service):
    rice=food(service,'Rice, white, dry')
    oil=food(service,'Olive oil')
    recipe=service.save_recipe('Rice and oil',[(rice['id'],100),(oil['id'],5)],300,serving_g=150)
    values=service.get('foods',recipe)
    assert values['calories']==pytest.approx((365+44.2)/3)
    assert calculate(values,1,'serving')['calories']==pytest.approx(204.6)
    assert values['preparation']=='Recipe'
    assert values['approximate']=='Yes'
    assert '5 g Olive oil' in values['notes']
