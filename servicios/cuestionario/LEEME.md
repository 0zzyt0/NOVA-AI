# Servicio del cuestionario anónimo (Cloudflare Worker)

NOVA AI 1.4 trae un **cuestionario anónimo**. Las respuestas llegan como *issues* de este repositorio, con la etiqueta `cuestionario`. El programa no puede llevar dentro un token de GitHub, porque cualquiera podría sacarlo. Por eso envía el cuestionario a este pequeño servicio, que guarda el token como secreto y crea el issue.

- Es gratis: el plan gratuito de Cloudflare Workers sobra para esto.
- No guarda nada. La IP solo se usa en memoria, resumida, para frenar envíos en masa (3 por hora como máximo).
- Comprueba cada envío:
  - las notas tienen que ir del 1 al 10;
  - el texto no puede pasar de 2.000 caracteres;
  - el texto se publica citado, sin menciones `@` ni referencias `#`.

## 1. Token de GitHub (solo para los issues de NOVA-AI)

1. En GitHub ve a **Settings › Developer settings › Personal access tokens › Fine-grained tokens** y pulsa **Generate new token**.
2. Rellena el token:
   - **Nombre:** `NOVA AI cuestionario`.
   - **Caducidad:** la más larga que te deje. Apunta la fecha para renovarlo.
   - **Repository access:** *Only select repositories* › `0zzyt0/NOVA-AI`.
   - **Permissions › Repository permissions › Issues:** *Read and write*. Nada más.
3. Pulsa **Generate token** y cópialo. No se vuelve a mostrar.

## 2. Crear el Worker

1. Crea una cuenta gratuita en [dash.cloudflare.com](https://dash.cloudflare.com) y entra.
2. Ve a **Workers & Pages › Create**. Elige **Create Worker** (o la plantilla *Hello World*), llámalo `nova-cuestionario` y pulsa **Deploy**.
3. En la página del Worker pulsa **Edit code**. Borra lo que haya, pega todo [`worker.js`](worker.js) y pulsa **Deploy**.
4. Ve a **Settings › Variables and Secrets › Add**:
   - **Type:** *Secret*.
   - **Variable name:** `GITHUB_TOKEN`.
   - **Value:** el token del paso 1.

   Guarda con **Deploy**.
5. Copia la dirección del Worker. Es parecida a `https://nova-cuestionario.TU-SUBDOMINIO.workers.dev`.

## 3. Conectarlo con NOVA AI

1. Pon esa dirección en `core/survey.py`, en `URL = "…"`, y compila. Con `URL` vacía el botón «Cuestionario» no aparece.
2. Crea la etiqueta `cuestionario` en el repositorio, en **Issues › Labels › New label**.

## Probarlo

En NOVA AI pulsa **Cuestionario** en el lateral, puntúa una pregunta y envía. Al momento aparece un issue nuevo con la etiqueta `cuestionario`.

Si no llega, mira **Workers & Pages › nova-cuestionario › Logs**. Estos son los errores posibles:

| Error | Qué significa |
|---|---|
| `503` | Falta el secreto `GITHUB_TOKEN`. |
| `502` | GitHub ha rechazado el token: ha caducado o no tiene permiso de *Issues*. |
| `429` | Se han hecho demasiados envíos desde la misma conexión en una hora. |

## Si alguien abusa

1. Borra el token en GitHub. El servicio deja de crear issues al momento.
2. Cierra los issues que sobren.
3. Crea un token nuevo y vuelve a ponerlo en el Worker.
