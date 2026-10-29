"""Offline nutrition from source-labelled composition records, never model output."""
import re
import math
from .models import NUTRIENTS

SOURCE = 'USDA FoodData Central, SR Legacy (https://fdc.nal.usda.gov/); typical composition'

# Values per 100 g; portion weights are explicit estimates and editable in the library.
# None means not supplied here, not nutrient-free. Names preserve raw/cooked distinction.
SEEDS = [
    ('Egg, whole, boiled','Cooked',50,None,None,155,12.58,1.12,10.61,0,1.12,50,1.19,124,126),
    ('Chicken breast, roasted, skinless','Cooked',None,None,None,165,31.02,0,3.57,0,0,15,1.04,74,256),
    ('Chicken breast, raw, skinless','Raw',None,None,None,120,22.5,0,2.62,0,0,5,0.37,45,334),
    ('Rice, white, cooked','Cooked',None,158,None,130,2.69,28.17,0.28,0.4,0.05,10,0.2,1,35),
    ('Rice, white, dry','Raw',None,185,None,365,7.13,80,0.66,1.3,0.12,28,0.8,5,115),
    ('Milk, whole, 3.25% fat','As sold',None,244,1.03,61,3.15,4.8,3.25,0,5.05,113,0.03,43,132),
    ('Banana, raw edible portion','Raw',118,None,None,89,1.09,22.84,0.33,2.6,12.23,5,0.26,1,358),
    ('Apple, raw with skin','Raw',182,None,None,52,0.26,13.81,0.17,2.4,10.39,6,0.12,1,107),
    ('Oats, dry','Raw',None,81,None,389,16.89,66.27,6.9,10.6,None,54,4.72,2,429),
    ('Lentils, boiled without salt','Cooked',None,198,None,116,9.02,20.13,0.38,7.9,1.8,19,3.33,2,369),
    ('Lentils, dry','Raw',None,192,None,352,24.63,63.35,1.06,10.7,2.03,35,6.51,6,677),
    ('Black gram (urad), dry','Raw',None,None,None,341,25.21,58.99,1.64,18.3,None,None,None,None,None),
    ('Chickpeas, boiled without salt','Cooked',None,164,None,164,8.86,27.42,2.59,7.6,4.8,49,2.89,7,291),
    ('Yogurt, plain whole milk','As sold',None,245,1.03,61,3.47,4.66,3.25,0,4.66,121,0.05,46,155),
    ('Olive oil','As sold',None,None,0.91,884,0,0,100,0,0,1,0.56,2,1),
    ('Butter, salted','As sold',None,None,None,717,0.85,0.06,81.11,0,0.06,24,0.02,643,24),
    ('Tomato, raw','Raw',123,180,None,18,0.88,3.89,0.2,1.2,2.63,10,0.27,5,237),
    ('Carrot, raw','Raw',61,128,None,41,0.93,9.58,0.24,2.8,4.74,33,0.3,69,320),
    ('Spinach, boiled without salt','Cooked',None,180,None,23,2.97,3.75,0.26,2.4,0.43,136,3.57,70,466),
    ('Potato, boiled without skin or salt','Cooked',None,None,None,87,1.87,20.13,0.1,1.8,0.91,5,0.31,4,379),
    ('Wheat flour, whole grain','Raw',None,120,None,340,13.21,72.57,2.5,10.7,0.41,34,3.6,5,363),
    ('Peanuts, dry roasted unsalted','As sold',None,146,None,587,24.35,21.26,49.66,8.4,4.9,58,1.58,6,634),
    ('Sugar, granulated','As sold',4,200,None,387,0,99.98,0,0,99.8,1,0.05,1,2),
]

def seed_foods(db):
    if db.one("SELECT value FROM settings WHERE key='_food_library_seeded'"):
        return
    columns = ['name','preparation','serving_g','cup_g','density',*NUTRIENTS,'source','approximate','notes']
    with db.transaction() as conn:
        for record in SEEDS:
            conn.execute(f"INSERT INTO foods ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                         (*record, SOURCE, 'Yes', 'Typical food composition; brands, edible size and cooking change values. Oil is logged separately.'))
        # Reference recipes are explicitly calculated examples, not laboratory values.
        # Users can replace them with their weighed recipe in the recipe builder.
        recipes=[
            ('Idli, reference rice + urad recipe',[(4,100),(11,40)],400,40,None),
            ('Sambar, reference lentil + vegetable recipe',[(10,50),(16,100),(17,100),(14,5)],700,None,240),
            ('Chapati, whole wheat reference recipe',[(20,100)],150,50,None),
        ]
        for name,parts,yield_g,serving,cup in recipes:
            ingredients=[]
            for index,grams in parts:
                record=SEEDS[index]
                ingredients.append((dict(zip(['name','preparation','serving_g','cup_g','density',*NUTRIENTS],record)),grams))
            nutrients=recipe_nutrients(ingredients,yield_g)
            details='; '.join(f"{grams} g {food['name']}" for food,grams in ingredients)
            values=(name,'Recipe',serving,cup,None,*[nutrients[n] for n in NUTRIENTS],
                    'Calculated reference recipe from USDA-labelled ingredients; not a measured Indian food standard','Yes',
                    f'{details}. Final cooked yield {yield_g} g. Reference approximation; actual recipes vary. Sambar spices/salt not included. Edit portions or build your own recipe.')
            conn.execute(f"INSERT INTO foods ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",values)
        conn.execute("INSERT INTO settings(key,value) VALUES ('_food_library_seeded','true')")

def grams_for(food, quantity, unit):
    quantity = float(quantity)
    if not math.isfinite(quantity) or quantity <= 0 or quantity > 100000:
        raise ValueError('Quantity must be greater than zero and at most 100,000.')
    factors = {'g':1, 'kg':1000, 'ml':food.get('density'),
               'cup':food.get('cup_g'), 'piece':food.get('serving_g'),
               'serving':food.get('serving_g'), 'oz':28.349523125,
               'tbsp':food.get('density') * 15 if food.get('density') else None,
               'tsp':food.get('density') * 5 if food.get('density') else None}
    factor = factors.get(unit)
    if not factor:
        raise ValueError(f'No reliable {unit} conversion for this food. Enter grams or set its portion weight / density in Food library.')
    return quantity * factor

def calculate(food, quantity, unit):
    grams = grams_for(food, quantity, unit)
    return {'grams':grams, **{n:None if food.get(n) is None else food[n] * grams / 100 for n in NUTRIENTS}}

def parse_food_text(text):
    """Extract quantity and food query only. The UI must confirm food/preparation."""
    if re.search(r'\b(with|and)\b|[+;]', text, re.I):
        raise ValueError('Log each component separately with a quantity, for example 3 idlis, then 150 g sambar. Add known cooking oil separately.')
    match = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(kg|grams?|g|ml|cups?|pieces?|servings?|oz|tbsp|tsp)?\s+(.+?)\s*', text, re.I)
    if not match:
        raise ValueError('Enter a quantity and food, such as 2 eggs, 150 g chicken or 1 cup cooked rice.')
    quantity, unit, query = match.groups()
    unit = (unit or 'piece').lower()
    unit = {'grams':'g','gram':'g','cups':'cup','pieces':'piece','servings':'serving'}.get(unit,unit)
    query = re.sub(r'\beggs\b','egg',query,flags=re.I)
    query = re.sub(r'\bidlis\b','idli',query,flags=re.I)
    return float(quantity),unit,query

def recipe_nutrients(ingredients, final_grams):
    """ingredients is a list of (food-record, grams), including oil where known."""
    if final_grams <= 0 or not ingredients:
        raise ValueError('Add ingredients and a positive final cooked recipe weight.')
    result = {}
    for nutrient in NUTRIENTS:
        result[nutrient] = None if any(f.get(nutrient) is None for f,g in ingredients) else sum(f[nutrient]*g/100 for f,g in ingredients)/final_grams*100
    return result
