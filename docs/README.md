# hackspain CLI — The One Doc

Cliente de terminal para participantes: misma cuenta y mismos datos que el dashboard (equipos, retos, entrega, feed y watcher). Documentación canónica en la web: [hackspain.app/cli](https://hackspain.app/cli).

```
Participante → hackspain (local) → API HackSpain → dashboard hackspain.app
```

## The taxonomy

| Área | Qué cubre en terminal |
|---|---|
| **auth** | Sesión, login por navegador o código de 8 dígitos |
| **profile** | Datos de participante y enlaces GitHub/X |
| **team** | Equipo, invitación, repo, stack |
| **track / project / submit** | Retos, proyecto y entrega |
| **perk / milestone** | Beneficios (catálogo) e hitos del equipo |
| **feed / post** | Feed social y publicaciones |
| **watch / telemetry** | Watcher de harnesses de IA y estadísticas locales |

## Instalación

macOS y Linux: binario autocontenido.

```bash
curl -fsSL https://hackspain.com/install.sh | sh
hackspain update   # más adelante, para la última versión
```

Windows: descarga `hackspain-windows-x64.exe` desde la página de releases y renómbralo a `hackspain.exe`.

## Primeros pasos

Misma cuenta que el dashboard. El login abre el navegador para aprobar el dispositivo; también vale el código de 8 dígitos. Después puede pedir nombre, teléfono o GitHub.

| Comando | Descripción |
|---|---|
| `hackspain` | Dónde estás y qué toca hacer; en terminal interactiva, menú para moverte |
| `hackspain auth login [--email …] [--code …]` | Por defecto abre `/cli-auth` para aprobar este dispositivo. Con `--email`/`--code`, código de 8 dígitos por correo, como en la web |
| `hackspain open [feed\|teams\|perks\|…]` | Abre el dashboard en el navegador con sesión ya iniciada |
| `hackspain auth status` | Comprueba tu sesión |
| `hackspain auth logout` | Cierra sesión |

## Perfil

La foto y la ficha completa se hacen en el dashboard.

| Comando | Descripción |
|---|---|
| `hackspain profile` | Nombre, dieta, viaje, teléfono, avisos, GitHub y X |
| `hackspain profile edit [--name …] [--diet …] [--diet-details …] [--from …]` | Edita datos del perfil |
| `hackspain profile notify on\|off` | Activa o desactiva avisos |
| `hackspain profile phone [+34…]` | Guarda teléfono de contacto |
| `hackspain profile github [--unlink]` | Enlace para autorizar GitHub en el navegador |
| `hackspain profile x [@usuario] [--clear]` | Guarda usuario de X |

## Equipo

Para unirte, el dueño comparte su código de invitación de 8 caracteres.

| Comando | Descripción |
|---|---|
| `hackspain team create <name> [-m github:x -m a@b.c]` | Crea el equipo; añade gente por GitHub, X o email |
| `hackspain team join <code>` | Únete con el código del dueño |
| `hackspain team show \| list` | Tu equipo, o todos los equipos |
| `hackspain team code [--regenerate]` | Muestra o regenera el código de invitación |
| `hackspain team repo [url…] [--clear]` | Vincula repositorio(s) público(s) de GitHub; actividad en el feed. Hazlo público antes de vincular |
| `hackspain team leave` | Sal del equipo |
| `hackspain team transfer [member]` | El dueño cede el equipo a otro miembro |
| `hackspain team dissolve` | El dueño borra un equipo sin otros miembros |
| `hackspain stack set nextjs convex claude-code` | Declara el stack tecnológico del equipo |

## Retos y entrega

Un proyecto por equipo, tantos retos como quieras. La entrega congela todo; los borradores se pueden guardar antes.

| Comando | Descripción |
|---|---|
| `hackspain track list` | Retos disponibles |
| `hackspain track register <slug…> \| unregister <slug…>` | Apúntate o bórrate de retos |
| `hackspain track move <from> <to>` | Cámbiate de reto |
| `hackspain submit [--draft]` | Formulario interactivo de entrega; flags para scripts |
| `hackspain project show \| list` | Tu proyecto, o todos los proyectos |

## Perks y milestones

| Comando | Descripción |
|---|---|
| `hackspain perk list` | Catálogo de beneficios de partners (reclamar en el dashboard) |
| `hackspain milestone add firstCommit\|firstBuild\|firstDemo\|custom [--label …] [--at ISO]` | Registra un hito del equipo |
| `hackspain milestone list [--all]` | Hitos registrados |

## Feed

Mismo feed que la página Feed del dashboard: mensajes y actividad GitHub de repos de equipo.

| Comando | Descripción |
|---|---|
| `hackspain feed [-n 20] [--no-images] [--before …]` | Últimas publicaciones y actividad, paginado. En kitty, Ghostty, WezTerm, iTerm2 o terminal de VS Code las fotos en terminal; en el resto, enlace |
| `hackspain post "texto" [--image foto.jpg]` | Publica (≤500 caracteres; jpeg/png/webp/gif ≤5 MB) |

## Watcher

Pensado para una terminal abierta todo el fin de semana: detecta harnesses de IA (Claude Code, Codex, Gemini CLI, Qwen Code, OpenCode, Kilo Code, Cline), muestra feed y avisos de la organización, y reporta uso. No envía prompts ni rutas completas de tu máquina.

| Comando | Descripción |
|---|---|
| `hackspain watch [--interval 30] [--no-upload] [--no-images] [--once]` | Arranca el watcher; reporta uso de IA en la ventana de la hackathon (también cuando estaba cerrado). `q` sale, `p` pausa, `↑`/`↓` recorren el feed, `g` vuelve al directo |
| `hackspain telemetry stats` | Lo que el watcher ha registrado en esta máquina |

### Key decisions

- **`--json` en scripts** — Cualquier comando con `--json` imprime un solo objeto JSON en stdout y desactiva prompts; el resto va a stderr (p. ej. `hackspain --json team show`, `hackspain --json feed -n 5`).
- **Fallos rápidos** — Comandos que requieren equipo, solicitud aceptada u onboarding completo fallan con el siguiente paso indicado. Fuera de la ventana de la hackathon siguen funcionando `hackspain profile`, `hackspain perk list` y `hackspain open participantes`.

## Códigos de salida

| Código | Significado |
|---|---|
| `0` | Todo bien |
| `1` | Error del servidor o genérico |
| `2` | Error de uso (flags mal puestos, falta input en modo no interactivo) |
| `3` | Sin sesión o sesión caducada |
| `4` | Aún no elegible (sin solicitud, sin aceptar, onboarding incompleto o hackathon no en marcha) |
| `5` | No se pudo alcanzar el backend |
| `130` | Interrumpido (Ctrl+C) |
