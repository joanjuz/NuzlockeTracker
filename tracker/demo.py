"""Deterministic UI fixtures. Never opens an emulator process or socket."""
import copy,queue
from .service import TrackerService

class DemoService(TrackerService):
    def __init__(self,output):
        super().__init__(output)
        rows=[(637,'Botella',144,287,[503,177,552,521],304,[211,153,249,317,224]),(350,'Nobara',14,234,[540,551,347,355],336,[151,178,183,266,258]),(282,'Misa',36,657,[188,585,326,548],279,[202,150,221,261,282]),(373,'Wayne',204,640,[706,572,550,216],328,[309,170,232,262,194]),(94,'Humo',162,275,[482,247,58,473],243,[180,177,288,302,176]),(289,'Jasnah',113,540,[216,529,421,208],421,[394,194,239,200,176])]
        self.team=[]
        for i,(species,nickname,ability,item,moves,hp,stats) in enumerate(rows):
            self.team.append(self.enrich(dict(slot=i+1,species_id=species,nickname=nickname,ability_id=ability,item_id=item,moves=moves,move_pp=[15,10,10,20],move_pp_ups=[0,0,0,0],level=100,hp=hp,max_hp=hp,stats=dict(zip(('ATQ','DEF','VEL','ATE','DEE'),stats)),nature='Firme',iv=[31,30,25,31,28,26],ev=[4,252,0,252,0,0],form=0,egg=False,checksum_valid=True,encryption_constant=1000+i,met_location_id=[8,8,8,112,152,180][i],egg_location_id=0,met_level=5+i,met_date='2026-10-08',origin_version=33)))
        for p in self.team:p['move_pp']=[self.reference.moves[str(m)]['pp'] for m in p['moves']]
        self.update(demo=True);self.scenario('normal')
    def box_data(self,number):
        data=[None]*30
        if number%4==0:return data
        for i in range(6 if number==1 else 3):
            p=copy.deepcopy(self.team[(i+number-1)%6]);p.update(slot=i+1,level=None,hp=None,max_hp=None,stats=None);data[i]=p
        return data
    def scenario(self,name):
        party=copy.deepcopy(self.team);stale=False
        if name=='damage':
            party[0]['hp']=0;party[1]['hp']=30;party[2]['hp']=150
        elif name=='empty':party=[None]*6
        elif name=='stale':stale=True
        elif name=='long':
            party[0]['nickname']='Nombre de prueba muy largo';party[0]['ability']='Habilidad con nombre extendido de prueba'
            party[0]['move_names'][0]='Movimiento con nombre largo de prueba'
        self.scan_next=None
        self.update(party=party,stale=stale,connection={'status':'disconnected' if stale else 'connected','message':'DEMO · Datos simulados para auditar la interfaz'},boxes={'1':self.box_data(1)},selected_box=1,scan={'active':False,'completed':0},demo_scenario=name)
    def handle(self,cmd):
        action=cmd['action']
        if action=='mark_dead':self.mark_dead(cmd)
        elif action=='revive':self.revive(cmd)
        elif action=='route_miss':self.set_route_miss(cmd)
        elif action=='demo':self.scenario(cmd['scenario'])
        elif action=='connect':self.scenario('normal')
        elif action=='disconnect':self.scenario('stale')
        elif action=='box':
            boxes=self.snapshot()['boxes'];boxes[str(cmd['number'])]=self.box_data(cmd['number']);self.update(selected_box=cmd['number'],boxes=boxes)
        elif action=='scan':self.scan_next=1;self.update(scan={'active':True,'completed':0})
        elif action=='cancel':self.scan_next=None;self.update(scan={'active':False,'completed':self.snapshot()['scan']['completed']})
    def run(self):
        while not self.stop.is_set():
            try:self.handle(self.commands.get(timeout=.1))
            except queue.Empty:pass
            if self.scan_next:
                number=self.scan_next;boxes=self.snapshot()['boxes'];boxes[str(number)]=self.box_data(number)
                self.update(boxes=boxes,scan={'active':number<32,'completed':number});self.scan_next=number+1 if number<32 else None
            self.stop.wait(.1)
