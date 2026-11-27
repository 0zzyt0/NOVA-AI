# ◆ NOVA AI — Asistente de vuelo por voz para Star Citizen

Nova es tu IA de a bordo (y puedes ponerle el nombre que quieras):
- **Te escucha:** mantienes una tecla o la llamas por su nombre («Nova…», o el que le pongas).
- **Aprende tu voz:** la primera vez te pregunta tu nombre y el suyo, y entrena su oído contigo.
- **Maneja la nave:** pulsa las teclas del juego por ti.
- **Responde:** con una voz natural y con humor.
- **Busca información en vivo:** lore, naves, armas, ubicaciones, misiones y precios.
- **Sigue la partida:** lee tu Game.log para saber dónde estás.
- **Lo sabe todo del parche:** enciclopedia local con misiones, planos (BP), fabricación y minería de scmdb.net, precios de UEX y los textos oficiales de tu juego, actualizada al arrancar.
- **Lleva un cuaderno de bitácora:** dónde dejaste el personaje, última nave pilotada, quién entra y sale de la nave, muertes…
- **Recuerda cosas** de ti entre sesiones, y **dónde lo dejaste**: al abrirla recupera la conversación, la sección y el tamaño de la ventana.
- **Se inventa lo que no sabe**, y te lo confiesa al final.
- **Usa tus teclas:** lee tu configuración de controles de Star Citizen cada vez que arranca.
- **Brilla en el juego:** su logo aparece en una esquina y parpadea mientras te habla (overlay).
- **Pone Star Citizen en español:** instala y mantiene al día la traducción de 0zzyt0.
- **Novedades 2.0:** ventana reorganizada (Juego SC · Nova · Pantalla · Información · Ajustes) con buscador de ajustes, 7 estilos de voz y nombres del juego pronunciados en inglés, temas de color, nuevos logos del overlay y modelos de holograma, letra más gruesa, copias de seguridad, y el instalador te deja elegir carpeta y unidad.
- **Novedades 1.5:** apunta tus compras, lo que te equipas y los atraques en la bitácora, y el manual llega en los cinco idiomas con sus propias capturas.
- **Novedades 1.4:** sigue en la bandeja de Windows con la ventana cerrada, modo reposo, recorrido guiado y cuestionario anónimo.
- **Novedades 1.2:** fichas en holograma sobre el juego: ficha policial de jugadores y de objetivos de recompensa, y fichas de planetas, lunas y lugares de verseguide.com.
- **Novedades 1.1:** busca jugadores en la web de RSI (y los manda a Discord), temporizadores de refinado y contratos, rutas con el beneficio real de tu bodega, perfiles por nave, estado de los servidores y estadísticas de todas tus sesiones.

Todo lo que usa es **gratis**.

---

## 1. Instalación (5 minutos)

1. Haz doble clic en **`NOVA AI Setup.exe`** (el instalador todo en uno, con el logo de NOVA AI). Windows pedirá **permiso de administrador**: pulsa «Sí». Se abre el instalador holográfico azul, que:
   - **te pide aceptar las Normas de uso y la Política de privacidad** (sin aceptarlas no se instala);
   - **instala NOVA AI en `C:\Program Files\NOVA AI`** («Archivos de programa») o donde quieras: en **▸ Carpeta de instalación** ves la ruta y el espacio libre de esa unidad, y **«Elegir carpeta…»** la cambia a otra carpeta o unidad (al actualizar se queda donde estaba);
   - **comprueba el sistema:** Python, tarjeta gráfica, espacio libre y conexión;
   - **instala Python 3.12** si no lo tienes, solo para tu usuario y sin tocar el tuyo;
   - **muestra el progreso** con porcentaje, paso actual, velocidad de descarga y **tiempo restante estimado**;
   - **crea el acceso directo «NOVA AI»** en el escritorio y en el menú Inicio, con su icono;
   - **registra el desinstalador** («Desinstalar NOVA AI», con su icono rojo) y abre Nova al terminar.
2. Ya puedes borrar el instalador. Abre Nova con el acceso directo **NOVA AI** del escritorio.

**¿Prefieres el `.zip`?** Descomprime `Nova.zip` y abre **`NOVA AI Setup.exe`** de dentro (o `INSTALAR.bat`, que hace lo mismo). Es el mismo instalador.

**«Windows protegió su PC»:** el instalador no está firmado con un certificado de pago, así que SmartScreen puede avisar la primera vez. Pulsa **«Más información → Ejecutar de todas formas»**.

**Si el instalador gráfico no llega a abrirse**, ya no se cierra sin decir nada: lo reintenta de otra forma y, si sigue sin poder, te enseña una ventana con el motivo y te ofrece abrir el registro (`%TEMP%\NOVA_AI_Setup.log`). Como último recurso, `INSTALAR_CONSOLA.bat` del `.zip` instala Nova en modo portátil.

### Dónde queda cada cosa
- **El programa:** `C:\Program Files\NOVA AI` (o la carpeta que elegiste).
- **Tus datos** (ajustes, comandos propios, memoria, sesión, voces y modelos descargados): `%LOCALAPPDATA%\NOVA AI\datos`. Windows no deja escribir en «Archivos de programa» sin ser administrador, por eso viven aparte. **Ajustes › Copias y archivos › Carpeta de datos** la abre.
- **Si ya tenías Nova instalada:** el instalador encuentra tu carpeta antigua (por su acceso directo «NOVA» del escritorio, o la carpeta `datos\` junto al instalador) y **trae tus ajustes, comandos y memoria**. Después puedes borrar la carpeta antigua.

### Desinstalar
Tres caminos, todos hacen lo mismo:
- **Menú Inicio → NOVA AI → Desinstalar NOVA AI.**
- **Configuración de Windows → Aplicaciones → Aplicaciones instaladas → NOVA AI → Desinstalar.**
- **`Desinstalar NOVA AI.exe`**, dentro de la carpeta del programa.

Borra el programa, los accesos directos y el registro. Tus datos **se conservan**, salvo que marques «Borrar también mis datos»; así, si reinstalas, Nova lo recuerda todo. Python 3.12 no se toca: si lo instaló Nova y ya no lo quieres, quítalo aparte desde Aplicaciones.

### La ventana de Nova
Se abre en una ventana propia de **Microsoft Edge** (modo aplicación, sin barra de direcciones), que Windows 10/11 ya trae. **Si cierras la ventana, Nova se apaga**; minimízala mientras juegas. El botón **⏻** (arriba a la derecha) apaga Nova del todo: cierra la ventana, el overlay y la escucha. Todo funciona en tu PC: la ventana solo habla con Nova dentro de tu propio ordenador.

**Al cerrar, Nova guarda dónde lo dejaste** (y además cada 30 segundos, por si se va la luz). Al día siguiente recupera:
- la conversación, con una línea «Sesión anterior»; y la IA sigue el hilo de lo que hablasteis;
- la sección que tenías abierta y la posición y el tamaño de la ventana;
- la última ubicación del juego: «La última vez nos quedamos en Lorville».

Los ajustes se guardan en el momento en que los cambias.

Notas:
- **Reparar o actualizar:** abre el `NOVA AI Setup.exe` de la versión nueva. Detecta la instalación, cierra Nova si está abierta, sustituye el programa y conserva tus datos.
- **Si algo falla durante la instalación:** el instalador muestra el error con los botones «Reintentar» y «Ver registro». El registro completo está en `%LOCALAPPDATA%\NOVA AI\datos\instalacion.log`. Si Nova ya instalada se cierra al arrancar, `NOVA AI.exe` te enseña las últimas líneas del error; para ver todos los mensajes usa **`DEPURAR.bat`** de la carpeta del programa.

## 1 bis. Primera vez: configuración y entrenamiento de voz

Antes de usar nada, Nova abre una ventana para terminar de configurarse. Puedes responder **hablando** (botón 🎙) **o escribiendo**. Cada respuesta se marca con un **✓ verde** si te ha entendido o una **✕ roja** si no ha entendido nada; en ese caso, repite.

1. **Micrófono:** elige el tuyo y comprueba que el medidor se mueve. Opcional: una clave gratis de Groq hace el reconocimiento instantáneo; sin ella se usa Whisper en tu PC, que la primera vez descarga el modelo.
2. **Tu juego:** Nova busca tu carpeta `LIVE` de Star Citizen y su traducción (`global.ini`). Si no tienes el juego en español te pregunta: «Veo que no dispones de una traducción al Español de Star Citizen. ¿Quieres que te descargue la versión más actual de 0zzyt0?». Con **Sí** la descarga y la instala ella sola (ver sección 7 quinquies). Si no encuentra el juego, pulsa «Elegir carpeta».
3. **¿Cómo te llamas?** («Me llamo Antonio»). Ahí eliges también cómo quieres que te trate: señor, capitán, por tu nombre…
4. **¿Cómo quieres que me llame?** Cualquier nombre: Nova, Atenea, Jarvis… Te avisa si es muy corto o una palabra demasiado común, porque se activaría sin querer.
5. **Ejercicios de sonido:** «Perfecto, mi nombre es Atenea. Vamos a entrenar mis oídos…». Pulsa «Escuchar cómo suena» y después **di solo su nombre tres veces**.
6. **Lee 3 frases** sobre Star Citizen que empiezan por su nombre. Se eligen **al azar** cada vez que haces la configuración:
   - una con **muchas vocales seguidas**, para que capte bien tu vocalización: «Atenea, aún oigo el aeropuerto de Área Dieciocho y huelo a aceite.»
   - otra con **ñ, ll, y, b, v, g, j, n y m**, los sonidos que más le cuestan: «Atenea, la señal de ayuda llega de un jugador bajo el hielo de Yela; vamos ya en la Gladius.»
   - y otra que mezcla las dos: «Atenea, oye, ayúdame: llevo veinte cajas de oro bajo la niebla y mañana viajo a Pyro.»
7. **Listo:** resumen. Opcional: tu clave gratis de Gemini.

**Lo que aprende:**
- **Cómo escribe el reconocimiento de voz su nombre** cuando lo dices tú. Si oye «Ya tenía» en vez de «Atenea», lo apunta y a partir de entonces también le sirve.
- **Tu volumen de voz y el ruido de tu habitación**, para ajustar solo la sensibilidad del micrófono.

**Para cambiarle el nombre o repetir el entrenamiento:** ve a **Ajustes › ADN e Inteligencia › Identidad**. Al cambiar el nombre olvida lo aprendido del anterior, así que conviene **repetir la configuración**. En **Ajustes › Voz y audio › Cómo hablarle** ves cómo oye su nombre en tu voz; si alguna forma aprendida la activa sin querer, pulsa «Olvidar».

## 2. Claves gratuitas (Ajustes › ADN e Inteligencia)

**Sin claves de serie (desde la 2.1.5):** NOVA ya no trae claves de IA de fábrica (eran las mismas para todos y el cupo gratis se agotaba entre todos). Consigue las tuyas, gratis y en 2 minutos (pasos abajo y en el manual), y pégalas en la casilla *Pega aquí cualquier clave*: NOVA reconoce de qué servicio es, la guarda y la prueba. Con la clave de un servicio usa todos sus modelos gratuitos y, si uno se queda sin cupo, salta sola al siguiente.

Sin ninguna clave, Nova ya ejecuta comandos por frase directa. **Para conversar y buscar** necesita al menos una.

| Servicio | Para qué | Dónde se consigue | Coste |
|---|---|---|---|
| **Gemini** (Google) | El cerebro más listo | aistudio.google.com/apikey | Gratis, sin tarjeta, con límite diario |
| **Groq** | Respaldo ultrarrápido **y** reconocimiento de voz en la nube | console.groq.com/keys | Gratis, sin tarjeta |
| OpenRouter | Más modelos gratis (`:free`) | openrouter.ai/keys | Gratis, unas 50 peticiones al día |
| Mistral | Europeo, muy bueno en español, francés y alemán. **Opcional** | console.mistral.ai/api-keys | **De pago** desde agosto de 2026 (va en *Avanzado*) |
| Ollama | IA en tu propio PC, sin internet | ollama.com | Gratis (necesita buena GPU) |

**Recomendado: Gemini + Groq.** Pulsa «Conseguir clave», copia la clave y pégala.

### Cadena de motores
Nova prueba los motores **en orden**. Si uno se queda sin cuota o falla, salta al siguiente sin que lo notes. El orden por defecto es:
1. Gemini `gemini-flash-lite-latest`: rápido, con muchas peticiones gratis, y siempre la última versión.
2. Gemini `gemini-3.5-flash-lite`.
3. Groq `openai/gpt-oss-120b`.
4. OpenRouter `openrouter/free`.

Si pones la clave de un servicio que no está en tu cadena, se añade solo al final. **Mistral** (de pago desde agosto de 2026) y **DeepSeek** ya no son gratuitos: solo entran en la cadena si pones tu propia clave. Al actualizar desde la 1.x, Nova quita la clave de fábrica de Mistral y respeta la tuya.

Los botones de cada motor:
- **Probar:** comprueba que la clave funciona.
- **Modelos:** descarga la lista actual de modelos del proveedor. Los modelos gratuitos cambian a menudo.

## 3. Cómo hablarle

- **Tecla para hablar:** mantén **Insert** mientras hablas y suelta. Puedes cambiarla en **Ajustes › Voz y audio › Cómo hablarle › Asignar**: sirve cualquier tecla, botón lateral del ratón o **botón del HOTAS o joystick**. Si pulsas la tecla mientras Nova habla, se calla.
- **Por su nombre:** di «**Nova**, baja el tren» (o el nombre que le hayas puesto). Si solo dices su nombre, te responde «¿Sí, señor?» y puedes dar la orden sin repetirlo. En **Ajustes › Voz y audio › Otras formas de llamarla** puedes añadir más, como «computadora».
- **Por escrito:** usa la caja de texto de la **Cabina**.
- **Para que se calle:** di «silencio», «cállate» o «basta», o pulsa 🔇.
- **Para pausarla:** di «Nova, desactívate» o pulsa ⏸. Vuelve con «Nova, actívate».

### Ejemplos
- «Preparar tren de aterrizaje», «Tren arriba», «Aterrizaje automático»
- «Activar escudos», «Desactivar energía», «Activa las armas», «Luces»
- «Prepara la nave», «Pide permiso para aterrizar», «Secuencia de despegue»
- «Bengalas», «Siguiente hostil», «Ping», «Modo cuántico», «Salto cuántico»
- Lenguaje libre, que resuelve la IA:
  - «Baja el tren y sube los escudos, que vamos a tomar tierra»
  - «¿Qué arma de tamaño 3 me recomiendas para la Gladius?»
  - «¿Dónde vendo Laranite más caro?»
  - «Dame una ruta comercial desde Lorville con 50.000 aUEC»
  - «Cuéntame el lore de los Tevarin»
  - «¿Dónde estoy?», «¿Qué contratos tengo?»
  - «Recuerda que mi nave favorita es la Cutlass Black»
  - «¿Qué es la Nebulosa del Gorgonzola?» (te lo inventará y lo confesará 😄)

## 4. Voces (Ajustes › Voz y audio)

**Estilos de voz (2.0):** arriba de **Ajustes › Voz y audio** tienes siete estilos ya afinados (voz, velocidad, tono y efecto de cabina) con el aire de las IA de a bordo del cine: *Clásica de NOVA*, *Mayordomo de a bordo*, *Ordenador de la nave*, *Copiloto cercano*, *IA táctica*, *Asistente serena* y *Voz internacional* (una voz inglesa que habla tu idioma con acento). Son voces sintéticas de Microsoft Edge: **no imitan a ningún actor ni personaje**. Si después tocas algo a mano, el estilo se desmarca.

**Nombres del juego en inglés (2.0):** Edge lee «Crusader» o «Hurston» con las reglas de tu idioma. Con **Nombres del juego en inglés** (activado de serie) Nova los dice como en el juego: planetas, lunas, estaciones, fabricantes y naves. En **Mi pronunciación** añades o corriges los tuyos, uno por línea (`Orison = Órison`).

- **Edge:** voces neuronales de Microsoft, gratis y muy naturales. Necesita internet. Prueba `es-ES-XimenaNeural`, `es-ES-AlvaroNeural` o las *Multilingual*, que son más expresivas.
- **Piper:** gratis y sin internet. La voz se descarga sola la primera vez.
- **Windows:** la voz del sistema, por si todo lo demás falla.

También puedes ajustar velocidad, tono, volumen y el **efecto de voz** (2.0): sin efecto, *IA de cabina* (altavoz de nave, más marcado que en la 1.x), *Comunicador del casco*, *Radio* o *Walkie-talkie* (con ruido de fondo, chasquido al empezar y al acabar y pitido de cambio), con su intensidad. Si el motor elegido falla, Nova cambia solo al siguiente. El botón **▶ Probar voz** es un interruptor: si lo pulsas otra vez, se calla.

**¿Por dónde suena?** Si tienes varias salidas de audio (altavoces, auriculares, interfaz USB…), elígela al final de **Ajustes › Voz y audio** (Salida de audio).

## 5. Reconocimiento de voz (Ajustes › Voz y audio)

- **auto** (por defecto): usa Groq si tienes clave, que es lo más rápido y no gasta tu PC. Si no hay clave, usa Whisper en tu PC.
- **local:** Whisper en tu PC. Con una tarjeta **NVIDIA** puedes usar `large-v3-turbo`, rapidísimo y muy preciso. Sin NVIDIA, usa `small` (el instalador detecta tu tarjeta). El modelo se descarga la primera vez.
- Nova ya conoce palabras del 'verso: Hurston, aUEC, Cutlass, CrimeStat…

> Con «Escuchar Nova sin tecla», cada frase que dices se transcribe para buscar su nombre. Con Groq eso gasta cuota: unas 2.000 frases gratis al día. Con Whisper local gasta algo de CPU. Si juegas hablando mucho por Discord, usa solo la tecla.

## 6. Comandos y teclas (Juego SC)

### Tus teclas del juego, siempre al día
Cada vez que arranca, Nova lee tu archivo de controles de Star Citizen:
`…\StarCitizen\LIVE\user\client\0\Profiles\default\actionmaps.xml`.

Ese archivo guarda **las teclas que has cambiado** en Opciones → Controles. Con él, Nova:
- **cambia sus comandos para pulsar tus teclas.** Si moviste el tren de aterrizaje a `Num 1`, «baja el tren» pulsará `Num 1`;
- **crea comandos nuevos** para las acciones a las que diste tecla en el juego y Nova no tenía. Salen con la etiqueta «DEL JUEGO»;
- **te avisa** de las acciones que dejaste sin tecla de teclado, o que solo tienes en el joystick o HOTAS. Nova no puede pulsar un botón del joystick: asígnales también una tecla.

El panel «Teclas de Star Citizen» muestra el resultado; tienes un botón **⟳ Sincronizar ahora** por si cambias controles con Nova abierta. Las acciones peligrosas (autodestrucción, eyección…) nunca se convierten en comandos automáticos.

Lo que no cambiaste se queda con las teclas de fábrica de Star Citizen 4.x.

### Crear tus propios comandos
Pulsa **＋ Nuevo comando** (o ✎ en uno existente):
1. Ponle un **nombre** y las **frases de voz** que quieras, una por línea. Esas frases se ejecutan al instante, sin IA.
2. Pulsa **● Grabar** y **pulsa la combinación en tu teclado** (por ejemplo `Ctrl der` + `Num 8`). Nova la graba tal cual, incluidas Ñ, Alt Gr y el teclado numérico.
3. Si quieres una secuencia, añade más pasos: **＋ Tecla**, **＋ Clic de ratón** o **＋ Espera**. Cada tecla puede **mantenerse** unos segundos o ser una **doble pulsación**.
4. **＋ Acción del juego** añade un paso ligado a una acción de Star Citizen. Si un día cambias esa tecla en el juego, Nova la actualiza sola (lo indica ⟳).
5. **▶ Probar en 3 s** ejecuta el comando tras una cuenta atrás, para que te dé tiempo a cambiar al juego. Después pulsa **Guardar**.

Tus comandos se guardan en tu carpeta de datos (`comandos_personales.json`), separados de los de fábrica, así que las actualizaciones de Nova no los borran. Si modificas uno de fábrica aparece como «MODIFICADO»; con ↺ vuelves al original. Con 🗑 los de fábrica solo se ocultan: puedes recuperarlos en «Comandos ocultos».

Activa **«Solo con la frase exacta»** en los comandos delicados: la IA nunca los ejecutará por su cuenta. Así está protegido «expulsar carga».

⚠ **Los sistemas son interruptores.** «Activar escudos» y «Desactivar escudos» pulsan la misma tecla: Nova no puede ver el estado real de la nave. Si ya estaban activos, «activar» los apaga.

⚠ **«Salto cuántico» mantiene la tecla del cuántico** (B por defecto) 2 segundos. Funciona en modo navegación con un destino marcado.

## 7. El Game.log

Nova lee el archivo de registro que escribe el juego. Solo lo lee: no toca la memoria del juego ni nada que pueda dar problemas con el anticheat. Busca el log solo en `…\StarCitizen\LIVE\Game.log`; si no lo encuentra, indica la ruta en **Juego**.

### En tu idioma, gracias al global.ini
El juego escribe los avisos del HUD tal cual los ves, **en tu idioma**: «Nuevo miembro unido · Ph3nomenas se ha unido a grupo», «AUTORIZACIÓN ATC: CONCEDIDO»… Nova lee el **global.ini** de tu juego, el archivo con todos sus textos, y aprende de él cómo es cada aviso.

**Dónde lo busca:** en `LIVE\data\Localization\<idioma>\global.ini`, según el idioma de tu `user.cfg`. Si usas una traducción de la comunidad, también vale. En **Fuentes de datos** puedes indicar otra ruta.

**Si cambias de idioma o un parche cambia los textos,** Nova se adapta sola. Sin global.ini (juego en inglés) usa los textos originales en inglés que trae.

**Resultado con tu Game.log del 7/11:** antes Nova entendía 8 de unos 90 avisos de la sesión; ahora los entiende todos.

### Qué sabe Nova por el log
- **Personaje, versión del juego y servidor.**
- **Dónde estás:** estaciones, ciudades, puntos de salto (con los nombres oficiales de tu idioma) y el destino de cada salto cuántico, con el combustible estimado.
- **Tu nave:**
  - a qué nave subes y de qué nave bajas, también si es la de otro jugador;
  - cuándo dejas los mandos;
  - la nave que te entregan en el hangar.
- **Tu tripulación:** quién sube y baja de tu nave (el canal de la nave).
- **Zonas:** armisticio, espacio vigilado, jurisdicción, territorio hostil, zona restringida y llamaradas solares.

### Avisos en voz
Nova comenta lo que pasa en la partida. Puedes activar o desactivar cada tipo en **Juego SC › Lectura del juego y teclas**:
- **Ubicación:** llegadas, armisticio y jurisdicción.
- **Tu nave:**
  - quién sube y quién baja;
  - si subes a otra nave;
  - daños, si el juego los anota.
- **Grupo:**
  - invitaciones;
  - quién entra y quién sale;
  - nuevo líder;
  - lanzamiento de grupo;
  - calibración cuántica;
  - alguien que salta hacia ti.
- **Dinero:** te envían dinero, te lo ofrecen o lo envías tú.
- **Amistad:** peticiones de amistad, amigos añadidos, llamadas entrantes y acceso a hangares.
- **Torre de control:** autorización concedida, puesto en la cola con el tiempo de espera, y nave incautada.
- **También:**
  - contratos y objetivos;
  - heridas, incapacitación, rescate y muerte;
  - CrimeStat, delitos y multas;
  - planos recibidos;
  - refinería lista.

Los avisos se ponen en cola: no se pierden aunque Nova esté hablando. Si uno lleva más de 45 segundos esperando, se descarta. «A bordo de la MOLE» solo se dice si llevas un rato fuera; entrar y salir de la cabina no se anuncia cada vez.

**Lo que el Game.log de la 4.10 no trae (o casi nunca):**
- **Las frases habladas de la torre:** sí aparece la **autorización** («AUTORIZACIÓN ATC: CONCEDIDO») y la cola, pero no lo que dice el controlador.
- **Combate y salud:** muertes de jugadores y NPC (quién, con qué arma y de qué), naves y vehículos destruidos o inutilizados, incapacitaciones con su causa, punto de reaparición y curas en camilla médica. Desde la versión 4.0.2 el juego solo escribe los que te afectan a ti (los que causas o sufres).
- **Carga:** conexión con el servidor, aparición del personaje, tiempo de carga del universo y las cargas que se atascan.
- **Qué NO aparece:** fijar un objetivo (marcar o «tarjetear» a un enemigo) no se escribe en el Game.log. Desde la 1.1, si se lo pides por voz («Nova, fija el objetivo»), Nova pulsa la tecla y lo anota ella en la bitácora.
- **Saldo, combustible y estado de los escudos.**

## 7 ter. Archivos de Bitácora

Cada sesión de juego queda apuntada en un archivo `.log` que puedes abrir con el Bloc de notas, en `%LOCALAPPDATA%\NOVA AI\datos\diario\` (por ejemplo `2026-11-07_2147_Nebula_Rider.log`). En **ADN y Memoria › Bitácora y estadísticas** ves el resumen de la sesión y las bitácoras guardadas (se conservan las 60 últimas).

**Cada línea:** la hora y lo que pasó: llegadas, saltos, subir y bajar de naves, quién entra y sale de tu nave y del grupo, la torre, amistades, contratos, planos, heridas…

Y todo lo de combate, salud y carga que te afecta:
- `COMBATE`: abates a un NPC o jugador (con qué arma y cómo), naves que destruyes o inutilizas;
- `MUERTE` / `MUERTES`: tus muertes (quién, con qué, causa: disparos, explosión, asfixia…), las de otros, y el punto de reaparición;
- `NAVES`: otras naves destruidas o inutilizadas que anota el juego;
- `SALUD`: incapacitaciones con su causa y curas en camilla médica (qué partes del cuerpo y en qué nave);
- `CARGA` y `RED`: conexión, aparición, tiempo de carga del universo, cargas atascadas y tirones de red.

**El resumen final:**
- dónde dejaste el personaje;
- última nave pilotada;
- estado de la nave: daños, última entrega en el hangar y último salto con su combustible;
- naves a las que has subido;
- gente que ha entrado y salido de tu nave (cuántas veces y quién);
- grupo, muertes, saltos y autorizaciones de la torre;
- combate y salud: bajas (NPC y jugadores), naves derribadas, curas en camilla médica y punto de reaparición;
- carga y red: tiempo de entrada al universo, cargas lentas y tirones de red.

Sale del propio Game.log: si abres Nova con la partida empezada o después de jugar, rehace el diario completo de esa sesión. Al día siguiente te saluda con «La última vez nos quedamos en…». Puedes preguntarle «¿dónde dejé el personaje?», «¿cuál fue la última nave que piloté?» o «¿quién ha entrado en la nave?».

## 7 octies. Novedades de la versión 1.1

- **Buscar jugadores.** Di «Nova, localízame a un jugador» o «búscame a un jugador»: te pedirá que **escribas el apodo** en el cuadro de texto de la Cabina (por voz se entendería mal). Lee su ficha pública en `robertsspaceindustries.com/en/citizens/APODO` y te da: Apodo en juego, HandleName, UEE Citizen Record, Fecha de alta (Enlisted), Fluency (idioma) y Main Organization; después abre `robertsspaceindustries.com/en/orgs/ORG` (miembros, tipo, actividad). La ficha se guarda en la bitácora (etiqueta `JUGADOR`) y, si pegas un webhook en **Ajustes › Discord**, se manda a ese canal. Si hay cualquier error o la ficha no trae esos datos: «Usuario no encontrado, ¿Está bien escrito el apodo?». Si el jugador o su organización tienen algún dato oculto (RSI lo muestra como `[REDACTED]`), Nova te avisa de que esa información está oculta. También vale escribirlo de una vez: «búscame al jugador Nebula_Rider».
- **Temporizadores** para refinados, contratos o lo que quieras: «avísame en 3 horas y 20 minutos, el refinado de ARC-L1». Se ven en la Cabina, se crean también a mano y **siguen aunque cierres Nova** (si terminan con ella cerrada, te lo dice al volver). Quedan en la bitácora (`TEMPORIZADOR`).
- **Rutas de comercio con beneficio real:** con los precios de UEX, Nova calcula cuántas SCU caben en la nave en la que vas (o la que le digas), el stock del origen, la demanda del destino y tu dinero, y ordena por lo que ganas de verdad. Si no sabe tu nave, usa la «Bodega por defecto» de Fuentes de datos.
- **Perfiles de nave:** en **Juego SC › Perfiles de nave**, cada nave puede tener sus propios avisos en voz. En el editor de comandos, **Solo en estas naves** limita un comando a ciertas naves (y deja usar la misma frase con teclas distintas en cada una).
- **Estado de los servidores:** al arrancar mira `status.robertsspaceindustries.com` y te avisa si hay caídas o mantenimiento (Cabina › Situación y Fuentes de datos). Pregúntale «¿cómo están los servidores?».
- **Fijar el objetivo por voz:** «Nova, fija el objetivo» pulsa la tecla y lo anota en la bitácora (`OBJETIVO`) con la nave y el lugar, ya que el Game.log no lo escribe.
- **Estadísticas de piloto:** horas, bajas, muertes, saltos y contratos de **todas** tus sesiones, semana a semana (ADN y Memoria › Bitácora y estadísticas). «Recalcular» lee los Game.log antiguos del juego (`logbackups`). Pregúntale «¿cuántas bajas llevo este mes?».
- **🧹 Limpiar transmisiones:** botón en la Cabina que vacía el chat (la memoria y la bitácora no se tocan).

## 7 nonies. Hologramas (versión 1.2 en adelante)

Nova enseña **fichas en holograma encima del juego** (como el logo: con Star Citizen en «Ventana sin bordes», sin robar el foco ni los clics). Aparecen con una animación de proyector, tienen líneas de barrido mientras están en pantalla y se pliegan al irse. Al encenderse y al apagarse suenan, y los objetivos de captura llevan una alerta: para cada momento eliges uno de los sonidos de la lista, un audio tuyo (WAV, MP3, OGG o FLAC) o ninguno, con su propio volumen. Se ajustan en **Ajustes › Pantalla › Overlay › Hologramas**: opacidad, tiempo en pantalla, tamaño, posición, **modelo de tarjeta** (clásico, biselado, cristal o táctico), **cómo aparece** (proyector, barrido, despliegue o transmisión), **grosor de la letra** (normal, gruesa o muy gruesa), sonido y en qué casos aparecen; los botones «Probar» enseñan un ejemplo.

- **Ficha policial UEE de un jugador** («búscame a un jugador»), en **tono azul**: foto de perfil, apodo, handle, expediente, fecha de alta, idiomas y la organización con su logotipo. Los datos ocultos salen tachados como `REDACTED`. Cada búsqueda queda anotada en **ADN y Memoria › Bitácora y estadísticas**, en el archivo `Busquedas_de_jugadores.log`, con fecha, hora, jugador y organización.
- **Objetivos de recompensa:** al aceptar una misión de cazarrecompensas o JcJ (o cuando aparece «Objetivo nuevo: Neutralizar XX»), Nova te pregunta «¿Busco su ficha en RSI?» y solo la busca si dices **«sí»** (así no se consulta la web de RSI sin que tú lo pidas). Si tiene ficha es un **jugador**: suena una **alerta** y su ficha sale en **rojo** con el sello **OBJETIVO DE CAZA**. Si no la tiene (o su nombre lleva espacios), te dice que es un **piloto NPC**. También queda en la bitácora de búsquedas.
- **Planetas y lunas:** «Nova, háblame de Daymar» → ficha de verseguide.com con el cuerpo girando, tipo, radio, gravedad, duración del día, atmósfera, nivel de peligro, economía y población, cuántos lugares tiene y su descripción (traducida al español con Google Translate, gratis y una sola vez). «Háblame de Daymar» se contesta sin gastar la IA: la ficha de VerseGuide y un resumen hablado.
- **Lugares planetarios** (cuevas, puestos avanzados, bases, búnkeres…): «Nova, ¿qué es Security Post Kareah?» → tipo, dónde está, temperatura y descripción.
- **Al llegar:** cuando el Game.log indica que te acercas a un planeta o una luna, o que llegas a uno de sus lugares, la ficha aparece sola (como mucho una vez cada media hora para el mismo sitio).

Las páginas de VerseGuide se guardan 3 días en tu equipo (`datos\cache\verseguide`) para no pedirlas una y otra vez.

## 7 decies. Actualizaciones automáticas

Desde la 1.2, **al iniciar y al cerrar** NOVA mira en GitHub ([github.com/0zzyt0/NOVA-AI](https://github.com/0zzyt0/NOVA-AI/releases)) si hay una versión nueva. Si la hay, te avisa en pantalla y de viva voz: **«Se ha detectado una nueva versión vX.X de NOVA AI. ¿Quieres actualizar ahora?»**

- **Sí:** descarga el instalador oficial de esa versión, comprueba que está completo y es el publicado (tamaño y huella SHA-256), y lo abre en modo actualización. Windows pide permiso, la instalación empieza sola y NOVA vuelve a abrirse actualizada.
- **No:** sigues con tu versión (en esa sesión no vuelve a preguntar).
- **Al cerrar la aplicación:** lo descarga ya y lo instala cuando cierres NOVA, sin volver a abrirla.

También puedes contestar por voz («sí», «no», «al cerrar»). Si no contestas y cierras, te lo pregunta en una ventana al salir. Tus datos, ajustes y comandos se conservan. Se desactiva y se busca a mano en **Ajustes › Actualizaciones de NOVA AI**.

## 7 vicies. Novedades de la versión 2.1.7: menús reorganizados

- **Menú más corto:** la pestaña **Nova** desaparece. **Voz** y **Escucha** están en **Ajustes › Voz y audio**; **Identidad**, **Modo reposo** e **Inteligencia** en **Ajustes › ADN e Inteligencia**; **Pantalla**, **Fuentes** y **Discord** también pasan a **Ajustes** (el icono de Ajustes es ahora un engranaje).
- **Información** se llama ahora **ADN y Memoria**: Diccionario, Lo que sabe de ti y Bitácora y estadísticas.
- **Ajustes › Pantalla** tiene cuatro pestañas: **Overlay** (con los hologramas), **Tipo de agente y estados** (el logo y los colores de cada estado), **Vista previa** y **Aspecto**.
- **Logos animados:** siete diseños nuevos (NOVA, Núcleo, Radar, Onda de voz, Órbitas, Escudo hexagonal y Retícula) en un desplegable. Los fijos de siempre quedan para el modo «Sin efectos». Son WebP animados con transparencia real, así que el borde se ve suave encima del juego (un GIF se vería dentado).
- **◆ Probar en pantalla:** eliges cuántos segundos dura (de 1 a 30; 5 de serie) y recorre todos los estados en ese tiempo.
- **Última sesión de Cabina:** al cerrar NOVA AI se guarda una copia de las transmisiones (aunque las limpiaras con 🧹) en `datos\diario\ultima_sesion_cabina.txt`. La ves en **ADN y Memoria › Bitácora y estadísticas**, y Nova la puede consultar: «Nova, ¿de qué hablamos la última vez?». Abrir y cerrar NOVA sin hablarle no borra la anterior.

## 7 octodecies. Novedades de la versión 2.0

- **Ventana reorganizada** para encontrarlo todo antes: **Juego SC** (comandos de voz, teclas y joystick, avisos del juego con perfiles de nave, chat e idioma del juego), **Nova** (identidad, voz, escucha e inteligencia), **Pantalla** (overlay, hologramas y aspecto), **Información** (fuentes y servidores, diccionario, lo que sabe de ti, bitácora y Discord) y **Ajustes** (el único sitio donde se cambia el idioma, ventana y bandeja, actualizaciones, copias y empezar de cero).
- **Buscador de ajustes** en la cabecera (o `Ctrl+F`): escribe «grosor», «micrófono» o «tema» y te lleva a la opción.
- **Estilos de voz**, **nombres del juego en inglés** y **efectos de voz** nuevos: IA de cabina más marcada, comunicador del casco, radio y walkie-talkie, con intensidad ajustable (sección 4).
- **Temas de color** de la ventana (Ajustes › Pantalla › Aspecto): cian, ámbar, verde, carmesí, violeta, oro y plata. Los colores de estado no cambian.
- **Logos del overlay:** NOVA, Núcleo, Onda de voz, Hexágono, Radar, Retícula o el tuyo (PNG con fondo transparente).
- **Hologramas:** 4 modelos de tarjeta, 4 formas de aparecer y **letra más gruesa** (de serie), que se lee mejor sobre el juego.
- **Copias de seguridad** (Ajustes › Copias y archivos): exporta e importa en un archivo `.novacopia` tus ajustes, comandos, memoria, diccionario y bitácora. **Nunca lleva tus claves de IA** ni tu webhook de Discord.
- **Primer inicio:** el asistente te enseña dónde ha encontrado el **Game.log** y te deja elegirlo si juegas desde otra carpeta.
- **Instalador:** eliges la **carpeta y la unidad** de instalación, con el espacio libre de esa unidad. Además es más ligero (el manual usa imágenes WebP) y tiene un modo desatendido para las pruebas automáticas.
- **Avisos:** la zona de armisticio se anuncia **una sola vez** al entrar y otra al salir; **◆ Probar en pantalla** dura 15 segundos; la vista previa del overlay lleva de fondo una escena del juego.
- **Mistral** es de pago desde agosto de 2026: sale de la cadena de fábrica y queda como opción tuya.
- **Arreglos:** el recuadro amarillo de comando sincronizado y la etiqueta «TUYO» ya no se salen del título; en inglés y alemán Nova entiende «pin the target» y «markiere das Ziel»; los nombres de sitios de la bitácora (puntos y estaciones de salto) salen en tu idioma.

## 7 septendecies. Novedades de la versión 1.5

- **Compras en tiendas.** Nova lee del Game.log lo que compras (con su nombre en tu idioma, sacado del global.ini) y lo apunta en la bitácora y en el resumen de la sesión («Compras: N · X aUEC»). Las **Estadísticas de piloto** suman los aUEC gastados en tiendas. Si una compra falla, te avisa (categoría «Avisos»).
- **Lo que te equipas.** Cuando te pones armadura, armas o MedPens, la bitácora lo agrupa en una sola línea por tanda, sin avisos en voz.
- **Atraques.** Cuando el tubo de atraque de **tu** nave está listo, Nova te lo dice (categoría «Nave»).
- **Saltos en grupo.** El salto cuántico siguiendo al marcador de un compañero de grupo se apunta como salto y conserva el destino.
- **Game.log más fino:** un fallo de salto solo se anuncia si es tuyo, y se entienden las invitaciones y las entradas a tu grupo.
- **Manual en cinco idiomas.** El PDF y el manual dentro de NOVA AI (botón «Consulta el Manual») vienen en español, inglés, catalán, francés y alemán, con las capturas de la ventana en cada idioma. Ya no hace falta traducirlo con Google al abrirlo.
- **Arreglos:**
  - El **desinstalador de la 1.4** no se abría en ningún idioma (unas comillas alemanas rompían el script). Si tienes la 1.4 y no puedes desinstalarla, instala la 1.5 encima: trae el desinstalador corregido.
  - El instalador muestra su subtítulo en el idioma elegido.
  - En inglés, catalán, francés y alemán: la ficha de jugador del chat, los datos de los hologramas (atmósfera, lugares, temperatura) y varios textos de la ventana que salían en español; y Nova entiende «Vull que et diguis…», «Je veux que tu t'appelles…» o «Ich möchte, dass du … heißt» al ponerle nombre.
  - Los avisos del interruptor NOVA ACTIVA salen en tu idioma.

## 7 sexdecies. Novedades de la versión 1.4.1

- **El cuestionario anónimo ya funciona.** El botón **Cuestionario** aparece en el lateral, debajo de «Consulta el Manual» (detalles en la sección siguiente).

## 7 quindecies. Novedades de la versión 1.4

- **Bandeja de Windows.** Al cerrar la ventana, Nova sigue funcionando junto al reloj de Windows: te escucha, el overlay sigue en el juego y los temporizadores avisan. **Clic** en su icono para abrir la ventana; **clic derecho** para MUTE, modo reposo o **Salir de NOVA AI**. También puedes mandarla a la bandeja con **⤓** (arriba a la derecha) o desde **Ajustes › General › Ventana y bandeja**. Si prefieres que cerrar la ventana cierre NOVA AI, como antes, desactiva «Al cerrar la ventana, seguir en la bandeja».
- **Modo reposo** (**Ajustes › ADN e Inteligencia › Modo reposo**). Elige tras cuántos minutos sin hablarle descansa (o «Nunca», que es lo que viene de serie). En reposo deja de escucharte y el overlay queda tenue; los temporizadores y los avisos del juego siguen. Cómo despertarla:
  - **Con la tecla o el botón** (de serie): el micrófono se apaga del todo. Pulsa tu tecla de hablar, el botón **☀** de la Cabina, «Modo reposo» en la bandeja o escríbele.
  - **También por su nombre**: el micrófono sigue abierto y solo atiende a «Nova…». Con Groq gasta algo de cuota.
  También puedes dormirla con el botón **💤** de la Cabina o diciendo «Nova, modo reposo» (o «a dormir», «descansa»). «Nova, desactívate» sigue siendo la pausa de siempre.
- **Recorrido guiado.** Tras la configuración inicial (o al estrenar la 1.4), Nova te enseña en un minuto dónde está cada opción. Repítelo cuando quieras en **Ajustes › General › Recorrido guiado**.
- **Cuestionario anónimo.** El botón **Cuestionario**, debajo de «Consulta el Manual», abre unas preguntas del 1 al 10 y un cuadro para tus ideas. Se publica como issue público en GitHub sin tu nombre, tu gametag ni datos de tu equipo (detalles en NORMAS_Y_PRIVACIDAD.md). A los 3 días Nova te lo recuerda una vez; si dices «Ahora no» te pregunta si quieres otro aviso en 3 días, y si dices que no, no insiste.

## 7 quaterdecies. Novedades de la versión 1.4: micrófono, juego limpio y motores de IA

- **Micrófono más robusto.** Nova prueba tu micrófono por varias vías de Windows (MME, DirectSound, WASAPI) y a su frecuencia nativa (por ejemplo 48 kHz). Si no puede abrirlo usa el micrófono predeterminado de Windows y te lo dice. En **Ajustes › Voz y audio** verás qué dispositivo está abierto y su estado: si llega silencio absoluto (micrófono silenciado en los auriculares o en Windows) o si la señal es muy baja.
- **Ganancia del micrófono** (×1 a ×8) en **Ajustes › Voz y audio**. Al terminar la configuración inicial, si tu voz llega muy baja, Nova la sube sola.
- **Botón MUTE** en la esquina del medidor del micrófono (lateral izquierdo). **MUTE ON** (verde): Nova no escucha nada, ni la tecla ni su nombre. Vuelve a pulsarlo para **MUTE OFF**.
- **Modo prudente con las teclas** (**Juego SC › Lectura del juego y teclas**, activado por defecto): un comando de voz hace como mucho lo que harías tú con una pulsación: sin esperas largas encadenadas, sin ratón dentro de secuencias, «mantener» como máximo 3 segundos y nunca en bucle. Así se respeta el espíritu de los Términos de RSI sobre macros.
- **Búsquedas en RSI y envíos a Discord solo si dices «sí».** Los objetivos de recompensa ya no se buscan solos y las fichas no se mandan solas a Discord. Además Nova guarda cada ficha 10 minutos y espera al menos 2 segundos entre consultas a la web de RSI.
- **Mistral sustituye a DeepSeek** como motor de IA gratuito (plan Experiment, sin tarjeta). DeepSeek sigue funcionando si ya tenías su clave.
- **Edge ya no ofrece guardar tus claves** como contraseñas.
- Traducciones corregidas: estado del Overlay, hologramas de ejemplo y la etiqueta «TÚ» del chat.

## 7 terdecies. Novedades de la versión 1.3.1

- **Cabina sin barras de desplazamiento:** la columna derecha se ajusta a tu pantalla. El holograma se encoge y, si aun así no cabe, **Situación** y luego **Temporizadores** se pliegan solos y muestran un resumen en la cabecera (la ubicación, «2 activos»…). Pulsa la cabecera de un panel para abrirlo o plegarlo; Nova lo recuerda.
- **Accesos rápidos en el lateral izquierdo**, encima de la señal del micrófono: escuchar «Nova…» sin tecla, el overlay en el juego y los comentarios del juego.
- **«Acerca de» renovado:** música nueva y una animación más rápida y alocada que va al ritmo de la canción (el túnel acelera y cambia de dibujo, la flecha hace toneles y el logo salta letra a letra). Con **Sin efectos** la ventana no tiembla. Ahora también se traduce a tu idioma.

## 7 duodecies. Novedades de la versión 1.3

- **Cinco idiomas: español, inglés, catalán, francés y alemán.** Se elige en la primera pantalla del instalador (preseleccionado con el de Windows) o en **Ajustes › General** / **Ajustes › ADN e Inteligencia › Identidad**. Cambia todo: la ventana, la voz de Nova, lo que entiende, sus comandos de voz, los hologramas y el manual. Nova te trata de forma formal en cada idioma (sir, senyor, monsieur, Herr…).
- **«Add your Language global.ini of Star Citizen [HERE]»** (en **Juego SC › Idioma del juego**): eliges un global.ini de la comunidad en tu idioma y Nova lo instala en la carpeta del juego, guarda una copia del que hubiera, ajusta user.cfg y lo usa para entender los avisos. Se puede deshacer con un botón. En idiomas distintos del español no se ofrece la traducción de 0zzyt0 ni su Google Drive.
- **Ventana nueva «Cristal holográfico»**, ordenada por tareas: Cabina · Nave y comandos · Nova (voz, IA, idioma) · Overlay y hologramas · Datos y memoria · Ajustes.
- **Efectos en tres niveles** (Overlay y hologramas): Cinematográficos (destellos, aberración cromática, motas de luz, anillo giratorio en el logo), Ligeros (fundidos suaves, para PCs justos o directos) y Sin efectos (estático).
- **«¿Dónde compro un P4-AR?»** se contesta por voz con los datos de UEX; Nova ya no abre el navegador por su cuenta (solo si se lo pides o le dices que sí).
- **Comprobar las páginas** (Ajustes › Fuentes › Páginas de consulta): comprueba desde tu PC, sin abrir el navegador, que cada página de consulta responde.

## 7 undecies. Novedades de la versión 1.2.2

- **Interruptor «NOVA ACTIVA» en la Cabina:** apágalo para detenerla al momento: cancela las búsquedas en curso (jugadores, IA, recompensas), se calla, quita el holograma y deja de atender órdenes hasta que lo enciendas o digas «Nova, actívate». Por voz: «Nova, detente». La bitácora y los temporizadores siguen.
- **Mensajes al chat del juego:** «Nova, envía mensaje al chat» y luego el mensaje (o todo seguido: «envía mensaje al chat: ¿alguien necesita escolta?»). Lo traduce al inglés con Google Translate (sin gastar IA) y hace lo mismo que tú: F12 + Intro, escribe tecla a tecla con tu distribución de teclado, Intro + F12. En **Juego SC › Chat del juego** eliges esas teclas, la velocidad, el idioma y si te lee la traducción antes de enviarla.
- **Discord:** después de cada ficha Nova pregunta «¿La mando a Discord?»; di o escribe **«sí»** en 30 segundos y se manda (con foto y logotipo), también los objetivos de recompensa en rojo. La Cabina y el panel de Discord dicen si llegó o qué respondió Discord; «Enviar ficha de prueba» comprueba todo el camino.
- **Sonidos de los hologramas a tu gusto:** cinco sonidos para cada momento, un audio tuyo o ninguno, y volumen para cada uno.
- **Diccionario de consultas** (`Diccionario_de_consultas.txt`, en tu carpeta de datos): la memoria física de Nova, por grupos (planetas y lunas, estaciones, ciudades, lugares, naves, armaduras, armas, componentes, recursos, mercancías, ropa, pinturas, fabricantes…) y en orden alfabético, con las variantes de cada familia juntas (Attrition-1 … Attrition-6). Al crearse se rellena con los textos oficiales del juego en español (unas 7.000 entradas). Cuando preguntas «háblame de X» o «¿qué es X?», el overlay se pone **morado** («buscando en memoria física») y, si está, contesta sin gastar IA; si no, lo busca en internet (amarillo: starcitizen.tools traducido con Google Translate) y lo guarda (**blanco**, «memorizando»). No caduca nunca: se conserva entre versiones, al empezar de cero y al desinstalar. Puedes editarlo con el Bloc de notas y Nova respeta tus cambios; «Nova, actualiza la ficha de X» la vuelve a buscar. Está en **ADN y Memoria › Diccionario**.
- **Nuevas páginas de consulta:** StarMap (starmap.space, con su API pública: gravedad, temperatura, coordenadas, servicios y minerales de planetas, estaciones y lugares) y, para abrirlas en tu navegador cuando son la mejor fuente, SC Ships Performances Viewer (spviewer.eu), Universal Item Finder (finder.cstone.space, dónde comprar cada objeto) y SC Haulers (schaulers.com). Créditos y agradecimientos a todas en **Acerca de** y en el manual.
- **«¿Quién eres?» / «Preséntate» / «¿Para qué sirves?»:** Nova se presenta con su versión, su creador (0zzyt0, con ceros) y alguna anécdota inventada, y cuenta todo lo que sabe hacer y lo que está por venir.
- **📖 Consulta el Manual:** botón debajo de Cabina (o «Nova, abre el manual») que abre el manual completo en tu navegador, con guía rápida y glosario.
- **Ahorro de tokens** (**Ajustes › ADN e Inteligencia › Ahorro de tokens**): respuestas guardadas para datos que no cambian (naves, armas, armaduras y ropa, minerales, planos, planetas…; caducan a los 14 días o con un parche nuevo), planetas y lugares contestados con VerseGuide sin IA, traducciones con Google Translate guardadas en tu equipo y una conversación más corta para la IA.

## 7 quater. Fuentes de datos y enciclopedia

**Al arrancar, antes de activar nada,** Nova comprueba si hay datos nuevos en sus páginas de consulta. Lo verás en una pantalla con el progreso; con «Continuar sin esperar» sigue en segundo plano. Sin internet usa la última copia guardada.

| Página | Qué aporta | Cuándo se descarga |
|---|---|---|
| **scmdb.net** | Misiones con pago, reputación y **planos (BP)** que dan; recetas de fabricación; minería por ubicación; refinerías; equipo de minería; armas, armaduras y componentes fabricables | Solo cuando sale un parche (versión LIVE nueva) |
| **UEX Corp** ([uexcorp.space](https://uexcorp.space/?set_lang=es_ES)) | Precios medios de mercancías, naves (SCU, tripulación, plataforma), métodos de refinado. Los precios y rutas en directo se siguen consultando al momento | Cada 24 h o cuando cambia la versión |
| **Star Citizen Wiki** | Lore y detalles (se consulta en directo) | Solo se comprueba que responde |
| **VerseGuide** ([verseguide.com](https://verseguide.com)) | Fichas de planetas, lunas y lugares planetarios (cuevas, puestos, bases) para los hologramas | Al pedirla o al llegar; se guarda 3 días |
| **Tu global.ini** | Textos oficiales: naves, objetos (fabricante, tipo, tamaño), planetas y lunas con sus minerales, recursos y criaturas, estaciones, delitos, lore y consejos | Se recarga si un parche lo cambia |

Con todo eso Nova monta una **enciclopedia local** de unas 12.000 entradas, que consulta primero: es instantánea y es de tu versión del juego. Ejemplos:
- «¿Dónde mino quantainium?» → lugares con su porcentaje, firma de escáner, mejores refinerías y precio de venta.
- «¿Qué misiones dan planos en Pyro?» → título, contratista, pago, reputación necesaria y planos.
- «¿Qué necesito para fabricar la Antium Core?» → materiales, cantidades, calidad, tiempo y qué misiones dan el plano.
- «¿Qué minerales hay en Hurston?», «Háblame de la Anvil Paladin», «¿Qué es el homicidio en la ley de la UEE?»

En **Fuentes de datos** tienes las páginas con su versión y la última comprobación, un buscador para probar la enciclopedia y los ajustes: comprobar al arrancar, LIVE o PTU, y la ruta del global.ini.

Los datos de scmdb.net tienen licencia CC BY-NC-ND 4.0: Nova los descarga en tu PC para tu uso personal, como haría tu navegador, y no los redistribuye. El zip de Nova no los incluye.

## 7 quinquies. Star Citizen en español (traducción de 0zzyt0)

Nova entiende mejor el juego si está en tu idioma, y puede ponértelo en español:

- **En la configuración inicial** busca tu carpeta `LIVE` y su `global.ini`. Si no hay traducción al español, te ofrece descargar la más actual de **0zzyt0** desde su Google Drive y la instala en `LIVE` (descomprime el `.zip` y ajusta `user.cfg` con `g_language = spanish_(spain)`; las voces del juego se quedan en inglés). Antes de tocar tu `user.cfg` guarda una copia: `user.cfg.nova_copia`.
- **Cada 3 meses** te pregunta **«¿Comprobar y reinstalar?»**:
  - **Sí:** vuelve a descargar el `.zip` y sobrescribe los archivos de `LIVE`;
  - **No:** no hace nada hasta dentro de otros 3 meses;
  - **Recuérdamelo en la siguiente sesión:** te lo vuelve a preguntar la próxima vez que abras Nova.
- **Cuando quieras:** **Juego SC › Idioma del juego › ⬇ Actualizar traducción** descarga la última versión y sobrescribe las carpetas de `LIVE`. Desde ahí también puedes elegir la carpeta del juego si Nova no la encuentra.
- **El enlace de descarga aparece oculto con asteriscos**, pero puedes cambiarlo: pega otro enlace de Google Drive encima. Si dejas el campo vacío, se usa el de 0zzyt0.

Si Star Citizen está abierto, reinícialo para ver los textos nuevos. Nova recarga sola los textos para entender el Game.log en español.

## 7 sexies. Empezar de cero

En **Ajustes › Empezar de cero**, el botón **⚠ Borrar todos mis datos y empezar de cero** borra todo lo que Nova ha aprendido de ti: tu nombre y el suyo, lo que recuerda, la conversación, las bitácoras, el entrenamiento de voz y tus ajustes. Después vuelve a abrir la configuración inicial («¿Cómo te llamas?», «¿Cómo quieres que me llame?»…).

Por defecto **conserva tus claves de IA y tus comandos personalizados** (desmarca las casillas si quieres borrarlos también). Nunca se borran la traducción del juego ni las rutas de tus archivos de Star Citizen.

## 7 bis. Overlay en el juego

El logo de Nova aparece en una esquina de la pantalla mientras juegas y cambia de color según lo que hace:

| Color | Significa |
|---|---|
| **Azul** (tu color) | escuchando o pensando; **parpadea** mientras la IA te habla |
| **Verde** | ha entendido tu orden; si después te responde, parpadea en verde |
| **Amarillo** | está buscando la información en internet (wiki, web, precios) |
| **Rojo** | en pausa, sin micrófono, o no te ha entendido |

**Solo parpadea cuando la IA está hablando**; el resto de estados son luz fija. Los colores se cambian en **Ajustes › Pantalla › Overlay**, donde también eliges el **logo** (NOVA, Núcleo, Onda de voz, Hexágono, Radar, Retícula o un PNG tuyo).

**Monitor:** el overlay se queda fijo en el monitor que elijas, el **Monitor 1 (principal)** por defecto. No sigue al ratón ni a la ventana activa. También puedes elegir «El monitor donde esté el juego».

**EasyAntiCheat:** al arrancar el juego aparece primero la ventanita de EasyAntiCheat, que se llama igual. Nova la descarta: solo usa la ventana real de `StarCitizen.exe`, y la vuelve a buscar cada pocos segundos hasta que aparece.

**Resolución:** en «Automática», Nova detecta la ventana de Star Citizen, o el monitor elegido, y escala el logo para que ocupe lo mismo en cualquier pantalla (tamaño medido a 1080p). Si la detección no acierta, elige la tuya en la lista, de **640×480 a 3840×2160 (4K)**. La vista previa adopta esa proporción.

**Pausa:** el botón ⏸ de la Cabina, o decir «Nova, desactívate», pone a Nova en pausa: no obedece nada y el overlay se queda en rojo. «Nova, actívate» (o el botón ▶) la reactiva. Al cerrar Nova, el overlay se pone rojo un momento antes de desaparecer.

En **Ajustes › Pantalla › Overlay** también eliges la esquina (pulsando en la pantalla de muestra, que lleva de fondo una escena del juego), el tamaño y la intensidad. En **Ajustes › Pantalla › Vista previa**, los botones de demostración enseñan cada color, y **◆ Probar en pantalla** recorre todos los estados sobre tu escritorio en el tiempo que elijas al lado del botón (de 1 a 30 segundos; 5 de serie). El logo se elige en **Ajustes › Pantalla › Tipo de agente y estados**: uno **animado** para los efectos Cinematográficos y Ligeros, y uno **fijo** (o tu PNG) para «Sin efectos».

- **Modo de pantalla:** se ve con Star Citizen en **«Ventana sin bordes» (Borderless)**. En «Pantalla completa» exclusiva, Windows no deja dibujar nada encima.
- **No molesta:** no recibe clics ni roba el foco; el ratón lo atraviesa.
- **Por defecto solo sale con el juego delante:** puedes cambiarlo en esa misma sección.

## 8. La regla de oro del humor

Si Nova no encuentra algo, o le preguntas por lore que no existe, se lo inventará con todo el aplomo y terminará con una **frase de confesión**. Por defecto es esta:

> «... la verdad señor, no tengo ni idea de lo que me está pidiendo, toda la información que le acabo de dar me la he inventado.»

En **Ajustes › ADN e Inteligencia › Personalidad** puedes escribir **tus propias frases**, una por línea; Nova elige una al azar cada vez, y `{t}` se cambia por cómo te llama. El botón «Restaurar la original» vuelve a la de fábrica. Si desactivas **«Inventar cuando no sabe algo»**, Nova te dirá con humor que no lo sabe, sin inventar nada.

Además, Nova tiene un control propio: si buscó en la wiki o en internet, no encontró nada y aun así dio una respuesta larga, añade la frase automáticamente.

## 9. Problemas frecuentes

- **«Failed to build pygame» o «subprocess-exited-with-error»:** tu Python es demasiado nuevo (3.14, 3.15…) y esas librerías todavía no tienen versión precompilada para él. Vuelve a abrir `NOVA AI Setup.exe`. El instalador ya no usa ese Python: instala Python 3.12 aparte, solo para Nova, sin tocar el tuyo. Tampoco instales nada con `pip` a mano: usa siempre el instalador.
- **El juego no recibe las teclas:** si ejecutas Star Citizen como administrador, ejecuta Nova también como administrador.
- **No me oye:** si el núcleo de la Cabina dice **MODO REPOSO**, pulsa tu tecla de hablar o el botón ☀ para despertarla. Si no, elige tu micrófono en **Ajustes › Voz y audio** y mira el medidor. Allí también ves qué micrófono se abrió y, si algo falla, el motivo. Comprueba que el botón **MUTE** del medidor del lateral izquierdo está en **MUTE OFF** y que tus auriculares no están silenciados. Si hablas bajo, sube la ganancia o la sensibilidad.
- **No encuentro la ventana:** con la ventana cerrada Nova sigue en la bandeja de Windows (junto al reloj; quizá dentro de la flecha ^). Haz clic en su icono. Para cerrarla del todo: clic derecho › Salir de NOVA AI.
- **Se activa sola:** baja la sensibilidad o desactiva «Escuchar por su nombre sin tecla». Si es por una forma aprendida del nombre, quítala en **Ajustes › Voz y audio › Cómo hablarle** con «Olvidar».
- **«Todos mis motores están sin cuota»:** añade una clave de Groq u OpenRouter como respaldo, o espera al día siguiente.
- **Nova se oye a sí misma por los altavoces:** el micrófono se queda sordo mientras Nova habla, e ignora lo que se parece a lo que acaba de decir. Aun así, con auriculares va mejor.
- **No reacciona cuando la llamas por su nombre:** repite el entrenamiento en **Ajustes › ADN e Inteligencia › Identidad**. Elige un nombre de 2 o 3 sílabas y que no sea una palabra común.
- **Se cierra sola de golpe:** mira `fallos.log` y `nova.log` en tu carpeta de datos (**Memoria → Archivos → Carpeta de datos**) y mándamelos.
- **La ventana no se abre:** Nova la abre con Edge. Si no tienes Edge ni Chrome, abre el navegador normal; si ni eso, entra a mano en la dirección de `ui_puerto.txt` de tu carpeta de datos (`http://127.0.0.1:PUERTO/`).
- **El overlay está en otro monitor:** en **Ajustes › Pantalla › Overlay › Monitor** elige el tuyo; el Monitor 1 es siempre el principal de Windows.
- **El overlay no se ve:** pon Star Citizen en «Ventana sin bordes». Prueba con «◆ Probar en pantalla» y desactiva «Solo con Star Citizen delante» para comprobarlo.
- **El mensaje no se escribe en el chat del juego:** en **Juego SC › Chat del juego** deja las teclas `f12` / `enter` / `f12` y «Teclas, letra a letra» (el chat de Star Citizen no admite pegar). Si se come letras, sube la velocidad al escribir o la espera.
- **La ficha no llega a Discord:** mira el mensaje de la Cabina o «Último envío» en **Ajustes › Discord**: dice qué respondió Discord. Si el webhook se borró, crea uno nuevo.
- **Nova no responde a nada:** puede estar detenida (overlay en rojo): enciende el interruptor de la Cabina o di «Nova, actívate».
- **Una tecla del juego no funciona:** pulsa «⟳ Sincronizar ahora» y revisa «Ver detalles». Si la acción solo está en tu HOTAS, dale también una tecla de teclado en el juego.

## 9 bis. Acerca de

Debajo de **Memoria**, en pequeño, está **ⓘ Acerca de**: una ventana al estilo de los keygens de los 90 y 2000, con su túnel de colores de 8 bits, una flecha volando dentro, el texto que se desplaza abajo y la música de NOVA AI en bucle. Ahí están los créditos, la licencia y los derechos de terceros. Se cierra con **Esc** o con el botón **Cerrar**; el botón **♪ Música** la silencia.

**NOVA AI · Versión oficial 1.3.1**, de **Aaron B. Roldan** (gametag de Star Citizen: **0zzyt0**), desarrollada con el motor de IA Claude Opus 5.5 (Anthropic). Agradecimientos a la Org. Defcorp y a Faibo, Galleg0, Sr.Scott, AlpacaInTrouble, Lother y muchos más.

**Licencia:** libre uso y modificación. Si usas este proyecto o lo modificas, por favor menciona de dónde has sacado las ideas y cuál es tu base. Texto completo, con los derechos de terceros, en `LICENCIA.txt`.

## 10. Privacidad y normas

Antes de instalar, el instalador te pide aceptar las **Normas de uso y la Política de privacidad** (`NORMAS_Y_PRIVACIDAD.md`, incluido en el programa). Lo esencial:

- **Lo que sale de tu PC:** el texto de lo que dices va al proveedor de IA que elijas. El audio solo sale si usas Groq para reconocer voz. Google indica que en el plan gratuito de Gemini puede usar lo que envías para mejorar sus productos.
- **Lo que se queda en tu PC:** las claves, la memoria, tus comandos, los ajustes y la sesión, en `%LOCALAPPDATA%\NOVA AI\datos`. Actualizar o desinstalar Nova no los borra, salvo que lo marques. El entrenamiento de voz no guarda grabaciones: solo apunta cómo se escribe tu forma de decir el nombre y el volumen medido.
- **Anticheat:** Nova solo simula pulsaciones de teclado y ratón, como VoiceAttack o Wingman AI. Úsala con sentido común: una orden, una acción.
- **Fuentes de datos:** la información viene de la comunidad: Star Citizen Wiki (starcitizen.tools), UEX Corp, scmdb.net y DuckDuckGo.
- **Traducción del juego:** es obra de la comunidad (0zzyt0). Nova solo la descarga de su Google Drive público cuando tú lo aceptas, y solo escribe dentro de tu carpeta `LIVE`.
- **Proyecto de fans:** no está afiliado a Cloud Imperium Games. Star Citizen® es marca registrada de Cloud Imperium Rights LLC.
- **scmdb.net y UEX Corp:** tienen sus propios derechos y condiciones de uso. NOVA AI solo consulta y lee lo que publican: no modifica, manipula ni redistribuye sus datos.
