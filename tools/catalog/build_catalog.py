"""
Extract the settings catalog (labels, help texts, choices as displayed) from the maprando.com website templates in the
MapRandomizer submodule, into tools/settings_catalog.json. The catalog only provides documentation for the options:
the settings themselves are read from Map Rando's Rust code and presets (see tools/upstream_data.py).

Usage: python tools/catalog/build_catalog.py
"""
import glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_fields import extract_fields
from extract_modals import extract_modals
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
R = os.path.join(ROOT, 'MapRandomizer', 'rust')
TEMPLATES = sorted(glob.glob(os.path.join(R, 'maprando-web', 'templates', 'generate', '**', '*.html'), recursive=True)
                   + glob.glob(os.path.join(R, 'maprando-web', 'templates', 'seed', '**', '*.html'), recursive=True))
M = extract_modals(TEMPLATES)
FL = extract_fields(TEMPLATES)
DEF=json.load(open(R+'/data/presets/full-settings/Default.json'))

def clean_body(t):
    out=[]
    for l in t.split('\n'):
        if l.startswith('| '):
            l=re.sub(r'^(\| )+','',l)
        out.append(l)
    return '\n'.join(out).strip()
for k in M: M[k]['body']=clean_body(M[k]['body'])
M['samusSpriteModal']['body']=M['samusSpriteModal']['body'].replace('\nSprite | Author','').strip()

def H(*ids):
    return '\n\n'.join(M[i]['body'] for i in ids)

# fields index (first occurrence by name in a specific file)
FI={}
for fn,fl in FL.items():
    for f in fl:
        FI.setdefault(f['name'],f)

def getdef(path):
    cur=DEF
    for p in path.split('.'):
        if isinstance(cur,dict) and p in cur: cur=cur[p]
        else: return None
    return cur

def conv(v,typ):
    if typ=='bool':
        return {'true':True,'false':False}.get(v,v)
    return v

def radio_choices(name, typ):
    f=FI[name]
    return [{'value':conv(c['value'],typ),'label':c['label']} for c in f['choices']]

def html_default(name, typ):
    f=FI[name]
    for c in f['choices']:
        if c.get('checked') or c.get('selected'): return conv(c['value'],typ)
    return None

RS=[]
def add(path, section, label, typ, description='', choices=None, mn=None, mx=None, step=None, default='__def__', notes='', **extra):
    e={'path':path,'section':section,'label':label,'description':description,'type':typ}
    if choices is not None: e['choices']=choices
    if typ in ('int','float') or mn is not None or mx is not None:
        e['min']=mn; e['max']=mx; e['step']=step
    e['default']=getdef(path) if default=='__def__' else default
    e['notes']=notes
    e.update(extra)
    RS.append(e)
    return e

def radio(path, section, form, typ='enum', description='', notes='', label=None, **kw):
    f=FI[form]
    ch=radio_choices(form, typ)
    hd=html_default(form, typ)
    n=f"Website form field '{form}' (radio buttons)."
    if hd is not None: n+=f" HTML pre-checked value before presets load: {json.dumps(hd)}."
    else: n+=" No option is pre-checked in the HTML (value set from the loaded preset)."
    if notes: n+=' '+notes
    return add(path, section, label or f['label'], typ, description, ch, notes=n, **kw)

# ---------------- top level ----------------
SKILL_SHOWN=["Basic","Medium","Hard","Very Hard","Expert","Expert+","Extreme","Extreme+","Insane","Insane+"]
add('version','(hidden)','Settings version','int','',default=DEF['version'],
    notes='Not user-editable. Set by the website JS to the current randomizer version ({{ version_info.version }}); settings with an older version are upgraded server-side via /upgrade-settings (try_upgrade_settings in settings.rs).')
add('name','Settings preset','Settings preset','string',H('presetModal'),
    choices=[{'value':n,'label':n} for n in ["Default","Community Race Season 5","Mentor Tournament","Summer Series Expert Challenge"]],
    notes="Website form field 'full_settings_preset' (select, id fullSettingsPreset). Option list: placeholder '' ('Select a preset to automatically fill all settings'), then any user custom presets (stored in browser localforage 'customPresets'), then the built-in full presets in order. Selecting a preset applies all its settings. Changing any setting afterwards resets the select to '' (sent as name=\"\" ; JSON type is Option<String>). Server-side (assign_presets), if name matches a built-in full preset, the whole settings object is replaced by that preset when apply_presets is true.")
add('debug','(hidden)','Debug','bool','',default=DEF.get('debug',False),
    notes='Not present on the website form (serde default false). Not in Default.json.')

# ---------------- skill assumptions ----------------
S='Skill assumptions'
add('skill_assumption_settings.preset',S,'Skill assumptions','enum',H('skillModal'),
    choices=[{'value':None,'label':'Select an option to discard custom skill assumption settings'}]+[{'value':n,'label':n} for n in SKILL_SHOWN],
    notes="Website form field 'skill_preset' (select, id skillPreset). Options generated from preset_data.skill_presets (data/presets/skill-assumptions/*.json, ordered Implicit, Basic, Medium, Hard, Very Hard, Expert, Expert+, Extreme, Extreme+, Insane, Insane+, Beyond), skipping 'Implicit', 'Beyond' and 'Ignored' (hidden on website; Implicit.json and Beyond.json exist as presets, Ignored has no preset file). HTML pre-selected: 'Basic'. The empty option '' means custom and is sent as null (emptyToNull). Choosing a preset fills all the numeric leniency fields and all tech/notable Yes/No toggles from that preset; editing any of them resets the select to '' (null). Server-side assign_presets replaces the whole skill_assumption_settings when preset matches a known preset name (including Implicit/Beyond).")
skill_nums=[
 ('resource_multiplier','General leniency','float'),('escape_timer_multiplier','General leniency','float'),('gate_glitch_leniency','General leniency','int'),('farm_time_limit','General leniency','float'),
 ('shinespark_tiles','Shinecharge leniency','float'),('heated_shinespark_tiles','Shinecharge leniency','float'),('speed_ball_tiles','Shinecharge leniency','float'),('shinecharge_leniency_frames','Shinecharge leniency','int'),
 ('phantoon_proficiency','Boss proficiency','float'),('draygon_proficiency','Boss proficiency','float'),('ridley_proficiency','Boss proficiency','float'),('botwoon_proficiency','Boss proficiency','float'),('mother_brain_proficiency','Boss proficiency','float'),
 ('door_stuck_leniency','Advanced tech leniency','int'),('bomb_into_cf_leniency','Advanced tech leniency','int'),('jump_into_cf_leniency','Advanced tech leniency','int'),('spike_suit_leniency','Advanced tech leniency','int'),('flash_suit_distance','Advanced tech leniency','int'),('blue_suit_distance','Advanced tech leniency','int'),('spike_xmode_leniency','Advanced tech leniency','int'),('spike_speed_keep_leniency','Advanced tech leniency','int'),('elevator_cf_leniency','Advanced tech leniency','int'),('crystal_spark_leniency','Advanced tech leniency','int'),
]
rust_types={'shinespark_tiles':'f32','heated_shinespark_tiles':'f32','speed_ball_tiles':'f32','shinecharge_leniency_frames':'i32','resource_multiplier':'f32','farm_time_limit':'f32','gate_glitch_leniency':'i32','door_stuck_leniency':'i32','bomb_into_cf_leniency':'i32','jump_into_cf_leniency':'i32','flash_suit_distance':'u8','blue_suit_distance':'u8','spike_suit_leniency':'i32','spike_xmode_leniency':'i32','spike_speed_keep_leniency':'i32','elevator_cf_leniency':'i32','crystal_spark_leniency':'i32','phantoon_proficiency':'f32','draygon_proficiency':'f32','ridley_proficiency':'f32','botwoon_proficiency':'f32','mother_brain_proficiency':'f32','escape_timer_multiplier':'f32'}
for name,card,typ in skill_nums:
    f=FI[name]
    lab=f['label']; m=re.match(r'^(.*?) \((.*)\)$',lab)
    label,desc=(m.group(1),m.group(2)) if m else (lab,'')
    step=f.get('step'); 
    n=f"Website form field '{name}' (<input type=\"{f['kind']}\">, HTML placeholder value {f.get('value')!r}; actual value filled from the selected skill preset). Parsed with parseFloat in JS; Rust type {rust_types[name]}."
    if rust_types[name] in ('i32','u8'): n+=' Must be an integer for the server to deserialize it.'
    if rust_types[name]=='u8': n+=' Range 0-255 (u8); upgrade code uses 255 for legacy settings lacking this field.'
    if 'proficiency' in name: n+=' Help text says value is between 0 and 1 (no HTML min/max).'
    add('skill_assumption_settings.'+name, f'{S} > {card}', label, typ, desc,
        mn=float(f['min']) if 'min' in f else None, mx=float(f['max']) if 'max' in f else None,
        step=(None if step in (None,'any') else float(step)), notes=n+(" HTML step=\"any\"." if step=='any' else ''))

# tech / notables
tech=json.load(open(R+'/data/tech_data.json')); notab=json.load(open(R+'/data/notable_data.json'))
for d in tech+notab:
    if d['difficulty']=='Uncategorized': d['difficulty']='Ignored'
TIERS=["Basic","Medium","Hard","Very Hard","Expert","Expert+","Extreme","Extreme+","Insane","Insane+","Beyond"]
tech_groups=[{'difficulty':t,'tech':[{'id':x['tech_id'],'name':x['name']} for x in tech if x['difficulty']==t]} for t in TIERS]
not_groups=[{'difficulty':t,'notables':[{'room_id':x['room_id'],'notable_id':x['notable_id'],'room_name':x['room_name'],'notable_name':x['name']} for x in notab if x['difficulty']==t]} for t in TIERS]
add('skill_assumption_settings.tech_settings', f'{S} > Tech and notable strats', 'Tech', 'other',
    "Each tech is shown with an animation/video, its description, dependencies, and a link to the strats using it; each has a No/Yes toggle.",
    default=f"list of {len(DEF['skill_assumption_settings']['tech_settings'])} {{id, name, enabled}} objects (Basic preset selection)",
    notes="JSON: list of {\"id\": TechId, \"name\": String, \"enabled\": bool}. Website presents tech in an accordion grouped by difficulty tier (Basic, Medium, Hard, Very Hard, Expert, Expert+, Extreme, Extreme+, Insane, Insane+, Beyond), each header showing the % of that tier enabled; tiers 'Implicit' and 'Ignored' are not shown (Implicit tech are always assumed; Ignored/Uncategorized tech are never offered). Each tech is a radio pair named 'tech-<id>' with values false (No, pre-checked) / true (Yes). buildTechArray() emits every shown tech in page order. Server upgrade (upgrade_tech_settings) rebuilds the list in the Default preset's order and sets any missing tech to false. Tier membership and names come from data/tech_data.json ('difficulty' field); descriptions from game data. The full shown list is in 'groups'.",
    groups=tech_groups)
add('skill_assumption_settings.notable_settings', f'{S} > Tech and notable strats', 'Notable strats', 'other',
    "Each notable strat is shown under a 'Notable strats' header inside its difficulty tier, with video, description and link to its strats; each has a No/Yes toggle. Label format: '<room name>: <notable name>'.",
    default=f"list of {len(DEF['skill_assumption_settings']['notable_settings'])} {{room_id, notable_id, room_name, notable_name, enabled}} objects (Basic preset selection)",
    notes="JSON: list of {\"room_id\", \"notable_id\", \"room_name\", \"notable_name\", \"enabled\": bool}. Grouped by the same difficulty tiers as tech (Basic..Insane+, Beyond; 'Implicit'/'Ignored' hidden). Radio pair named 'strat-<room_id>-<notable_id>' with values false (No, pre-checked) / true (Yes). Server upgrade (upgrade_notable_settings) rebuilds in Default preset order, missing ones false. Source: data/notable_data.json. Full shown list in 'groups'.",
    groups=not_groups)

# ---------------- item progression ----------------
IP='Item progression'
ITEMS_MULTI=["Missile","ETank","ReserveTank","Super","PowerBomb"]
ITEMS_SINGLE=["Charge","Ice","Wave","Spazer","Plasma","XRayScope","Morph","Bombs","Grapple","HiJump","SpeedBooster","SparkBooster","BlueBooster","SpringBall","WallJump","SpaceJump","ScrewAttack","Varia","Gravity"]
PRIO=["ETank","ReserveTank","Super","PowerBomb"]+ITEMS_SINGLE
add('item_progression_settings.preset',IP,'Item progression','enum',H('progressionModal'),
    choices=[{'value':n,'label':n} for n in ["Normal","Tricky","Technical","Challenge","Desolate"]]+[{'value':None,'label':'(custom - no button selected)'}],
    notes="Website form field 'item_progression_preset' (radio buttons on main page, HTML pre-checked 'Normal'), plus a gear button opening the Item Progression modal. Presets from data/presets/item-progression/{Normal,Tricky,Technical,Challenge,Desolate}.json. Changing any item-progression sub-setting unchecks all buttons -> null (custom). Note: when start location 'Escape' is selected the preset buttons are visually flagged as conflicting (starting items are forced to all).")
pf='Item progression > Item Progression modal'
def manual_radio(path, section, label, form, vals, typ='enum', checked=None, description='', notes='', labels=None):
    ch=[{'value':conv(v,typ) if isinstance(v,str) else v,'label':(labels[i] if labels else v)} for i,v in enumerate(vals)]
    n=f"Website form field '{form}' (radio buttons)."
    n+= f" HTML pre-checked value before presets load: {json.dumps(checked)}." if checked is not None else " No option is pre-checked in the HTML (value set from the loaded preset)."
    if notes: n+=' '+notes
    return add(path, section, label, typ, description, ch, notes=n)
manual_radio('item_progression_settings.progression_rate',pf,'Progression rate','progression_rate',["Fast","Uniform","Slow"],description=H('progressionRateModal'),notes="Choices rendered from progression_rates = ['Fast','Uniform','Slow'] (main.rs).")
manual_radio('item_progression_settings.item_placement_style',pf,'Item placement','item_placement_style',["Neutral","Forced","Local"],checked="Neutral",description=H('itemPlacementModal'))
manual_radio('item_progression_settings.item_priority_strength',pf,'Item priority strength','item_priority_strength',["Moderate","Heavy"],checked="Moderate",description=H('itemPriorityStrengthModal'))
add('item_progression_settings.random_tank',pf,'Random tank priority','bool',H('randomTankModal'),[{'value':False,'label':'No'},{'value':True,'label':'Yes'}],
    notes="Website form field 'random_tank' (radio, values 'false'/'true'). HTML pre-checked: true.")
add('item_progression_settings.spazer_before_plasma',pf,'Spazer before Plasma','bool',H('spazerBeforePlasmaModal'),[{'value':False,'label':'No'},{'value':True,'label':'Yes'}],
    notes="Website form field 'spazer_before_plasma' (radio, values 'false'/'true'). HTML pre-checked: true. Flagged as conflicting on the website if Spazer or Plasma is removed from the item pool.")
add('item_progression_settings.ammo_collect_fraction',pf,'Ammo collect fraction','float',H('ammoCollectFractionModal'),mn=0.5,mx=1.0,step=0.1,
    notes="Website form field 'ammo_collect_fraction' (<input type=\"number\" min=\"0.5\" max=\"1.0\" step=\"0.1\">, HTML value 0.7). Parsed with parseFloat.")
add('item_progression_settings.item_pool_preset',pf+' > Item pool','Item pool','enum',H('itemPoolModal'),
    [{'value':'Full','label':'Full'},{'value':'Reduced','label':'Reduced'},{'value':None,'label':'(custom - no button selected)'}],
    notes="Website form field 'item_pool_preset' (radio, HTML pre-checked 'Full'); JSON Option<ItemPoolPreset>. Selecting Full sets: stop_item_placement_early=No, Missile 46, Super 10, PowerBomb 10, ETank 14, ReserveTank 4, all unique items Yes, pickup sizes 5/5/5/1/1. Selecting Reduced sets: stop_item_placement_early=Yes, Missile 12, Super 6, PowerBomb 5 (note: help text says 6, the JS and Desolate preset use 5), ETank 3, ReserveTank 3, all unique items Yes, pickup sizes 5/5/5/1/1. Editing anything in the 'Customize' section unchecks both -> null.")
add('item_progression_settings.stop_item_placement_early',pf+' > Item pool > Customize','Stop item placement early','bool',H('stopItemPlacementEarlyModal'),[{'value':False,'label':'No'},{'value':True,'label':'Yes'}],
    notes="Website form field 'stop_item_placement_early' (radio 'false'/'true', HTML pre-checked false). Located inside the collapsible 'Customize' section of Item pool. When Yes, the QoL 'Hyper Beam gives all movement items' row is flagged as conflicting (it is forced on).")
POOL_MAX={'Missile':1099,'ETank':114,'ReserveTank':104,'Super':199,'PowerBomb':199}
pool_items=[{'item':i,'label':i,'input':'count (text box)','min':0,'max':POOL_MAX[i]} for i in ITEMS_MULTI]+[{'item':i,'label':i,'input':'No/Yes radio (count 0 or 1)','min':0,'max':1} for i in ITEMS_SINGLE]
add('item_progression_settings.item_pool',pf+' > Item pool > Customize','Item pool counts','item_counts',H('itemPoolModal'),
    notes="JSON: list of {\"item\": Item, \"count\": usize}. Website builds it from text boxes 'item_pool_<Item>' for Missile, ETank, ReserveTank, Super, PowerBomb (JS validateItemPool clamps to 0..1099 / 0..114 / 0..104 / 0..199 / 0..199 respectively) and No/Yes radios 'item_pool_<Item>' for each unique item (Yes -> count 1, No -> count 0; HTML pre-checked Yes). Order emitted: Missile, ETank, ReserveTank, Super, PowerBomb, then Charge, Ice, Wave, Spazer, Plasma, XRayScope, Morph, Bombs, Grapple, HiJump, SpeedBooster, SparkBooster, BlueBooster, SpringBall, WallJump, SpaceJump, ScrewAttack, Varia, Gravity. Default.json lists only the 5 multi-count items (46/14/4/10/10); when loaded, the website first sets every unique item to Yes (count 1). WallJump only matters with wall_jump=Collectible; SparkBooster/BlueBooster only with speed_booster=Split, SpeedBooster only with Vanilla (others are flagged as conflicting).",
    items=pool_items)
for key,form,lab,mx,dv in [('missile_size','pickup_size_Missile','Missiles per pickup',999,5),('super_size','pickup_size_Super','Supers per pickup',99,5),('powerbomb_size','pickup_size_PowerBomb','Power Bombs per pickup',99,5),('etank_size','pickup_size_ETank','E-Tanks per pickup',14,1),('reserve_size','pickup_size_ReserveTank','Reserve Tanks per pickup',4,1)]:
    add('item_progression_settings.'+key,pf+' > Item pool > Customize > Pickup sizes',lab,'int',H('pickupSizeModal'),mn=1,mx=mx,step=1,
        notes=f"Website form field '{form}' (<input type=\"text\">, no HTML min/max; parsed with parseInt). min/max given here are enforced by JS validatePickupSize(): values < 1 are reset to {dv}, values > {mx} are clamped to {mx}. Rust type {'u16' if key in ('missile_size','super_size','powerbomb_size') else 'u8'}.")
add('item_progression_settings.starting_items_preset',pf+' > Starting items','Starting items','enum',H('startingItemsModal'),
    [{'value':'None','label':'None'},{'value':'All','label':'All'},{'value':None,'label':'(custom - no button selected)'}],
    notes="Website form field 'starting_items_preset' (radio, HTML pre-checked 'None'); JSON Option<StartingItemsPreset>. None: all counts 0 / No. All: Missile 46, ETank 14, ReserveTank 4, Super 10, PowerBomb 10, every unique item Yes. Editing the Customize section unchecks both -> null.")
START_MAX={'Missile':999,'ETank':14,'ReserveTank':4,'Super':99,'PowerBomb':99}
add('item_progression_settings.starting_items',pf+' > Starting items > Customize','Starting item counts','item_counts',H('startingItemsModal'),
    notes="JSON: list of {\"item\", \"count\"}. Text boxes 'starting_item_<Item>' for Missile, ETank, ReserveTank, Super, PowerBomb (JS validateStartingItems clamps to 0..999 / 0..14 / 0..4 / 0..99 / 0..99) and No/Yes radios 'starting_item_<Item>' for each unique item (HTML pre-checked No; Yes -> 1). Same item order as item_pool. Note the Missile/Super/PowerBomb counts here are numbers of packs (help: 'Using starting items will cause an equal number of item locations to be missing an item'). With start location Escape, Samus always starts with all items.",
    items=[{'item':i,'label':i,'input':'count (text box)','min':0,'max':START_MAX[i]} for i in ITEMS_MULTI]+[{'item':i,'label':i,'input':'No/Yes radio (count 0 or 1)','min':0,'max':1} for i in ITEMS_SINGLE])
add('item_progression_settings.key_item_priority',pf+' > Key item priority','Key item priority','item_priorities',H('keyItemPriorityModal'),
    choices=[{'value':v,'label':v} for v in ["Early","Default","Late"]],
    notes="JSON: list of {\"item\": Item, \"priority\": \"Early\"|\"Default\"|\"Late\"} (KeyItemPriority). One radio group 'item_priority_<Item>' per prioritizable item, in this order: "+', '.join(PRIO)+". Every item offers exactly Early / Default / Late (HTML pre-checked Default). Missile is not listed (always filler). Items with 0 count in the pool are flagged as conflicting.",
    items=[{'item':i,'label':i,'allowed':["Early","Default","Late"]} for i in PRIO])
FILL4=["Super","PowerBomb","ETank","ReserveTank"]
add('item_progression_settings.filler_items',pf+' > Filler items','Filler items','item_priorities',H('fillerItemsModal'),
    choices=[{'value':v,'label':v} for v in ["No","Semi","Yes","Early"]],
    notes="JSON: list of {\"item\": Item, \"priority\": \"No\"|\"Semi\"|\"Yes\"|\"Early\"} (FillerItemPriority). One radio group 'filler_items_<Item>' per prioritizable item (same order as key_item_priority). 'Semi' is offered ONLY for Super, PowerBomb, ETank, ReserveTank; all other items offer No / Yes / Early. No HTML pre-checked value (filled from preset). Missile is not listed (always filler).",
    items=[{'item':i,'label':i,'allowed':(["No","Semi","Yes","Early"] if i in FILL4 else ["No","Yes","Early"])} for i in PRIO])

# ---------------- QoL ----------------
Q='Quality-of-life options'
add('quality_of_life_settings.preset',Q,'Quality-of-life options','enum',H('qualityModal'),
    [{'value':n,'label':n} for n in ["Off","Low","Default","High","Max"]]+[{'value':None,'label':'(custom - no button selected)'}],
    notes="Website form field 'quality_of_life_preset' (radio, HTML pre-checked 'Default'); presets from data/presets/quality-of-life/{Off,Low,Default,High,Max}.json (each sets every QoL field including enhanced map, initial map reveal, map station activation and crash fixes sub-settings). Changing any QoL setting unchecks all -> null.")
qcard={}
def qsec(form):
    return f"{Q} > {FI[form]['section']}"
# enhanced map preset
e=radio('quality_of_life_settings.enhanced_map_settings.preset',qsec('enhanced_map'),'enhanced_map',description=H('enhancedMapHelpModal'),
      notes="JSON type Option<String>. 'No' sets all door/environment items Hidden and walls/objectives/map station/refill station Vanilla; 'Yes' sets all Visible / Enhanced / Icon. Editing any sub-setting (gear button -> Enhanced map modal) unchecks both -> null.")
e['choices'].append({'value':None,'label':'(custom - no button selected)'})
EM=[('blue_doors','enhanced_map_blue_doors'),('gray_doors','enhanced_map_gray_doors'),('ammo_doors','enhanced_map_ammo_doors'),('beam_doors','enhanced_map_beam_doors'),('heat','enhanced_map_heat'),('water','enhanced_map_water'),('lava','enhanced_map_lava'),('acid','enhanced_map_acid'),('walls','enhanced_map_walls'),('objectives','enhanced_map_objectives'),('map_station','enhanced_map_station'),('refill_station','enhanced_map_refill')]
for k,form in EM:
    radio('quality_of_life_settings.enhanced_map_settings.'+k, f"{Q} > Map > Enhanced map (gear) > {FI[form]['section']}", form, description=H('enhancedMapHelpModal'))
e=radio('quality_of_life_settings.initial_map_reveal_settings.preset',qsec('initial_map_reveal'),'initial_map_reveal',description=H('initialMapRevealHelpModal'),
      notes="JSON type Option<String>. Note: the help text calls the first option 'None' but its value/label is 'No'. No: all tile types No, all_areas false. Maps: all No except map_stations Full, all_areas false. Partial: all Partial, all_areas false. Full: all Full, all_areas false. Global: all Full, all_areas true. Editing any sub-setting (gear -> Initial map reveal modal) unchecks all -> null.")
e['choices'].append({'value':None,'label':'(custom - no button selected)'})
IMR=[('map_stations','initial_map_reveal_maps'),('save_stations','initial_map_reveal_saves'),('refill_stations','initial_map_reveal_refills'),('ship','initial_map_reveal_ship'),('objectives','initial_map_reveal_objectives'),('area_transitions','initial_map_reveal_area_transitions'),('items1','initial_map_reveal_items1'),('items2','initial_map_reveal_items2'),('items3','initial_map_reveal_items3'),('items4','initial_map_reveal_items4'),('other','initial_map_reveal_other')]
for k,form in IMR:
    radio('quality_of_life_settings.initial_map_reveal_settings.'+k, f"{Q} > Map > Initial map reveal (gear) > Tile types", form, description=H('initialMapRevealHelpModal'))
radio('quality_of_life_settings.initial_map_reveal_settings.all_areas', f"{Q} > Map > Initial map reveal (gear) > Tile types", 'initial_map_reveal_all_areas', typ='bool', description=H('initialMapRevealHelpModal'))
e=radio('quality_of_life_settings.map_station_activation_settings.preset',qsec('map_station_reveal'),'map_station_reveal',description=H('mapStationActivationHelpModal'),
      notes="JSON type Option<MapStationActivationPreset> ('Partial'|'Full'). Partial: all tile types Partial, sub_area Same. Full: all tile types Full, sub_area Same. Editing any sub-setting (gear -> Map station activation reveal modal) unchecks both -> null. The website JS also sends this value as other_settings.map_station_reveal (ignored by the server; not a struct field).")
e['choices'].append({'value':None,'label':'(custom - no button selected)'})
MSA=[('save_stations','map_station_activation_saves'),('refill_stations','map_station_activation_refills'),('ship','map_station_activation_ship'),('objectives','map_station_activation_objectives'),('area_transitions','map_station_activation_transitions'),('items1','map_station_activation_tier1'),('items2','map_station_activation_tier2'),('items3','map_station_activation_tier3'),('items4','map_station_activation_tier4'),('other','map_station_activation_other'),('sub_area','map_station_activation_sub_area')]
for k,form in MSA:
    radio('quality_of_life_settings.map_station_activation_settings.'+k, f"{Q} > Map > Map station activation reveal (gear) > Tile types", form, description=H('mapStationActivationHelpModal'),
          notes=("Applies to tiles in non-primary sub-areas of the map station's area (MapStationActivationSubArea: No/Partial/Same, where Same = same reveal level as the primary sub-area)." if k=='sub_area' else ''))
QOL=[('item_markers','enum','itemMarkersModal',"Values '3-Tiered' and '4-Tiered' are serde renames of ThreeTiered/FourTiered."),('room_outline_revealed','bool','roomOutlineModal',''),('opposite_area_revealed','bool','oppositeAreaModal',''),('hazard_markers','bool','hazardMarkersModal',''),
     ('mother_brain_fight','enum','shortMotherBrainModal',''),('supers_double','bool','supersDoubleModal',''),('escape_autosave','bool','escapeAutosaveModal',''),('escape_movement_items','bool','movementItemsModal','Forced on (flagged as conflicting) when stop_item_placement_early is Yes.'),('escape_refill','bool','escapeRefillModal',''),('escape_enemies_cleared','bool','enemiesClearedModal',''),
     ('fast_elevators','bool','fastElevatorsModal',''),('fast_doors','bool','fastDoorsModal',''),('fast_pause_menu','bool','fastPauseMenuModal',''),('fast_saves','bool','fastSavesModal',''),('fast_baby_cutscene','bool','fastBabyCutsceneModal',''),('fast_mother_brain_cutscene','bool','fastMotherBrainCutsceneModal',''),('fast_decompression','bool','fastDecompressionModal',''),('fanfares','enum','fanfaresModal',''),
     ('respin','bool','respinModal',''),('infinite_space_jump','bool','infiniteSpaceJumpModal',''),('momentum_conservation','bool','momentumConservationModal',''),
     ('all_items_spawn','bool','itemsSpawnModal',''),('acid_chozo','bool','acidChozoModal',''),('remove_climb_lava','bool','removeClimbLavaModal','')]
for k,typ,mid,nt in QOL:
    radio('quality_of_life_settings.'+k, qsec(k), k, typ=typ, description=H(mid), notes=nt)
e=radio('quality_of_life_settings.crash_fixes.preset',qsec('crash_fixes_preset'),'crash_fixes_preset',description=H('crashFixesHelpModal'),
      notes="JSON Option<CrashFixesPreset>. Crash: all five set Crash. Death: spring_ball/yapping_maw/auto_reserve/x_mode Death, sprite_overflow Silent. Warn: four set Warn, sprite_overflow Silent. Silent: all Silent. Editing an individual fix (gear -> Crash fixes modal) unchecks all -> null. Server-side upgrade: if preset is set, all individual fields are recomputed from it (CrashFixes::from_preset).")
e['choices'].append({'value':None,'label':'(custom - no button selected)'})
CF=[('spring_ball','crash_fixes_springball'),('yapping_maw','crash_fixes_yappingmaw'),('auto_reserve','crash_fixes_autoreserve'),('x_mode','crash_fixes_xmode'),('sprite_overflow','crash_fixes_spriteoverflow')]
for k,form in CF:
    radio('quality_of_life_settings.crash_fixes.'+k, f"{Q} > Tweaks to unintuitive vanilla behavior > Crash fixes (gear)", form, description=H('crashFixesHelpModal'),
          notes=("Only Crash/Death/Silent offered (no Warn) for sprite overflow. FixMode enum also has Warn but the website does not offer it here." if k=='sprite_overflow' else ''))
QOL2=[('fix_blue_echoes','bool','fixBlueEchoesModal',''),('ammo_refill_all','bool','ammoRefillAllModal',''),('energy_station_reserves','bool','energyStationReservesModal',''),('etank_refill','enum','etankRefillModal',"Legacy settings stored this under other_settings.etank_refill (Default.json still contains a stale other_settings.etank_refill='Vanilla', which is ignored)."),('disableable_etanks','enum','disableableETanksModal','Legacy bool values are upgraded: false->Off, true->Standard.'),('reserve_backward_transfer','bool','reserveBackwardTransferModal',''),
      ('enemy_drops','enum','enemyDropsModal',''),('early_save','bool','earlySaveModal',''),('persist_flash_suit','bool','persistFlashSuitModal',''),('persist_blue_suit','bool','persistBlueSuitModal',''),('camera_fixes','bool','cameraFixesModal','')]
for k,typ,mid,nt in QOL2:
    radio('quality_of_life_settings.'+k, qsec(k), k, typ=typ, description=H(mid), notes=nt)

# ---------------- objectives ----------------
O='Objectives'
add('objective_settings.preset',O,'Objectives','enum',H('objectivesHelpModal'),
    [{'value':n,'label':n} for n in ["None","Bosses","Minibosses","Chozos","Pirates","Metroids","Random"]]+[{'value':None,'label':'(custom - no button selected)'}],
    notes="Website form field 'objective_preset' (radio; HTML pre-checks index 1 = 'Bosses'). Presets from data/presets/objectives/*.json, loaded in order None, Bosses, Minibosses, Chozos, Pirates, Metroids, Random. Each sets objective_options, min/max_objectives and objective_screen. Changing anything in the Objectives modal (gear) unchecks all -> null.")
groups=[("Bosses",[("Kraid","Kraid"),("Phantoon","Phantoon"),("Draygon","Draygon"),("Ridley","Ridley")]),("Minibosses",[("SporeSpawn","Spore Spawn"),("Crocomire","Crocomire"),("Botwoon","Botwoon"),("GoldenTorizo","Golden Torizo")]),("Pirates",[("PitRoom","Pit Room"),("BabyKraidRoom","Baby Kraid"),("PlasmaRoom","Plasma Room"),("MetalPiratesRoom","Metal Pirates")]),("Chozos",[("BombTorizo","Bomb Torizo"),("BowlingStatue","Bowling"),("AcidChozoStatue","Acid Statue")]),("Metroids",[("MetroidRoom1","Metroids 1"),("MetroidRoom2","Metroids 2"),("MetroidRoom3","Metroids 3"),("MetroidRoom4","Metroids 4")])]
add('objective_settings.objective_options',O+' > Objectives modal (gear)','Objective options','objective_options',H('objectivesHelpModal'),
    choices=[{'value':v,'label':v} for v in ["No","Maybe","Yes"]],
    notes="JSON: list of {\"objective\": Objective, \"setting\": \"No\"|\"Maybe\"|\"Yes\"}. Website shows one No/Maybe/Yes radio group 'objective_<Objective>' per objective (HTML pre-checked No), in cards by group (displayed two cards per row): Bosses, Minibosses, Pirates, Chozos, Metroids (see 'objectives'). The JS emits the list in the order of the 'None' preset's objective_options (Kraid, Phantoon, Draygon, Ridley, SporeSpawn, Crocomire, Botwoon, GoldenTorizo, BombTorizo, BowlingStatue, AcidChozoStatue, PitRoom, BabyKraidRoom, PlasmaRoom, MetalPiratesRoom, MetroidRoom1-4). 'Yes' objectives are always chosen; between min_objectives and max_objectives total objectives are chosen, with 'Maybe' objectives filling the remainder randomly. With Small map layout, objectives absent from the map are excluded.",
    objectives=[{'group':g,'objectives':[{'value':a,'label':b} for a,b in obs]} for g,obs in groups])
for k,lab,hid in [('min_objectives','Minimum number of objectives','minimumObjectives'),('max_objectives','Maximum number of objectives','maximumObjectives')]:
    add('objective_settings.'+k,O+' > Objectives modal (gear)',lab,'int','',mn=0,mx=19,step=None,
        notes=f"Website <input type=\"number\" id=\"{hid}\" min=\"0\" max=\"19\"> (no name attribute; read by id, parseInt; HTML value 4). JS dynamically restricts both min and max inputs to the range [#Yes, #Yes + #Maybe] whenever objectives change, and keeps min <= max.")
radio('objective_settings.objective_screen',O+' > Objectives modal (gear)','objective_screen',description='')

# ---------------- map layout / doors / start / animals ----------------
radio('map_layout','Map layout','map_layout',typ='enum',description=H('mapLayoutModal'),
      notes="JSON type is a plain String (not an enum); valid values Vanilla, Small, Standard, Wild (MapPreset). Legacy value 'Tame' is upgraded to 'Standard'.")
D='Doors'
add('doors_settings.preset',D,'Doors','enum',H('doorsHelpModal'),
    [{'value':n,'label':n} for n in ["Blue","Ammo","Beam"]]+[{'value':None,'label':'(custom - no button selected)'}],
    notes="Website form field 'doors_preset' (radio; HTML pre-checks index 1 = 'Ammo'). Presets from data/presets/doors/{Blue,Ammo,Beam}.json set the 8 door counts (Blue: all 0; Ammo: red 30, green 15, yellow 10, beams 0; Beam: red 18, green 10, yellow 7, charge/ice/wave/spazer/plasma 4 each). Editing any count in the Doors modal (gear) unchecks all -> null.")
for k in ["red_doors_count","green_doors_count","yellow_doors_count","charge_doors_count","ice_doors_count","wave_doors_count","spazer_doors_count","plasma_doors_count"]:
    add('doors_settings.'+k,D+' > Doors modal (gear)',FI[k]['label'].rstrip(':'),'int',H('doorsHelpModal'),mn=None,mx=None,step=None,
        notes=f"Website form field '{k}' (<input type=\"text\">, no min/max; parseInt; HTML value 0). Maximum number of doors of this type the randomizer attempts to place. Rust type i32.")
add('start_location_settings.mode','Start location','Start location','enum',H('startLocationModal'),
    [{'value':'Ship','label':'Ship'},{'value':'Random','label':'Random'},{'value':'Escape','label':'Escape'},{'value':'Custom','label':'(Custom start location selected in gear modal)'}],
    notes="Website form field 'start_location' (radio Ship/Random/Escape, HTML pre-checked Ship) plus a gear button opening the 'Start location' modal with a 'Custom start location' select. If a specific location is selected there, the radios are all unchecked and mode is sent as 'Custom' with room_id/node_id; selecting a radio resets the select to 'unspecified'. Escape forces all starting items.")
sl=json.load(open(R+'/data/start_locations.json'))
add('start_location_settings.room_id','Start location > Start location modal (gear)','Custom start location (room)','int',H('startLocationModal'),default=getdef('start_location_settings.room_id'),
    notes="Option<usize>; null unless mode is 'Custom'. Set from the selected <option data-room-id> in the 'customStartLocation' select. The select's first option is 'unspecified' ('Select a specific location to start at'); the remaining options are grouped into <optgroup> by area (game_data.area_order, using each room's full area name) and sorted by (room name, location name) within each area; option text is the start location name. Source list: data/start_locations.json (see 'start_locations': name, room_id, node_id). Default.json omits room_id/node_id (null).",
    start_locations=[{'name':x['name'],'room_id':x['room_id'],'node_id':x['node_id']} for x in sl])
add('start_location_settings.node_id','Start location > Start location modal (gear)','Custom start location (node)','int',H('startLocationModal'),default=getdef('start_location_settings.node_id'),
    notes="Option<usize>; null unless mode is 'Custom'. Set from the selected option's data-node-id (paired with room_id; see start_location_settings.room_id for the list).")
radio('save_animals','Save the animals','save_animals',description=H('saveTheAnimalsModal'),notes="Display order is No, Yes, Optional, Random (enum order No, Optional, Yes, Random). Legacy value 'Maybe' upgraded to 'Optional'.")

# ---------------- other settings ----------------
OT='Other options'
radio('other_settings.wall_jump',OT,'wall_jump',description=H('wallJumpModal'))
radio('other_settings.speed_booster',OT,'split_speed',description=H('speedBoosterModal'),notes="Form field name is 'split_speed' but JSON key is other_settings.speed_booster.")
e=radio('other_settings.area_assignment.preset',OT,'area_assignment_preset',description=H('areaAssignmentHelpModal'),
      notes="JSON Option<AreaAssignmentPreset>. Standard: base_order Size, ship_in_crateria true, mother_brain_in_tourian true. Size: Size/false/false. Depth: Depth/false/false. Random: Random/false/false. Editing a sub-option (gear -> Area assignment modal) unchecks all -> null. Legacy string values upgraded: 'Ordered' -> Size.")
e['choices'].append({'value':None,'label':'(custom - no button selected)'})
for k in ['base_order','ship_in_crateria','mother_brain_in_tourian']:
    radio('other_settings.area_assignment.'+k, OT+' > Area assignment (gear)', 'area_assignment_'+k, typ=('enum' if k=='base_order' else 'bool'), description=H('areaAssignmentHelpModal'))
radio('other_settings.door_locks_size',OT,'door_locks_size',description=H('doorLocksSizeModal'))
for k,form,mid,nt in [('energy_free_shinesparks','energy_free_shinesparks','energyFreeShinesparksModal',''),('all_enemies_respawn','all_enemies_respawn','allEnemiesRespawnModal',"The 'Yes' button is styled as a danger/warning button (exclamation-triangle icon)."),('disable_spikesuit','disable_spike_suit','disableSpikeSuitModal',"Form field name 'disable_spike_suit'."),('disable_bluesuit','disable_blue_suit','disableBlueSuitModal',"Form field name 'disable_blue_suit'."),('enable_major_glitches','enable_major_glitches','enableMajorGlitchesModal',''),('race_mode','race_mode','raceModal','')]:
    radio('other_settings.'+k,OT,form,typ='bool',description=H(mid),notes=nt)
radio('other_settings.savestate',OT,'savestate',description=H('saveStateHelpModal'))
add('other_settings.random_seed',OT,'Random seed','int',H('seedModal'),mn=None,mx=None,step=None,
    notes="Website form field 'random_seed' (<input type=\"text\">, blank by default; parseInt, blank -> null). JSON Option<usize>. The website clears this field on page load (checkOtherOptions). Ignored when race mode is enabled.")

# ================= customize =================
CS=[]
def cadd(path, section, label, typ, description='', choices=None, default=None, notes='', **extra):
    e={'path':path,'section':section,'label':label,'description':description,'type':typ}
    if choices is not None: e['choices']=choices
    if typ in ('int','float'): e['min']=None; e['max']=None; e['step']=None
    e['default']=default; e['notes']=notes; e.update(extra); CS.append(e)
def cradio(form, section, typ, mid, notes='', label=None):
    f=FI[form]
    lab=label or re.sub(r'\{%.*?%\}','',f['label']).strip()
    ch=radio_choices(form,typ)
    cadd(form, section, lab, typ, H(mid) if mid else '', ch, html_default(form,typ), (f"Radio buttons, form field '{form}'. Form values sent as strings"+(" 'true'/'false' (Text<bool>)." if typ=='bool' else '.')+(' '+notes if notes else '')))
C='Seed page > Customization'
cadd('rom',C,'Input ROM (vanilla Super Metroid)','other',M['inputRomModal']['body'] if 'inputRomModal' in M else '',default=None,
     notes="File upload field 'rom' (Bytes). Must be the unheadered NTSC USA/JU Super Metroid ROM, SHA-256 12b77c4bc9c1832cee8881244659065ee1d84c70c3d29e6eaf92e6798cc2ca72 (checked client-side and server-side). Not a setting per se; stored in browser localforage.")
sprites=json.load(open(os.path.join(ROOT, 'worlds', 'sm_map_rando_upstream', 'data', 'maprando', 'MapRandoSprites', 'samus_sprites', 'manifest.json')))
cadd('samus_sprite',C,'Samus sprite','enum',H('samusSpriteModal'),
     [{'value':s['name'],'label':s['display_name'],'category':c['category_name']} for c in sprites for s in c['sprites']],
     'samus_vanilla',
     notes=f"Hidden input 'samus_sprite' (HTML value 'samus_vanilla'), set by clicking a sprite in the 'Select your character' modal. Sprite list comes from MapRandoSprites/samus_sprites/manifest.json (loaded by maprando-web main.rs from ../MapRandoSprites/samus_sprites/manifest.json relative to the rust dir); shown grouped by category ({', '.join(c['category_name'] for c in sprites)}), {sum(len(c['sprites']) for c in sprites)} sprites total at time of extraction. value = sprite 'name', label = 'display_name'.")
etc=json.load(open(R+'/data/etank_colors.json'))
cadd('etank_color',C,'Energy tank color','string',H('energyTankColorModal'),
     [{'value':c,'label':'#'+c} for row in etc for c in row],'de3894',
     notes="Hidden input 'etank_color' (id etankColor, HTML value 'de3894'), a 6-hex-digit RGB string chosen from a grid in the 'Select your Energy Tank color' modal (colors from data/etank_colors.json: 2 rows x 12). Server converts each 8-bit channel to 5-bit SNES color by integer division by 8: (int(rr,16)//8, int(gg,16)//8, int(bb,16)//8). Any hex string would be accepted by the server, but the website only offers these 24. (The modal also contains an unused hidden input 'energy_tank_color'.)")
cadd('room_theming',C,'Room theming','enum',H('roomThemingModal'),
     [{'value':'vanilla','label':'Vanilla'},{'value':'palettes','label':'Area Palettes'},{'value':'tiling','label':'Area Tiling'}],'tiling',
     notes="UI convenience radio (form field 'room_theming'); NOT a CustomizeRequest field - it only sets the two real fields via JS roomThemingChanged(): vanilla -> room_palettes='vanilla', tile_theme='none'; palettes -> room_palettes='area-themed', tile_theme='none'; tiling -> room_palettes='vanilla', tile_theme='area_themed'. Manually changing room_palettes or tile_theme unchecks all three.")
cradio('door_theme',C,'enum','doorColorsModal',"Maps to DoorTheme Vanilla/Vibrant/Contrast.")
cradio('music',C,'enum','musicModal',"'area' -> MusicSettings::AreaThemed, 'disabled' -> MusicSettings::Disabled.")
cradio('shaking',C,'enum','shakingModal')
cradio('flashing',C,'enum','flashingModal')
cradio('disable_beeping',C,'bool','beepingModal',"Value true = beeping disabled (label 'Disabled'), false = 'Vanilla'.")
CO=C+' > Other customization options'
cadd('room_palettes',CO,'Room palettes','enum',H('roomPalettesModal'),
     [{'value':c['value'],'label':c['label']} for c in FI['room_palettes']['choices']],'vanilla',
     notes="Select 'room_palettes' (id roomPalettes); an <hr> separates the first four options from the per-area constant palettes. Server mapping: area-themed->AreaThemed, area-shuffled->AreaShuffled, scrambled->Scrambled, vanilla->Vanilla, crateria/brinstar/norfair/wrecked-ship/maridia/tourian -> PaletteTheme::Constant(0..5). Default effectively 'vanilla' (also set by room_theming 'tiling' default).")
mos=[("OuterCrateria","Outer Crateria"),("InnerCrateria","Inner Crateria"),("BlueBrinstar","Blue Brinstar"),("GreenBrinstar","Green Brinstar"),("PinkBrinstar","Pink Brinstar"),("RedBrinstar","Red Brinstar"),("WarehouseBrinstar","Warehouse Brinstar"),("UpperNorfair","Upper Norfair"),("LowerNorfair","Lower Norfair"),("WreckedShip","Wrecked Ship"),("WestMaridia","West Maridia"),("YellowMaridia","Yellow Maridia"),("Bedrock","Bedrock"),("MechaTourian","Mecha Tourian"),("MetroidHabitat","Metroid Habitat")]
cadd('tile_theme',CO,'Tile theme','enum',H('tileThemeModal'),
     [{'value':'none','label':'Vanilla'},{'value':'area_themed','label':'Area-themed'},{'value':'area_shuffled','label':'Area-shuffled'},{'value':'scrambled','label':'Scrambled'}]+[{'value':a,'label':b} for a,b in mos]+[{'value':'StatuesHallway','label':'Statues Hallway'},{'value':'Outline','label':'Practice Outlines'},{'value':'Invisible','label':'Invisible'}],
     'none',
     notes="Select 'tile_theme' (id tileTheme). HTML pre-selected 'none', but on page load room_theming defaults to 'tiling' which sets tile_theme to 'area_themed' (so the effective default is 'area_themed'). Server mapping: none->Vanilla, scrambled->Scrambled, area_themed->AreaThemed, area_shuffled->AreaShuffled, anything else -> TileTheme::Constant(<value>) (mosaic theme names from main.rs mosaic_themes, plus StatuesHallway, Outline, Invisible). <hr> separators after Scrambled and after Statues Hallway.",
     effective_default='area_themed')
cradio('reserve_hud_style',CO,'bool','reserveHudStyleModal',"true = Revamped, false = Vanilla.")
cradio('vanilla_screw_attack_animation',CO,'bool','screwAttackModal',"Inverted sense: value true = 'Vanilla' animation, false = 'Split' (default).")
cradio('room_names',CO,'bool','roomNamesModal')
MA=CO+' > Map appearance options'
cradio('map_theme',MA,'enum','mapThemeModal',"Maps to MapTheme Light/Dark.")
cradio('item_dot_change',MA,'enum','itemDotChangeModal',"Maps to ItemDotChange Stay/Fade/Disappear. (Default.json also has a stale other_settings.item_dot_change which is not a RandomizerSettings field.)")
cradio('transition_letters',MA,'bool','transitionLettersModal',"false = Arrows, true = Letters. (Default.json has a stale other_settings.transition_letters, not a RandomizerSettings field.)")
cradio('boss_icons',MA,'bool','bossIconsModal')
cradio('miniboss_icons',MA,'bool','miniBossIconsModal')
cradio('save_icons',MA,'bool','saveIconsModal')
TP=CO+' > Tourian proximity theming'
cradio('statues_hallway_tiling',TP,'enum','statuesHallwayTilingModal')
cradio('statues_hallway_audio',TP,'enum','statuesHallwayAudioModal')
CC=CO+' > Controller settings'
for lab,form,dflt in [("Shot","control_shot","X"),("Jump","control_jump","A"),("Dash","control_dash","B"),("Item Select","control_item_select","Select"),("Item Cancel","control_item_cancel","Y"),("Angle Up","control_angle_up","R"),("Angle Down","control_angle_down","L")]:
    cadd(form,CC,lab,'enum','',[{'value':b,'label':b} for b in ["X","Y","A","B","L","R","Select"]],dflt,
         notes=f"Radio buttons '{form}', options X, Y, A, B, L, R, Select (HTML pre-checked '{dflt}'). Clicking a button already assigned to another action swaps the two assignments (JS swapButtonAssignment), so the 7 actions always use 7 distinct buttons. Server parse_controller_button also accepts Left/Right/Up/Down (not offered); 'Start' is not accepted.")
BUT=[("X","X"),("Y","Y"),("A","A"),("B","B"),("L","L"),("R","R"),("Select","Select"),("Start","Start"),("Up","↑"),("Down","↓"),("Left","←"),("Right","→")]
COMBOS=[('quick_reload','Quick reload',["L","R","Start","Select"]),('spin_lock','Spin lock',["L","R","Up","X"]),('save_state','Save state',["L","R","Select","X"]),('load_state','Load state',["L","R","Select","Y"])]
for pre,lab,dch in COMBOS:
    for b,disp in BUT:
        cadd(f"{pre}_{b.lower()}",CC+' > '+lab,f"{lab}: {disp}",'bool',(H('saveStateHelpModal') if pre in ('save_state','load_state') else ''),[{'value':False,'label':'(unchecked)'},{'value':True,'label':disp}],b in dch,
             notes=f"Checkbox (toggle button) named '{pre}_{b.lower()}' in the '{lab}' button-combination row (row displays buttons in order X, Y, A, B, L, R, Select, Start, Up, Down, Left, Right). When checked the browser submits value 'on' (field omitted when unchecked; Option<Text<String>>, server treats only 'on' as pressed). The checked buttons together form the {lab.lower()} button combination; website default combination: {'+'.join(dch)}."+(" Save/load state combos only matter if the seed was generated with other_settings.savestate != No." if pre in ('save_state','load_state') else ''))
cradio('moonwalk',CC,'bool','',"No help text.")

# ================= presets =================
full_presets=["Default","Community Race Season 5","Mentor Tournament","Summer Series Expert Challenge"]
category_presets={
 'full_settings':{'presets':full_presets,'notes':'Displayed in the Settings preset select after any user-saved custom presets. Loaded from data/presets/full-settings/ in this fixed order (preset.rs). The help modal text mentions an outdated "Community Racing Season 3".'},
 'skill':{'presets':SKILL_SHOWN,'hidden':['Implicit','Beyond','Ignored'],'all_preset_files_in_order':['Implicit']+SKILL_SHOWN+['Beyond'],'json_path':'skill_assumption_settings.preset','notes':"Implicit and Beyond preset files exist (data/presets/skill-assumptions) and are accepted by the server but are hidden from the website select; 'Ignored' is a difficulty tier with no preset. The tech/notable accordion shows tiers Basic..Insane+ and Beyond (not Implicit/Ignored). Custom = null."},
 'item_progression':{'presets':["Normal","Tricky","Technical","Challenge","Desolate"],'json_path':'item_progression_settings.preset'},
 'item_pool':{'presets':["Full","Reduced"],'json_path':'item_progression_settings.item_pool_preset'},
 'starting_items':{'presets':["None","All"],'json_path':'item_progression_settings.starting_items_preset'},
 'quality_of_life':{'presets':["Off","Low","Default","High","Max"],'json_path':'quality_of_life_settings.preset'},
 'enhanced_map':{'presets':["No","Yes"],'json_path':'quality_of_life_settings.enhanced_map_settings.preset'},
 'initial_map_reveal':{'presets':["No","Maps","Partial","Full","Global"],'json_path':'quality_of_life_settings.initial_map_reveal_settings.preset'},
 'map_station_activation':{'presets':["Partial","Full"],'json_path':'quality_of_life_settings.map_station_activation_settings.preset'},
 'crash_fixes':{'presets':["Crash","Death","Warn","Silent"],'json_path':'quality_of_life_settings.crash_fixes.preset'},
 'objectives':{'presets':["None","Bosses","Minibosses","Chozos","Pirates","Metroids","Random"],'json_path':'objective_settings.preset'},
 'map_layout':{'presets':["Vanilla","Small","Standard","Wild"],'json_path':'map_layout'},
 'doors':{'presets':["Blue","Ammo","Beam"],'json_path':'doors_settings.preset'},
 'start_location':{'presets':["Ship","Random","Escape"],'extra_mode':'Custom (via gear modal select)','json_path':'start_location_settings.mode'},
 'save_animals':{'presets':["No","Yes","Optional","Random"],'json_path':'save_animals'},
 'area_assignment':{'presets':["Standard","Size","Depth","Random"],'json_path':'other_settings.area_assignment.preset'},
 'customize_room_theming':{'presets':["Vanilla","Area Palettes","Area Tiling"],'values':["vanilla","palettes","tiling"],'notes':'Seed customize page helper that sets room_palettes/tile_theme.'},
}

out={'source':{'repo':'MapRandomizer/rust','settings_version':DEF['version'],'default_preset':'data/presets/full-settings/Default.json'},
     'full_presets':full_presets,'category_presets':category_presets,
     'randomizer_settings':RS,'customize_settings':CS}
json.dump(out,open(os.path.join(ROOT,'tools','settings_catalog.json'),'w'),indent=1,ensure_ascii=False)

# ---- coverage check ----
def leaves(d,p=''):
    for k,v in d.items():
        q=p+k
        if isinstance(v,dict): yield from leaves(v,q+'.')
        else: yield q
paths={e['path'] for e in RS}
import itertools
dl=set(leaves(DEF))
print('missing from catalog:',sorted(dl-paths))
print('catalog not in Default.json:',sorted(paths-dl))
print(len(RS),len(CS))
