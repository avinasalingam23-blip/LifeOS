"""Offline exercise reference, not a record of the user's activity.

General gradual-progression and recovery principles:
https://www.cdc.gov/physical-activity-basics/guidelines/adults.html
https://www.nia.nih.gov/health/four-types-exercise-can-improve-your-health-and-physical-ability
Instructions are original concise cues. Work within comfortable range; stop for pain.
"""
MUSCLES=('Chest','Back','Shoulders','Biceps','Triceps','Forearms','Core/abs',
         'Quadriceps','Hamstrings','Glutes','Calves')
REGIONS={'Upper chest':'Chest','Lats':'Back','Upper back':'Back','Abs':'Core/abs','Core':'Core/abs'}
EQUIPMENT=('Bodyweight','Pull-up bar','Resistance band','Dumbbells','Gym','Exercise mat')
CATEGORIES=('Strength','Cardio','Core','Mobility','Stretching')

def exercise(key,name,primary,secondary,equipment,category,difficulty,instructions,alternatives):
    return dict(key=key,name=name,primary=primary.split('|'),secondary=secondary.split('|') if secondary else [],
                equipment=equipment.split('|'),category=category,difficulty=difficulty,instructions=instructions,
                alternatives=alternatives.split('|') if alternatives else [])

EXERCISES=[
exercise('wall-pushup','Wall push-up','Chest','Triceps|Shoulders','Bodyweight','Strength','Beginner',
 'Hands on a stable wall at chest height. Keep the body aligned, bend elbows comfortably, then press away. Move feet closer to make it easier.','incline-pushup|pushup'),
exercise('incline-pushup','Incline push-up','Chest','Triceps|Shoulders','Bodyweight','Strength','Beginner',
 'Use a fixed, non-slip counter or sturdy elevated surface. Lower chest toward it with elbows comfortably angled. Raise the surface to reduce difficulty.','wall-pushup|pushup'),
exercise('pushup','Push-up','Chest','Triceps|Shoulders|Core/abs','Bodyweight','Strength','Intermediate',
 'Keep a straight trunk; lower under control without shoulder pain, then press up. Stop before form breaks; use an incline if needed.','incline-pushup|wall-pushup'),
exercise('band-chest-press','Band chest press','Chest','Triceps|Shoulders','Resistance band','Strength','Beginner',
 'Place an intact band around the upper back, below the neck. Press hands forward smoothly without locking elbows. Keep the band away from the face.','wall-pushup|incline-pushup'),
exercise('band-row','Seated resistance-band row','Back','Biceps|Forearms','Resistance band','Strength','Beginner',
 'Sit tall, secure an intact band around the middle of both feet and pull elbows back gently. Do not let the band slip toward the face; use comfortable tension.','dumbbell-row|lat-pulldown'),
exercise('pullup-assisted','Foot-assisted pull-up','Back','Biceps|Forearms','Pull-up bar','Strength','Intermediate',
 'Use a correctly installed rated bar and a stable platform to support the feet. Assist with legs, pull smoothly and lower slowly. No swinging or jumping.','band-row|lat-pulldown'),
exercise('pullup','Pull-up','Back','Biceps|Forearms|Core/abs','Pull-up bar','Strength','Advanced',
 'Use a rated secure bar. Begin from a comfortable controlled hang, pull without swinging and lower smoothly. Use foot assistance if a clean repetition is not available.','pullup-assisted|band-row'),
exercise('band-curl','Resistance-band curl','Biceps','Forearms','Resistance band','Strength','Beginner',
 'Stand securely on the middle of an intact band. Keep elbows near the ribs, curl smoothly, then lower without snapping the band.','dumbbell-curl'),
exercise('band-triceps','Band triceps extension','Triceps','','Resistance band','Strength','Beginner',
 'Hold an intact band with the lower hand behind the back and extend the upper elbow in a comfortable range. Keep tension low and the band away from the face.','wall-pushup|cable-triceps'),
exercise('band-shoulder','Band shoulder press','Shoulders','Triceps','Resistance band','Strength','Intermediate',
 'Stand on an intact light band and press overhead only through a comfortable range. Keep ribs controlled; stop for shoulder discomfort.','wall-slide|dumbbell-press'),
exercise('band-pullapart','Band pull-apart','Back','Shoulders','Resistance band','Strength','Beginner',
 'Hold a light intact band in front of the chest. Spread hands gently with soft elbows; avoid shrugging or stretching the band toward the face.','wall-slide|band-row'),
exercise('squat','Bodyweight squat','Quadriceps|Glutes','Hamstrings|Core/abs','Bodyweight','Strength','Beginner',
 'Feet comfortable and stable. Sit hips down and back, knees tracking over feet. Use a sturdy chair as a depth guide and rise under control.','chair-squat|goblet-squat'),
exercise('chair-squat','Chair sit-to-stand','Quadriceps|Glutes','','Bodyweight','Strength','Beginner',
 'Use a sturdy chair against a wall. Lean forward slightly, stand with control, then sit slowly. Use hands for support if needed.','squat|leg-press'),
exercise('split-squat','Supported split squat','Quadriceps|Glutes','Hamstrings','Bodyweight','Strength','Intermediate',
 'Hold a fixed support, take a split stance and bend both knees through a comfortable depth. Keep balance; perform both sides.','chair-squat|squat'),
exercise('glute-bridge','Glute bridge','Glutes','Hamstrings|Core/abs','Bodyweight','Strength','Beginner',
 'Lie on your back with knees bent and feet planted. Lift hips without arching the lower back, pause, and lower slowly.','band-hinge'),
exercise('band-hinge','Band hip hinge','Hamstrings|Glutes','Back','Resistance band','Strength','Intermediate',
 'Stand on a light band, keep spine comfortably neutral and move hips back with soft knees. Stand by extending the hips; learn the unloaded hinge first.','glute-bridge'),
exercise('calf-raise','Supported calf raise','Calves','','Bodyweight','Strength','Beginner',
 'Hold a stable support, rise onto the balls of both feet, pause, then lower slowly on level ground.','ankle-mobility'),
exercise('dead-bug','Dead bug','Core/abs','','Bodyweight','Core','Beginner',
 'Lie on your back, keep the trunk steady and slowly extend opposite arm and leg. Shorten the reach if the back arches. Alternate sides.','bird-dog|plank'),
exercise('bird-dog','Bird dog','Core/abs','Glutes|Back','Bodyweight','Core','Beginner',
 'On hands and knees, reach opposite arm and leg without twisting. Return slowly, then switch sides. Keep the range comfortable.','dead-bug'),
exercise('plank','Forearm plank','Core/abs','Shoulders','Bodyweight','Core','Intermediate',
 'Support on forearms and toes with a steady trunk. Breathe normally; use knees down or shorten the hold if form declines. Log the hold duration.','dead-bug|bird-dog'),
exercise('walk','Comfortable walk','Quadriceps|Glutes','Calves','Bodyweight','Cardio','Beginner',
 'Walk at a comfortable conversational pace on a safe surface. Start with a short duration and adjust to energy and recovery.','march'),
exercise('march','March in place','Quadriceps','Core/abs|Calves','Bodyweight','Cardio','Beginner',
 'Stand near support if needed and alternate comfortable knee lifts. Keep breathing easy; slow down if uncomfortable.','walk'),
exercise('cat-cow','Gentle cat-cow','Back','Core/abs','Bodyweight','Mobility','Beginner',
 'On hands and knees, gently round then lengthen the spine within a comfortable range. Move slowly with breathing; never force the end range.','wall-slide'),
exercise('wall-slide','Wall shoulder slide','Shoulders','Back','Bodyweight','Mobility','Beginner',
 'Stand at a wall and slide forearms upward only as far as comfortable. Keep ribs relaxed. Reduce range or skip if painful.','cat-cow'),
exercise('ankle-mobility','Supported ankle mobility','Calves','','Bodyweight','Mobility','Beginner',
 'Near a fixed support, gently move a knee forward over the foot while the heel stays down. Use a small pain-free range on both sides.','calf-stretch'),
exercise('calf-stretch','Standing calf stretch','Calves','','Bodyweight','Stretching','Beginner',
 'Hands against a wall, one leg behind with heel down. Hold a gentle stretch without bouncing; repeat the other side.','ankle-mobility'),
exercise('hip-stretch','Gentle hip-flexor stretch','Quadriceps','Glutes','Bodyweight','Stretching','Beginner',
 'Use a supported split stance, gently tuck the pelvis and shift forward slightly until a mild front-hip stretch is felt. Avoid arching the back.','cat-cow'),
exercise('goblet-squat','Dumbbell goblet squat','Quadriceps|Glutes','Core/abs','Dumbbells','Strength','Intermediate',
 'First master an unloaded squat. Hold a light dumbbell close to the chest, squat comfortably and stand. Increase load only after controlled practice.','squat|chair-squat'),
exercise('dumbbell-row','Supported dumbbell row','Back','Biceps|Forearms','Dumbbells','Strength','Intermediate',
 'Use a stable support and a light dumbbell. Keep the trunk still, row toward the hip and lower under control. Avoid twisting.','band-row'),
exercise('dumbbell-curl','Dumbbell curl','Biceps','Forearms','Dumbbells','Strength','Beginner',
 'Stand tall with light dumbbells; curl without swinging and lower smoothly. Keep elbows near the body.','band-curl'),
exercise('dumbbell-press','Dumbbell shoulder press','Shoulders','Triceps','Dumbbells','Strength','Intermediate',
 'Begin with light weights. Press overhead only through a pain-free range while keeping the trunk steady. Get technique guidance before increasing load.','wall-slide|band-shoulder'),
exercise('lat-pulldown','Lat pulldown','Back','Biceps','Gym','Strength','Beginner',
 'Ask staff to set up the machine. Start light, pull in front toward the upper chest and return slowly. Avoid behind-neck pulls and momentum.','band-row|pullup-assisted'),
exercise('leg-press','Machine leg press','Quadriceps|Glutes','Hamstrings','Gym','Strength','Beginner',
 'Ask staff for seat and safety-stop setup. Start light; bend only to a comfortable depth with the back supported. Do not lock the knees.','chair-squat|squat'),
exercise('cable-triceps','Cable triceps pressdown','Triceps','','Gym','Strength','Beginner',
 'Use a light cable load with staff guidance. Keep elbows near the ribs, extend smoothly and return slowly without swinging.','band-triceps|wall-pushup'),
]
BY_KEY={e['key']:e for e in EXERCISES}

def matching(exercises,search='',muscle='',equipment='',category='',available=None):
    terms=search.casefold().split()
    muscle=REGIONS.get(muscle,muscle)
    allowed={v.casefold() for v in available}|{'bodyweight'} if available is not None else None
    result=[]
    for item in exercises:
        hay=' '.join([item['name'],*item['primary'],*item['secondary'],*item['equipment'],item['category']]).casefold()
        if not all(t in hay for t in terms):
            continue
        if muscle and muscle not in (*item['primary'],*item['secondary']):
            continue
        if equipment and equipment not in item['equipment']:
            continue
        if category and category!=item['category']:
            continue
        if allowed is not None and not set(v.casefold() for v in item['equipment'])<=allowed:
            continue
        result.append(item)
    return result
