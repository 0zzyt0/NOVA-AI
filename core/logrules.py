"""Reglas de los avisos del HUD, sacadas de los textos del propio juego (global.ini).

Star Citizen escribe en el Game.log el aviso tal cual lo ves en pantalla, EN TU IDIOMA:
«Nuevo miembro unido · Ph3nomenas se ha unido a grupo.» o «AUTORIZACION ATC: CONCEDIDO.»
Por eso no sirve buscar frases fijas en inglés. Aquí se dice qué CLAVE del global.ini
corresponde a cada evento (p. ej. comms_member_left = «%S ha dejado el %s.») y Nova
construye la expresión a partir del texto que tiene TU juego. Si falta la clave (o no
hay global.ini) se usa el texto inglés original del juego, que viene en game_text_en.py.

Cada regla: (tipo, categoría, claves, campos, forma)
  campos: nombre de cada hueco %s/%ls/%i… en el orden en que aparecen.
          Los huecos ~funcion(Var) se nombran solos (PlayerName -> nombre…).
          %S (mayúscula) siempre es un jugador -> «nombre».
  forma:  "tpl"   la plantilla está al final del aviso (lo normal)
          "title" basta con que aparezca el título (avisos sin datos)
          "name_title"  «Ph3nomenas · Solicitud de amistad»  (nombre delante)
          "title_name"  «Amigo agregado · Ph3nomenas»        (nombre detrás)
"""
from __future__ import annotations

# Valores fijos que añade una regla (p. ej. gravedad de la herida según la clave).
CONST = {
    "hud_actorStatus_injuryWarning_severity_injury": {"x": "leve"},
    "hud_actorStatus_injuryWarning_severity_majorInjury": {"x": "moderada"},
    "hud_actorStatus_injuryWarning_severity_deadlyInjury": {"x": "grave"},
}

RULE_KEYS: list[tuple[str, str, tuple[str, ...], tuple[str, ...], str]] = [
    # ------------------------------------------------------------ ubicación y zonas
    ("zona_armisticio_entra", "ubicacion", ("hud_enter_green_zone",), (), "title"),
    ("zona_armisticio_sale", "ubicacion", ("hud_leave_green_zone",), (), "title"),
    ("espacio_vigilado_entra", "", ("hud_monitored_space_enter", "text_hostility_EnterMonitoredArea"), (), "title"),
    ("espacio_vigilado_sale", "", ("hud_monitored_space_leave", "text_hostility_LeaveMonitoredArea"), (), "title"),
    ("jurisdiccion", "ubicacion", ("hud_law_EnteredJurisdiction",), ("x",), "tpl"),
    ("territorio_hostil_entra", "ley", ("hud_enter_hostile_territory", "hud_law_GenericHostileWarning"), (), "title"),
    ("territorio_hostil_sale", "", ("hud_leave_hostile_territory",), (), "title"),
    ("zona_neutral_entra", "", ("hud_enter_neutral_territory",), (), "title"),
    ("propiedad_privada", "ubicacion", ("hud_enter_trespassing_area", "hud_law_TrespassPropertyWarning"), (), "title"),
    ("zona_restringida", "ley", ("hud_law_RestrictedArea", "mobiGlas_ui_notification_RestrictedArea_Title",
                                 "hud_enter_impounding_zone"), (), "title"),
    ("reubicado", "ley", ("mobiGlas_ui_notification_RestrictedArea_Despawn",
                          "mobiGlas_ui_notification_RestrictedArea_Disallow"), (), "title"),
    ("llamarada_solar", "avisos", ("mobiGlas_ui_notification_SolarFlareHazard_DangerZone_0",
                                   "mobiGlas_ui_notification_SolarFlareHazard_DangerZone_1",
                                   "mobiGlas_ui_notification_SolarFlareHazard_DangerZone_2"), (), "title"),
    ("llamarada_fin", "", ("mobiGlas_ui_notification_SolarFlareHazard_Finished",
                           "mobiGlas_ui_notification_SolarFlareHazard_SafeZone"), (), "title"),
    # ------------------------------------------------------------ grupo y canales de nave
    # «%S se ha unido a %s.»: el %s dice si es el grupo o el canal de una nave (ver suffix_kind()).
    ("grupo_entra", "grupo", ("comms_invite_accepted", "mobiGlas_ui_notification_Party_Member_Joined"), ("donde",), "tpl"),
    ("grupo_sale", "grupo", ("comms_member_left", "mobiGlas_ui_notification_Party_Member_Left"), ("donde",), "tpl"),
    ("grupo_expulsa", "grupo", ("comms_member_kicked", "mobiGlas_ui_notification_Party_Member_Kicked"), ("donde",), "tpl"),
    ("grupo_lider", "grupo", ("comms_leader_changed", "mobiGlas_ui_notification_Party_New_Leader"), ("donde",), "tpl"),
    ("grupo_invitacion", "grupo", ("comms_invite_received", "mobiGlas_ui_notification_Party_Invite"), ("donde",), "tpl"),
    ("grupo_rechaza", "grupo", ("comms_invite_declined", "mobiGlas_ui_notification_Party_Invite_Declined"), ("donde",), "tpl"),
    ("grupo_te_unes", "grupo", ("comms_local_player_joined", "comms_local_player_joined_auto",
                                "mobiGlas_ui_notification_Party_Self_Join"), ("donde",), "tpl"),
    ("grupo_dejas", "grupo", ("comms_local_player_left", "mobiGlas_ui_notification_Party_Self_Left"), ("donde",), "tpl"),
    ("grupo_expulsado", "grupo", ("comms_local_player_kicked", "mobiGlas_ui_notification_Party_Self_Kicked"), ("donde",), "tpl"),
    ("grupo_disuelto", "grupo", ("comms_group_disbanded", "mobiGlas_ui_notification_Party_Disband"), ("donde",), "tpl"),
    ("grupo_disuelto", "grupo", ("notification_group_disbanded_Title",), (), "title"),
    ("grupo_creado", "grupo", ("comms_group_created", "mobiGlas_ui_notification_Party_Created"), ("donde",), "tpl"),
    ("grupo_creado", "grupo", ("notification_group_created_Title",), (), "title"),
    ("grupo_lanzamiento", "grupo", ("mobiGlas_ui_notification_Party_Launch",), (), "tpl"),
    ("grupo_lanzamiento", "grupo", ("notification_party_launch_Title",), (), "title"),
    ("grupo_salto_hacia_ti", "grupo", ("notification_party_member_started_QT_to_you",), ("nombre",), "tpl"),
    ("grupo_calibracion_inicio", "grupo", ("notification_calibration_onCalibrationStart_title",), (), "tpl"),
    ("grupo_calibracion", "grupo", ("notification_calibration_onCalibrationCompleted_title",), (), "tpl"),
    ("grupo_calibracion_fallo", "grupo", ("notification_calibration_onCalibrationFailed_title",), (), "tpl"),
    # ------------------------------------------------------------ amistad y llamadas
    ("amistad_peticion", "amistad", ("mobiGlas_ui_notification_Friend_Request_Received",), (), "tpl"),
    ("amistad_peticion", "amistad", ("notification_invite_friend_request_received_title",), (), "name_title"),
    ("amistad_aceptada", "amistad", ("mobiGlas_ui_notification_Friend_Added",), (), "tpl"),
    ("amistad_aceptada", "amistad", ("notification_invite_friend_added_title",), (), "title_name"),
    ("llamada", "amistad", ("hud_IncomingCall_Notification",), (), "title"),
    ("hangar_acceso", "amistad", ("mobiGlas_ui_notification_Hangar_Access_Granted",), (), "tpl"),
    # ------------------------------------------------------------ dinero
    ("dinero_recibido", "dinero", ("notification_PlayerTrade_Notification_RecipientSuccess_Desc",), (), "tpl"),
    ("dinero_ofrecido", "dinero", ("notification_PlayerTrade_TradeOffer_Desc",), ("nombre", "cantidad", "moneda"), "tpl"),
    ("dinero_enviado", "dinero", ("notification_PlayerTrade_Notification_SenderSuccess_Desc",), (), "tpl"),
    ("dinero_recibido", "dinero", ("notification_PlayerTrade_Notification_RecipientSuccess_Title",), (), "title"),
    ("multa", "ley", ("hud_law_FinePaid",), ("cantidad",), "tpl"),
    # ------------------------------------------------------------ torre de control y hangar
    ("atc_hangar_listo", "atc", ("ATC_GatewayQueue_End",), (), "title"),
    ("atc_cola_hangar", "atc", ("ATC_GatewayQueue_Update",), ("puesto", "espera"), "tpl"),
    ("atc_incautada", "atc", ("hud_law_ImpoundingNotification",), ("x",), "tpl"),
    ("atc_incautando", "atc", ("hud_law_ImpoundingInProgress",), (), "title"),
    # ------------------------------------------------------------ contratos
    ("contrato_aceptado", "contratos", ("mobiGlas_ui_MissionEvent_Activated",), ("x",), "tpl"),
    ("contrato_completado", "contratos", ("mobiGlas_ui_MissionEvent_Complete",), ("x",), "tpl"),
    ("contrato_fallido", "contratos", ("mobiGlas_ui_MissionEvent_Fail",), ("x",), "tpl"),
    ("contrato_retirado", "", ("mobiGlas_ui_MissionEvent_Deactivate",), ("x",), "tpl"),
    ("contrato_disponible", "", ("mobiGlas_ui_MissionEvent_Available",), ("x",), "tpl"),
    ("objetivo_nuevo", "", ("mobiGlas_ui_ObjectiveEvent_Activated",), ("x",), "tpl"),
    ("objetivo_completado", "", ("mobiGlas_ui_ObjectiveEvent_Complete",), ("x",), "tpl"),
    ("objetivo_fallido", "", ("mobiGlas_ui_ObjectiveEvent_Fail",), ("x",), "tpl"),
    # ------------------------------------------------------------ salud
    ("herida", "salud", ("hud_actorStatus_injuryWarning_severity_injury",
                         "hud_actorStatus_injuryWarning_severity_majorInjury",
                         "hud_actorStatus_injuryWarning_severity_deadlyInjury"), (), "title"),
    ("incapacitado", "salud", ("hud_incapacitated_downedStateWarning",), (), "title"),
    ("sobredosis", "salud", ("hud_incapacitated_overdosedStateWarning",), (), "title"),
    ("emergencias", "salud", ("hud_incapacitated_landingZoneRescue_notification",), (), "title"),
    ("rescate_aceptado", "salud", ("hud_incapacitated_downedReviveRequestAccepted",), ("nombre", "x"), "tpl"),
    # ------------------------------------------------------------ ley
    ("crimestat", "ley", ("text_hostility_Wanted",), (), "title"),
    ("crimen_contra_ti", "ley", ("hud_law_charge_player_crime", "hud_law_charge_player_crime_party"), ("nombre", "x"), "tpl"),
    ("crimen_cometido", "ley", ("hud_law_CrimeCommitted",), ("x",), "tpl"),
    # ------------------------------------------------------------ otros
    ("plano_recibido", "avisos", ("crafting_hud_notification_received_blueprint",), ("x",), "tpl"),
    ("refineria_lista", "avisos", ("refinery_ui_jobComplete",), ("lugar",), "tpl"),
    ("refineria_lista", "avisos", ("refinery_ui_multipleJobsComplete",), ("cantidad", "lugar"), "tpl"),
]

# Huecos ~funcion(Variable) -> campo
TILDE_FIELDS = {
    "playername": "nombre", "tradername": "nombre", "currencyvalueuec": "cantidad",
    "currencytypeuec": "moneda", "selecteddestination": "lugar",
}

# Claves que hacen falta además de las reglas (sufijos del grupo / canal de nave, nombres…)
EXTRA_KEYS = ("comms_suffix_party", "comms_suffix_group", "comms_suffix_ship_channel")

ALL_KEYS = sorted({k for _, _, keys, _, _ in RULE_KEYS for k in keys} | set(CONST) | set(EXTRA_KEYS))
