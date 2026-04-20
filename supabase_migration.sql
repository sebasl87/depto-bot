-- Ejecutar en el SQL Editor de Supabase Dashboard
-- o guardar como migration en supabase/migrations/

create table if not exists depto_listings_seen (
  listing_id  text        primary key,
  source      text        not null,          -- 'zonaprop' | 'argenprop'
  url         text        not null,
  created_at  timestamptz default now()
);

-- Índice para acelerar el lookup de IDs ya vistos
create index if not exists idx_depto_listings_source
  on depto_listings_seen (source);

-- Política RLS: solo el service role puede escribir
-- (la key que usás en el bot debe ser la service_role key)
alter table depto_listings_seen enable row level security;

create policy "service role full access"
  on depto_listings_seen
  for all
  using (true)
  with check (true);
