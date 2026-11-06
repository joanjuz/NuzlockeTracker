# Datos de Definitive Randomizer en Progressive Tracker

Definitive Game Data v1 importa metadatos de **Ultra Sol o Ultra Luna** desde el estado guardado de un proyecto de Definitive Randomizer. Se conserva una importación por partida del Tracker. No escribe en ROMs, guardados o RAM ni conecta con servicios remotos.

## Uso

1. En Randomizer, guarda tus cambios y usa **Exportar datos para Progressive Tracker**.
2. En Tracker, abre la partida que debe usar esos datos. En **Conexión**, selecciona el juego correspondiente.
3. Abre **Datos de Definitive Randomizer**, selecciona el JSON y pulsa **Importar datos de Definitive Randomizer**.
4. Revisa el juego, las cantidades y la muestra de diferencias. El archivo todavía no se ha importado. Si la revisión es desconocida, confirma expresamente el aviso. El Tracker solo tiene perfiles USUM 1.0; el aviso no verifica la revisión real de la ROM del emulador.
5. Pulsa **Confirmar importación**. Se guardará en la carpeta de esa partida y se conservará al cerrar y reabrir Tracker. Solo se activa cuando el juego actual coincide. Conecta el juego compatible si todavía no está seleccionado como sesión actual.

Para reemplazar los datos, previsualiza y confirma otro archivo. **Cancelar** no escribe nada. **Retirar importación** vuelve a los CSV y las referencias existentes. Una importación inválida o un error de escritura conserva el catálogo anterior.

## Qué utiliza esta entrega

| Datos del archivo | Integración en Tracker |
| --- | --- |
| Especie y forma, nombre y tipos | Fichas/equipo/cajas y análisis por tipos. Los IDs de tipo se interpretan con la numeración Gen7; el idioma del nombre exportado no redefine su significado |
| Estadísticas base | Sección **Estadísticas base · Definitive Game Data**. No sustituyen PS actuales, nivel, estadísticas calculadas, IV o EV de RAM |
| Habilidades | Nombres por ID y lista de habilidades de la especie. La habilidad del Pokémon actual sigue obteniéndose de su ID leído en RAM; no se inventa un cambio de habilidad |
| Movimientos | Nombre, tipo, categoría, potencia, precisión, PP y prioridad en la ficha y análisis. Descripciones y efectos no incluidos en v1 conservan la referencia; no se simulan parches de combate |
| Evoluciones | Rutas por especie/forma con método, argumento, destino, forma y nivel. Una lista explícitamente vacía elimina las rutas de referencia para ese registro. Métodos especiales no descritos por el catálogo se muestran con su código, sin inventar condiciones |
| Juego, revisión, productor y fingerprint | Validación, estado de importación y procedencia. El fingerprint identifica los datos exportados; no demuestra qué ROM está ejecutando el emulador |
| Índice personal | Identificación técnica del registro exportado. Tracker usa especie/forma como clave, no offsets ni clases binarias del Randomizer |

Para registros presentes, **DGD prevalece sobre CSV**, y CSV sobre las referencias originales. Los registros ausentes conservan las referencias/CSV aplicables. Las listas de evoluciones presentes reemplazan la lista entera del registro; no se añaden silenciosamente a la original. Los datos de otra partida o de otro juego no se activan.

## Contrato y límites

El contrato canónico, el esquema JSON y el ejemplo sintético se mantienen en [Definitive Randomizer · docs/contracts](https://github.com/joanjuz/Definitive-Randomizer/tree/main/docs/contracts). No existe dependencia binaria entre aplicaciones.

`tests/fixtures/definitive-game-data-v1.synthetic.json` conserva una copia del ejemplo sintético para comprobar compatibilidad en CI sin acceder al otro repositorio ni distribuir datos de una ROM.

Se admite `schemaVersion: 1`, productor `DefinitiveRandomizer`, Ultra Sol/Ultra Luna y revisión conocida `1.0`, o desconocida con confirmación. Otras versiones del esquema, juegos, Title IDs incoherentes, IDs/valores fuera de rango, claves duplicadas, referencias inválidas y archivos mayores de 5 MB se rechazan. Se toleran campos opcionales adicionales para futuras extensiones.

Los datos se guardan como `definitive-game-data.json` dentro de la carpeta de la partida. Son metadatos locales, no una prueba de que una ROM coincida con el archivo. No se transmite el documento por Soul Link ni se cambia el contrato de sus snapshots; cada jugador importa su propio catálogo. La demo y las fuentes remotas OBS no permiten importar. No se añade soporte de memoria DS, Switch, Sol/Luna o revisiones distintas de 1.0.
