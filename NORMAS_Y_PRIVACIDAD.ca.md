# NOVA AI · Normes d'ús i Política de privacitat

Versió 1.3 · novembre de 2026

## En poques paraules

- **Les teves dades es queden al teu PC.** Tot el que NOVA AI desa (ajustos, memòria, conversa, bitàcoles, ordres i claus) viu al teu ordinador, a la carpeta `%LOCALAPPDATA%\NOVA AI\datos`. NOVA AI no té servidors propis, no et demana comptes ni correu, no recull estadístiques d'ús ni telemetria, i no ven ni comparteix les teves dades amb ningú.
- **No es fan enregistraments.** El micròfon només es fa servir mentre parles amb la Nova. La teva veu no es desa en cap fitxer: l'entrenament de veu només anota com s'escriu el seu nom quan el dius tu i el volum mesurat.
- **Les consultes a internet són consultes normals**, les mateixes que podries fer tu a Google, a la wiki del joc o a qualsevol assistent d'intel·ligència artificial. No porten els teus fitxers, el teu correu, les teves contrasenyes ni dades del teu compte de Star Citizen.
- **Tu manes:** pots esborrar-ho tot quan vulguis des d'Ajustos › Començar de zero, o en desinstal·lar.

## Què surt del teu PC i per a què

Per funcionar, la Nova fa servir serveis d'internet gratuïts. Això és exactament el que s'envia a cadascun:

- **Intel·ligència artificial (Google Gemini, Groq, OpenRouter, DeepSeek):** el text del que demanes a la Nova i els últims missatges de la conversa, juntament amb el context que necessita per respondre bé: el teu nom i com vols que et tracti, el que li has demanat que recordi, el teu personatge i un breu resum de la partida (ubicació, nau, contractes, grup i últims avisos del joc). És el mateix que escriure-ho tu al web d'aquesta IA. Només es fa servir el servei que tinguis a la cadena de motors. Cadascun té les seves pròpies condicions; per exemple, Google indica que en el pla gratuït de Gemini pot fer servir el que s'envia per millorar els seus productes.
- **Reconeixement de veu:** si fas servir Groq per entendre la teva veu, l'àudio de cada frase s'envia a Groq per convertir-lo en text, i no es desa al teu PC. Amb el reconeixement local (Whisper) la teva veu no surt mai del teu ordinador.
- **Veu de la Nova:** amb les veus de Microsoft Edge, el text de la resposta s'envia a Microsoft per generar l'àudio. Amb Piper o la veu de Windows no surt res.
- **Informació del joc:** cerques a Star Citizen Wiki, UEX Corp, scmdb.net i DuckDuckGo sobre naus, missions, preus o llocs. En arrencar, la Nova comprova si aquestes fonts tenen dades noves.
- **Traducció al castellà:** només si l'acceptes (i només amb NOVA AI en castellà), la Nova descarrega la traducció de la comunitat (0zzyt0) del seu Google Drive i la instal·la a la carpeta del joc.
- **Fitxes de jugadors i estat dels servidors:** quan li demanes cercar un jugador, la Nova llegeix la seva fitxa pública a robertsspaceindustries.com (només l'àlies que escrius, o el de l'objectiu d'una recompensa sobre un jugador que acceptis) i la de la seva organització; en arrencar llegeix la pàgina pública status.robertsspaceindustries.com. Són les mateixes pàgines que obriries tu al navegador.
- **Fitxes de planetes, llunes i llocs:** quan li demanes informació d'un planeta o arribes a prop d'un, la Nova llegeix la seva pàgina pública a verseguide.com (per exemple verseguide.com/location/STANTON/2B) i la desa uns dies al teu equip. Les fotos de perfil i els logotips de les organitzacions es descarreguen de robertsspaceindustries.com. Si actives la traducció, la descripció (en anglès) s'envia a Google Translate per passar-la al teu idioma (o al teu motor d'IA si Google no respon o si tries la IA a Nova › Estalvi de tokens). El que es tradueix es desa al teu equip i no es torna a enviar.
- **StarMap:** per a les dades de planetes, estacions i llocs (gravetat, temperatura, serveis…), la Nova consulta l'API pública de starmap.space, demanant només el planeta que cal, i la desa una setmana al teu equip. Altres pàgines de la comunitat (spviewer.eu, finder.cstone.space, schaulers.com) només s'obren al teu navegador quan tu ho demanes.
- **Actualitzacions:** en iniciar i en tancar, NOVA pregunta a GitHub (api.github.com) quina és l'última versió publicada de NOVA AI. Si actualitzes, descarrega de GitHub l'instal·lador oficial. Es pot desactivar a Ajustos.
- **Discord (opcional):** només si enganxes el webhook d'un canal teu, la Nova envia a aquest canal la fitxa pública del jugador que hagis cercat (i la dels objectius de recompensa que siguin jugadors, si ho deixes activat). Sense webhook no s'envia res.
- **Diccionari de consultes:** és un fitxer de text a la teva carpeta de dades. Quan alguna cosa no hi és, la Nova la cerca a la wiki pública starcitizen.tools (com faries tu) i la tradueix amb Google Translate; el que aprèn es queda al teu PC.
- **Idioma de NOVA AI (castellà, anglès, català, francès o alemany):** si tries un idioma diferent del castellà, les frases fixes de la Nova, els avisos del sistema i el manual es tradueixen amb Google Translate (translate.googleapis.com) i es desen al teu PC per no tornar-los a enviar. Amb «Afegeix el global.ini del teu idioma» la Nova copia a la carpeta del joc el fitxer que triïs (desant una còpia del que hi hagués) i ajusta user.cfg; aquest fitxer no s'envia enlloc.
- **Missatges al xat del joc:** quan li demanes «envia missatge al xat», el text d'aquest missatge s'envia a Google Translate (translate.googleapis.com) per traduir-lo, igual que si l'enganxessis tu a translate.google.com. La Nova l'escriu al xat de Star Citizen prement tecles al teu PC.

Res més surt del teu PC. El Game.log del joc es llegeix al teu ordinador i el fitxer no s'envia mai: a la IA només li arriba el breu resum de la partida del punt anterior.

## Normes d'ús

- **Projecte de fans.** NOVA AI no està afiliat a Cloud Imperium Games ni a Roberts Space Industries. Star Citizen i les seves marques són dels seus propietaris.
- **Juga net.** La Nova prem tecles per tu, com VoiceAttack o altres assistents de veu. Fes-la servir amb sentit comú: una ordre, una acció. No la facis servir per automatitzar el joc mentre no hi ets, ni per a res que vagi contra les condicions d'ús de Star Citizen. Tu ets responsable de complir-les.
- **Claus gratuïtes incloses (si la teva versió en porta).** Algunes versions del programa porten claus gratuïtes de prova per a Gemini, Groq, OpenRouter i DeepSeek. Tenen un límit diari compartit, es poden esgotar o deixar de funcionar en qualsevol moment, i no s'han de copiar a altres programes. Pots posar les teves pròpies claus gratuïtes a Nova › Intel·ligència. En fer-les servir acceptes també les condicions de cada proveïdor.
- **La IA es pot equivocar.** Les respostes les genera una intel·ligència artificial i poden contenir errors. Quan s'inventa alguna cosa, la Nova t'ho confessa al final amb humor. No prenguis decisions importants només pel que digui.
- **Contingut de tercers.** La traducció és obra de la comunitat (0zzyt0). Les dades de scmdb.net tenen llicència CC BY-NC-ND 4.0: es descarreguen al teu PC per al teu ús personal i no s'han de redistribuir.
- **Sense garantia.** NOVA AI s'ofereix gratis i tal qual, sense garanties de cap mena. Els seus autors no es fan responsables de pèrdues o danys derivats del seu ús, incloses les sancions dins del joc.

## Els teus drets i com exercir-los

- **Veure les teves dades:** Ajustos › Fitxers › Carpeta de dades obre la carpeta on hi ha tot.
- **Esborrar-les:** Ajustos › Començar de zero esborra el que la Nova ha après de tu. En desinstal·lar, marca «Esborrar també les meves dades» per no deixar res.
- **Canvis en aquestes normes:** si canvien, l'instal·lador et demanarà que les tornis a acceptar abans d'instal·lar la versió nova.

En prémer «Accepto» confirmes que has llegit i acceptes aquestes Normes d'ús i aquesta Política de privacitat.
