import concurrent.futures
import time
import queue
import json
import tkinter as tk
from tkinter import ttk,filedialog
from tracker.connectors import LimeGDB
from tracker.profiles import capture_party
from tracker.pokemon import decode_party
from tracker.boxes import read_box,decode_box
from tracker.catalog import Catalog
from tracker.search import matches
from tracker.sprites import SpriteCache
from tracker.state import SnapshotStore
from tracker.presentation import stat_text,move_text
from tracker.process_memory import LimeProcessMemory,PARTY

class App:
    def __init__(self,root):
        self.root=root;self.diagnostic=None;self.progress_queue=queue.SimpleQueue();self.snapshots=SnapshotStore();self.card_widgets={};self.text_values={};self.box_signature=None;self.catalog=Catalog();self.sprites=SpriteCache();self.images={};self.heartbeat_at=0;self.reader=None;self.busy=False;self.closed=False;self.ready=False
        self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.party=[];self.data=None;self.boxes={};self.box_bytes={};self.box_times={};self.scan=[]
        self.last_party=0;self.last_box=0;self.reconnect_at=0;self.retry_delay=2;self.had_session=False;self.was_running=False
        root.title('Pokémon Progressive Tracker 0.10.2');root.geometry('1180x900');root.minsize(1000,780);root.configure(bg='#0b1220')
        style=ttk.Style();style.theme_use('clam')
        style.configure('.',background='#0b1220',foreground='#e6eefb',font=('Segoe UI',10))
        style.configure('TFrame',background='#0b1220');style.configure('TLabel',background='#0b1220',foreground='#e6eefb')
        style.configure('TButton',padding=(10,7),background='#22334e',foreground='#edf5ff',borderwidth=0)
        style.map('TButton',background=[('active','#34557b')],foreground=[('disabled','#697b92')])
        style.configure('TNotebook',background='#0b1220',borderwidth=0);style.configure('TNotebook.Tab',padding=(22,10),background='#18243a')
        style.map('TNotebook.Tab',background=[('selected','#234364')])
        style.configure('Treeview',rowheight=30,background='#121e30',fieldbackground='#121e30',foreground='#e6eefb',borderwidth=0)
        style.configure('Treeview.Heading',background='#22334e',foreground='#b7c9e0',padding=8)
        style.map('Treeview',background=[('selected','#235879')])
        style.configure('TCheckbutton',background='#0b1220',foreground='#b7c9e0')
        style.map('TCheckbutton',background=[('active','#0b1220')])
        style.configure('HP.Horizontal.TProgressbar',background='#3ad6a1',troughcolor='#29384c',borderwidth=0)
        style.configure('TEntry',fieldbackground='#15243a',foreground='#e6eefb')
        outer=ttk.Frame(root,padding=14);outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='POKÉMON  /  PROGRESSIVE TRACKER',font=('Segoe UI',20,'bold')).pack(anchor='w')
        ttk.Label(outer,text='Lime3DS 2119.1 · Ultra Moon 1.0',foreground='#8da5c4').pack(anchor='w')
        row=ttk.Frame(outer);row.pack(fill='x',pady=10)
        self.mode=tk.StringVar(value='Windows sin GDB')
        ttk.Combobox(row,textvariable=self.mode,values=['Windows sin GDB','GDB'],state='readonly',width=19).pack(side='left',padx=5)
        ttk.Label(row,text='PID (opcional)').pack(side='left')
        self.pid=tk.StringVar();ttk.Entry(row,textvariable=self.pid,width=7).pack(side='left',padx=5)
        ttk.Label(row,text='Puerto GDB').pack(side='left');self.port=tk.StringVar(value='24689');ttk.Entry(row,textvariable=self.port,width=7).pack(side='left',padx=8)
        self.buttons=[]
        for label,cmd in [('Conectar / reconectar',self.connect),('Continuar juego',self.resume),('Desconectar',self.disconnect)]:
            b=ttk.Button(row,text=label,command=cmd);b.pack(side='left',padx=3);self.buttons.append(b)
        self.reconnect=tk.BooleanVar(value=True);ttk.Checkbutton(row,text='Reconectar automáticamente',variable=self.reconnect).pack(side='left',padx=8)
        ttk.Button(outer,text='Guardar diagnóstico de conexión',command=self.save_diagnostic).pack(anchor='w',pady=3)
        self.connection=tk.StringVar(value='Sin conexión');ttk.Label(outer,textvariable=self.connection).pack(anchor='w')
        self.status=tk.StringVar(value='Inicia Ultra Moon con GDB desactivado, carga la partida y pulsa Conectar.');ttk.Label(outer,textvariable=self.status,wraplength=1050).pack(anchor='w',pady=5)
        self.tabs=ttk.Notebook(outer);self.tabs.pack(fill='both',expand=True)
        self.team_tab=ttk.Frame(self.tabs,padding=10);self.box_tab=ttk.Frame(self.tabs,padding=10)
        self.tabs.add(self.team_tab,text='Equipo');self.tabs.add(self.box_tab,text='Cajas PC')
        row=ttk.Frame(self.team_tab);row.pack(fill='x')
        for label,cmd in [('Actualizar equipo',self.refresh),('Abrir captura',self.load_party),('Guardar captura',self.save_party)]:ttk.Button(row,text=label,command=cmd).pack(side='left',padx=3)
        self.auto=tk.BooleanVar(value=True);ttk.Checkbutton(row,text='Actualizar cada segundo',variable=self.auto).pack(side='left',padx=8)
        self.team_status=tk.StringVar(value='Sin lectura');ttk.Label(self.team_tab,textvariable=self.team_status).pack(anchor='w',pady=8)
        self.card_canvas=tk.Canvas(self.team_tab,bg='#0b1220',highlightthickness=0)
        card_scroll=ttk.Scrollbar(self.team_tab,orient='vertical',command=self.card_canvas.yview)
        card_scroll.pack(side='right',fill='y');self.card_canvas.pack(fill='both',expand=True)
        self.card_canvas.configure(yscrollcommand=card_scroll.set)
        self.cards=ttk.Frame(self.card_canvas)
        card_window=self.card_canvas.create_window((0,0),window=self.cards,anchor='nw')
        self.cards.bind('<Configure>',lambda event:self.card_canvas.configure(scrollregion=self.card_canvas.bbox('all')))
        self.card_canvas.bind('<Configure>',lambda event:self.card_canvas.itemconfigure(card_window,width=event.width))
        self.root.bind_all('<MouseWheel>',self.scroll_cards,add='+')
        for col in range(3):self.cards.columnconfigure(col,weight=1,uniform='cards')
        self.table=self.table_widget(self.team_tab,('slot','species','nick','level','hp','atk','def','spa','spd','spe'),('Slot','Pokémon','Apodo','Nivel','HP','ATQ','DEF','AT. ESP.','DEF. ESP.','VEL'),6)
        self.table.master.pack_forget()
        self.table.bind('<<TreeviewSelect>>',self.team_detail)
        self.detail_tab=ttk.Frame(self.tabs,padding=14);self.tabs.add(self.detail_tab,text='Detalles del Pokémon')
        ttk.Label(self.detail_tab,text='Selecciona una tarjeta o un Pokémon de las cajas.',font=('Segoe UI',14,'bold')).pack(anchor='w',pady=8)
        self.output=self.text_widget(self.detail_tab,22)
        row=ttk.Frame(self.box_tab);row.pack(fill='x')
        ttk.Label(row,text='Caja').pack(side='left');self.number=tk.StringVar(value='1');ttk.Spinbox(row,from_=1,to=32,width=5,textvariable=self.number).pack(side='left',padx=5)
        for label,cmd in [('Leer caja',self.refresh_box),('Leer las 32 cajas',self.start_scan),('Cancelar recorrido',self.cancel_scan),('Guardar caja',self.save_box),('Abrir captura',self.load_box)]:ttk.Button(row,text=label,command=cmd).pack(side='left',padx=3)
        row=ttk.Frame(self.box_tab);row.pack(fill='x',pady=7)
        ttk.Label(row,text='Buscar').pack(side='left');self.query=tk.StringVar();ttk.Entry(row,textvariable=self.query,width=35).pack(side='left',padx=5)
        self.all_cached=tk.BooleanVar(value=False);ttk.Checkbutton(row,text='En todas las cajas leídas',variable=self.all_cached,command=self.render_boxes).pack(side='left')
        self.box_auto=tk.BooleanVar(value=False);ttk.Checkbutton(row,text='Actualizar caja cada 3 s',variable=self.box_auto).pack(side='left',padx=8)
        self.query.trace_add('write',lambda *_:self.render_boxes());self.number.trace_add('write',lambda *_:self.render_boxes())
        self.box_status=tk.StringVar(value='Sin lectura. Búsqueda por especie, apodo, movimiento, habilidad u objeto.');ttk.Label(self.box_tab,textvariable=self.box_status,wraplength=1000).pack(anchor='w',pady=5)
        self.box_table=self.table_widget(self.box_tab,('box','slot','species','nick','item','ability'),('Caja','Slot','Pokémon','Apodo','Objeto','Habilidad'),12)
        self.box_table.bind('<<TreeviewSelect>>',self.box_detail);self.box_output=self.text_widget(self.box_tab,8)
        root.protocol('WM_DELETE_WINDOW',self.close);root.after(200,self.tick)

    def table_widget(self,parent,columns,labels,height):
        f=ttk.Frame(parent);f.pack(fill='both',expand=True)
        t=ttk.Treeview(f,columns=columns,show='headings',height=height)
        for key,label in zip(columns,labels):t.heading(key,text=label);t.column(key,width=130 if key in ('species','nick','item','ability') else 70,minwidth=45)
        y=ttk.Scrollbar(f,orient='vertical',command=t.yview);x=ttk.Scrollbar(f,orient='horizontal',command=t.xview);t.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        t.grid(row=0,column=0,sticky='nsew');y.grid(row=0,column=1,sticky='ns');x.grid(row=1,column=0,sticky='ew');f.rowconfigure(0,weight=1);f.columnconfigure(0,weight=1);return t
    def text_widget(self,parent,height=12):
        frame=ttk.Frame(parent);frame.pack(fill='both',expand=True,pady=8)
        t=tk.Text(frame,height=height,font=('Segoe UI',11),wrap='word',state='disabled',bg='#121e30',fg='#dde9f8',relief='flat',padx=18,pady=14,insertbackground='white')
        scroll=ttk.Scrollbar(frame,orient='vertical',command=t.yview);scroll.pack(side='right',fill='y');t.pack(side='left',fill='both',expand=True);t.configure(yscrollcommand=scroll.set);return t
    def write(self,widget,text):
        if self.text_values.get(widget)==text:return
        self.text_values[widget]=text
        widget.configure(state='normal');widget.delete('1.0','end');widget.insert('end',text);widget.configure(state='disabled')
    def detail_text(self,p):
        if p is None:return 'Espacio vacío.'
        c=self.catalog
        stats=p['stats'] or {}
        statline='  ·  '.join(f'{k}: {stats[k]}' for k in ('ATQ','DEF','ATE','DEE','VEL') if k in stats)
        return statline+'\n\n'+f"{c.name('species',p['species_id'])} · {p['nickname']}\nNaturaleza: {p['nature']} · Forma: {p['form']}\nHabilidad: {c.name('abilities',p['ability_id'])} · Objeto: {c.name('items',p['item_id'])}\n\nMovimientos: {', '.join(c.name('moves',m) for m in p['moves'])}\n\nIV (HP, ATQ, DEF, VEL, AT. ESP., DEF. ESP.): {p['iv']}\nEV (mismo orden): {p['ev']}"
    def sprite(self,species):
        if species not in self.images:
            path=self.sprites.path(species)
            if path:
                try:self.images[species]=tk.PhotoImage(file=str(path)).zoom(1)
                except tk.TclError:return None
        return self.images.get(species)
    def render_cards(self):
        for i in range(6):
            p=self.party[i] if i<len(self.party) else None
            if i not in self.card_widgets:
                card=tk.Frame(self.cards,bg='#15243a',highlightbackground='#29415d',highlightthickness=1,padx=14,pady=10)
                card.grid(row=i//3,column=i%3,sticky='nsew',padx=5,pady=5)
                top=tk.Frame(card,bg='#15243a');top.pack(fill='x')
                icon=tk.Label(top,bg='#15243a',fg='#7fb9ed',font=('Segoe UI',18));icon.pack(side='left')
                info=tk.Frame(top,bg='#15243a');info.pack(side='left',fill='both',expand=True,padx=5)
                name=tk.Label(info,bg='#15243a',fg='#f0f5ff',font=('Segoe UI',14,'bold'),anchor='w');name.pack(fill='x')
                species=tk.Label(info,bg='#15243a',fg='#8eaacb',anchor='w');species.pack(fill='x',pady=4)
                labels=[]
                hp=tk.Label(card,bg='#15243a',fg='#a8e8d4',anchor='w');hp.pack(fill='x')
                bar=ttk.Progressbar(card,style='HP.Horizontal.TProgressbar');bar.pack(fill='x',pady=(5,8))
                for color in ('#a7bbd5','#7fb9ed'):
                    label=tk.Label(card,bg='#15243a',fg=color,anchor='w');label.pack(fill='x',pady=3);labels.append(label)
                item=tk.Label(card,bg='#15243a',fg='#d6b786',anchor='w');item.pack(fill='x',pady=(4,8))
                moves=tk.Label(card,bg='#101d30',fg='#dce9fa',anchor='w',justify='left',padx=10,pady=8);moves.pack(fill='x')
                ttk.Button(card,text='Ver detalles',command=lambda index=i:self.open_detail(index)).pack(anchor='e',pady=(8,0))
                self.card_widgets[i]=(card,icon,name,species,hp,bar,*labels,item,moves)
                def select(event=None,index=i):
                    if index<len(self.party) and self.party[index]:self.table.selection_set(str(index));self.team_detail()
                def bind_all(widget):
                    widget.bind('<Button-1>',select)
                    for child in widget.winfo_children():bind_all(child)
                bind_all(card)
            card,icon,name,species,hp,bar,ability,stats,item,moves=self.card_widgets[i]
            image=self.sprite(p['species_id']) if p else None
            signature=(p,str(image))
            if not self.snapshots.update(('card',i),signature):continue
            icon.configure(image=image or '',text='' if image else (f"#{p['species_id']}" if p else '—'))
            name.configure(text=p['nickname'] if p else 'Espacio vacío')
            species.configure(text=self.catalog.name('species',p['species_id'])+' · Nv. '+str(p['level'] or '—') if p else '')
            hp.configure(text=f"HP {p['hp']} / {p['max_hp']}" if p and p['max_hp'] else '—')
            bar.configure(maximum=p['max_hp'] or 1 if p else 1,value=p['hp'] or 0 if p else 0)
            ability.configure(text=self.catalog.name('abilities',p['ability_id'])+' · '+p['nature'] if p else '')
            st=p['stats'] or {} if p else {}
            stats.configure(text=stat_text(p) if p else '',justify='left')
            item.configure(text='Objeto: '+self.catalog.name('items',p['item_id']) if p else '')
            moves.configure(text=move_text(p,self.catalog) if p else '')

    def scroll_cards(self,event):
        if self.tabs.index('current')==0:
            self.card_canvas.yview_scroll(int(-event.delta/120),'units')
    def open_detail(self,index):
        if index<len(self.party) and self.party[index]:
            self.table.selection_set(str(index));self.team_detail();self.tabs.select(self.detail_tab)

    def is_direct(self):
        return hasattr(self,'mode') and self.mode.get()=='Windows sin GDB'
    def heartbeat(self):
        if not self.reader:return
        def op():
            if isinstance(self.reader,LimeProcessMemory):return self.reader.read(PARTY,1)
            if self.was_running:self.reader.resume()
            return self.reader.identify()
        def done(_):
            self.heartbeat_at=time.monotonic();self.connection.set('Lime3DS conectado · '+('lectura de proceso sin GDB' if self.is_direct() else 'sesión supervisada'))
        self.run(op,done)

    def team_detail(self,event=None):
        ids=self.table.selection()
        if ids and self.party:self.write(self.output,self.detail_text(self.party[int(ids[0])]))
    def box_detail(self,event=None):
        ids=self.box_table.selection()
        if ids:
            n,i=map(int,ids[0].split(':'));self.write(self.box_output,self.detail_text(self.boxes[n][i]))

    def run(self,operation,done):
        if self.busy or self.closed:return False
        self.busy=True
        for b in self.buttons:b.configure(state='disabled')
        future=self.pool.submit(operation)
        def poll():
            if self.closed:
                if future.done() and self.reader:self.reader.close();self.reader=None
                return
            if not future.done():self.root.after(40,poll);return
            self.busy=False
            for b in self.buttons:b.configure(state='normal')
            try:result=future.result()
            except Exception as exc:self.transport_error(exc);return
            try:done(result)
            except Exception as exc:
                self.status.set(f'Lectura descartada: {exc}');self.last_party=time.monotonic();self.last_box=time.monotonic()
                if self.scan:self.cancel_scan()
        self.root.after(40,poll);return True
    def save_diagnostic(self):
        if not self.diagnostic:self.status.set('No hay diagnóstico. Intenta conectar primero.');return
        path=filedialog.asksaveasfilename(initialfile='diagnostico_conexion.json',defaultextension='.json')
        if path:
            try:
                with open(path,'w',encoding='utf-8') as f:json.dump(self.diagnostic,f,ensure_ascii=False,indent=2)
                self.status.set('Diagnóstico guardado; adjunta el JSON para revisar el fallo.')
            except OSError as exc:self.status.set(str(exc))

    def transport_error(self,exc):
        self.diagnostic=getattr(exc,'diagnostic',None) or {'error':str(exc),'connector':'Windows' if self.is_direct() else 'GDB'}
        while not self.progress_queue.empty():self.progress_queue.get()
        if self.reader:
            self.reader.close();self.reader=None
        self.ready=False;self.scan=[];self.boxes.clear();self.box_bytes.clear();self.box_times.clear();self.render_boxes();self.reconnect_at=time.monotonic()+self.retry_delay;self.retry_delay=min(30,self.retry_delay*2)
        self.connection.set('Conexión perdida · lecturas anteriores conservadas')
        self.team_status.set('Sin conexión · datos anteriores');self.box_status.set('Sin conexión · datos anteriores')
        refused=getattr(exc,'winerror',None)==10061 or getattr(exc,'errno',None) in (10061,111)
        self.status.set('Lime3DS no acepta GDB. Reactiva GDB en su configuración y vuelve a iniciar el juego. El tracker seguirá reintentando.' if refused else f'{exc} · Reintentará si la reconexión automática está activada.')
    def connect(self,automatic=False):
        if self.busy:return
        direct=self.is_direct()
        try:
            port=int(self.port.get())
            if not 1<=port<=65535:raise ValueError()
            pid=int(self.pid.get()) if direct and self.pid.get().strip() else None
        except ValueError:self.status.set('Puerto o PID inválido.');return
        self.ready=False;self.connection.set('Localizando RAM…' if direct else 'Conectando…')
        def op():
            if self.reader:self.reader.close();self.reader=None
            self.reader=LimeProcessMemory(pid,progress=self.progress_queue.put) if direct else LimeGDB(port)
            info=self.reader.identify()
            if not direct and automatic and self.was_running:self.reader.resume()
            return info
        def done(info):
            while not self.progress_queue.empty():self.progress_queue.get()
            if direct:self.diagnostic=getattr(self.reader.process,'discovery_report',{})
            self.had_session=True;self.retry_delay=2;self.ready=direct or (automatic and self.was_running)
            self.boxes.clear();self.box_bytes.clear();self.box_times.clear();self.render_boxes()
            self.team_status.set('Lectura anterior · pendiente de actualizar');self.connection.set('Conectado · '+str(info))
            self.status.set('Conector sin GDB activo. El juego continúa normalmente.' if direct else ('Reconectado y ejecución reanudada.' if self.ready else 'Conectado. Pulsa Continuar juego.'))
        self.run(op,done)
    def resume(self):
        if not self.reader:self.status.set('Conecta primero.');return
        if isinstance(self.reader,LimeProcessMemory):self.status.set('Sin GDB: la ejecución se controla desde Lime3DS.');return
        def done(_):self.ready=True;self.was_running=True;self.status.set('Juego en ejecución. Carga la partida para ver el equipo.')
        self.run(self.reader.resume,done)
    def disconnect(self):
        if self.busy:return
        self.reconnect.set(False);self.had_session=False;self.ready=False;self.scan=[]
        if self.reader:self.reader.close();self.reader=None
        self.connection.set('Desconectado');self.team_status.set('Sin conexión · datos anteriores');self.box_status.set('Sin conexión · datos anteriores')
    def refresh(self):
        if self.reader and self.ready:self.run(lambda:capture_party(self.reader),self.show_party)
        else:self.status.set('Carga tu partida y conecta primero.' if self.is_direct() else 'Conecta y pulsa Continuar juego primero.')
    def show_party(self,data,imported=False):
        party=decode_party(data)
        self.data=data
        if not self.snapshots.update('party',party):
            self.render_cards();self.last_party=time.monotonic()
            self.team_status.set(('Captura importada' if imported else 'Lectura '+time.strftime('%H:%M:%S'))+' · sin cambios')
            return
        selected=self.table.selection();self.party=party
        self.table.delete(*self.table.get_children());self.write(self.output,'')
        for i,p in enumerate(party):
            if p is None:continue
            st=p['stats'] or {};hp=f"{p['hp']}/{p['max_hp']}" if p['max_hp'] else 'Incompleto'
            self.table.insert('','end',iid=str(i),values=(i+1,self.catalog.name('species',p['species_id']),p['nickname'],p['level'] or '—',hp,*[st.get(k,'—') for k in ('ATQ','DEF','ATE','DEE','VEL')]))
        ids=self.table.get_children()
        if ids:self.table.selection_set(selected[0] if selected and selected[0] in ids else ids[0]);self.team_detail()
        self.status.set('Lectura de equipo válida.');self.render_cards();self.last_party=time.monotonic();self.team_status.set(('Captura importada' if imported else 'Actualizado '+time.strftime('%H:%M:%S'))+' · checksum válido')
    def refresh_box(self,number=None):
        if not self.reader or not self.ready:self.status.set('Conecta y continúa el juego primero.');return
        try:n=int(self.number.get()) if number is None else number
        except ValueError:self.status.set('Caja inválida.');return
        if not 1<=n<=32:self.status.set('Usa una caja de 1 a 32.');return
        def done(data):
            party=decode_box(data);self.boxes[n]=party;self.box_bytes[n]=data;self.box_times[n]=time.strftime('%H:%M:%S');self.last_box=time.monotonic();self.render_boxes()
            if self.scan and self.scan[0]==n:
                self.scan.pop(0)
                if not self.scan:self.status.set('Recorrido completo: 32 cajas leídas. La búsqueda usa estas capturas.')
        self.run(lambda:read_box(self.reader,n),done)
    def start_scan(self):
        if not self.reader or not self.ready:self.status.set('Conecta y continúa el juego primero.');return
        self.scan=list(range(1,33));self.all_cached.set(True)
    def cancel_scan(self):self.scan=[];self.status.set('Recorrido detenido; se conserva lo ya leído.')
    def render_boxes(self):
        if not hasattr(self,'box_table'):return
        try:n=int(self.number.get())
        except ValueError:return
        signature=(n,self.query.get(),self.all_cached.get(),tuple((key,self.box_bytes.get(key)) for key in sorted(self.boxes)))
        if signature==self.box_signature:
            self.box_status.set(f'{len(self.boxes)}/32 cajas leídas · Caja {n}: {self.box_times.get(n,"sin lectura")} · sin cambios')
            return
        self.box_signature=signature
        selected=self.box_table.selection();self.box_table.delete(*self.box_table.get_children());self.write(self.box_output,'')
        numbers=sorted(self.boxes) if self.all_cached.get() else [n];count=0
        for box in numbers:
            for i,p in enumerate(self.boxes.get(box,[])):
                if p is None:
                    if self.query.get().strip() or self.all_cached.get():continue
                    values=(box,i+1,'Vacío','','','')
                else:
                    if not matches(p,self.query.get(),self.catalog):continue
                    c=self.catalog;values=(box,i+1,c.name('species',p['species_id']),p['nickname'],c.name('items',p['item_id']),c.name('abilities',p['ability_id']));count+=1
                self.box_table.insert('','end',iid=f'{box}:{i}',values=values)
        ids=self.box_table.get_children()
        if selected and selected[0] in ids:self.box_table.selection_set(selected[0]);self.box_detail()
        when=self.box_times.get(n,'sin lectura')
        self.box_status.set(f'{count} Pokémon mostrados · {len(self.boxes)}/32 cajas leídas · Caja {n}: {when}. La búsqueda global usa las cajas ya leídas.')
    def tick(self):
        if self.closed:return
        now=time.monotonic()
        while not self.progress_queue.empty():
            progress=self.progress_queue.get()
            if self.busy:self.status.set(progress)
        if not self.busy:
            if not self.reader and self.had_session and self.reconnect.get() and now>=self.reconnect_at:self.connect(automatic=True)
            elif self.reader and self.ready:
                if now-self.heartbeat_at>=2:self.heartbeat()
                elif self.scan:
                    self.status.set(f'Leyendo caja {self.scan[0]}/32…');self.refresh_box(self.scan[0])
                elif self.tabs.index('current') in (0,2) and self.auto.get() and now-self.last_party>=1:self.refresh()
                elif self.tabs.index('current')==1 and self.box_auto.get() and now-self.last_box>=3:self.refresh_box()
        self.root.after(200,self.tick)
    def load_party(self):
        if self.busy:return
        self.auto.set(False);path=filedialog.askopenfilename(filetypes=[('Captura equipo','*.bin')])
        if path:
            try:
                with open(path,'rb') as f:data=f.read(2915)
                if len(data) not in (2904,2914):raise ValueError('Captura de equipo inválida.')
                self.show_party(data,True)
            except Exception as exc:self.status.set(str(exc))
    def save_bytes(self,data,name,extension):
        if data is None:self.status.set('No hay lectura para guardar.');return
        path=filedialog.asksaveasfilename(initialfile=name,defaultextension=extension)
        if path:
            try:
                with open(path,'wb') as f:f.write(data)
                self.status.set('Captura guardada.')
            except OSError as exc:self.status.set(str(exc))
    def load_box(self):
        if self.busy:return
        try:n=int(self.number.get())
        except ValueError:self.status.set('Selecciona una caja válida.');return
        if not 1<=n<=32:self.status.set('Selecciona una caja de 1 a 32.');return
        self.box_auto.set(False);self.scan=[]
        path=filedialog.askopenfilename(filetypes=[('Captura caja','*.boxbin'),('Binario','*.bin')])
        if path:
            try:
                with open(path,'rb') as f:data=f.read(6961)
                party=decode_box(data);self.boxes[n]=party;self.box_bytes[n]=data;self.box_times[n]='captura importada'
                self.render_boxes();self.status.set(f'Captura asignada a caja {n}; el archivo no verifica ese número.')
            except Exception as exc:self.status.set(str(exc))

    def save_party(self):self.save_bytes(self.data,'equipo.bin','.bin')
    def save_box(self):
        try:n=int(self.number.get())
        except ValueError:return
        self.save_bytes(self.box_bytes.get(n),f'caja_{n}.boxbin','.boxbin')
    def close(self):
        self.closed=True;self.sprites.close()
        if self.reader:self.reader.close()
        self.pool.shutdown(wait=False,cancel_futures=True);self.root.destroy()
if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()
