# Victorin

Plataforma de gestion de prestamos en Streamlit con persistencia en Supabase.

## Funciones

- Dashboard con capital total, total prestado y saldo disponible.
- Registro de capital inicial, ingreso 15 e ingreso 30.
- Registro de prestamos detallados por persona o como total agregado.
- Edicion y eliminacion de registros.
- Exportacion completa en CSV.
- Preparado para despliegue en Streamlit Cloud.

## Estructura

- `app.py`: punto de entrada de Streamlit.
- `src/config.py`: lectura de variables de entorno y secretos.
- `src/db.py`: acceso a Supabase.
- `src/services.py`: logica de negocio y transformaciones.
- `supabase/schema.sql`: esquema de base de datos.

## Configuracion local

1. Crea un proyecto en Supabase.
2. Ejecuta el SQL de `supabase/schema.sql`.
3. Copia `.env.example` a `.env` y completa los valores, o usa el `.env` local ya preparado.
4. Instala dependencias:

```bash
pip install -r requirements.txt
```

5. Ejecuta la app:

```bash
streamlit run app.py
```

## Variables de entorno

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`

## Streamlit Cloud

Agrega `SUPABASE_URL` y `SUPABASE_ANON_KEY` en la configuracion de secrets de Streamlit Cloud.

## Credenciales

- La `SUPABASE_ANON_KEY` publicada para la app corresponde al `publishable key`.
- La `secret key` no debe usarse en el frontend de Streamlit; guardala solo para tareas administrativas si las necesitas.

## Nota sobre ingresos 15 y 30

Las categorias `Ingreso 15` y `Ingreso 30` se suman al capital total disponible junto con el capital inicial. Luego se descuenta el total prestado para calcular el saldo.
