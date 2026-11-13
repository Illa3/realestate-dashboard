# 관심구역 부동산 대시보드

국토부 실거래가를 30분마다 모으고, 매물/경매 캡처를 올리면 Claude Vision이 자동으로 정리해서
급매를 감지하는 대시보드 + 텔레그램 알림. 폰 브라우저로 접속해서 봅니다.

```
GitHub Actions (30분 cron)
  ├─ 국토부 실거래가 수집 → Supabase
  ├─ 대기 중인 매물/경매 캡처 → Claude Vision 파싱 → Supabase (+ 실거래가와 비교해 급매 판정)
  └─ 입찰일 임박 경매물건 → 텔레그램 알림
Supabase → 정적 프론트엔드(Vercel): 대시보드 / 업로드 / 관리 탭
```

네이버 부동산 매물 자동 수집은 봇 차단 때문에 포기했습니다 — 대신 **직접 캡처해서 올리면 자동 정리**하는 방식으로 바꿨습니다 (아래 "매물/경매 캡처 업로드 기능" 참고).

## 설정 순서

### 1. 공공데이터포털 서비스키 발급
1. https://www.data.go.kr 가입 후 아래 4개를 각각 검색해서 활용신청 (보통 즉시~1일 승인, 키는 4개 다 동일한 서비스키 하나 공유):
   - **국토교통부_아파트 매매 실거래가 상세 자료** (https://www.data.go.kr/data/15126468/openapi.do)
   - **국토교통부_연립다세대 매매 실거래가 자료**
   - **국토교통부_단독/다가구 매매 실거래가 자료** (북아현3구역 등 재개발구역의 단독·다가구·상가주택용)
   - **국토교통부_상업업무용 부동산 매매 신고 자료** (신천동 장미아파트 상가용)
2. 단독/다가구, 상업업무용 두 API는 **정확한 Operation 주소를 신청 화면에서 확인해서** [scraper/molit_client.py](scraper/molit_client.py)의 `HOUSE_ENDPOINT`, `COMMERCIAL_ENDPOINT` 값을 맞게 고쳐주세요 (검색만으로는 100% 확정하지 못했습니다).
3. 마이페이지 > 오픈API 활용현황에서 서비스키(인증키) 복사

### 2. Supabase 프로젝트 생성
1. https://supabase.com 가입 (GitHub 계정으로 바로 가능, 카드 등록 불필요)
2. New Project 생성
3. SQL Editor에서 [supabase/schema.sql](supabase/schema.sql) 전체 실행
4. 이어서 [supabase/schema_captures.sql](supabase/schema_captures.sql) 실행 (매물/경매 캡처 업로드 기능용 테이블 + Storage 버킷)
5. 이어서 [supabase/migration_add_match_keywords.sql](supabase/migration_add_match_keywords.sql) 실행 (캡처 자동분류용 키워드 컬럼 추가)
6. 이어서 [config/seed_targets.sql](config/seed_targets.sql) 실행 (초기 6개 단지/구역 등록 — lawd_cd는 code.go.kr에서 확인 완료된 값)
7. Settings > API Keys에서 `Project URL`, publishable key(`sb_publishable_...`, 예전 anon key), secret key(`sb_secret_...`, 예전 service_role key) 복사 — 새로 만든 프로젝트는 새 키 체계라 이름이 다를 수 있음
8. 로컬에 `.env` 만들고 (`.env.example` 복사) 값 채운 뒤 `pip install -r requirements.txt && python -m scraper.healthcheck` 실행해서 연결 확인

### 3. 텔레그램 봇 만들기
1. 텔레그램에서 `@BotFather` 검색 → `/newbot` → 토큰 받기
2. `@userinfobot`에게 말 걸어서 본인 chat_id 확인 (검색 결과에 가짜가 많으니 `@username`이 정확히 `userinfobot`인지 확인)
3. 만든 봇에게 먼저 아무 메시지나 한 번 보내두기 (안 하면 알림이 안 옴)

### 4. Anthropic API 키 발급 (매물/경매 캡처 파싱용)
1. https://console.anthropic.com → API Keys → Create Key
2. 생성 직후에만 전체 값(`sk-ant-...`)이 보이니 그때 복사 — 나중엔 마스킹된 값만 보임

### 5. GitHub 저장소 설정
1. 이 폴더를 public 저장소로 push
2. Settings > Secrets and variables > Actions에서 등록 (`gh secret set <이름>`으로 터미널에서 직접 입력하면 값이 화면에 노출 안 돼서 더 안전함):
   - `MOLIT_SERVICE_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY` (secret key — 절대 코드에 커밋하지 말 것)
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `ANTHROPIC_API_KEY`
3. Actions 탭에서 `scrape` 워크플로를 한 번 수동 실행(`workflow_dispatch`)해서 에러 없는지 확인

### 6. 프론트엔드 배포 (Vercel)
1. [frontend/config.js](frontend/config.js)에 Supabase `Project URL`과 publishable key 입력 (공개되어도 안전한 키)
2. Vercel에 GitHub 저장소 연결, **Root Directory를 `frontend`로 설정**, Build Command 없음(정적 파일)
3. 배포 후 나온 URL을 폰 브라우저 홈 화면에 추가하면 앱처럼 쓸 수 있음

## 매물/경매 캡처 업로드 기능

네이버 매물 자동 수집은 봇 차단 때문에 포기했습니다 (아래 한계 참고). 대신 **대시보드 "업로드" 탭**(로그인 필요)에서
매물이나 법원경매 물건 캡처 이미지를 올리면, 다음 자동 실행(최대 30분 이내) 때 Claude Vision이 읽어서 자동으로 정리합니다.

- **매물 캡처** → `listings` 테이블에 추가되고, 같은 단지/구역의 최근 6개월 실거래가(또는 재개발구역은 총투자금)와 비교해서 급매 조건에 맞으면 텔레그램으로 알림
- **경매 캡처** → `auction_items` 테이블에 추가, **입찰기일 3일 전**에 텔레그램으로 자동 알림
- 업로드 시 단지/구역을 **지정하지 않으면 자동 분류**를 시도합니다 — Claude Vision이 읽은 캡처 상단의 단지/건물 이름을 각 target의 단지명(apt_name)/법정동명(dong_name)/매칭 키워드(match_keywords, 관리 탭에서 설정)와 비교해서 하나로 좁혀지면 자동 연결하고, 둘 이상 겹치거나 아예 못 찾으면 텔레그램으로 알려드립니다.
- 자동 분류가 실패한 캡처는 업로드 탭 "최근 업로드" 목록에 관심구역을 고르는 드롭다운이 뜨니 거기서 수동으로 연결하면 다음 자동 실행 때 반영됩니다.

## 알아둘 점 / 한계

- **네이버 매물 자동 수집은 포기했습니다.** `scraper/naver_client.py`에 코드는 남아있지만 실제로 호출하면 봇 차단(세션/쿠키/TLS 핑거프린팅 요구)에 막혀요. `main.py`에서도 더 이상 호출하지 않습니다 — 참고용으로만 남겨뒀어요.
- 국토부 실거래가 4개 API(아파트/연립다세대/단독다가구/상업업무용) 엔드포인트는 **실제 서비스키로 호출까지 검증 완료**했습니다.
- 요청 사이 간격을 두고 있지만, 캡처 업로드 방식이라 네이버 쪽 약관 리스크 자체가 거의 없어졌어요.
- 단지 추가/삭제는 "관리" 탭에서, 매물/경매 업로드는 "업로드" 탭에서 로그인 후 바로 할 수 있어요 (코드 수정 불필요).
