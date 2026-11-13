-- 부동산 관심구역 대시보드 — Supabase 스키마
-- Supabase 프로젝트 생성 후 SQL Editor에서 이 파일 전체를 실행하세요.

create extension if not exists "uuid-ossp";

-- 1. 관심 단지/구역 (관리 탭에서 추가/삭제)
create table if not exists targets (
  id uuid primary key default uuid_generate_v4(),
  name text not null,                         -- 예: 잠실 엘스
  type text not null check (type in ('apartment', 'redevelopment', 'commercial')),
  lawd_cd text not null,                       -- 법정동코드 5자리 (구 단위), 예: 송파구 11710
  naver_complex_no text,                       -- 네이버 단지번호 (아파트/상가만, 재개발구역은 null)
  naver_dong_code text,                        -- 네이버 지역 코드 (구역 단위 매물 검색용)
  discount_threshold_pct numeric not null default 10, -- 급매 판정 기준: 실거래/감정가 대비 할인율(%)
  price_drop_threshold_pct numeric not null default 5, -- 호가 인하 감지 기준(%)
  appraisal_value bigint,                      -- 재개발구역: 감정가 (총투자금 계산용, 평당 또는 호별)
  dong_name text,                               -- 상가 등: 국토부 API 응답의 법정동명(umdNm)과 일치해야 할 값 (구 전체로 범위가 너무 넓을 때 좁히는 용도)
  jibun text,                                   -- 상가 등: 국토부 API 응답의 지번(jibun)과 일치해야 할 값
  active boolean not null default true,
  memo text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 2. 네이버 매물 (현재 시점 스냅샷, article_no가 고유 매물 ID)
create table if not exists listings (
  id uuid primary key default uuid_generate_v4(),
  target_id uuid not null references targets(id) on delete cascade,
  article_no text not null,                    -- 네이버 매물 고유번호
  price bigint,                                 -- 매매가 (원)
  deposit bigint,                                -- 보증금 (상가/재개발 - 총투자금 계산용)
  area_m2 numeric,
  floor_info text,
  tags text[],                                  -- '급매','급처','협의가능' 등
  description text,
  raw_json jsonb,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  is_active boolean not null default true,      -- false면 매물이 사라짐(거래완료 추정)
  unique (target_id, article_no)
);

-- 3. 매물 가격 변동 이력 (호가 인하 감지용)
create table if not exists listing_price_history (
  id uuid primary key default uuid_generate_v4(),
  listing_id uuid not null references listings(id) on delete cascade,
  price bigint not null,
  recorded_at timestamptz not null default now()
);

-- 4. 실거래가 수집 결과 (국토부 API)
create table if not exists transactions (
  id uuid primary key default uuid_generate_v4(),
  target_id uuid not null references targets(id) on delete cascade,
  source text not null check (source in ('apt', 'villa', 'house', 'commercial')),
  deal_date date not null,
  price bigint not null,
  area_m2 numeric,
  floor_info text,
  raw_json jsonb,
  created_at timestamptz not null default now()
);

-- 5. 급매 판정 알림 로그
create table if not exists alerts (
  id uuid primary key default uuid_generate_v4(),
  target_id uuid not null references targets(id) on delete cascade,
  listing_id uuid references listings(id) on delete set null,
  reason text not null,                         -- 'below_median' | 'price_drop' | 'keyword' | 'premium_low'
  detail jsonb,
  notified boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists idx_listings_target on listings(target_id);
create index if not exists idx_transactions_target on transactions(target_id, deal_date desc);
create index if not exists idx_alerts_target on alerts(target_id, created_at desc);

-- RLS: 기본적으로 전체 차단되므로 아래 정책을 반드시 추가
alter table targets enable row level security;
alter table listings enable row level security;
alter table listing_price_history enable row level security;
alter table transactions enable row level security;
alter table alerts enable row level security;

-- 누구나 읽기 가능 (대시보드 조회용, anon key)
create policy "public read targets" on targets for select using (true);
create policy "public read listings" on listings for select using (true);
create policy "public read price history" on listing_price_history for select using (true);
create policy "public read transactions" on transactions for select using (true);
create policy "public read alerts" on alerts for select using (true);

-- 로그인한 사용자만 관심 단지 추가/수정/삭제 (관리 탭, Supabase Auth 필요)
create policy "authenticated manage targets insert" on targets for insert with check (auth.role() = 'authenticated');
create policy "authenticated manage targets update" on targets for update using (auth.role() = 'authenticated');
create policy "authenticated manage targets delete" on targets for delete using (auth.role() = 'authenticated');

-- listings/transactions/alerts 쓰기는 service_role 키(GitHub Actions)만 가능 (RLS 우회, 별도 정책 불필요)

-- 신규 Supabase 프로젝트(새 API 키 체계)는 service_role/anon/authenticated 모두
-- 테이블 권한이 기본으로 안 붙어 있는 경우가 있어, 이 GRANT를 안 하면
-- "permission denied for table ..." 에러가 납니다 (RLS 정책과는 별개로 필요).
grant usage on schema public to service_role, anon, authenticated;
grant all on all tables in schema public to service_role;
grant all on all sequences in schema public to service_role;
alter default privileges in schema public grant all on tables to service_role;

grant select on all tables in schema public to anon, authenticated;
grant insert, update, delete on targets to authenticated;
