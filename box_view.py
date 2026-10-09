import tkinter as tk
from tkinter import ttk,filedialog
from tracker.boxes import read_box,decode_box
class BoxView:
    def __init__(self,app):
        self.app=app;self.data=None;self.party=[];self.loaded_number=None;self.closed=False
        self.root=tk.Toplevel(app.root);self.root.title('Cajas PC — lectura experimental');self.root.geometry('850x720')
        f=ttk.Frame(self.root,padding=12);f.pack(fill='both',expand=True)
        row=ttk.Frame(f);row.pack(fill='x')
        ttk.Label(row,text='Caja:').pack(side='left')
        self.number=tk.StringVar(value='1');ttk.Spinbox(row,from_=1,to=32,textvariable=self.number,width=5).pack(side='left',padx=8)
        for label,cmd in [('Leer caja',self.refresh),('Guardar caja',self.save),('Abrir captura',self.load)]:ttk.Button(row,text=label,command=cmd).pack(side='left',padx=4)
        self.auto=tk.BooleanVar(value=False);ttk.Checkbutton(f,text='Actualizar caja seleccionada cada 3 segundos',variable=self.auto).pack(anchor='w',pady=8)
        self.status=tk.StringVar(value='Ubicación candidata: compara los Pokémon con la caja del juego antes de validarla.')
        ttk.Label(f,textvariable=self.status,wraplength=800).pack(anchor='w',pady=5)
        self.table=ttk.Treeview(f,columns=('slot','species','nick','item','ability'),show='headings',height=15)
        for key,label in [('slot','Slot'),('species','Pokémon'),('nick','Apodo'),('item','Objeto'),('ability','Habilidad')]:
            self.table.heading(key,text=label);self.table.column(key,width=145 if key!='slot' else 60)
        self.table.pack(fill='both',expand=True);self.table.bind('<<TreeviewSelect>>',self.detail)
        self.output=tk.Text(f,height=9,font=('Consolas',11),state='disabled');self.output.pack(fill='x',pady=8)
        ttk.Label(f,text='Sin HP ni estadísticas de combate: las cajas almacenan PK7 de 232 bytes.').pack(anchor='w')
        self.root.protocol('WM_DELETE_WINDOW',self.close);self.root.after(3000,self.tick)
    def refresh(self):
        if self.app.busy:self.status.set('Esperando a que termine la lectura actual…');return
        if not self.app.reader:self.auto.set(False);self.status.set('Conecta primero desde la ventana principal.');return
        try:number=int(self.number.get())
        except ValueError:self.status.set('Usa una caja de 1 a 32.');return
        def done(data):
            if self.closed:return
            try:self.show(data,number)
            except Exception as exc:self.auto.set(False);self.status.set(str(exc))
        self.app.run(lambda:read_box(self.app.reader,number),done)
    def show(self,data,number):
        party=decode_box(data)
        self.data,self.party,self.loaded_number=data,party,number
        self.table.delete(*self.table.get_children())
        self.output.configure(state='normal');self.output.delete('1.0','end');self.output.configure(state='disabled')
        c=self.app.catalog
        for i,p in enumerate(party):
            values=(i+1,c.name('species',p['species_id']),p['nickname'],c.name('items',p['item_id']),c.name('abilities',p['ability_id'])) if p else (i+1,'Vacío','','','')
            self.table.insert('','end',iid=str(i),values=values)
        count=sum(p is not None for p in party)
        self.status.set(f'Caja {number if number is not None else "importada"}: {count} Pokémon · bloques válidos. Compara con el juego.' + (' Una caja vacía no confirma la dirección.' if count==0 else ''))
    def detail(self,event=None):
        ids=self.table.selection()
        if not ids:return
        p=self.party[int(ids[0])];c=self.app.catalog
        text='Slot vacío.' if p is None else f"{c.name('species',p['species_id'])} · {p['nickname']}\nNaturaleza: {p['nature']} · Forma: {p['form']}\nMovimientos: {', '.join(c.name('moves',x) for x in p['moves'])}\nIV (HP/ATQ/DEF/VEL/ATE/DEE): {p['iv']}\nEV (mismo orden): {p['ev']}"
        self.output.configure(state='normal');self.output.delete('1.0','end');self.output.insert('end',text);self.output.configure(state='disabled')
    def tick(self):
        if self.closed:return
        if not self.app.reader:self.auto.set(False)
        if self.auto.get():self.refresh()
        self.root.after(3000,self.tick)
    def save(self):
        if self.data is None:self.status.set('Lee una caja primero.');return
        path=filedialog.asksaveasfilename(defaultextension='.boxbin',initialfile=f'caja_{self.loaded_number or "importada"}.boxbin')
        if path:
            try:
                with open(path,'wb') as f:f.write(self.data)
                self.status.set('Captura guardada. Adjunta ese archivo para validar la caja.')
            except OSError as exc:self.status.set(str(exc))
    def load(self):
        self.auto.set(False)
        path=filedialog.askopenfilename(filetypes=[('Captura de caja','*.boxbin'),('Binario','*.bin')])
        if path:
            try:
                with open(path,'rb') as f:data=f.read(6961)
                self.show(data,None)
            except Exception as exc:self.status.set(str(exc))
    def close(self):self.closed=True;self.root.destroy();self.app.box_view=None
