# Sala de situación

Vigilancia automática de noticias y alertas en tiempo real (sucesos, emergencias, transporte, meteorología, sismos y última hora) con avisos al móvil a través de la app gratuita **ntfy**.

- Se ejecuta sola en GitHub cada 5 minutos; no necesita ningún ordenador encendido.
- Las zonas, fuentes y palabras vigiladas están en `config.yaml` y se pueden editar desde esta misma web (icono del lápiz).
- La clave del canal de avisos se guarda como secreto (`NTFY_TOPIC`) y no es visible.
- Para pausarlo: pestaña **Actions** → *Sala de situación* → menú «···» → *Disable workflow*.
