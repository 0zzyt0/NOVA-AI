"""Lo que Nova entiende en cada idioma (v1.3): palabras de control, órdenes fijas y frases del entrenamiento.

Las órdenes fijas (manual, presentación, «¿dónde compro…?», «háblame de…», «actualiza…») se pasan a su
forma en español antes de reconocerlas, así el resto de Nova funciona igual en los cinco idiomas.
Todo va en texto normalizado (minúsculas, sin tildes ni signos: «Où acheter» → «ou acheter»).
"""
from __future__ import annotations

import re

# ----------------------------------------------------------- palabras sueltas (normalizadas)
STOP = {
    "en": {"silence", "quiet", "shut up", "stop", "enough", "hush", "be quiet", "stop talking"},
    "ca": {"silenci", "calla", "calla t", "prou", "para", "atura t"},
    "fr": {"silence", "tais toi", "chut", "stop", "assez", "arrete", "taisez vous"},
    "de": {"ruhe", "still", "sei still", "stopp", "stop", "genug", "schweig", "halt die klappe"},
}
PAUSE = {
    "en": {"deactivate", "pause", "pause mode", "go to sleep", "sleep", "standby", "stand by", "power down"},
    "ca": {"desactiva t", "desactivat", "pausa", "mode pausa", "a dormir", "descansa", "apaga t"},
    "fr": {"desactive toi", "pause", "mode pause", "dors", "va dormir", "mets toi en pause", "eteins toi"},
    "de": {"deaktivieren", "deaktiviere dich", "pause", "pausenmodus", "schlaf", "schlafen", "ruhemodus",
           "schalte dich aus"},
}
HALT = {
    "en": {"halt", "stop everything", "stop it all", "cancel everything", "cancel all", "stop all searches",
           "stop the searches", "cancel the searches", "cancel all searches", "abort", "abort everything"},
    "ca": {"atura t", "aturat", "para ho tot", "atura ho tot", "cancel la ho tot", "atura les cerques",
           "cancel la les cerques", "para les cerques"},
    "fr": {"arrete tout", "annule tout", "stoppe tout", "arrete les recherches", "annule les recherches",
           "stop tout"},
    "de": {"stopp alles", "halt alles", "brich alles ab", "alles abbrechen", "suche abbrechen",
           "stoppe die suche", "breche alles ab", "alles stoppen"},
}
RESUME = {
    "en": {"activate", "wake up", "resume", "come back", "reactivate", "power up", "online", "go online"},
    "ca": {"activa t", "activat", "desperta", "desperta t", "torna", "reactiva t", "en linia", "encen t"},
    "fr": {"active toi", "reveille toi", "reviens", "reactive toi", "en ligne", "allume toi"},
    "de": {"aktiviere dich", "aktivieren", "wach auf", "aufwachen", "komm zuruck", "online", "schalte dich ein"},
}
YES = {
    "en": {"yes", "yeah", "yep", "send it", "send", "ok", "okay", "go ahead", "sure", "confirm", "correct",
           "do it", "yes please", "send it please"},
    "ca": {"si", "envia ho", "envia", "d acord", "endavant", "confirmo", "correcte", "si si us plau", "vinga"},
    "fr": {"oui", "envoie", "envoie le", "d accord", "vas y", "ok", "confirme", "correct", "oui s il te plait",
           "ouais"},
    "de": {"ja", "sende", "schick es", "schick", "okay", "ok", "los", "bestatige", "richtig", "ja bitte", "genau",
           "mach", "mach es"},
}
CANCEL = {
    "en": {"cancel", "never mind", "nevermind", "nothing", "no", "forget it", "leave it"},
    "ca": {"cancel la", "cancella", "no", "res", "deixa ho", "oblida ho", "tant se val"},
    "fr": {"annule", "non", "rien", "laisse tomber", "oublie", "oublie ca"},
    "de": {"abbrechen", "nein", "nichts", "vergiss es", "lass es", "egal"},
}
FILLERS = {
    "en": {"please", "hey", "now", "quick", "quickly"},
    "ca": {"ei", "ara", "rapid", "vinga"},
    "fr": {"stp", "svp", "maintenant", "vite"},
    "de": {"bitte", "mal", "jetzt", "schnell"},
}

# --------------------------------------------- órdenes fijas → su forma en español (normalizada)
_RULES: dict[str, list[tuple[str, str]]] = {
    "en": [
        (r"^(?:forget|clear|delete) the conversation$|^new conversation$", "nueva conversacion"),
        (r"^(?:open|show(?: me)?|i want to see|where is) (?:the |your )?(?:user )?manual(?: of nova(?: ai)?)?$",
         "abre el manual"),
        (r"^(?:who are you|introduce yourself|tell me about yourself|what are you|who (?:made|created|built|"
         r"programmed|developed) you|who is your (?:creator|author|developer|maker)|what version (?:are you|do you "
         r"have)|which version are you)$", "quien eres"),
        (r"^(?:what (?:can you do|are you for|do you do|can you do for me)|what are you good for|how can you "
         r"help(?: me)?|what are your (?:functions|capabilities|skills)|what can i ask you)$", "para que sirves"),
        (r"^where (?:can i |do i |could i |should i |to )?(?:buy|purchase|get hold of) (?:an? |the |some )?(?P<x>.+)$",
         "donde compro {x}"),
        (r"^where (?:is|are) (?:an? |the )?(?P<x>.+?) sold$", "donde compro {x}"),
        (r"^(?:update|refresh|look up again)(?: the)?(?: entry| data| info| information| definition| card)?"
         r"(?: (?:on|for|of|about))? (?:the )?(?P<x>.+)$", "actualiza {x}"),
        (r"^(?:tell me (?:something )?about|what is|whats|what s|what are|who is|who are|info(?:rmation)? (?:on|about)"
         r"|data on|describe|define|explain what is)(?: the| an?)? (?P<x>.+)$", "hablame de {x}"),
    ],
    "ca": [
        (r"^(?:oblida|esborra) la conversa$|^nova conversa$", "nueva conversacion"),
        (r"^(?:obre(?: ?m)?|ensenya(?: ?m)?|mostra(?: ?m)?|vull veure|on es|consulta) (?:el |teu |el teu )?manual"
         r"(?: d usuari| de nova(?: ai)?)?$", "abre el manual"),
        (r"^(?:qui ets(?: tu)?|presenta ?t|presenta te|que ets(?: tu)?|qui t ha (?:creat|fet|programat|desenvolupat)|"
         r"qui es el teu (?:creador|autor|desenvolupador)|parla ?m de tu|quina versio (?:ets|tens))$", "quien eres"),
        (r"^(?:per a que serveixes|per que serveixes|que (?:saps|pots) fer|que fas|com (?:em )?pots ajudar(?: ?me)?|"
         r"en que (?:em )?pots ajudar|quines son les teves (?:funcions|capacitats)|que et puc demanar)$",
         "para que sirves"),
        (r"^(?:on|a quina botiga|a quin lloc)(?: es)?(?: puc| podria)? (?:compro|comprar|venen|ven|aconsegueixo|"
         r"aconseguir)(?: un| una| el| la| els| les| l)? (?P<x>.+)$", "donde compro {x}"),
        (r"^(?:actualitza|refresca|torna a buscar)(?: la fitxa| la definicio| l entrada| les dades)?"
         r"(?: de| del| de la| dels)?(?: la| el| els| les| l)? (?P<x>.+)$", "actualiza {x}"),
        (r"^(?:parla ?m|explica ?m|digues ?me|que es|que son|qui es|informacio|dades|fitxa|que saps|descriu|"
         r"defineix)(?: de| del| sobre| dels| de la| de les| d)?(?: la| el| els| les| un| una| l)? (?P<x>.+)$",
         "hablame de {x}"),
    ],
    "fr": [
        (r"^(?:oublie|efface) la conversation$|^nouvelle conversation$", "nueva conversacion"),
        (r"^(?:ouvre(?: moi)?|montre(?: moi)?|affiche|je veux voir|ou est) (?:le |ton )?manuel"
         r"(?: d utilisation| de nova(?: ai)?)?$", "abre el manual"),
        (r"^(?:qui es tu|qui etes vous|presente toi|presentez vous|qu est ce que tu es|qui t a (?:cree|fait|programme|"
         r"developpe)|qui est ton (?:createur|auteur|developpeur)|parle moi de toi|quelle version es tu|"
         r"quelle est ta version)$", "quien eres"),
        (r"^(?:a quoi tu sers|a quoi sers tu|a quoi servez vous|que (?:sais|peux) tu faire|qu est ce que tu (?:sais|"
         r"peux) faire|comment (?:peux tu|pourrais tu) m aider|quelles sont tes (?:fonctions|capacites)|"
         r"que puis je te demander)$", "para que sirves"),
        (r"^(?:ou|dans quel magasin)(?: est ce que)?(?: je peux| puis je| peut on| on peut| je pourrais)?"
         r" (?:acheter|j achete|trouver)(?: un| une| le| la| les| des| l| du)? (?P<x>.+)$", "donde compro {x}"),
        (r"^ou (?:se vend|vend on|on vend)(?: un| une| le| la| les| des| l| du)? (?P<x>.+)$", "donde compro {x}"),
        (r"^(?:mets a jour|actualise|rafraichis)(?: la fiche| la definition| l entree| les donnees)?"
         r"(?: de| du| des| d)?(?: la| le| les| l)? (?P<x>.+)$", "actualiza {x}"),
        (r"^(?:parle moi|dis moi|explique moi|qu est ce que|c est quoi|qui est|informations?|infos?|donnees|fiche|"
         r"que sais tu|decris|definis)(?: de| du| des| sur| a propos de| d)?(?: la| le| les| un| une| l)? (?P<x>.+)$",
         "hablame de {x}"),
    ],
    "de": [
        (r"^(?:vergiss|losche) das gesprach$|^neues gesprach$", "nueva conversacion"),
        (r"^(?:offne|zeig(?:e)?(?: mir)?|ich will sehen|wo ist) (?:das |dein )?(?:benutzer)?handbuch"
         r"(?: von nova(?: ai)?)?$", "abre el manual"),
        (r"^(?:wer bist du|stell dich vor|stellen sie sich vor|was bist du|wer hat dich (?:erschaffen|gemacht|"
         r"programmiert|entwickelt)|wer ist dein (?:schopfer|autor|entwickler)|erzahl mir von dir|"
         r"welche version (?:bist du|hast du))$", "quien eres"),
        (r"^(?:wofur bist du(?: da)?|wozu bist du da|was kannst du(?: fur mich tun)?|wie kannst du mir helfen|"
         r"wobei kannst du mir helfen|was sind deine (?:funktionen|fahigkeiten)|was machst du)$", "para que sirves"),
        (r"^wo (?:kann ich|kaufe ich|bekomme ich|kann man)(?: ein| eine| einen| den| die| das)? (?P<x>.+?)"
         r"(?: kaufen| bekommen| erwerben)?$", "donde compro {x}"),
        (r"^wo gibt es (?:ein |eine |einen |den |die |das )?(?P<x>.+?) zu kaufen$", "donde compro {x}"),
        (r"^(?:aktualisiere|erneuere)(?: den eintrag| die daten| die definition| die infos)?(?: (?:zu|von|uber))?"
         r"(?: den| die| das| dem| der)? (?P<x>.+)$", "actualiza {x}"),
        (r"^(?:erzahl mir (?:etwas )?(?:uber|von)|was ist|was sind|wer ist|infos? (?:uber|zu)|informationen "
         r"(?:uber|zu)|daten (?:uber|zu)|beschreibe|definiere)(?: den| die| das| dem| der| ein| eine| einen)? "
         r"(?P<x>.+)$", "hablame de {x}"),
    ],
}
RULES = {lang: [(re.compile(rx), out) for rx, out in rules] for lang, rules in _RULES.items()}


def canonical(norm: str, lang: str) -> str | None:
    """Forma en español de una orden fija dicha en otro idioma, o None si no es ninguna."""
    for rx, out in RULES.get(lang, ()):
        m = rx.match(norm)
        if m:
            return out.format(**m.groupdict())
    return None


def words(table: dict, lang: str) -> set:
    return table.get(lang, set())


# ------------------------------------------------------------- «envía mensaje al chat»
CHAT_INTENT = {
    "en": r"^\s*(?:please\s+)?(?:send|write|post|say|type)\s+(?:a\s+|the\s+|this\s+)?(?:message|text)?\s*"
          r"(?:to|in|on|into)\s+(?:the\s+)?(?:game\s+)?chat(?:\s+(?:saying|that says))?\s*[:,;.\-]?\s*",
    "ca": r"^\s*(?:si us plau\s+)?(?:envia|escriu|posa|digues|publica)\s+(?:un\s+|el\s+|aquest\s+)?(?:missatge|text)\s+"
          r"(?:al|en el|pel|a el)\s+xat(?:\s+del\s+joc)?(?:\s+que\s+digui|\s+dient)?\s*[:,;.\-]?\s*",
    "fr": r"^\s*(?:s'il te plait\s+)?(?:envoie|ecris|mets|dis|poste|publie)\s+(?:un\s+|le\s+|ce\s+)?(?:message|texte)\s+"
          r"(?:au|dans\s+le|sur\s+le|dans\s+la)\s+(?:chat|tchat)(?:\s+du\s+jeu)?(?:\s+qui\s+dit|\s+disant)?\s*[:,;.\-]?\s*",
    "de": r"^\s*(?:bitte\s+)?(?:sende|schick(?:e)?|schreib(?:e)?|poste)\s+(?:eine\s+|die\s+|diese\s+)?(?:nachricht|text)\s+"
          r"(?:in\s+den|an\s+den|im|in)\s+chat(?:\s+des\s+spiels)?(?:\s*,?\s*die\s+lautet)?\s*[:,;.\-]?\s*",
}
CHAT_RX = {k: re.compile(v, re.I) for k, v in CHAT_INTENT.items()}

# ------------------------------------------------------- «búscame a un jugador» y su apodo
PLAYER_VERBS = (r"find\w*|look\s?up|search\w*|locate\w*|investigate\w*|track\w*|troba\w*|cerca\w*|localitza\w*|"
                r"investiga\w*|trouve\w*|cherche\w*|recherche\w*|localise\w*|finde\w*|such\w*|lokalisier\w*|"
                r"ermittle\w*")
PLAYER_WORD = r"player|players|jugador|jugadora|jugadors|joueur|joueuse|joueurs|spieler|spielerin"
PLAYER_NAMED = r"called|named|dit|anomenat|anomenada|qui s appelle|nomme|namens|der heisst|die heisst"

# --------------------------------------------------------------- configuración inicial
PILOT_INTRO = {
    "en": r"my name is|i am|i'm|im|call me|you can call me|they call me",
    "ca": r"em dic|el meu nom es|el meu nom és|soc|sóc|pots dir-me|digues-me",
    "fr": r"je m'appelle|je m appelle|mon nom est|je suis|appelle-moi|appelle moi|tu peux m'appeler",
    "de": r"ich heiße|ich heisse|mein name ist|ich bin|nenn mich|du kannst mich",
}
AI_INTRO = {
    "en": r"call yourself|your name will be|your name is|i'll call you|i will call you|you will be called|"
          r"you're called|be called|i name you",
    "ca": r"et diràs|et diras|el teu nom serà|el teu nom sera|et diré|et dire|dis-te|digues-te|et posaré|et posare",
    "fr": r"tu t'appelleras|tu t appelleras|appelle-toi|appelle toi|ton nom sera|je t'appellerai|je t appellerai|"
          r"tu vas t'appeler",
    "de": r"du heißt|du heisst|dein name ist|dein name wird|ich nenne dich|nenn dich|du wirst .{0,10}heißen",
}

TRAINING = {
    "en": (
        ["{nombre}, I can still hear the airport of Area Eighteen and the old engines idling.",
         "{nombre}, our Aurora is approaching the outpost on Aberdeen; I hear the alarm in the area.",
         "{nombre}, every outpost on Euterpe is quiet; aim our ion cannon at the ore."],
        ["{nombre}, tomorrow I'm flying my Vanguard and a Gladius through the snow on Yela.",
         "{nombre}, my wingman just joined in the Vulture; we'll travel with the Banu Merchantman.",
         "{nombre}, the distress signal comes from a player under the ice of Yela; launch the Gladius."],
        ["{nombre}, that player was heading for the mountains; take me there in the Cutlass Black.",
         "{nombre}, help me out: twenty boxes of gold under the fog and tomorrow we jump to Pyro.",
         "{nombre}, the Reclaimer holds; tomorrow we carry the loot to the New Babbage spaceport."],
    ),
    "ca": (
        ["{nombre}, encara sento l'aeroport d'Àrea Divuit i fa olor d'oli.",
         "{nombre}, l'Aurora aterra a Orison i l'eufòria aèria augmenta.",
         "{nombre}, aquí el pilot: l'Aquila udola a l'oest de Daymar."],
        ["{nombre}, demà porto la meva Vanguard i un Gladius sota la neu de Yela.",
         "{nombre}, ja ha arribat el meu company a la Vulture; viatgem junts amb la Banu Merchantman.",
         "{nombre}, el vell canó ja brilla; baixa i vigila la muntanya d'Hurston."],
        ["{nombre}, aquell jugador anava cap a la muntanya; porta'm ja a la Cutlass Black.",
         "{nombre}, ajuda'm: porto vint caixes d'or sota la boira i demà viatjo a Pyro.",
         "{nombre}, la Reclaimer aguanta; demà portem el botí a l'aeroport de New Babbage."],
    ),
    "fr": (
        ["{nombre}, j'entends encore l'aéroport d'Area Dix-Huit et l'odeur d'huile.",
         "{nombre}, l'euphorie aérienne augmente quand j'atterris l'Aurora à Orison.",
         "{nombre}, ici le pilote : l'Aquila hurle à l'ouest de Daymar."],
        ["{nombre}, demain je pilote mon Vanguard et un Gladius sous la neige de Yela.",
         "{nombre}, mon coéquipier est arrivé dans le Vulture ; on voyage ensemble avec le Banu Merchantman.",
         "{nombre}, le vieux canon brille déjà ; descends et surveille la montagne d'Hurston."],
        ["{nombre}, ce joueur allait vers la montagne ; emmène-moi vite dans le Cutlass Black.",
         "{nombre}, aide-moi : vingt caisses d'or sous le brouillard et demain je pars pour Pyro.",
         "{nombre}, le Reclaimer tient bon ; demain on porte le butin à l'astroport de New Babbage."],
    ),
    "de": (
        ["{nombre}, ich höre noch den Flughafen von Area Achtzehn und rieche Öl.",
         "{nombre}, die Aurora euphorisch auf Orison aufsetzen, auf auf!",
         "{nombre}, hier spricht der Pilot: die Aquila heult im Westen von Daymar."],
        ["{nombre}, morgen fliege ich meine Vanguard und eine Gladius durch den Schnee auf Yela.",
         "{nombre}, mein Flügelmann ist in der Vulture da; wir reisen mit der Banu Merchantman.",
         "{nombre}, die alte Kanone glänzt schon; flieg runter und bewache den Berg auf Hurston."],
        ["{nombre}, der Spieler flog zu den Bergen; bring mich sofort mit der Cutlass Black hin.",
         "{nombre}, hilf mir: zwanzig Kisten Gold im Nebel und morgen springen wir nach Pyro.",
         "{nombre}, die Reclaimer hält; morgen bringen wir die Beute zum Raumhafen von New Babbage."],
    ),
}
