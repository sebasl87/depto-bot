# 🏠 Depto Bot — CABA

Bot que busca departamentos en venta en CABA 2x por día y notifica por Telegram.

**Filtros aplicados:**
- 📍 Capital Federal
- 💰 USD 10.000 – 50.000
- 📐 Más de 30 m²
- 🏗️ Terminados / A estrenar (sin pozo)
- 🔎 Fuentes: Zonaprop + Argenprop

---

## Setup (5 pasos)

### 1. Crear el bot de Telegram

1. Hablar con [@BotFather](https://t.me/BotFather) en Telegram
2. `/newbot` → elegir nombre → te da el **TELEGRAM_TOKEN**
3. Iniciar una conversación con tu bot
4. Ir a `https://api.telegram.org/bot<TOKEN>/getUpdates` para obtener el **chat_id**
   (tu **TELEGRAM_CHAT_ID** es el número en `"id":` dentro de `"chat":`)

### 2. Crear la tabla en Supabase

Ir al **SQL Editor** de tu proyecto Supabase y ejecutar el contenido de `supabase_migration.sql`.

La `SUPABASE_KEY` a usar es la **service_role** key (Settings → API), NO la anon key.

### 3. Agregar secrets en GitHub

En tu repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret | Valor |
|---|---|
| `SUPABASE_URL` | URL de tu proyecto Supabase |
| `SUPABASE_KEY` | service_role key de Supabase |
| `TELEGRAM_TOKEN` | Token del bot (BotFather) |
| `TELEGRAM_CHAT_ID` | Tu chat ID numérico |

### 4. Subir el repo

```bash
git init
git add .
git commit -m "feat: depto bot inicial"
git remote add origin https://github.com/sebasl87/depto-bot.git
git push -u origin main
```

### 5. Verificar que funciona

En GitHub → Actions → "Depto Bot" → Run workflow (disparo manual).

Deberías recibir en Telegram:
- Las publicaciones nuevas encontradas (si hay)
- Un mensaje resumen al final

---

## Horarios de ejecución

| Corrida | Hora Argentina |
|---|---|
| Mañana | 9:00 AM |
| Tarde | 6:00 PM |

---

## Ajustar los filtros de búsqueda

Las URLs de búsqueda están en `scraper.py` en la variable `SEARCH_URLS`.

Para cambiar zona, precio o superficie, la forma más fácil es:
1. Ir a zonaprop.com.ar o argenprop.com
2. Aplicar los filtros que querés visualmente
3. Copiar la URL resultante y reemplazarla en `SEARCH_URLS`

---

## Formato del mensaje en Telegram

```
🟡 Departamento 2 ambientes en Palermo
💰 USD 45.000
📍 Av. Santa Fe 3200, Palermo
📐 38 m² cubiertos
🔗 Ver publicación
```

🟡 = Zonaprop | 🔵 = Argenprop

---

## Troubleshooting

**El bot corre pero no llegan mensajes**
→ Verificá que hayas iniciado una conversación con el bot en Telegram antes.

**Error de Supabase**
→ Confirmá que usás la `service_role` key, no la `anon` key.

**Los selectores CSS dejaron de funcionar**
→ Zonaprop/Argenprop cambian su HTML de vez en cuando. Inspeccioná el elemento
en el navegador y actualizá los selectores en `parse_zonaprop()` o `parse_argenprop()`.
