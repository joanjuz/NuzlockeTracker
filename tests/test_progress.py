import copy,tempfile,unittest
from pathlib import Path
from tracker.demo import DemoService
from tracker.service import TrackerService

class ProgressTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'demo-state.json';self.service=DemoService(self.path)
 def tearDown(self):self.tmp.cleanup()
 def test_first_death_persists_without_duplicates_after_healing_or_evolution(self):
  self.service.scenario('damage');deaths=self.service.snapshot()['progress']['deaths'];self.assertEqual(len(deaths),1)
  self.service.scenario('normal');self.service.scenario('damage')
  party=copy.deepcopy(self.service.team);party[0].update(hp=0,nickname='Otro mote',species_id=1,slot=6)
  self.service.update(party=party,stale=False)
  self.assertEqual(self.service.snapshot()['progress']['deaths'],deaths)
  self.assertEqual(DemoService(self.path).snapshot()['progress']['deaths'],deaths)
  self.assertEqual(TrackerService(self.path.with_name('state.json')).snapshot()['progress']['deaths'],{})
 def test_only_valid_live_party_is_observed(self):
  party=copy.deepcopy(self.service.team);party[0]['hp']=0
  self.service.update(party=party,stale=True);self.assertFalse(self.service.snapshot()['progress']['deaths'])
  for change in ({'max_hp':None},{'egg':True},{'checksum_valid':False}):
   invalid=copy.deepcopy(party);invalid[0].update(change);self.service.update(party=invalid,stale=False)
   self.assertFalse(self.service.snapshot()['progress']['deaths'])
  self.service.update(boxes={'1':party});self.assertFalse(self.service.snapshot()['progress']['deaths'])
  self.service.update(party=party,stale=False);self.assertEqual(len(self.service.snapshot()['progress']['deaths']),1)
 def test_origin_classification_without_hardcoding_species_and_persists(self):
  from tracker.progress import RunProgress,origin_category,pokemon_key
  p=dict(self.service.team[0])
  self.assertEqual(origin_category(p),'route')
  hatched=dict(p,egg=False,egg_location_id=30001)
  self.assertEqual(origin_category(hatched),'egg')
  self.assertEqual(origin_category(dict(p,egg=True)),'egg')
  path=Path(self.tmp.name)/'origin-progress.json'
  progress=RunProgress(path)
  self.assertTrue(progress.set_origin(p,'fossil'))
  self.assertEqual(origin_category(p,progress.data['origins']),'fossil')
  renamed=dict(p,nickname='Nuevo mote',species_id=150)
  self.assertEqual(origin_category(renamed,progress.data['origins']),'fossil')
  loaded=RunProgress(path)
  self.assertEqual(loaded.data['origins'],progress.data['origins'])
  self.assertEqual(origin_category(hatched,loaded.data['origins']),'fossil')
  loaded.set_origin(p,'auto')
  self.assertEqual(origin_category(hatched,loaded.data['origins']),'egg')
  self.assertNotIn(pokemon_key(p),RunProgress(path).data['origins'])
  with self.assertRaises(ValueError):loaded.set_origin(p,'inventado')
  with self.assertRaises(ValueError):loaded.set_origin(p,None)

 def test_origin_command_requires_existing_pokemon_and_valid_category(self):
  from tracker.progress import pokemon_key
  state_path=Path(self.tmp.name)/'clasificacion-state.json'
  live=TrackerService(state_path)
  mon=copy.deepcopy(self.service.team[0])
  live.update(party=[mon]+[None]*5,stale=False)
  key=pokemon_key(mon)
  command={'action':'set_origin','key':key,'category':'gift'}
  live.validate_set_origin(command)
  live.handle(command)
  self.assertEqual(live.snapshot()['progress']['origins'][key],'gift')
  self.assertEqual(TrackerService(state_path).snapshot()['progress']['origins'][key],'gift')
  live.handle(dict(command,category='auto'))
  self.assertNotIn(key,live.snapshot()['progress']['origins'])
  for invalid in [dict(command,category='fossils'),dict(command,key='33:999999999'),
                  dict(command,key='../../secret'),dict(command,category=None)]:
   with self.subTest(invalid=invalid),self.assertRaises(ValueError):
    live.validate_set_origin(invalid)

 def test_historical_trade_mark_persists_after_member_disappears(self):
  from tracker.progress import pokemon_key
  import copy
  path=Path(self.tmp.name)/'trade-state.json'
  app=TrackerService(path)
  mon=copy.deepcopy(self.service.team[0])
  key=pokemon_key(mon)
  app.update(party=[mon]+[None]*5,stale=False)
  self.assertIn(key,app.snapshot()['progress']['encounters'])
  # El Pokémon se fue, pero NO suponemos automáticamente que fue intercambio.
  app.update(party=[None]*6,boxes={'1':[None]*30},stale=False)
  saved=app.snapshot()['progress']
  self.assertIn(key,saved['encounters'])
  self.assertNotIn(key,saved['route_marks'])
  app.handle({'action':'mark_route','key':key,'kind':'trade'})
  self.assertEqual(app.snapshot()['progress']['route_marks'][key]['kind'],'trade')
  restarted=TrackerService(path)
  self.assertEqual(restarted.snapshot()['progress']['route_marks'][key]['pokemon']['nickname'],mon['nickname'])
  restarted.handle({'action':'clear_route_mark','key':key})
  self.assertNotIn(key,restarted.snapshot()['progress']['route_marks'])
  # El historial permanece para corregir un intercambio marcado por error.
  self.assertIn(key,restarted.snapshot()['progress']['encounters'])

 def test_fossil_button_moves_origin_and_undo_restores_automatic(self):
  from tracker.progress import pokemon_key
  path=Path(self.tmp.name)/'fossil-state.json'
  app=TrackerService(path)
  mon=copy.deepcopy(self.service.team[1])
  key=pokemon_key(mon)
  app.update(party=[mon]+[None]*5,stale=False)
  app.handle({'action':'mark_route','key':key,'kind':'fossil'})
  progress=app.snapshot()['progress']
  self.assertEqual(progress['origins'][key],'fossil')
  self.assertEqual(progress['route_marks'][key]['kind'],'fossil')
  self.assertEqual(progress['death_count'],0)
  app.handle({'action':'clear_route_mark','key':key})
  progress=app.snapshot()['progress']
  self.assertNotIn(key,progress['route_marks'])
  self.assertNotIn(key,progress['origins'])
  app.handle({'action':'mark_route','key':key,'kind':'fossil'})
  app.handle({'action':'set_origin','key':key,'category':'gift'})
  self.assertNotIn(key,app.snapshot()['progress']['route_marks'])
  self.assertEqual(app.snapshot()['progress']['origins'][key],'gift')

 def test_route_mark_rejects_unknown_keys_and_invalid_kind(self):
  path=Path(self.tmp.name)/'marks-state.json'
  app=TrackerService(path)
  for bad in ({'key':'../../secret','kind':'trade'},
              {'key':'33:123','kind':'unknown'},
              {'key':'33:123','kind':'trade'}):
   with self.subTest(bad=bad),self.assertRaises(ValueError):
    app.validate_route_mark(bad)
  with self.assertRaises(ValueError):
   app.validate_route_mark({'key':'33:123'},undo=True)

 def test_full_scan_auto_trade_requires_exchange_and_foreign_ot(self):
  from tracker.progress import RunProgress, pokemon_key
  path=Path(self.tmp.name)/'full-scan-progress.json'
  progress=RunProgress(path)
  own=[copy.deepcopy(self.service.team[i]) for i in range(3)]
  for i,p in enumerate(own):
   p.update(encryption_constant=501+i,ot_id=1234567,checksum_valid=True)
  received=copy.deepcopy(own[0])
  received.update(encryption_constant=7777,ot_id=9999999,nickname='Regalo por intercambio')
  boxes={str(i):[None]*30 for i in range(1,33)}
  party=own+[None]*3
  progress.remember(party,boxes)
  self.assertFalse(progress.observe_full_scan(party,boxes))
  # Con cajas incompletas NO puede concluir intercambio.
  missing=[own[1],own[2],received,None,None,None]
  progress.remember(missing,boxes)
  self.assertFalse(progress.observe_full_scan(missing,{'1':[None]*30}))
  self.assertNotIn(pokemon_key(own[0]),progress.data['route_marks'])
  self.assertTrue(progress.observe_full_scan(missing,boxes))
  key=pokemon_key(own[0])
  self.assertEqual(progress.data['route_marks'][key]['kind'],'trade')
  self.assertEqual(progress.data['route_marks'][key]['source'],'auto')
  self.assertEqual(progress.data['route_marks'][key]['pokemon']['nickname'],own[0]['nickname'])
  self.assertTrue(RunProgress(path).data['full_scan_baseline'])
  # No se vuelve a generar por escanear dos veces el mismo estado.
  self.assertFalse(progress.observe_full_scan(missing,boxes))

 def test_full_scan_does_not_guess_trade_on_missing_or_same_ot(self):
  from tracker.progress import RunProgress
  path=Path(self.tmp.name)/'no-trade.json'
  progress=RunProgress(path)
  own=[copy.deepcopy(self.service.team[i]) for i in range(3)]
  for i,p in enumerate(own):
   p.update(encryption_constant=900+i,ot_id=456,checksum_valid=True)
  boxes={str(i):[None]*30 for i in range(1,33)}
  party=own+[None]*3
  progress.remember(party,boxes)
  progress.observe_full_scan(party,boxes)
  same=copy.deepcopy(own[0]);same['encryption_constant']=919
  changed=[same,own[1],own[2],None,None,None]
  self.assertFalse(progress.observe_full_scan(changed,boxes))
  self.assertEqual(progress.data['route_marks'],{})
  # La simple desaparición tampoco da evidencia de intercambio.
  self.assertFalse(progress.observe_full_scan([None,own[1],own[2],None,None,None],boxes))
  self.assertEqual(progress.data['route_marks'],{})

 def test_route_trade_flag_can_be_undone_without_affecting_miss(self):
  path=Path(self.tmp.name)/'flag-progress.json'
  app=TrackerService(path)
  command={'action':'route_trade','route':'8','traded':True}
  app.handle(command)
  self.assertIn('8',app.snapshot()['progress']['traded_routes'])
  app.handle({'action':'route_miss','route':'8','missed':True})
  app.handle(command)
  self.assertIn('8',app.snapshot()['progress']['traded_routes'])
  app.handle({**command,'traded':False})
  self.assertNotIn('8',app.snapshot()['progress']['traded_routes'])
  for invalid in (dict(command,route='inventada'),dict(command,traded='true')):
   with self.assertRaises(ValueError):app.validate_route_trade(invalid)

 def test_miss_reversible_persistent_and_validated(self):
  cmd={'action':'route_miss','route':'8','missed':True};self.service.handle(cmd);self.service.handle(cmd)
  self.assertEqual(DemoService(self.path).snapshot()['progress']['missed_routes'],['8'])
  self.service.handle(dict(cmd,missed=False));self.assertEqual(DemoService(self.path).snapshot()['progress']['missed_routes'],[])
  for invalid in (dict(cmd,route='unknown'),dict(cmd,missed='false')):
   with self.assertRaises(ValueError):self.service.handle(invalid)
 def test_revive_waits_for_health_before_next_death_and_survives_restart(self):
  self.service.scenario('damage');key=next(iter(self.service.snapshot()['progress']['deaths']))
  self.service.handle({'action':'revive','key':key})
  self.assertFalse(self.service.snapshot()['progress']['deaths'])
  self.service.scenario('damage');self.assertFalse(self.service.snapshot()['progress']['deaths'])
  reloaded=TrackerService(self.path)
  damaged=copy.deepcopy(self.service.snapshot()['party'])
  reloaded.update(party=damaged,stale=False);self.assertFalse(reloaded.snapshot()['progress']['deaths'])
  healed=copy.deepcopy(damaged);healed[0]['hp']=1
  reloaded.update(party=healed,stale=False)
  reloaded.update(party=damaged,stale=False)
  self.assertEqual(len(reloaded.snapshot()['progress']['deaths']),1)
 def test_revive_already_healed_can_die_again_immediately(self):
  self.service.scenario('damage');key=next(iter(self.service.snapshot()['progress']['deaths']))
  self.service.scenario('normal');self.service.handle({'action':'revive','key':key})
  self.assertFalse(self.service.snapshot()['progress']['deaths'])
  self.service.scenario('damage');self.assertIn(key,self.service.snapshot()['progress']['deaths'])
 def test_death_counter_is_durable_and_revival_is_opt_in(self):
  self.service.scenario('damage')
  progress=self.service.snapshot()['progress']
  self.assertEqual(progress['death_count'],1)
  key=next(iter(progress['deaths']))
  self.service.handle({'action':'revive','key':key,'decrement_counter':False})
  self.assertEqual(self.service.snapshot()['progress']['death_count'],1)
  self.service.scenario('normal')
  self.service.scenario('damage')
  self.assertEqual(self.service.snapshot()['progress']['death_count'],2)
  self.service.handle({'action':'revive','key':key,'decrement_counter':True})
  self.assertEqual(self.service.snapshot()['progress']['death_count'],1)
  self.assertEqual(DemoService(self.path).snapshot()['progress']['death_count'],1)
  with self.assertRaises(ValueError):
   self.service.handle({'action':'revive','key':key,'decrement_counter':'yes'})

 def test_soullink_reply_records_source_and_persists(self):
  from tracker.progress import RunProgress,pokemon_key
  path=Path(self.tmp.name)/'soullink-progress.json'
  progress=RunProgress(path)
  mon=copy.deepcopy(self.service.team[0])
  key=pokemon_key(mon)
  self.assertTrue(progress.mark_dead(mon,source='soullink-response'))
  self.assertEqual(progress.data['deaths'][key]['source'],'soullink-response')
  self.assertEqual(progress.data['death_count'],1)
  self.assertFalse(progress.mark_dead(mon,source='soullink-response'))
  saved=RunProgress(path)
  self.assertEqual(saved.data['deaths'][key]['source'],'soullink-response')
  self.assertEqual(saved.data['death_count'],1)
  with self.assertRaises(ValueError):
   saved.mark_dead(mon,source='unknown')
  saved.revive(key)
  self.assertTrue(saved.mark_dead(mon))
  self.assertEqual(saved.data['deaths'][key]['source'],'manual')

 def test_revive_validates_key(self):
  for key in (None,{},'not-registered'):
   with self.assertRaises(ValueError):self.service.handle({'action':'revive','key':key})
