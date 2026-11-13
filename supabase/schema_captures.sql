-- 매물/경매 캡처 업로드 + 자동 파싱 기능 (schema.sql 실행 이후, 추가로 실행)

-- 1. 업로드된 캡처 이미지 (대기 중 → Claude Vision이 파싱 → listings/auction_items로 분류)
create table if not exists captures (
  id uuid primary key default uuid_generate_v4(),
  kind text not null check (kind in ('listing', 'auction')),
  image_path text not null,                      -- Supabase Storage 내 경로 (captures 버킷)
  status text not null default 'pending' check (status in ('pending', 'processed', 'error')),
  target_id uuid references targets(id) on delete set null,  -- 업로드 시 연결할 단지/구역(선택)
  parsed jsonb,                                   -- Claude Vision이 추출한 원본 결과
  error_message text,
  created_at timestamptz not null default now(),
  processed_at timestamptz
);

-- 2. 관심 경매 물건 (입찰일 임박 시 텔레그램 알림)
create table if not exists auction_items (
  id uuid primary key default uuid_generate_v4(),
  target_id uuid references targets(id) on delete set null,
  capture_id uuid references captures(id) on delete set null,
  case_number text,                               -- 사건번호 (예: 2025타경13341)
  title text,                                      -- 물건 소재지/설명
  court text,                                       -- 관할법원
  bid_date date,                                    -- 입찰기일
  appraisal_value bigint,                           -- 감정가
  min_bid_price bigint,                             -- 최저입찰가
  status text not null default 'upcoming' check (status in ('upcoming', 'done', 'cancelled')),
  reminded_at timestamptz,
  notes text,
  created_at timestamptz not null default now()
);

create index if not exists idx_captures_status on captures(status);
create index if not exists idx_auction_items_bid_date on auction_items(bid_date);

alter table captures enable row level security;
alter table auction_items enable row level security;

create policy "public read captures" on captures for select using (true);
create policy "authenticated insert captures" on captures for insert with check (auth.role() = 'authenticated');

create policy "public read auction items" on auction_items for select using (true);
create policy "authenticated manage auction items" on auction_items for all using (auth.role() = 'authenticated');

grant all on captures to service_role;
grant all on auction_items to service_role;

-- 캡처 이미지 저장용 비공개 버킷
insert into storage.buckets (id, name, public)
values ('captures', 'captures', false)
on conflict (id) do nothing;

create policy "authenticated upload captures" on storage.objects
  for insert with check (bucket_id = 'captures' and auth.role() = 'authenticated');

create policy "authenticated read captures" on storage.objects
  for select using (bucket_id = 'captures' and auth.role() = 'authenticated');
