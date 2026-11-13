-- 업로드한 매물(listings) 삭제 기능용 권한 추가
-- Supabase SQL Editor에서 한 번만 실행하세요.

create policy "authenticated delete listings" on listings for delete using (auth.role() = 'authenticated');
grant delete on listings to authenticated;
