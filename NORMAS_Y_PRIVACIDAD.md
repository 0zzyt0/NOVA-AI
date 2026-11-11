# NOVA AI · Normas de uso y Política de privacidad

Versión 1.3 · noviembre de 2026

## En pocas palabras

- **Tus datos se quedan en tu PC.** Todo lo que NOVA AI guarda (ajustes, memoria, conversación, bitácoras, comandos y claves) vive en tu ordenador, en la carpeta `%LOCALAPPDATA%\NOVA AI\datos`. NOVA AI no tiene servidores propios, no te pide cuentas ni correo, no recoge estadísticas de uso ni telemetría, y no vende ni comparte tus datos con nadie.
- **No se hacen grabaciones.** El micrófono solo se usa mientras hablas con Nova. Tu voz no se guarda en ningún archivo: el entrenamiento de voz solo apunta cómo se escribe su nombre cuando lo dices tú y el volumen medido.
- **Las consultas a internet son consultas normales**, las mismas que podrías hacer tú en Google, en la wiki del juego o en cualquier asistente de inteligencia artificial. No llevan tus archivos, tu correo, tus contraseñas ni datos de tu cuenta de Star Citizen.
- **Tú mandas:** puedes borrarlo todo cuando quieras desde Ajustes › Empezar de cero, o al desinstalar.

## Qué sale de tu PC y para qué

Para funcionar, Nova usa servicios de internet gratuitos. Esto es exactamente lo que se envía a cada uno:

- **Inteligencia artificial (Google Gemini, Groq, OpenRouter, DeepSeek):** el texto de lo que le pides a Nova y los últimos mensajes de la conversación, junto con el contexto que necesita para responder bien: tu nombre y cómo quieres que te trate, lo que le has pedido que recuerde, tu personaje y un breve resumen de la partida (ubicación, nave, contratos, grupo y últimos avisos del juego). Es lo mismo que escribirlo tú en la web de esa IA. Solo se usa el servicio que esté en tu cadena de motores. Cada uno tiene sus propias condiciones; por ejemplo, Google indica que en el plan gratuito de Gemini puede usar lo enviado para mejorar sus productos.
- **Reconocimiento de voz:** si usas Groq para entender tu voz, el audio de cada frase se envía a Groq para convertirlo en texto, y no se guarda en tu PC. Con el reconocimiento local (Whisper) tu voz no sale nunca de tu ordenador.
- **Voz de Nova:** con las voces de Microsoft Edge, el texto de la respuesta se envía a Microsoft para generar el audio. Con Piper o la voz de Windows no sale nada.
- **Información del juego:** búsquedas en Star Citizen Wiki, UEX Corp, scmdb.net y DuckDuckGo sobre naves, misiones, precios o lugares. Al arrancar, Nova comprueba si esas fuentes tienen datos nuevos.
- **Traducción al español:** solo si lo aceptas (y solo con NOVA AI en español), Nova descarga la traducción de la comunidad (0zzyt0) desde su Google Drive y la instala en tu carpeta del juego.
- **Fichas de jugadores y estado de los servidores:** cuando le pides buscar un jugador, Nova lee su ficha pública en robertsspaceindustries.com (solo el apodo que escribes, o el del objetivo de una recompensa sobre un jugador que aceptes) y la de su organización; al arrancar lee la página pública status.robertsspaceindustries.com. Son las mismas páginas que abrirías tú en el navegador.
- **Fichas de planetas, lunas y lugares:** cuando le pides información de un planeta o llegas cerca de uno, Nova lee su página pública en verseguide.com (por ejemplo verseguide.com/location/STANTON/2B) y la guarda unos días en tu equipo. Las fotos de perfil y los logotipos de las organizaciones se descargan de robertsspaceindustries.com. Si activas la traducción, la descripción (en inglés) se manda a Google Translate para pasarla al español (o a tu motor de IA si Google no responde o si eliges la IA en Nova › Ahorro de tokens). Lo traducido se guarda en tu equipo y no se vuelve a enviar.
- **StarMap:** para los datos de planetas, estaciones y lugares (gravedad, temperatura, servicios…), Nova consulta la API pública de starmap.space, pidiendo solo el planeta que hace falta, y la guarda una semana en tu equipo. Otras páginas de la comunidad (spviewer.eu, finder.cstone.space, schaulers.com) solo se abren en tu navegador cuando tú lo pides.
- **Actualizaciones:** al iniciar y al cerrar, NOVA pregunta a GitHub (api.github.com) cuál es la última versión publicada de NOVA AI. Si actualizas, descarga de GitHub el instalador oficial. Se puede desactivar en Ajustes.
- **Discord (opcional):** solo si pegas el webhook de un canal tuyo, Nova manda a ese canal la ficha pública del jugador que hayas buscado (y la de los objetivos de recompensa que sean jugadores, si lo dejas activado). Sin webhook no se envía nada.
- **Diccionario de consultas:** es un archivo de texto en tu carpeta de datos. Cuando algo no está en él, Nova lo busca en la wiki pública starcitizen.tools (como harías tú) y lo traduce con Google Translate; lo aprendido se queda en tu PC.
- **Idioma de NOVA AI (español, inglés, catalán, francés o alemán):** si eliges un idioma distinto del español, las frases fijas de Nova, los avisos del sistema y el manual se traducen con Google Translate (translate.googleapis.com) y se guardan en tu PC para no volver a enviarlos. Con «Añade el global.ini de tu idioma» Nova copia en tu carpeta del juego el archivo que tú elijas (guardando una copia del que hubiera) y ajusta user.cfg; ese archivo no se envía a ningún sitio.
- **Mensajes al chat del juego:** cuando le pides «envía mensaje al chat», el texto de ese mensaje se manda a Google Translate (translate.googleapis.com) para traducirlo, igual que si lo pegaras tú en translate.google.es. Nova lo escribe en el chat de Star Citizen pulsando teclas en tu PC.

Nada más sale de tu PC. El Game.log del juego se lee en tu ordenador y el archivo nunca se envía: a la IA solo le llega el breve resumen de la partida del punto anterior.

## Normas de uso

- **Proyecto de fans.** NOVA AI no está afiliado a Cloud Imperium Games ni a Roberts Space Industries. Star Citizen y sus marcas son de sus dueños.
- **Juega limpio.** Nova pulsa teclas por ti, como VoiceAttack u otros asistentes de voz. Úsala con sentido común: una orden, una acción. No la uses para automatizar el juego mientras no estás, ni para nada que vaya contra las condiciones de uso de Star Citizen. Tú eres responsable de cumplirlas.
- **Claves gratuitas incluidas (si tu versión las trae).** Algunas versiones del programa traen claves gratuitas de prueba para Gemini, Groq, OpenRouter y DeepSeek. Tienen un límite diario compartido, pueden agotarse o dejar de funcionar en cualquier momento, y no deben copiarse a otros programas. Puedes poner tus propias claves gratuitas en Nova › Inteligencia. Al usarlas aceptas también las condiciones de cada proveedor.
- **La IA se puede equivocar.** Las respuestas las genera una inteligencia artificial y pueden contener errores. Cuando se inventa algo, Nova te lo confiesa al final con humor. No tomes decisiones importantes solo por lo que diga.
- **Contenido de terceros.** La traducción es obra de la comunidad (0zzyt0). Los datos de scmdb.net tienen licencia CC BY-NC-ND 4.0: se descargan en tu PC para tu uso personal y no deben redistribuirse.
- **Sin garantía.** NOVA AI se ofrece gratis y tal cual, sin garantías de ningún tipo. Sus autores no se hacen responsables de pérdidas o daños derivados de su uso, incluidas las sanciones dentro del juego.

## Tus derechos y cómo ejercerlos

- **Ver tus datos:** Ajustes › Archivos › Carpeta de datos abre la carpeta donde está todo.
- **Borrarlos:** Ajustes › Empezar de cero borra lo que Nova ha aprendido de ti. Al desinstalar, marca «Borrar también mis datos» para no dejar nada.
- **Cambios en estas normas:** si cambian, el instalador te pedirá que las aceptes de nuevo antes de instalar la versión nueva.

Al pulsar «Acepto» confirmas que has leído y aceptas estas Normas de uso y esta Política de privacidad.
