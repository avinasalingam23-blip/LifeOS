from .lifecycle import Textbox
from .scrolling import ScrollFrame
from datetime import date
from tkinter import messagebox
import customtkinter as ctk
from ..nutrition import parse_food_text,calculate
from ..models import NUTRIENTS
from .common import BG,PANEL,CARD,TEXT,MUTED,ACCENT,Dialog,button,label,safe
from .theme import BORDER,INPUT
from .collections import GlassTabs
from .charts import GlassPlot,style_axes

class FoodDialog(Dialog):
    def __init__(self,parent,app,record=None,on_save=None,selected_date=None,meal_type=None):
        super().__init__(parent,'Food logger',820,790)
        self.app,self.record,self.on_save=app,record,on_save
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(1,weight=1)
        label(self,'Food logger',26).grid(row=0,column=0,sticky='w',padx=24,pady=(20,10))
        body=ScrollFrame(self,fg_color=PANEL,corner_radius=18,border_width=1,border_color=BORDER)
        body.grid(row=1,column=0,sticky='nsew',padx=20)
        body.grid_columnconfigure(0,weight=1)
        label(body,'Use a phrase, then confirm the exact food and preparation.',13,MUTED).grid(row=0,column=0,sticky='w',padx=12,pady=(10,4))
        self.phrase=ctk.CTkEntry(body,placeholder_text='2 eggs · 150 g chicken · 1 cup cooked rice · 250 ml milk',height=38)
        self.phrase.grid(row=1,column=0,sticky='ew',padx=12,pady=5)
        self.phrase.bind('<Return>',lambda e:self.lookup())
        button(body,'Find food / parse quantity',self.lookup,width=220).grid(row=2,column=0,sticky='w',padx=12,pady=5)
        self.status=label(body,'Offline food library · No personal records are sent online.',12,ACCENT,wraplength=700,justify='left')
        self.status.grid(row=3,column=0,sticky='w',padx=12,pady=6)
        label(body,'Exact food * · Raw and cooked weights differ',13,MUTED).grid(row=4,column=0,sticky='w',padx=12)
        self.foods=app.service.list('foods')
        self.food_map={app.service.label('foods',f):f for f in self.foods}
        self.food=ctk.CTkOptionMenu(body,values=['— Select food —']+list(self.food_map),dynamic_resizing=False,command=lambda v:self.preview())
        self.food.grid(row=5,column=0,sticky='ew',padx=12,pady=5)
        fields=ctk.CTkFrame(body,fg_color='transparent')
        fields.grid(row=6,column=0,sticky='ew',padx=12,pady=6)
        for i in range(4):
            fields.grid_columnconfigure(i,weight=1)
        self.quantity=self.entry(fields,'Quantity *',0,record['quantity'] if record else '1')
        label(fields,'Unit *',12,MUTED).grid(row=0,column=1,sticky='w',padx=5)
        self.unit=ctk.CTkOptionMenu(fields,values=['g','kg','ml','cup','piece','serving','oz','tbsp','tsp'],width=120,command=lambda v:self.preview())
        self.unit.grid(row=1,column=1,padx=5,sticky='ew')
        self.unit.set(record['unit'] if record else 'g')
        self.day=self.entry(fields,'Date * (YYYY-MM-DD)',2,record['date'] if record else date.today().isoformat())
        label(fields,'Meal *',12,MUTED).grid(row=0,column=3,sticky='w',padx=5)
        self.meal=ctk.CTkOptionMenu(fields,values=['Breakfast','Lunch','Dinner','Snacks'],width=130)
        self.meal.grid(row=1,column=3,sticky='ew',padx=5)
        self.meal.set(record['meal'] if record else 'Breakfast')
        if not record:
            if selected_date:
                self.day.delete(0,'end')
                self.day.insert(0,selected_date)
            if meal_type: self.meal.set(meal_type)
        self.quantity.bind('<KeyRelease>',lambda e:self.preview(quiet=True))
        self.preview_label=label(body,'Choose a food to preview calculated nutrition.',14,TEXT,justify='left',anchor='w',wraplength=690)
        self.preview_label.grid(row=7,column=0,sticky='ew',padx=14,pady=15)
        label(body,'Notes / known preparation / additional ingredients',12,MUTED).grid(row=8,column=0,sticky='w',padx=12)
        self.notes=Textbox(body,height=85,fg_color=INPUT)
        self.notes.grid(row=9,column=0,sticky='ew',padx=12,pady=5)
        self.notes.insert('1.0',record['notes'] if record else '')
        label(body,'Add cooking oil as a separate food, or include it in a weighed recipe.\nMissing food? Add it to Food library or use Build recipe.\nEditing a meal recalculates nutrients using the current library values.',12,MUTED,justify='left',wraplength=690).grid(row=10,column=0,sticky='w',padx=12,pady=12)
        footer=ctk.CTkFrame(self,fg_color='transparent')
        footer.grid(row=2,column=0,sticky='ew',padx=20,pady=14)
        button(footer,'Cancel',self.destroy,True,width=100).pack(side='right',padx=4)
        button(footer,'Save food entry',self.save,width=150).pack(side='right',padx=4)
        if record:
            selected=next((name for name,f in self.food_map.items() if f['id']==record['food_id']),None)
            if selected:
                self.food.set(selected)
                self.preview(quiet=True)

    @staticmethod
    def entry(parent,name,col,value):
        label(parent,name,12,MUTED).grid(row=0,column=col,sticky='w',padx=5)
        entry=ctk.CTkEntry(parent,width=120,height=34)
        entry.grid(row=1,column=col,sticky='ew',padx=5)
        entry.insert(0,str(value))
        return entry

    def lookup(self):
        def action():
            quantity,unit,query=parse_food_text(self.phrase.get())
            self.quantity.delete(0,'end')
            self.quantity.insert(0,str(quantity))
            self.unit.set(unit)
            terms=[w for w in query.lower().replace(',',' ').split() if w not in ('of','a','an')]
            matches={name:f for name,f in self.food_map.items() if all(term in (f['name']+' '+f['preparation']).lower() for term in terms)}
            self.food.configure(values=['— Select food —']+list(matches or self.food_map))
            self.food.set('— Select food —')
            if matches:
                self.status.configure(text=f'{len(matches)} matching food(s). Choose the exact food below and confirm the portion size.')
            else:
                self.status.configure(text='No exact match. Choose a verified equivalent, add a custom food, or build a recipe. No nutrition has been guessed.')
            self.preview_label.configure(text='Confirm a food to calculate nutrition.')
        safe(self,action)

    def preview(self,quiet=False):
        food=self.food_map.get(self.food.get())
        if not food:
            return
        try:
            values=calculate(food,float(self.quantity.get()),self.unit.get())
            lines=[f"{food['name']} · {values['grams']:.1f} g · {'Approximate' if food['approximate']=='Yes' else 'Source-labelled'}",
                f"{values['calories']:.0f} kcal  |  Protein {values['protein']:.1f} g  |  Carbs {values['carbs']:.1f} g  |  Fat {values['fat']:.1f} g"]
            if self.app.db.settings()['nutrition_mode']=='Detailed':
                lines.append(' · '.join(f"{n.replace('_',' ')}: {'unknown' if values[n] is None else format(values[n],'.1f')}" for n in NUTRIENTS[4:]))
            if self.unit.get() in ('piece','cup','serving','ml','tbsp','tsp'):
                lines.append('Portion conversion uses the editable library weight or density. Weigh food for better accuracy.')
            lines.append('Source: '+food['source'])
            self.preview_label.configure(text='\n\n'.join(lines))
        except (ValueError,TypeError) as error:
            self.preview_label.configure(text=str(error))

    def save(self):
        def action():
            food=self.food_map.get(self.food.get())
            if not food:
                raise ValueError('Select the exact food and preparation before saving.')
            self.app.service.log_food(food['id'],float(self.quantity.get()),self.unit.get(),self.day.get(),self.meal.get(),self.notes.get('1.0','end-1c'),self.record['id'] if self.record else None)
            if self.on_save:
                self.on_save()
            self.app.notice('Food and calculated nutrient snapshot saved.')
            self.destroy()
        safe(self,action)

class RecipeDialog(Dialog):
    def __init__(self,parent,app,on_save):
        super().__init__(parent,'Recipe builder',800,710)
        self.app,self.on_save,self.ingredients=app,on_save,[]
        body=ScrollFrame(self,fg_color=PANEL,corner_radius=18,border_width=1,border_color=BORDER)
        body.pack(fill='both',expand=True,padx=20,pady=20)
        body.grid_columnconfigure(0,weight=1)
        label(body,'Build a weighed recipe',24).grid(row=0,column=0,sticky='w',pady=8)
        label(body,'Combine source-labelled ingredients, including oil. Enter final cooked weight to account for water gained or lost.\nUse this for idli, sambar, chapati, dal and homemade meals.',12,MUTED,justify='left',wraplength=680).grid(row=1,column=0,sticky='w',pady=8)
        self.name=self.add_entry(body,'Recipe name *',2)
        self.yield_g=self.add_entry(body,'Final cooked recipe weight (g) *',4)
        self.serving=self.add_entry(body,'One piece / serving weight (g), optional',6)
        self.cup=self.add_entry(body,'One cup weight (g), optional',8)
        food_map={app.service.label('foods',f):f['id'] for f in app.service.list('foods')}
        self.food_map=food_map
        self.food=ctk.CTkOptionMenu(body,values=['— Select ingredient —']+list(food_map),dynamic_resizing=False)
        self.food.grid(row=10,column=0,sticky='ew',pady=(15,5))
        self.grams=ctk.CTkEntry(body,placeholder_text='Ingredient weight in grams')
        self.grams.grid(row=11,column=0,sticky='ew',pady=5)
        button(body,'Add ingredient',self.add_ingredient,width=150).grid(row=12,column=0,sticky='w',pady=5)
        self.items=label(body,'No ingredients yet.',12,TEXT,justify='left',wraplength=680)
        self.items.grid(row=13,column=0,sticky='w',pady=8)
        button(body,'Remove last ingredient',self.remove_ingredient,True,width=180).grid(row=14,column=0,sticky='w',pady=5)
        footer=ctk.CTkFrame(self,fg_color='transparent')
        footer.pack(fill='x',padx=20,pady=(0,15))
        button(footer,'Cancel',self.destroy,True,width=100).pack(side='right',padx=4)
        button(footer,'Save to food library',self.save,width=170).pack(side='right',padx=4)

    @staticmethod
    def add_entry(parent,text,row):
        label(parent,text,12,MUTED).grid(row=row,column=0,sticky='w',pady=(8,2))
        widget=ctk.CTkEntry(parent)
        widget.grid(row=row+1,column=0,sticky='ew')
        return widget

    def add_ingredient(self):
        def action():
            rid=self.food_map.get(self.food.get())
            grams=float(self.grams.get())
            if not rid or grams<=0:
                raise ValueError('Choose an ingredient and enter its positive weight in grams.')
            self.ingredients.append((rid,grams))
            self.render()
        safe(self,action)

    def remove_ingredient(self):
        if self.ingredients:
            self.ingredients.pop()
        self.render()

    def render(self):
        self.items.configure(text='\n'.join(f"{i+1}. {self.app.service.get('foods',rid)['name']} · {g:g} g" for i,(rid,g) in enumerate(self.ingredients)) or 'No ingredients yet.')

    def save(self):
        def action():
            self.app.service.save_recipe(self.name.get(),self.ingredients,float(self.yield_g.get()),
                                         float(self.serving.get()) if self.serving.get() else None,
                                         float(self.cup.get()) if self.cup.get() else None)
            self.on_save()
            self.app.notice('Recipe saved. It is now available in the food logger.')
            self.destroy()
        safe(self,action)

class NutritionReviewDialog(Dialog):
    def __init__(self,parent,app):
        super().__init__(parent,'Nutrition coach',900,750)
        self.app=app
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(1,weight=1)
        header=ctk.CTkFrame(self,fg_color='transparent')
        header.grid(row=0,column=0,sticky='ew',padx=22,pady=14)
        label(header,'Nutrition coach',23).pack(side='left')
        from .fitness import PreferencesDialog
        button(header,'Preferences',lambda:PreferencesDialog(self,app,self.render),True,width=125,icon_name='settings').pack(side='right')
        self.tabs=GlassTabs(self)
        self.tabs.grid(row=1,column=0,sticky='nsew',padx=22,pady=(0,16))
        trends=self.tabs.add('Weekly nutrition')
        trends.grid_columnconfigure(0,weight=1)
        trends.grid_rowconfigure(1,weight=1)
        self.summary=label(trends,'',12,MUTED,anchor='w',justify='left',wraplength=760)
        self.summary.grid(row=0,column=0,sticky='ew',pady=8)
        self.plot=GlassPlot(trends,app)
        self.plot.grid(row=1,column=0,sticky='nsew')
        suggestions=self.tabs.add('Practical meal ideas')
        suggestions.grid_columnconfigure(0,weight=1)
        suggestions.grid_rowconfigure(0,weight=1)
        body=ScrollFrame(suggestions,fg_color='transparent')
        body.grid(row=0,column=0,sticky='nsew')
        body.grid_columnconfigure(0,weight=1)
        self.ideas=label(body,'',13,anchor='w',justify='left',wraplength=740)
        self.ideas.grid(row=0,column=0,sticky='ew',padx=12,pady=12)
        controls=ctk.CTkFrame(suggestions,fg_color='transparent')
        controls.grid(row=1,column=0,sticky='ew',pady=10)
        button(controls,'Add food',lambda:FoodDialog(self,app,on_save=self.render),width=130,icon_name='plus').pack(side='left')
        button(controls,'Build recipe',lambda:RecipeDialog(self,app,self.render),True,width=135).pack(side='left',padx=8)
        self.render()

    def render(self):
        from datetime import timedelta
        from matplotlib.figure import Figure
        end=date.today().isoformat()
        start=(date.today()-timedelta(days=6)).isoformat()
        self.report=self.app.coach.nutrition_review(start,end)
        r=self.report
        self.summary.configure(text=f"{start} to {end} · {r['logged_days']} / 7 days have entries; {r['missing_days']} days unknown.\nLogged protein reaches your target on {r['protein_target_days']} days. Partial food logs do not establish full intake.\nDaily targets are editable in Settings; source-labelled values and portion conversions are estimates.")
        fig=Figure(figsize=(8,5),dpi=100,layout='constrained')
        ax1,ax2=fig.subplots(2,1)
        style_axes(fig,(ax1,ax2))
        days=r['daily']
        labels=[d['date'][5:] for d in days]
        x=list(range(len(days)))
        for ax,key,goal,title in [(ax1,'calories','calorie_goal','Logged energy (kcal)'),(ax2,'protein','protein_goal','Logged protein (g)')]:
            ax.bar(x,[d[key] if d['entries'] else 0 for d in days],color='#d0d0d0',label='Logged')
            ax.plot(x,[d[goal] for d in days],color='#969696',linestyle=':',label='User-set target')
            ax.set_xticks(x,labels,rotation=20)
            ax.set_title(title+' · missing days are unknown',fontsize=10)
            ax.legend(facecolor=PANEL,labelcolor=TEXT,fontsize=7)
        self.plot.show(fig)
        preferences=self.app.coach.preferences()
        foods=self.app.coach.meal_suggestions()
        text=f"{preferences['diet']} · {preferences['meals']} meals/day · Budget note: {preferences['budget']}\nGoal: {preferences['goal']}\nRestrictions: {preferences['restrictions'] or 'None supplied'}\n\nPractical options from your actual offline library:\n\n"
        text+='\n\n'.join('• '+f['name']+'\n  '+f['source'] for f in foods) or 'Add suitable foods or a weighed recipe to your food library.'
        text+='\n\nCombine a suitable protein food with vegetables and a carbohydrate portion that fits your preferences. Indian reference foods (idli, sambar, chapati) are editable recipe estimates.\n\nChoose and confirm actual portions in Add food before calculating nutrients. No meal total is guessed here. Text restriction matching is not an allergen check; inspect ingredients. Budget is a planning note, not verified prices.'
        self.ideas.configure(text=text)
        self.app.refresh_nutrition()

