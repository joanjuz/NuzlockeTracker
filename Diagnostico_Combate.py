"""Interactive battle-memory capture for Ultra Sun/Moon 1.0 on Windows."""
import json
from dataclasses import replace
from pathlib import Path
from datetime import datetime,timezone
from tracker.process_memory import LimeProcessMemory
from tracker.profiles import PROFILES
from tracker.battle_probe import initial_search,narrow,sample


def number(prompt,minimum=1,maximum=9999):
    while True:
        try:
            value=int(input(prompt))
            if minimum<=value<=maximum:return value
        except ValueError:pass
        print(f'Escribe un número entre {minimum} y {maximum}.')


def main():
    print('DIAGNÓSTICO DE COMBATE · Solo lectura · No necesita GDB')
    print('Usa un combate individual normal, sin aliados/SOS ni transformaciones.')
    print('No cambies de Pokémon durante las tres lecturas. No reinicies el juego.')
    choice=number('Juego: 1 Ultra Luna 1.0 / 2 Ultra Sol 1.0: ',1,2)
    profile=PROFILES['Ultra Moon 1.0' if choice==1 else 'Ultra Sun 1.0']
    label=input('Nombre o especie del Pokémon que usarás: ').strip()[:80]
    maximum=number('PS máximos: ')
    input('Carga la partida, fuera de combate. Pulsa Enter para localizar la RAM. ')
    report={'schema_version':1,'game':profile.name,'pokemon':label,'max_hp':maximum,'samples':[],
            'note':'Candidatos experimentales; no son direcciones verificadas.'}
    output=Path(__file__).resolve().parent/'runtime'/('combate-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'.json')
    reader=None
    try:
        reader=LimeProcessMemory(progress=print,dynamic=profile.name=='Ultra Sun 1.0')
        profile=replace(profile,party_address=reader.party_address)
        report['party_address']=hex(profile.party_address)
        report['samples'].append({'stage':'outside_before',**sample(reader,profile)})
        input('Entra en combate. En el menú de elegir movimiento, PAUSA Lime3DS y pulsa Enter aquí. ')
        hp=number('PS actuales que muestra el juego: ',1,maximum)
        candidates,errors=initial_search(reader,hp,print)
        report['scan_read_errors']=errors
        report['samples'].append({'stage':'battle_1','visible_hp':hp,'candidate_count':len(candidates),**sample(reader,profile)})
        for stage in (2,3):
            print('Reanuda Lime3DS. Recibe daño o cura al MISMO Pokémon; espera a que termine el turno.')
            input('Cuando tenga OTROS PS, pausa en el menú de movimientos y pulsa Enter. ')
            current=number('Nuevos PS visibles: ',1,maximum)
            while current==hp:
                current=number('Deben ser distintos a la lectura anterior. Nuevos PS: ',1,maximum)
            hp=current;candidates=narrow(reader,candidates,hp)
            report['samples'].append({'stage':f'battle_{stage}','visible_hp':hp,'candidate_count':len(candidates),**sample(reader,profile,candidates)})
            print(f'Quedan {len(candidates)} candidatos.')
        print('Reanuda y termina el combate. No cures todavía al equipo.')
        input('Ya fuera de combate, pausa Lime3DS y pulsa Enter. ')
        report['samples'].append({'stage':'outside_after',**sample(reader,profile,candidates)})
        report['candidates']=[hex(a) for a in candidates];report['complete']=True
    except (Exception,KeyboardInterrupt) as exc:
        report['error']=str(exc) or 'Captura cancelada';report['complete']=False
        print('Captura incompleta:',report['error'])
    finally:
        if reader:reader.close()
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('\nArchivo para enviar: '+str(output))
        print('Recuerda reanudar Lime3DS. El diagnóstico no cambia ni cura Pokémon.')

if __name__=='__main__':main()
