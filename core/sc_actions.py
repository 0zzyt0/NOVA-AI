"""Catálogo de acciones de Star Citizen 4.x (nombres internos de CIG) con nombre en
español, tecla por defecto y frases sugeridas. Sirve para:
  - saber qué acción del juego corresponde a cada comando de Nova,
  - crear comandos nuevos desde el editor eligiendo la acción del juego,
  - dar nombre en español a las teclas que configures en el juego.
Las teclas por defecto pueden cambiar entre parches: por eso Nova lee además tu
actionmaps.xml, que guarda las teclas que tú has cambiado.
"""

# acción: (nombre en español, tecla por defecto, mantener (s), [frases], categoría)
CATALOG: dict[str, tuple[str, str, float, list[str], str]] = {
    "v_flightready": ("Preparar nave para el vuelo", "r", 0, ["preparar nave", "listo para volar"], "Despegue y aterrizaje"),
    "v_toggle_landing_system": ("Tren de aterrizaje", "n", 0, ["tren de aterrizaje"], "Despegue y aterrizaje"),
    "v_autoland": ("Aterrizaje automático", "n", 2.0, ["aterrizaje automático"], "Despegue y aterrizaje"),
    "v_atc_request": ("Pedir permiso a la torre", "lalt+n", 0, ["llama a la torre"], "Despegue y aterrizaje"),
    "v_vtol_toggle": ("Modo VTOL", "k", 0, ["modo vtol"], "Despegue y aterrizaje"),
    "pl_exit": ("Levantarse del asiento", "y", 1.2, ["levántate"], "Despegue y aterrizaje"),
    "v_power_toggle": ("Energía principal", "u", 0, ["energía principal"], "Energía y sistemas"),
    "v_power_toggle_shields": ("Energía de escudos", "o", 0, ["escudos"], "Energía y sistemas"),
    "v_power_toggle_weapons": ("Energía de armas", "p", 0, ["armas"], "Energía y sistemas"),
    "v_power_toggle_thrusters": ("Energía de propulsores", "i", 0, ["propulsores"], "Energía y sistemas"),
    "v_lights": ("Luces exteriores", "l", 0, ["luces"], "Energía y sistemas"),
    "v_doors_open_all": ("Abrir todas las puertas", "", 0, ["abre las puertas"], "Energía y sistemas"),
    "v_doors_close_all": ("Cerrar todas las puertas", "", 0, ["cierra las puertas"], "Energía y sistemas"),
    "v_doors_lock_all": ("Bloquear puertas", "", 0, ["bloquea las puertas"], "Energía y sistemas"),
    "v_doors_unlock_all": ("Desbloquear puertas", "", 0, ["desbloquea las puertas"], "Energía y sistemas"),
    "v_master_mode_cycle": ("Cambiar modo maestro (NAV/SCM)", "b", 0, ["cambia de modo"], "Navegación"),
    "v_master_mode_set_nav": ("Modo navegación (NAV)", "", 0, ["modo navegación"], "Navegación"),
    "v_master_mode_set_scm": ("Modo combate (SCM)", "", 0, ["modo combate"], "Navegación"),
    "v_toggle_qdrive_engagement": ("Salto cuántico", "b", 2.0, ["salto cuántico"], "Navegación"),
    "v_toggle_quantum_mode": ("Modo cuántico", "", 0, ["modo cuántico"], "Navegación"),
    "v_ifcs_throttle_swap_mode": ("Control de crucero", "lalt+c", 0, ["control de crucero"], "Navegación"),
    "v_ifcs_vector_decoupling_toggle": ("Modo desacoplado", "c", 0, ["modo desacoplado"], "Navegación"),
    "v_space_brake": ("Freno espacial", "x", 2.0, ["freno"], "Navegación"),
    "v_invoke_ping": ("Ping de radar", "tab", 0, ["ping"], "Navegación"),
    "v_toggle_scan_mode": ("Modo escáner", "v", 0, ["modo escáner"], "Navegación"),
    "v_starmap": ("Mapa estelar", "f2", 0, ["mapa"], "Interfaz"),
    "mobiglas": ("mobiGlas", "f1", 0, ["mobiglas"], "Interfaz"),
    "v_view_cycle_fwd": ("Cambiar cámara", "f4", 0, ["cámara"], "Interfaz"),
    "v_target_cycle_hostile_fwd": ("Siguiente objetivo hostil", "5", 0, ["siguiente hostil"], "Combate"),
    "v_target_cycle_attacker_fwd": ("Siguiente atacante", "4", 0, ["siguiente atacante"], "Combate"),
    "v_target_cycle_all_fwd": ("Siguiente objetivo", "t", 0, ["siguiente objetivo"], "Combate"),
    "v_target_unlock": ("Quitar objetivo", "lalt+t", 0, ["quitar objetivo"], "Combate"),
    "v_weapon_countermeasure_decoy_launch": ("Lanzar bengalas", "h", 0, ["bengalas"], "Combate"),
    "v_weapon_countermeasure_noise_launch": ("Lanzar chaff", "j", 0, ["chaff"], "Combate"),
    "v_operator_mode_cycle_forward": ("Siguiente modo de operador", "", 0, ["siguiente modo"], "Combate"),
    "v_toggle_missile_mode": ("Modo misiles", "", 0, ["modo misiles"], "Combate"),
    "v_toggle_mining_mode": ("Modo minería", "m", 0, ["modo minería"], "Minería y salvamento"),
    "v_toggle_salvage_mode": ("Modo salvamento", "m", 0, ["modo salvamento"], "Minería y salvamento"),
    "v_jettison_volatile_cargo": ("Expulsar carga", "lalt+j", 0, [], "Minería y salvamento"),
}

# Nombres antiguos o alternativos de algunas acciones (según el parche).
ALIASES = {
    "v_vtol_toggle": ["v_toggle_vtol"],
    "v_ifcs_vector_decoupling_toggle": ["v_ifcs_toggle_vector_decoupling"],
    "v_ifcs_throttle_swap_mode": ["v_ifcs_toggle_cruise_control"],
    "v_target_unlock": ["v_target_unlock_selected"],
    "pl_exit": ["v_exit"],
}


def label(action: str) -> str:
    if action in CATALOG:
        return CATALOG[action][0]
    for main, alts in ALIASES.items():
        if action in alts:
            return CATALOG[main][0]
    return humanize(action)


def humanize(action: str) -> str:
    """'v_shield_raise_level_front' -> 'Shield raise level front' (para acciones fuera del catálogo)."""
    words = [w for w in action.split("_") if w not in ("v", "pc", "pl", "ui")]
    text = " ".join(words) or action
    return text[:1].upper() + text[1:]


def names_for(action: str) -> list[str]:
    return [action, *ALIASES.get(action, [])]


# Nunca se convierten en comandos automáticos (la IA no debe poder hacerlas por error).
DANGEROUS = ("self_destruct", "eject", "emergency", "suicide", "jettison", "respawn", "quit", "logout",
             "exit_game", "abandon", "detonate", "release_all", "unequip")


def is_dangerous(action: str) -> bool:
    a = action.lower()
    return any(d in a for d in DANGEROUS)
