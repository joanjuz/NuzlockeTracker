"""Diagnóstico interactivo Gen6 para Lime3DS/Citra/Azahar. No escribe RAM."""
import json
import sys
from dataclasses import replace
from datetime import datetime,timezone
from pathlib import Path
from tracker.process_memory import LimeProcessMemory
from tracker.profiles import PROFILES,capture_party
from tracker.pokemon import decode_party
from tracker.gen6_diagnostic import find_deposited_box
from tracker.battle_probe import initial_search,narrow
from tracker.battle_gen6 import apply_gen6_battle_hp

GAMES=('Pokémon X 1.0','Pokémon Y 1.0','Omega Ruby 1.0','Alpha Sapphire 1.0')


def ask_number(prompt,lower,upper):
    while True:
        value=input(prompt).strip()
        try:
            n=int(value)
            if lower<=n<=upper:return n
        except ValueError:pass
        print(f'Número entre {lower} y {upper}, por favor.')


def party_sample(reader,profile):
    party=decode_party(capture_party(reader,profile),max_species=721)
    return party,[{'slot':i+1,'species_id':p['species_id'],
                   'level':p['level'],'current_hp':p['hp'],'max_hp':p['max_hp']}
                   for i,p in enumerate(party) if p]


def probe_battle(reader,profile,party):
    summary={}
    _,confirmed=apply_gen6_battle_hp(reader,party,profile.name,profile.party_address,summary)
    summary['confirmed']=confirmed
    return summary


def main():
    print('\n=== DIAGNÓSTICO GEN6 · CAJAS Y PS EN COMBATE ===')
    print('Solo lectura. No modifica el juego ni los archivos guardados.')
    print('Necesita Windows de 64 bits, Python 3 y Lime3DS/Citra/Azahar abierto.')
    print('Evita los cambios de Pokémon entre las muestras del combate.')
    n=ask_number('Juego: 1=X, 2=Y, 3=Omega Ruby, 4=Alpha Sapphire: ',1,4)
    name=GAMES[n-1]
    pid_text=input('PID del emulador (Enter = detectar automáticamente): ').strip()
    pid=int(pid_text) if pid_text else None
    report={'schema_version':1,'game':name,'emulator':'Lime3DS/Citra/Azahar',
            'created_at':datetime.now(timezone.utc).isoformat(),
            'pc':{},'battle':{},'status':'incomplete',
            'privacy':'No contiene bytes crudos, nombres de entrenador, guardados ni credenciales.'}
    base=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
    out=base/'runtime'/(
        'diagnostico_gen6_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'.json')
    reader=None
    try:
        input('\nCarga la partida, fuera del combate y del PC; pulsa Enter para localizar el equipo. ')
        reader=LimeProcessMemory(pid=pid,progress=print,dynamic=True,generation=6)
        profile=replace(PROFILES[name],party_address=reader.party_address)
        report['party_address']=hex(profile.party_address)
        report['discovery']=getattr(reader.process,'discovery_report',{})
        party,summary=party_sample(reader,profile)
        if not summary:raise ValueError('No hay equipo válido.')
        print('Equipo reconocido:',', '.join(f"Slot {m['slot']}: especie {m['species_id']}, PS {m['current_hp']}/{m['max_hp']}" for m in summary))
        report['party_before']=summary

        answer=input('\n¿Localizar cajas depositando un Pokémon del equipo en CAJA 1 / CASILLA 1? [S/n]: ').strip().lower()
        if answer not in ('n','no'):
            chosen=ask_number('Número del slot del equipo que depositarás (1 a 6): ',1,6)-1
            target=party[chosen]
            if target is None:raise ValueError('El slot indicado no tiene Pokémon.')
            print('Pokémon de referencia: especie',target['species_id'],', ID cifrado ',hex(target['encryption_constant']))
            input('DEPOSITA ese Pokémon en la Caja 1, casilla 1. Cierra el PC y pulsa Enter. ')
            after,after_summary=party_sample(reader,profile)
            report['party_after_deposit']=after_summary
            report['pc']=find_deposited_box(reader,target['encryption_constant'],
                       target['species_id'],progress=print)
            print('PC:',json.dumps({k:v for k,v in report['pc'].items()
                    if k in ('ec_match_count','valid_stored_pk6_addresses',
                             'complete_box_base','ambiguous')},ensure_ascii=False))
        else:
            report['pc']={'skipped':True}

        answer=input('\n¿Capturar diagnóstico de PS durante combate? [S/n]: ').strip().lower()
        if answer not in ('n','no'):
            input('Fuera de combate, con el equipo preparado: pulsa Enter para tomar referencia. ')
            battle_party,summary=party_sample(reader,profile)
            report['battle']['party_before']=summary
            maximum=ask_number('PS MÁXIMOS del Pokémon que peleará: ',1,999)
            input('Entra en combate con ESE Pokémon. Pausa el emulador en el menú de movimientos y pulsa Enter. ')
            hp=ask_number('PS actuales que muestra el combate: ',1,maximum)
            found,errors=initial_search(reader,hp,progress=print,start=0x08000000,
                                        end=0x10000000,limit=500000)
            stages=[{'stage':'battle_1','hp':hp,'candidates':len(found),
                     'roster':probe_battle(reader,profile,battle_party)}]
            print('Coincidencias iniciales de PS:',len(found),'· errores de lectura:',errors)
            for idx in (2,3):
                print('Reanuda Lime3DS, recibe daño o cúrate sin cambiar de Pokémon.')
                input('Pausa de nuevo el emulador en el menú de movimientos y pulsa Enter. ')
                new_hp=ask_number('Nuevos PS (distintos a la lectura anterior): ',1,maximum)
                while new_hp==hp:
                    new_hp=ask_number('Los PS deben haber cambiado. Nuevo valor: ',1,maximum)
                hp=new_hp
                found=narrow(reader,found,hp)
                stages.append({'stage':'battle_'+str(idx),'hp':hp,
                               'candidates':len(found),
                               'roster':probe_battle(reader,profile,battle_party)})
                print('Direcciones restantes:',len(found))
            report['battle'].update(
                status='completed',read_errors=errors,stages=stages,
                candidate_addresses=[hex(addr) for addr in found[:256]],
                total_candidates=len(found))
            print('Captura de combate completada. Puedes reanudar el juego.')
        else:
            report['battle']={'skipped':True}
        report['status']='completed'
    except (Exception,KeyboardInterrupt) as exc:
        report['error']=str(exc) or 'Captura interrumpida'
        print('Se guardará el diagnóstico parcial:',report['error'])
    finally:
        if reader:
            try:reader.close()
            except Exception:pass
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('\nArchivo JSON para compartir:\n',out.resolve())
        print('El diagnóstico es de SOLO LECTURA. Recuerda reanudar el emulador.')


if __name__=='__main__':
    main()
