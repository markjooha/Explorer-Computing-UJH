"""
STEP: 단계적 과제 관리 캘린더

실행 방법
1. 레퍼런스 데이터 수집: python step_app.py --crawl
2. 웹앱 실행: streamlit run step_app.py

이 파일 하나 안에 BeautifulSoup 크롤링, CSV/JSON 저장, 추천 로직,
일정 분배, Streamlit 화면 구성을 모두 포함했습니다.
"""

# ============================================================
# 1. import
# ============================================================

import calendar
import csv
import hashlib
import html
import json
import re
import sys
import uuid
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup


# Streamlit과 matplotlib은 웹앱 실행 시점에 import합니다.
# 이렇게 하면 `python step_app.py --crawl` 실행 시 Streamlit 화면 코드가 실행되지 않습니다.
st = None
plt = None


# ============================================================
# 2. 상수 및 기본 설정
# ============================================================

APP_TITLE = "STEP: 단계적 과제 관리 캘린더"

BASE_DIR = Path(__file__).resolve().parent
REFERENCES_FILE = BASE_DIR / "references.csv"
SAMPLE_REFERENCES_FILE = BASE_DIR / "sample_references.csv"
TASKS_FILE = BASE_DIR / "tasks.json"
FIREBASE_COLLECTION = "step_users"

PAGE_HOME = "✅ STEP"
PAGE_PLAN = "🧭 할 일 계획하기"
PAGE_CALENDAR = "🗓️ 캘린더"
PAGE_REVIEW = "📊 나의 작업 패턴 분석"
PAGE_REFERENCE = "🔎 레퍼런스 탐색"
PAGE_OPTIONS = [PAGE_HOME, PAGE_PLAN, PAGE_CALENDAR, PAGE_REVIEW, PAGE_REFERENCE]

REFERENCE_COLUMNS = [
    "title",
    "category",
    "keywords",
    "process_steps",
    "source_url",
    "collected_at",
    "collection_method",
]

TASK_CATEGORIES = [
    "과제",
    "시험 공부",
    "개인 프로젝트",
    "팀 프로젝트",
    "디자인 과제",
    "포스터 디자인",
    "브랜딩",
    "UX/UI",
    "편집 디자인",
    "기타",
]

FRAMEWORK_STEPS = {
    "기본형: 조사 → 아이디어 → 제작 → 수정 → 제출": [
        "자료 조사",
        "아이디어 정리",
        "초안 제작",
        "수정 및 보완",
        "최종 제출",
    ],
    "디자인 프로세스형: 조사 → 분석 → 콘셉트 → 시안 → 피드백 → 최종화": [
        "자료 조사",
        "문제 및 요구 분석",
        "콘셉트 설정",
        "시안 제작",
        "피드백 반영",
        "최종 결과물 정리",
    ],
    "리서치형: 문제 정의 → 자료 조사 → 분석 → 정리 → 발표": [
        "문제 정의",
        "자료 조사",
        "자료 분석",
        "내용 정리",
        "발표 자료 제작",
    ],
    "팀 프로젝트형: 주제 선정 → 역할 분담 → 자료 조사 → 결과물 제작 → 발표": [
        "주제 선정",
        "역할 분담",
        "자료 조사",
        "결과물 제작",
        "발표 준비",
    ],
    "단일 과제: 과제 완료": [
        "과제 완료",
    ],
}

REFERENCE_CATEGORIES = [
    "시각 디자인",
    "그래픽 디자인",
    "타이포그래피",
    "일러스트레이션",
    "UX/UI 디자인",
    "브랜딩 디자인",
    "편집 디자인",
    "인포그래픽 디자인",
    "광고 디자인",
    "산업 디자인",
    "제품 디자인",
    "공간 디자인",
    "가구 디자인",
    "환경 디자인",
    "게임 디자인",
]

CRAWL_SOURCES = [
    {
        "url": "https://en.wikipedia.org/wiki/Design_thinking",
        "category": "디자인 과제",
        "fallback_steps": "문제 이해|사용자 관찰|아이디어 도출|프로토타입 제작|테스트|개선",
    },
    {
        "url": "https://en.wikipedia.org/wiki/User_experience_design",
        "category": "UX/UI",
        "fallback_steps": "문제 정의|사용자 조사|정보 구조 설계|와이어프레임 제작|프로토타입 제작|사용성 테스트",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Brand",
        "category": "브랜딩",
        "fallback_steps": "브랜드 조사|타깃 분석|키워드 도출|무드보드 제작|시안 제작|가이드 정리",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Poster",
        "category": "포스터 디자인",
        "fallback_steps": "주제 조사|레퍼런스 수집|콘셉트 설정|레이아웃 시안 제작|피드백 반영|최종 출력",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Project_management",
        "category": "팀 프로젝트",
        "fallback_steps": "목표 설정|역할 분담|일정 계획|자료 조사|결과물 제작|최종 발표",
    },
]

REFERENCE_PLATFORMS = [
    {
        "name": "Pinterest",
        "domain": "pinterest.com",
        "search_url": "https://www.pinterest.com/search/pins/?q={query}",
    },
    {
        "name": "Are.na",
        "domain": "are.na",
        "search_url": "https://www.are.na/search?q={query}",
    },
    {
        "name": "Behance",
        "domain": "behance.net",
        "search_url": "https://www.behance.net/search/projects?search={query}",
    },
]

REFERENCE_CATEGORY_TERMS = {
    "시각 디자인": "visual design reference",
    "그래픽 디자인": "graphic design reference",
    "타이포그래피": "typography design reference",
    "일러스트레이션": "illustration design reference",
    "UX/UI 디자인": "ux ui design reference",
    "브랜딩 디자인": "branding identity design reference",
    "편집 디자인": "editorial design layout reference",
    "인포그래픽 디자인": "infographic design reference",
    "광고 디자인": "advertising campaign design reference",
    "산업 디자인": "industrial design reference",
    "제품 디자인": "product design reference",
    "공간 디자인": "spatial design interior reference",
    "가구 디자인": "furniture design reference",
    "환경 디자인": "environmental design reference",
    "게임 디자인": "game design art reference",
}


# ============================================================
# 3. 샘플 레퍼런스 데이터 생성 함수
# ============================================================

def get_sample_reference_rows():
    """크롤링 실패 시 사용하는 기본 레퍼런스 데이터입니다."""
    collected_at = date.today().isoformat()
    return [
        {
            "title": "Poster Design Process",
            "category": "포스터 디자인",
            "keywords": "타이포그래피,레이아웃,컬러,전시,포스터",
            "process_steps": "주제 조사|레퍼런스 수집|콘셉트 설정|시안 제작|피드백 반영|최종 출력",
            "source_url": "https://example.com/poster-design-process",
            "collected_at": collected_at,
            "collection_method": "Fallback Sample",
        },
        {
            "title": "Brand Identity Project",
            "category": "브랜딩",
            "keywords": "로고,무드보드,아이덴티티,브랜드,가이드",
            "process_steps": "브랜드 조사|타깃 분석|키워드 도출|무드보드 제작|로고 스케치|시안 제작|최종 가이드 정리",
            "source_url": "https://example.com/brand-identity-project",
            "collected_at": collected_at,
            "collection_method": "Fallback Sample",
        },
        {
            "title": "UX Research Project",
            "category": "UX/UI",
            "keywords": "사용자 조사,페르소나,와이어프레임,프로토타입,테스트",
            "process_steps": "문제 정의|사용자 조사|페르소나 작성|와이어프레임 제작|프로토타입 제작|사용성 테스트|수정",
            "source_url": "https://example.com/ux-research-project",
            "collected_at": collected_at,
            "collection_method": "Fallback Sample",
        },
        {
            "title": "Editorial Design Project",
            "category": "편집 디자인",
            "keywords": "그리드,타이포그래피,인쇄,페이지 구성,편집",
            "process_steps": "자료 조사|콘텐츠 구조화|그리드 설정|시안 제작|편집 수정|인쇄 파일 정리",
            "source_url": "https://example.com/editorial-design-project",
            "collected_at": collected_at,
            "collection_method": "Fallback Sample",
        },
        {
            "title": "Team Project Process",
            "category": "팀 프로젝트",
            "keywords": "역할 분담,회의,자료 정리,발표,협업",
            "process_steps": "주제 선정|역할 분담|자료 조사|중간 점검|결과물 제작|발표 자료 정리|최종 발표",
            "source_url": "https://example.com/team-project-process",
            "collected_at": collected_at,
            "collection_method": "Fallback Sample",
        },
        {
            "title": "Study Plan Process",
            "category": "시험 공부",
            "keywords": "복습,요약,기출,암기,학습 계획",
            "process_steps": "범위 확인|자료 정리|핵심 개념 요약|문제 풀이|오답 정리|최종 복습",
            "source_url": "https://example.com/study-plan-process",
            "collected_at": collected_at,
            "collection_method": "Fallback Sample",
        },
        {
            "title": "General Assignment Workflow",
            "category": "과제",
            "keywords": "과제,리포트,자료 조사,작성,제출",
            "process_steps": "요구사항 확인|자료 조사|개요 작성|초안 작성|검토 및 수정|최종 제출",
            "source_url": "https://example.com/general-assignment-workflow",
            "collected_at": collected_at,
            "collection_method": "Fallback Sample",
        },
    ]


def write_reference_rows(rows, file_path):
    """레퍼런스 행 목록을 CSV로 저장합니다."""
    with open(file_path, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=REFERENCE_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in REFERENCE_COLUMNS})


def create_sample_references():
    """fallback 샘플 CSV를 생성하고 DataFrame으로 반환합니다."""
    rows = get_sample_reference_rows()
    write_reference_rows(rows, REFERENCES_FILE)
    write_reference_rows(rows, SAMPLE_REFERENCES_FILE)
    return pd.DataFrame(rows, columns=REFERENCE_COLUMNS)


# ============================================================
# 4. BeautifulSoup 데이터 수집 함수
# ============================================================

def clean_text(text):
    """HTML에서 추출한 텍스트를 검색과 저장에 적합하게 정리합니다."""
    return re.sub(r"\s+", " ", text or "").strip()


def guess_keywords_from_text(text, category):
    """본문에서 자주 등장하는 간단한 키워드를 추출합니다."""
    common_words = {
        "the",
        "and",
        "for",
        "that",
        "with",
        "from",
        "this",
        "into",
        "are",
        "was",
        "were",
        "design",
        "which",
        "their",
        "have",
        "has",
        "can",
        "such",
        "also",
        "use",
        "used",
    }

    words = re.findall(r"[A-Za-z가-힣]{3,}", text.lower())
    counts = {}
    for word in words:
        if word not in common_words:
            counts[word] = counts.get(word, 0) + 1

    top_words = [word for word, _ in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:8]]

    category_keywords = {
        "디자인 과제": ["디자인", "프로세스", "문제 정의"],
        "UX/UI": ["사용자", "경험", "프로토타입"],
        "브랜딩": ["브랜드", "아이덴티티", "로고"],
        "포스터 디자인": ["포스터", "시각 전달", "레이아웃"],
        "팀 프로젝트": ["협업", "일정", "관리"],
    }
    keywords = category_keywords.get(category, []) + top_words
    unique_keywords = []
    for keyword in keywords:
        if keyword and keyword not in unique_keywords:
            unique_keywords.append(keyword)
    return ",".join(unique_keywords[:10])


def crawl_single_reference(source):
    """하나의 공개 웹페이지에서 제목, 본문 일부, 키워드를 수집합니다."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; STEP-Student-Project/1.0; "
            "+https://example.com/student-project)"
        )
    }
    response = requests.get(source["url"], headers=headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    title_tag = soup.find("h1") or soup.find("title")
    if not title_tag:
        raise ValueError("페이지 제목을 찾을 수 없습니다.")

    title = clean_text(title_tag.get_text())
    paragraphs = [clean_text(p.get_text()) for p in soup.find_all("p")]
    paragraphs = [paragraph for paragraph in paragraphs if len(paragraph) >= 80]
    if not paragraphs:
        raise ValueError("분석할 본문 문단을 충분히 찾을 수 없습니다.")

    body_sample = " ".join(paragraphs[:4])
    keywords = guess_keywords_from_text(body_sample, source["category"])

    return {
        "title": title,
        "category": source["category"],
        "keywords": keywords,
        "process_steps": source["fallback_steps"],
        "source_url": source["url"],
        "collected_at": date.today().isoformat(),
        "collection_method": "BeautifulSoup",
    }


def crawl_references_with_beautifulsoup():
    """
    BeautifulSoup으로 레퍼런스 데이터를 수집해 references.csv를 생성합니다.

    네트워크 오류, HTML 구조 변경, 수집량 부족이 발생하면 fallback 샘플을 함께 사용합니다.
    이 함수는 `python step_app.py --crawl` 명령에서만 호출됩니다.
    """
    print("[STEP] BeautifulSoup 레퍼런스 수집을 시작합니다.")
    collected_rows = []

    for source in CRAWL_SOURCES:
        try:
            row = crawl_single_reference(source)
            collected_rows.append(row)
            print(f"[수집 성공] {row['title']} - {source['url']}")
        except requests.exceptions.RequestException as error:
            print(f"[네트워크 오류] {source['url']} - {error}")
        except Exception as error:
            print(f"[파싱 오류] {source['url']} - {error}")

    sample_rows = get_sample_reference_rows()
    if len(collected_rows) < 3:
        print("[안내] 수집 데이터가 부족해 fallback 샘플 데이터를 함께 사용합니다.")
        rows = collected_rows + sample_rows
    else:
        rows = collected_rows

    write_reference_rows(rows, REFERENCES_FILE)
    write_reference_rows(sample_rows, SAMPLE_REFERENCES_FILE)
    print(f"[완료] {REFERENCES_FILE.name} 파일에 {len(rows)}개 레퍼런스를 저장했습니다.")


# ============================================================
# 5. CSV / JSON 데이터 로드 및 저장 함수
# ============================================================

def load_references():
    """references.csv를 읽고, 없거나 깨져 있으면 샘플 데이터로 자동 생성합니다."""
    if not REFERENCES_FILE.exists():
        return create_sample_references()

    try:
        references_df = pd.read_csv(REFERENCES_FILE, encoding="utf-8-sig")
    except Exception:
        return create_sample_references()

    missing_columns = [column for column in REFERENCE_COLUMNS if column not in references_df.columns]
    if missing_columns or references_df.empty:
        return create_sample_references()

    return references_df[REFERENCE_COLUMNS].fillna("")


def get_firebase_service_account():
    """Streamlit Secrets에 저장된 Firebase 서비스 계정을 읽습니다."""
    if st is None:
        return None

    try:
        service_account = st.secrets.get("firebase_service_account")
    except Exception:
        return None

    if not service_account:
        return None

    return dict(service_account)


def is_firebase_enabled():
    """Firebase Secrets가 설정되어 있으면 Firestore 저장소를 사용합니다."""
    return get_firebase_service_account() is not None


def get_active_user_code():
    """사이드바에서 입력한 개인 접속 코드를 가져옵니다."""
    if st is None:
        return ""
    return st.session_state.get("user_code", "").strip()


def ensure_user_code():
    """Firebase 모드에서는 개인 접속 코드를 입력해야 데이터 페이지를 사용할 수 있습니다."""
    if not is_firebase_enabled():
        return True

    if get_active_user_code():
        return True

    st.info("사이드바에서 개인 접속 코드를 입력하면 나만의 캘린더 데이터를 불러오고 저장할 수 있습니다.")
    return False


def get_user_document_id(user_code):
    """개인 접속 코드를 Firestore 문서 ID로 바로 노출하지 않도록 해시합니다."""
    normalized_code = user_code.strip().lower()
    return hashlib.sha256(normalized_code.encode("utf-8")).hexdigest()


def get_firestore_client():
    """Firebase Admin SDK를 초기화하고 Firestore client를 반환합니다."""
    service_account = get_firebase_service_account()
    if not service_account:
        return None

    import firebase_admin
    from firebase_admin import credentials, firestore

    try:
        firebase_admin.get_app()
    except ValueError:
        cred = credentials.Certificate(service_account)
        firebase_admin.initialize_app(cred)

    return firestore.client()


def load_tasks_from_firestore(user_code):
    """Firestore에서 개인 접속 코드에 해당하는 작업 목록을 불러옵니다."""
    if not user_code:
        return []

    try:
        db = get_firestore_client()
        if db is None:
            return []
        document_id = get_user_document_id(user_code)
        snapshot = db.collection(FIREBASE_COLLECTION).document(document_id).get()
        if not snapshot.exists:
            return []
        data = snapshot.to_dict() or {}
        tasks = data.get("tasks", [])
        return tasks if isinstance(tasks, list) else []
    except Exception as error:
        if st is not None:
            st.error(f"Firebase에서 데이터를 불러오지 못했습니다: {error}")
        return []


def save_tasks_to_firestore(user_code, tasks):
    """Firestore에 개인 접속 코드별 작업 목록을 저장합니다."""
    if not user_code:
        if st is not None:
            st.warning("개인 접속 코드를 입력해야 캘린더 데이터를 저장할 수 있습니다.")
        return

    try:
        db = get_firestore_client()
        if db is None:
            return
        document_id = get_user_document_id(user_code)
        db.collection(FIREBASE_COLLECTION).document(document_id).set(
            {
                "user_code_hash": document_id,
                "tasks": tasks,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            merge=True,
        )
    except Exception as error:
        if st is not None:
            st.error(f"Firebase에 데이터를 저장하지 못했습니다: {error}")


def load_tasks():
    """작업 데이터를 불러옵니다. Firebase 설정이 있으면 Firestore를 우선 사용합니다."""
    if is_firebase_enabled():
        return load_tasks_from_firestore(get_active_user_code())

    if not TASKS_FILE.exists():
        save_tasks([])
        return []

    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as json_file:
            tasks = json.load(json_file)
        if isinstance(tasks, list):
            return tasks
    except Exception:
        pass

    save_tasks([])
    return []


def save_tasks(tasks):
    """작업 데이터를 저장합니다. Firebase 설정이 있으면 Firestore를 우선 사용합니다."""
    if is_firebase_enabled():
        save_tasks_to_firestore(get_active_user_code(), tasks)
        return

    with open(TASKS_FILE, "w", encoding="utf-8") as json_file:
        json.dump(tasks, json_file, ensure_ascii=False, indent=2)


# ============================================================
# 6. 작업 단계 추천 함수
# ============================================================

def split_steps(process_steps):
    """`|` 또는 줄바꿈으로 연결된 단계 문자열을 리스트로 변환합니다."""
    if isinstance(process_steps, list):
        raw_steps = process_steps
    else:
        raw_steps = re.split(r"\||\n", str(process_steps))
    return [step.strip() for step in raw_steps if step and step.strip()]


def get_default_steps(framework):
    """선택한 작업 모델에 맞는 기본 단계를 반환합니다."""
    return FRAMEWORK_STEPS.get(framework, FRAMEWORK_STEPS[list(FRAMEWORK_STEPS.keys())[0]])


def recommend_steps(title, category, framework, references_df):
    """
    references.csv의 category, title, keywords를 바탕으로 작업 단계를 추천합니다.
    복잡한 AI 추천 대신 교수님이 확인하기 쉬운 규칙 기반 로직을 사용합니다.
    """
    title = (title or "").lower()
    title_words = [word for word in re.findall(r"[A-Za-z가-힣0-9]+", title) if len(word) >= 2]

    best_row = None
    best_score = 0

    for _, row in references_df.iterrows():
        score = 0
        row_category = str(row.get("category", ""))
        row_title = str(row.get("title", "")).lower()
        row_keywords = str(row.get("keywords", "")).lower()

        if category and category == row_category:
            score += 5
        for word in title_words:
            if word in row_title:
                score += 2
            if word in row_keywords:
                score += 2

        if score > best_score:
            best_score = score
            best_row = row

    if best_row is not None and best_score > 0:
        return split_steps(best_row.get("process_steps", ""))

    return get_default_steps(framework)


# ============================================================
# 7. 자동 일정 분배 함수
# ============================================================

def schedule_steps(steps, deadline):
    """오늘부터 마감일까지 단계 수에 맞춰 날짜를 균등하게 배정합니다."""
    today = date.today()

    if isinstance(deadline, str):
        deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
    else:
        deadline_date = deadline

    cleaned_steps = [step.strip() for step in steps if step and step.strip()]
    if not cleaned_steps:
        return []

    if deadline_date <= today:
        scheduled_dates = [today for _ in cleaned_steps]
    elif len(cleaned_steps) == 1:
        scheduled_dates = [deadline_date]
    else:
        total_days = (deadline_date - today).days
        interval = total_days / (len(cleaned_steps) - 1)
        scheduled_dates = [
            today + timedelta(days=round(index * interval))
            for index in range(len(cleaned_steps))
        ]

    scheduled_steps = []
    for step_title, scheduled_date in zip(cleaned_steps, scheduled_dates):
        scheduled_steps.append(
            {
                "step_id": str(uuid.uuid4()),
                "step_title": step_title,
                "scheduled_date": scheduled_date.isoformat(),
                "completed": False,
                "completed_at": "",
                "estimated_hours": 1.5,
                "actual_hours": 0.0,
            }
        )
    return scheduled_steps


# ============================================================
# 8. 통계 및 회고 분석 함수
# ============================================================

def parse_date_safe(date_text):
    """YYYY-MM-DD 문자열을 date로 변환하고, 실패하면 None을 반환합니다."""
    try:
        if not date_text:
            return None
        return datetime.strptime(str(date_text), "%Y-%m-%d").date()
    except Exception:
        return None


def format_remaining_days(days_left):
    """남은 기간을 '3일' 또는 '45일 / 6주 3일' 형식으로 표시합니다."""
    if days_left is None:
        return "-"

    prefix = "-" if days_left < 0 else ""
    absolute_days = abs(int(days_left))

    if absolute_days >= 7:
        weeks = absolute_days // 7
        days = absolute_days % 7
        if days == 0:
            return f"{prefix}{absolute_days}일 / {prefix}{weeks}주"
        return f"{prefix}{absolute_days}일 / {prefix}{weeks}주 {days}일"

    return f"{prefix}{absolute_days}일"


def get_completion_delta(step):
    """
    완료일과 세부 단계 예정일의 차이를 계산합니다.
    음수는 예정일보다 일찍 완료, 양수는 늦게 완료를 의미합니다.
    """
    if not bool(step.get("completed", False)):
        return None

    scheduled_date = parse_date_safe(step.get("scheduled_date", ""))
    completed_date = parse_date_safe(step.get("completed_at", ""))

    # 기존 tasks.json에 completed_at이 없는 완료 단계는 예정일에 완료한 것으로 처리합니다.
    if completed_date is None:
        completed_date = scheduled_date

    if scheduled_date is None or completed_date is None:
        return None

    return (completed_date - scheduled_date).days


def format_completion_time(step):
    """완료 여부와 완료일을 바탕으로 사용자가 읽기 쉬운 완료 시간 문구를 만듭니다."""
    delta = get_completion_delta(step)
    if delta is None:
        return "-"
    if delta == 0:
        return "마감일에 완료"
    if delta < 0:
        return f"{abs(delta)}일 일찍 완료"
    return f"{delta}일 늦게 완료"


def get_completion_timing_label(delta):
    """회고 차트에 사용할 완료 시점 분류입니다."""
    if delta is None:
        return "미완료"
    if delta < 0:
        return "일찍 완료"
    if delta == 0:
        return "마감일에 완료"
    return "늦게 완료"


def format_average_completion_delta(average_delta):
    """평균 완료 시점을 마감일 기준 수치로 변환합니다."""
    if average_delta is None:
        return "-"
    return f"마감일 기준 {average_delta:+.1f}일"


def flatten_tasks(tasks):
    """중첩된 tasks.json 구조를 표와 통계에 쓰기 쉬운 행 목록으로 펼칩니다."""
    rows = []
    today = date.today()

    for task in tasks:
        deadline_text = task.get("deadline", "")
        deadline_date = parse_date_safe(deadline_text)
        days_left = (deadline_date - today).days if deadline_date else None

        for step in task.get("steps", []):
            scheduled_text = step.get("scheduled_date", "")
            scheduled_date = parse_date_safe(scheduled_text) or today

            completed = bool(step.get("completed", False))
            delayed = scheduled_date < today and not completed
            completion_delta = get_completion_delta(step)
            completed_at_text = step.get("completed_at", "") or (scheduled_text if completed else "")

            rows.append(
                {
                    "task_id": task.get("task_id", ""),
                    "step_id": step.get("step_id", ""),
                    "날짜": scheduled_text,
                    "과제명": task.get("title", ""),
                    "세부 단계": step.get("step_title", ""),
                    "중요도": task.get("priority", ""),
                    "작업 유형": task.get("category", ""),
                    "마감일": deadline_text,
                    "남은 일수": days_left,
                    "남은 기간": format_remaining_days(days_left),
                    "완료 여부": "완료" if completed else "미완료",
                    "completed": completed,
                    "완료일": completed_at_text,
                    "완료 시간": format_completion_time(step),
                    "완료 차이": completion_delta,
                    "완료 시점": get_completion_timing_label(completion_delta),
                    "지연 여부": delayed,
                    "예상 소요 시간": float(step.get("estimated_hours", 0) or 0),
                }
            )
    return rows


def calculate_review_metrics(tasks):
    """회고 페이지에서 사용할 핵심 지표를 계산합니다."""
    rows = flatten_tasks(tasks)
    total_tasks = len(tasks)
    total_steps = len(rows)
    completed_steps = sum(1 for row in rows if row["completed"])
    delayed_steps = sum(1 for row in rows if row["지연 여부"])
    completion_rate = (completed_steps / total_steps * 100) if total_steps else 0

    completion_deltas = [row["완료 차이"] for row in rows if row["완료 차이"] is not None]
    average_completion_delta = (
        sum(completion_deltas) / len(completion_deltas)
        if completion_deltas
        else None
    )

    timing_counts = {
        "일찍 완료": sum(1 for delta in completion_deltas if delta < 0),
        "마감일에 완료": sum(1 for delta in completion_deltas if delta == 0),
        "늦게 완료": sum(1 for delta in completion_deltas if delta > 0),
    }
    timing_rates = {}
    for label, count in timing_counts.items():
        timing_rates[label] = (count / len(completion_deltas) * 100) if completion_deltas else 0

    category_delay_counts = {}
    for row in rows:
        if row["지연 여부"]:
            category = row["작업 유형"] or "기타"
            category_delay_counts[category] = category_delay_counts.get(category, 0) + 1

    most_delayed_category = "-"
    if category_delay_counts:
        most_delayed_category = max(category_delay_counts, key=category_delay_counts.get)

    most_late_completed_step = "-"
    completed_rows = [row for row in rows if row["완료 차이"] is not None]
    if completed_rows:
        latest_row = max(completed_rows, key=lambda row: row["완료 차이"])
        if latest_row["완료 차이"] > 0:
            most_late_completed_step = (
                f"{latest_row['과제명']} - {latest_row['세부 단계']} "
                f"({latest_row['완료 차이']}일 늦게 완료)"
            )
        else:
            most_late_completed_step = "늦게 완료한 단계가 없습니다."

    return {
        "rows": rows,
        "total_tasks": total_tasks,
        "total_steps": total_steps,
        "completed_steps": completed_steps,
        "delayed_steps": delayed_steps,
        "completion_rate": completion_rate,
        "average_completion_delta": average_completion_delta,
        "average_completion_text": format_average_completion_delta(average_completion_delta),
        "timing_counts": timing_counts,
        "timing_rates": timing_rates,
        "most_delayed_category": most_delayed_category,
        "most_late_completed_step": most_late_completed_step,
    }


def find_task_and_step(tasks, task_id, step_id):
    """선택한 task_id와 step_id에 해당하는 작업과 단계를 찾습니다."""
    for task in tasks:
        if task.get("task_id") == task_id:
            for step in task.get("steps", []):
                if step.get("step_id") == step_id:
                    return task, step
    return None, None


def find_task_by_id(tasks, task_id):
    """task_id에 해당하는 프로젝트를 찾습니다."""
    for task in tasks:
        if task.get("task_id") == task_id:
            return task
    return None


def sync_completion_state_from_session(tasks):
    """
    세부 단계 체크박스 상태를 tasks.json에 즉시 반영합니다.
    Streamlit은 체크 변경 시 화면 전체를 다시 실행하므로, 화면을 그리기 전에 먼저 저장합니다.
    """
    changed = False
    today_text = date.today().isoformat()

    for task in tasks:
        for step in task.get("steps", []):
            step_id = step.get("step_id", "")
            progress_key = f"complete_{step_id}"
            today_key = f"today_complete_{step_id}"
            if today_key in st.session_state:
                new_completed = bool(st.session_state[today_key])
            elif progress_key in st.session_state:
                new_completed = bool(st.session_state[progress_key])
            else:
                continue

            old_completed = bool(step.get("completed", False))
            if new_completed == old_completed:
                continue

            step["completed"] = new_completed
            step["completed_at"] = today_text if new_completed else ""
            if progress_key in st.session_state:
                st.session_state[progress_key] = new_completed
            if today_key in st.session_state:
                st.session_state[today_key] = new_completed
            changed = True

    if changed:
        save_tasks(tasks)
    return changed


def get_category_color(category):
    """캘린더 배지에 사용할 작업 유형별 색상입니다."""
    colors = {
        "과제": "#DBEAFE",
        "시험 공부": "#FEF3C7",
        "개인 프로젝트": "#EDE9FE",
        "팀 프로젝트": "#DCFCE7",
        "디자인 과제": "#FCE7F3",
        "포스터 디자인": "#FFEDD5",
        "브랜딩": "#E0F2FE",
        "UX/UI": "#CCFBF1",
        "편집 디자인": "#F3E8FF",
        "기타": "#F1F5F9",
    }
    return colors.get(category, "#F1F5F9")


def get_priority_color(priority):
    """중요도 태그 색상입니다."""
    colors = {
        "낮음": "#DCFCE7",
        "보통": "#FEF3C7",
        "높음": "#FEE2E2",
    }
    return colors.get(priority, "#F1F5F9")


def get_status_color(completed):
    """완료 상태 태그 색상입니다."""
    return "#DCFCE7" if completed else "#F1F5F9"


def get_remaining_color(days_left):
    """남은 기간이 짧을수록 붉게 보이도록 색상을 정합니다."""
    if days_left is None:
        return "#F1F5F9"
    if days_left < 0:
        return "#991B1B"
    if days_left <= 1:
        return "#FEE2E2"
    if days_left <= 3:
        return "#FFEDD5"
    if days_left <= 7:
        return "#FEF3C7"
    return "#E5E7EB"


def get_completion_time_color(completion_time):
    """완료 시간 태그 색상입니다."""
    if completion_time == "-":
        return "#F1F5F9"
    if "일찍" in completion_time:
        return "#DBEAFE"
    if "늦게" in completion_time:
        return "#FEE2E2"
    return "#DCFCE7"


def get_priority_rank(priority):
    """정렬을 위한 중요도 순위입니다. 값이 작을수록 먼저 표시됩니다."""
    ranks = {
        "높음": 0,
        "보통": 1,
        "중간": 1,
        "낮음": 2,
    }
    return ranks.get(priority, 3)


def truncate_text(text, max_length=18):
    """캘린더 셀 안에서 너무 긴 텍스트를 짧게 줄입니다."""
    text = str(text or "")
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def render_calendar_grid(df, year, month):
    """월간 캘린더 형태로 세부 단계를 시각화합니다."""
    calendar.setfirstweekday(calendar.SUNDAY)
    weeks = calendar.monthcalendar(year, month)
    weekdays = ["일", "월", "화", "수", "목", "금", "토"]
    today_text = date.today().isoformat()

    style = """
    <style>
    .step-calendar-title {
        font-size: 1.4rem;
        font-weight: 800;
        margin: 0.6rem 0 0.8rem 0;
    }
    .step-calendar {
        display: grid;
        grid-template-columns: repeat(7, minmax(0, 1fr));
        border-top: 1px solid #CBD5E1;
        border-left: 1px solid #CBD5E1;
        background: #FFFFFF;
    }
    .step-weekday {
        padding: 0.55rem;
        border-right: 1px solid #CBD5E1;
        border-bottom: 1px solid #CBD5E1;
        text-align: center;
        font-weight: 700;
        background: #F8FAFC;
    }
    .step-day {
        min-height: 145px;
        padding: 0.55rem;
        border-right: 1px solid #CBD5E1;
        border-bottom: 1px solid #CBD5E1;
        vertical-align: top;
    }
    .step-day.empty {
        background: #F8FAFC;
    }
    .step-day.today {
        box-shadow: inset 0 0 0 2px #2563EB;
    }
    .step-day-number {
        font-size: 1.25rem;
        font-weight: 800;
        margin-bottom: 0.45rem;
    }
    .step-pill {
        display: block;
        padding: 0.25rem 0.35rem;
        margin-bottom: 0.28rem;
        border-radius: 0.45rem;
        font-size: 0.78rem;
        line-height: 1.15;
        color: #0F172A;
        border: 1px solid rgba(15, 23, 42, 0.08);
    }
    .step-pill.completed {
        opacity: 0.55;
        text-decoration: line-through;
    }
    .step-more {
        font-size: 0.75rem;
        color: #64748B;
        margin-top: 0.2rem;
    }
    .step-card {
        border: 1px solid #E2E8F0;
        border-radius: 0.8rem;
        padding: 0.85rem;
        margin-bottom: 0.65rem;
        background: #FFFFFF;
    }
    .step-card-title {
        font-weight: 800;
        margin-bottom: 0.25rem;
    }
    .step-card-meta {
        color: #475569;
        font-size: 0.9rem;
    }
    .step-small-badge {
        display: inline-block;
        border-radius: 999px;
        padding: 0.12rem 0.5rem;
        margin-right: 0.25rem;
        font-size: 0.78rem;
        background: #F1F5F9;
    }
    </style>
    """

    html_parts = [style, f"<div class='step-calendar-title'>{year}년 {month}월</div>", "<div class='step-calendar'>"]
    for weekday in weekdays:
        html_parts.append(f"<div class='step-weekday'>{weekday}</div>")

    for week in weeks:
        for day_number in week:
            if day_number == 0:
                html_parts.append("<div class='step-day empty'></div>")
                continue

            current_date = date(year, month, day_number).isoformat()
            css_class = "step-day today" if current_date == today_text else "step-day"
            day_rows = df[df["날짜"] == current_date].to_dict("records")
            html_parts.append(f"<div class='{css_class}'>")
            html_parts.append(f"<div class='step-day-number'>{day_number}</div>")

            for row in day_rows[:4]:
                color = get_category_color(row.get("작업 유형", ""))
                completed_class = " completed" if row.get("completed") else ""
                status_mark = "✓" if row.get("completed") else "○"
                task_title = html.escape(truncate_text(row.get("과제명", ""), 16))
                step_title = html.escape(truncate_text(row.get("세부 단계", ""), 18))
                html_parts.append(
                    f"<span class='step-pill{completed_class}' style='background:{color};'>"
                    f"{status_mark} {task_title}<br>{step_title}"
                    "</span>"
                )

            if len(day_rows) > 4:
                html_parts.append(f"<div class='step-more'>+{len(day_rows) - 4}개 더 있음</div>")

            html_parts.append("</div>")

    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_step_cards(rows, include_completion_time, allow_completion_check=False, show_date=True):
    """오늘의 할 일을 카드형 목록으로 표시합니다."""
    if not rows:
        st.info("표시할 작업이 없습니다.")
        return

    html_parts = [
        """
        <style>
        .step-card {
            border: 1px solid #E2E8F0;
            border-radius: 0.8rem;
            padding: 0.85rem;
            margin-bottom: 0.65rem;
            background: #FFFFFF;
        }
        .step-card-title {
            font-weight: 800;
            margin-bottom: 0.25rem;
        }
        .step-card-meta {
            color: #475569;
            font-size: 0.9rem;
        }
        .step-small-badge {
            display: inline-block;
            border-radius: 999px;
            padding: 0.12rem 0.5rem;
            margin-right: 0.25rem;
            margin-top: 0.35rem;
            font-size: 0.78rem;
            color: #0F172A;
        }
        </style>
        """
    ]
    for row in rows:
        color = get_category_color(row.get("작업 유형", ""))
        completed_text = "완료" if row.get("completed") else "미완료"
        task_title = html.escape(str(row.get("과제명", "")))
        step_title = html.escape(str(row.get("세부 단계", "")))
        date_text = html.escape(str(row.get("날짜", "")))
        priority = html.escape(str(row.get("중요도", "")))
        category = html.escape(str(row.get("작업 유형", "")))
        days_left = html.escape(str(row.get("남은 기간", "-")))
        priority_color = get_priority_color(row.get("중요도", ""))
        status_color = get_status_color(row.get("completed", False))
        remaining_color = get_remaining_color(row.get("남은 일수"))

        meta_items = [
            f"<span class='step-small-badge' style='background:{color};'>{category}</span>",
            f"<span class='step-small-badge' style='background:{priority_color};'>중요도 {priority}</span>",
            f"<span class='step-small-badge' style='background:{status_color};'>{completed_text}</span>",
            f"<span class='step-small-badge' style='background:{remaining_color};'>남은 기간 {days_left}</span>",
        ]
        if include_completion_time:
            completion_time = html.escape(str(row.get("완료 시간", "-")))
            completion_time_color = get_completion_time_color(row.get("완료 시간", "-"))
            meta_items.append(
                f"<span class='step-small-badge' style='background:{completion_time_color};'>완료 시간 {completion_time}</span>"
            )

        card_title = f"{date_text} · {task_title}" if show_date else task_title

        html_parts.append(
            "<div class='step-card'>"
            f"<div class='step-card-title'>{card_title}</div>"
            f"<div>{step_title}</div>"
            f"<div class='step-card-meta'>{''.join(meta_items)}</div>"
            "</div>"
        )

        if allow_completion_check:
            st.markdown("".join(html_parts), unsafe_allow_html=True)
            html_parts = []
            st.checkbox(
                "완료 표시",
                value=bool(row.get("completed", False)),
                key=f"today_complete_{row.get('step_id', '')}",
            )

    st.markdown("".join(html_parts), unsafe_allow_html=True)


def get_project_progress_summary(task):
    """미완료 프로젝트 카드에 표시할 현재 진행 단계와 단계 수를 계산합니다."""
    steps = task.get("steps", [])
    total_steps = len(steps)
    completed_steps = [step for step in steps if bool(step.get("completed", False))]
    completed_count = len(completed_steps)

    if total_steps == 0:
        return {
            "completed_count": 0,
            "total_steps": 0,
            "stage_number": 0,
            "current_stage": "세부 단계 없음",
            "completed_trail": "-",
        }

    next_step = None
    for step in steps:
        if not bool(step.get("completed", False)):
            next_step = step
            break

    if next_step is None:
        current_stage = "완료"
        stage_number = total_steps
    else:
        current_stage = f"{next_step.get('step_title', '')} 진행 중"
        stage_number = completed_count + 1

    completed_titles = [step.get("step_title", "") for step in completed_steps]
    completed_trail = " - ".join(completed_titles) if completed_titles else "아직 완료된 단계가 없습니다."

    return {
        "completed_count": completed_count,
        "total_steps": total_steps,
        "stage_number": stage_number,
        "current_stage": current_stage,
        "completed_trail": completed_trail,
    }


def render_project_summary_cards(tasks):
    """100% 완료되지 않은 프로젝트들을 프로젝트 단위 카드로 묶어 표시합니다."""
    incomplete_tasks = []
    today = date.today()

    for task in tasks:
        steps = task.get("steps", [])
        if not steps:
            continue
        completed_count = sum(1 for step in steps if bool(step.get("completed", False)))
        if completed_count < len(steps):
            incomplete_tasks.append(task)

    if not incomplete_tasks:
        st.success("아직 완료되지 않은 프로젝트가 없습니다.")
        return

    html_parts = []
    for task in incomplete_tasks:
        summary = get_project_progress_summary(task)
        deadline_date = parse_date_safe(task.get("deadline", ""))
        days_left = (deadline_date - today).days if deadline_date else None
        remaining_text = format_remaining_days(days_left)
        progress_percent = (
            summary["completed_count"] / summary["total_steps"] * 100
            if summary["total_steps"]
            else 0
        )

        category = html.escape(str(task.get("category", "")))
        priority = html.escape(str(task.get("priority", "")))
        title = html.escape(str(task.get("title", "")))
        current_stage = html.escape(summary["current_stage"])
        completed_trail = html.escape(summary["completed_trail"])
        step_count_text = f"{summary['stage_number']}/{summary['total_steps']}단계"

        category_color = get_category_color(task.get("category", ""))
        priority_color = get_priority_color(task.get("priority", ""))
        remaining_color = get_remaining_color(days_left)

        html_parts.append(
            "<div class='step-card'>"
            f"<div class='step-card-title'>{title}</div>"
            f"<div style='font-size:1.05rem;font-weight:800;margin-bottom:0.25rem;'>{current_stage}</div>"
            f"<div style='color:#475569;margin-bottom:0.5rem;'>현재까지 완료: {completed_trail}</div>"
            "<div style='width:100%;height:0.55rem;background:#E2E8F0;border-radius:999px;overflow:hidden;margin-bottom:0.5rem;'>"
            f"<div style='height:100%;width:{progress_percent:.1f}%;background:#2563EB;'></div>"
            "</div>"
            "<div class='step-card-meta'>"
            f"<span class='step-small-badge' style='background:{category_color};'>{category}</span>"
            f"<span class='step-small-badge' style='background:{priority_color};'>중요도 {priority}</span>"
            f"<span class='step-small-badge'>{step_count_text}</span>"
            f"<span class='step-small-badge' style='background:{remaining_color};'>남은 기간 {remaining_text}</span>"
            f"<span class='step-small-badge'>마감일 {html.escape(str(task.get('deadline', '-')))}</span>"
            "</div>"
            "</div>"
        )

    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_project_progress_controls(tasks):
    """프로젝트 단위로 세부 단계 완료 여부를 체크하는 영역입니다."""
    st.subheader("프로젝트 진척도 확인")

    task_options = {
        f"{task.get('title', '제목 없음')} · 마감일 {task.get('deadline', '-')} · {task.get('task_id', '')[:8]}": task.get("task_id", "")
        for task in tasks
    }
    selected_label = st.selectbox("프로젝트 진척도 확인", list(task_options.keys()))
    selected_task = find_task_by_id(tasks, task_options[selected_label])

    if selected_task is None:
        st.warning("선택한 과제를 찾을 수 없습니다.")
        return

    steps = selected_task.get("steps", [])
    completed_count = sum(1 for step in steps if bool(step.get("completed", False)))
    progress = completed_count / len(steps) if steps else 0
    st.progress(progress)
    st.write(f"**{selected_task.get('title', '')}** 진행률: {completed_count}/{len(steps)} 단계 완료 ({progress * 100:.1f}%)")

    for step in steps:
        label = f"{step.get('scheduled_date', '-')} · {step.get('step_title', '')}"
        st.checkbox(
            label,
            value=bool(step.get("completed", False)),
            key=f"complete_{step.get('step_id', '')}",
            help="체크하면 완료일이 오늘 날짜로 자동 기록됩니다.",
        )


def build_design_reference_query(category, keyword):
    """카테고리와 키워드를 조합해 디자인 레퍼런스 검색어를 만듭니다."""
    parts = []
    if category != "전체":
        parts.append(REFERENCE_CATEGORY_TERMS.get(category, category))
    if keyword.strip():
        parts.append(keyword.strip())
    if not parts:
        parts.append("graphic design reference")
    parts.append("design inspiration")
    return " ".join(parts)


def get_platform_search_links(query):
    """Pinterest, Are.na, Behance 검색 링크를 생성합니다."""
    encoded_query = urllib.parse.quote_plus(query)
    links = []
    for platform in REFERENCE_PLATFORMS:
        links.append(
            {
                "name": platform["name"],
                "domain": platform["domain"],
                "url": platform["search_url"].format(query=encoded_query),
            }
        )
    return links


def fetch_duckduckgo_image_results(query, max_results=12):
    """
    별도 API 키 없이 이미지 검색 결과 일부를 가져옵니다.
    실패해도 레퍼런스 페이지는 플랫폼 검색 링크를 통해 계속 사용할 수 있습니다.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
        )
    }
    search_url = "https://duckduckgo.com/"
    params = {"q": query, "iax": "images", "ia": "images"}

    response = requests.get(search_url, params=params, headers=headers, timeout=8)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    page_text = str(soup)

    vqd_match = re.search(r"vqd=['\"]([^'\"]+)['\"]", page_text)
    if not vqd_match:
        vqd_match = re.search(r"vqd=([^&]+)&", page_text)
    if not vqd_match:
        return []

    image_params = {
        "l": "us-en",
        "o": "json",
        "q": query,
        "vqd": vqd_match.group(1),
        "f": ",,,",
        "p": "1",
    }
    image_response = requests.get("https://duckduckgo.com/i.js", params=image_params, headers=headers, timeout=8)
    image_response.raise_for_status()
    data = image_response.json()

    results = []
    for item in data.get("results", [])[:max_results]:
        image_url = item.get("image")
        page_url = item.get("url")
        if not image_url:
            continue
        results.append(
            {
                "title": item.get("title", "Design reference"),
                "image_url": image_url,
                "page_url": page_url or image_url,
                "source": item.get("source", ""),
            }
        )
    return results


def fetch_platform_image_references(query, per_platform=10):
    """플랫폼별 검색어로 이미지 결과를 모아 반환합니다."""
    all_results = []
    for platform in REFERENCE_PLATFORMS:
        platform_query = f"{query} site:{platform['domain']}"
        try:
            results = fetch_duckduckgo_image_results(platform_query, max_results=per_platform)
        except Exception:
            results = []

        for result in results:
            result["platform"] = platform["name"]
            all_results.append(result)

    return all_results


def render_platform_link_cards(links):
    """각 플랫폼 검색 결과로 이동하는 링크 카드를 표시합니다."""
    html_parts = [
        """
        <style>
        .reference-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 0.85rem;
            margin: 0.8rem 0 1.2rem 0;
        }
        .reference-link-card {
            border: 1px solid #E2E8F0;
            border-radius: 0.9rem;
            padding: 1rem;
            background: linear-gradient(135deg, #F8FAFC, #EEF2FF);
        }
        .reference-link-card a {
            color: #1D4ED8;
            font-weight: 800;
            text-decoration: none;
        }
        .reference-image-card {
            border: 1px solid #E2E8F0;
            border-radius: 0.9rem;
            overflow: hidden;
            background: #FFFFFF;
        }
        .reference-image-card img {
            width: 100%;
            height: 210px;
            object-fit: cover;
            display: block;
        }
        .reference-image-body {
            padding: 0.75rem;
        }
        .reference-platform {
            display: inline-block;
            background: #EEF2FF;
            border-radius: 999px;
            padding: 0.12rem 0.5rem;
            font-size: 0.78rem;
            margin-bottom: 0.35rem;
        }
        </style>
        """,
        "<div class='reference-grid'>",
    ]

    for link in links:
        name = html.escape(link["name"])
        url = html.escape(link["url"])
        domain = html.escape(link["domain"])
        html_parts.append(
            "<div class='reference-link-card'>"
            f"<div style='font-size:1.1rem;font-weight:900;margin-bottom:0.35rem;'>{name}</div>"
            f"<div style='color:#475569;margin-bottom:0.8rem;'>{domain} 검색 결과</div>"
            f"<a href='{url}' target='_blank'>검색 결과 열기</a>"
            "</div>"
        )

    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_image_reference_cards(results):
    """이미지 검색 결과를 카드 그리드로 표시합니다."""
    if not results:
        st.warning("이미지 미리보기를 가져오지 못했습니다. 위의 플랫폼 검색 링크로 직접 확인해주세요.")
        return

    html_parts = ["<div class='reference-grid'>"]
    for result in results:
        title = html.escape(truncate_text(result.get("title", "Design reference"), 54))
        image_url = html.escape(result.get("image_url", ""))
        page_url = html.escape(result.get("page_url", image_url))
        platform = html.escape(result.get("platform", "Reference"))
        source = html.escape(result.get("source", ""))
        html_parts.append(
            "<div class='reference-image-card'>"
            f"<a href='{page_url}' target='_blank'><img src='{image_url}' alt='{title}'></a>"
            "<div class='reference-image-body'>"
            f"<div class='reference-platform'>{platform}</div>"
            f"<div style='font-weight:800;line-height:1.25;margin-bottom:0.25rem;'>{title}</div>"
            f"<div style='font-size:0.82rem;color:#64748B;'>{source}</div>"
            "</div>"
            "</div>"
        )
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


# ============================================================
# 9. Streamlit 페이지 함수
# ============================================================

def render_home_page():
    """STEP 앱의 목적과 사용 흐름을 소개하는 인포 페이지입니다."""
    st.header(PAGE_HOME)
    st.write(
        "STEP은 막연한 프로젝트를 작은 단계로 나누고, 오늘 해야 할 일을 캘린더에서 확인하며, "
        "완료 기록을 바탕으로 작업 패턴을 돌아볼 수 있게 돕는 단계적 과제 관리 캘린더입니다."
    )

    st.subheader("이 앱의 목표")
    st.markdown(
        """
        - 큰 프로젝트를 세부 목표에 따라 단계별로 분할합니다.
        - 마감일까지 남은 기간에 맞추어 각 단계를 자동으로 캘린더에 배치합니다.
        - 오늘의 할 일을 리스트 형태로 확인하고, 완료 여부를 표시할 수 있습니다.
        - 과제 완료 기록을 바탕으로 자신의 작업 일정 패턴을 분석합니다.
        - 디자인 작업 과정에서 참고할 수 있는 이미지 레퍼런스 검색 결과를 제공합니다.
        """
    )

    st.subheader("기본 사용 로드맵")
    st.markdown(
        """
        1. **할 일 계획하기**에서 프로젝트 제목, 마감일, 중요도, 작업 유형을 입력합니다.
        2. 추천된 세부 단계를 확인하고 필요에 따라 수정합니다.
        3. **할 일 저장**을 누르면 프로젝트가 캘린더에 추가됩니다.
        4. **캘린더**에서 오늘의 할 일을 확인하고 완료한 항목을 체크합니다.
        5. **전체 일정표**에서 현재 진행 중인 프로젝트의 현재 단계를 확인합니다.
        6. 모든 세부 단계를 완료해 프로젝트를 마무리합니다.
        7. **나의 작업 패턴 분석**에서 완료 속도와 지연 경향을 확인합니다.
        """
    )

    st.subheader("페이지별 역할")
    st.markdown(
        f"""
        - **{PAGE_PLAN}**: 프로젝트를 만들고, 작업 유형과 프레임워크에 맞는 세부 단계를 추천받습니다.
        - **{PAGE_CALENDAR}**: 오늘의 할 일, 월간 캘린더, 진행 중인 프로젝트를 한 화면에서 확인합니다.
        - **{PAGE_REVIEW}**: 완료율, 지연 단계, 마감일 기준 완료 시점을 분석합니다.
        - **{PAGE_REFERENCE}**: 디자인 카테고리와 키워드로 이미지 레퍼런스 검색 링크와 미리보기를 확인합니다.
        """
    )

    if st.button("캘린더로 시작하기", type="primary"):
        st.session_state["pending_page"] = PAGE_CALENDAR
        st.rerun()


def render_plan_page():
    """페이지 1: 새 할 일을 만들고 추천 단계를 수정한 뒤 저장합니다."""
    st.header(PAGE_PLAN)
    st.write("프로젝트를 추가하면 작업 유형과 관련 프레임워크를 바탕으로 세부 단계를 추천합니다.")

    if not ensure_user_code():
        return

    references_df = load_references()

    title = st.text_input("작업 제목", placeholder="예: 전시 포스터 디자인")
    description = st.text_area("작업 설명", placeholder="수업 과제 내용이나 목표를 간단히 적어주세요.")

    col1, col2 = st.columns(2)
    with col1:
        deadline = st.date_input("마감일", value=date.today() + timedelta(days=7))
        priority = st.selectbox("중요도", ["낮음", "보통", "높음"], index=1)
    with col2:
        category = st.selectbox("작업 유형", TASK_CATEGORIES)
        framework = st.selectbox("작업 모델 또는 프레임워크", list(FRAMEWORK_STEPS.keys()))

    recommended = recommend_steps(title, category, framework, references_df)
    recommended_text = "\n".join(recommended)
    previous_auto_text = st.session_state.get("last_auto_steps_text", "")

    if "plan_steps_text" not in st.session_state or st.session_state["plan_steps_text"] == previous_auto_text:
        st.session_state["plan_steps_text"] = recommended_text
        st.session_state["last_auto_steps_text"] = recommended_text

    if st.button("세부 단계 초기화"):
        st.session_state["plan_steps_text"] = recommended_text
        st.session_state["last_auto_steps_text"] = recommended_text

    steps_text = st.text_area(
        "추천 세부 단계 (줄바꿈으로 단계 구분)",
        key="plan_steps_text",
        height=180,
        help="한 줄에 하나의 세부 단계를 적어주세요. 저장 전에 자유롭게 수정할 수 있습니다.",
    )

    if st.button("할 일 저장", type="primary"):
        if not title.strip():
            st.warning("작업 제목을 입력해주세요.")
            return

        steps = split_steps(steps_text)
        if not steps:
            st.warning("세부 단계를 하나 이상 입력해주세요.")
            return

        if deadline < date.today():
            st.warning("마감일이 오늘보다 빠릅니다. 모든 세부 단계가 오늘 날짜로 배정됩니다.")

        tasks = load_tasks()
        new_task = {
            "task_id": str(uuid.uuid4()),
            "title": title.strip(),
            "description": description.strip(),
            "deadline": deadline.isoformat(),
            "priority": priority,
            "category": category,
            "framework": framework,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "steps": schedule_steps(steps, deadline),
        }
        tasks.append(new_task)
        save_tasks(tasks)
        st.session_state["calendar_flash"] = "할 일이 저장되었습니다. 날짜별 일정과 프로젝트 진척도를 확인해보세요."
        st.session_state["pending_page"] = PAGE_CALENDAR
        st.rerun()


def render_calendar_page():
    """페이지 2: 캘린더형 일정 확인과 프로젝트 단위 완료 체크를 제공합니다."""
    st.header(PAGE_CALENDAR)
    st.write("저장된 세부 단계를 오늘의 할 일, 월간 캘린더, 프로젝트 요약으로 확인하고 진척도를 관리합니다.")

    if not ensure_user_code():
        return

    if "calendar_flash" in st.session_state:
        st.success(st.session_state.pop("calendar_flash"))

    tasks = load_tasks()
    if sync_completion_state_from_session(tasks):
        st.toast("진척도가 자동 저장되었습니다.")

    rows = flatten_tasks(tasks)

    if not rows:
        st.info(f"아직 저장된 할 일이 없습니다. 먼저 '{PAGE_PLAN}' 페이지에서 새 과제를 만들어주세요.")
        return

    df = pd.DataFrame(rows).sort_values(["날짜", "과제명", "세부 단계"])

    total_steps = len(df)
    completed_steps = int(df["completed"].sum())
    progress = completed_steps / total_steps if total_steps else 0
    st.progress(progress)
    st.write(f"전체 진행률: **{completed_steps}/{total_steps} 단계 완료 ({progress * 100:.1f}%)**")

    today_text = date.today().isoformat()
    today_df = df[df["날짜"] == today_text].copy()
    st.subheader("오늘의 할 일")
    if today_df.empty:
        st.info("오늘로 배정된 작업이 없습니다.")
    else:
        today_df["priority_rank"] = today_df["중요도"].apply(get_priority_rank)
        today_df = today_df.sort_values(["남은 일수", "priority_rank", "과제명", "세부 단계"])
        render_step_cards(
            today_df.to_dict("records"),
            include_completion_time=True,
            allow_completion_check=True,
            show_date=False,
        )

    if st.button("할 일 추가하기", type="primary"):
        st.session_state["pending_page"] = PAGE_PLAN
        st.rerun()

    month_candidates = set()
    for row in rows:
        scheduled_date = parse_date_safe(row.get("날짜", ""))
        if scheduled_date:
            month_candidates.add((scheduled_date.year, scheduled_date.month))
    month_candidates.add((date.today().year, date.today().month))
    month_options = sorted(month_candidates)
    month_labels = [f"{year}년 {month}월" for year, month in month_options]
    current_month = (date.today().year, date.today().month)
    default_month_index = month_options.index(current_month) if current_month in month_options else 0
    selected_month_label = st.selectbox("표시할 월", month_labels, index=default_month_index)
    selected_year, selected_month = month_options[month_labels.index(selected_month_label)]

    st.subheader("월간 캘린더")
    render_calendar_grid(df, selected_year, selected_month)

    st.subheader("전체 일정표")
    st.caption("현재 진행 중인 전체 프로젝트입니다.")
    render_project_summary_cards(tasks)

    render_project_progress_controls(tasks)


def render_review_page():
    """페이지 3: 누적 작업 기록을 지표와 그래프로 분석합니다."""
    st.components.v1.html(
        "<script>window.parent.scrollTo({top: 0, left: 0, behavior: 'instant'});</script>",
        height=0,
    )
    st.header(PAGE_REVIEW)
    st.write("완료율, 지연 단계, 예정일 대비 완료 시점을 바탕으로 나의 작업 패턴을 분석합니다.")

    if not ensure_user_code():
        return

    tasks = load_tasks()
    metrics = calculate_review_metrics(tasks)
    rows = metrics["rows"]

    if not rows:
        st.info("분석할 작업 기록이 없습니다. 먼저 할 일을 저장하고 진행 상황을 기록해주세요.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("전체 프로젝트 수", metrics["total_tasks"])
    col2.metric("전체 세부 단계 수", metrics["total_steps"])
    col3.metric("완료된 단계 수", metrics["completed_steps"])
    col4.metric("전체 완료율", f"{metrics['completion_rate']:.1f}%")

    col5, col6, col7 = st.columns(3)
    col5.metric("지연된 단계 수", metrics["delayed_steps"])
    col6.metric("평균 완료 시간", metrics["average_completion_text"])
    col7.metric("가장 많이 지연되는 작업 유형", metrics["most_delayed_category"])

    rate_col1, rate_col2, rate_col3 = st.columns(3)
    rate_col1.metric("일찍 완료한 작업", f"{metrics['timing_rates']['일찍 완료']:.1f}%")
    rate_col2.metric("마감일에 완료한 작업", f"{metrics['timing_rates']['마감일에 완료']:.1f}%")
    rate_col3.metric("늦게 완료한 작업", f"{metrics['timing_rates']['늦게 완료']:.1f}%")

    st.write(f"가장 늦게 완료한 작업 단계: **{metrics['most_late_completed_step']}**")

    task_df = pd.DataFrame(tasks)
    step_df = pd.DataFrame(rows)

    st.subheader("작업 유형별 / 중요도별 프로젝트 수")
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        category_counts = task_df["category"].value_counts() if "category" in task_df else pd.Series(dtype=int)
        fig, ax = plt.subplots(figsize=(6, 4))
        category_counts.plot(kind="bar", ax=ax, color="#4C78A8")
        ax.set_xlabel("작업 유형")
        ax.set_ylabel("프로젝트 수")
        ax.set_title("작업 유형별 프로젝트 수")
        ax.tick_params(axis="x", rotation=45)
        st.pyplot(fig)

    with chart_col2:
        priority_counts = task_df["priority"].value_counts() if "priority" in task_df else pd.Series(dtype=int)
        fig, ax = plt.subplots(figsize=(6, 4))
        priority_counts.plot(kind="bar", ax=ax, color="#F58518")
        ax.set_xlabel("중요도")
        ax.set_ylabel("프로젝트 수")
        ax.set_title("중요도별 프로젝트 수")
        ax.tick_params(axis="x", rotation=0)
        st.pyplot(fig)

    st.subheader("완료 상태와 날짜별 완료 기록")
    chart_col3, chart_col4 = st.columns(2)

    with chart_col3:
        completion_counts = step_df["완료 여부"].value_counts()
        fig, ax = plt.subplots(figsize=(5, 4))
        completion_counts.plot(kind="pie", autopct="%1.1f%%", ax=ax, colors=["#54A24B", "#E45756"])
        ax.set_ylabel("")
        ax.set_title("완료/미완료 단계 비율")
        st.pyplot(fig)

    with chart_col4:
        completed_steps_df = step_df[(step_df["completed"]) & (step_df["완료일"].astype(str) != "")]
        completed_by_date = completed_steps_df.groupby("완료일").size()
        fig, ax = plt.subplots(figsize=(6, 4))
        if completed_by_date.empty:
            ax.text(0.5, 0.5, "완료된 작업이 아직 없습니다.", ha="center", va="center")
            ax.set_axis_off()
        else:
            completed_by_date.plot(kind="bar", ax=ax, color="#72B7B2")
            ax.set_xlabel("완료일")
            ax.set_ylabel("완료 단계 수")
            ax.set_title("날짜별 완료한 작업 수")
            ax.tick_params(axis="x", rotation=45)
        st.pyplot(fig)

    st.subheader("완료 시간 비율")
    timing_series = pd.Series(metrics["timing_counts"])
    fig, ax = plt.subplots(figsize=(6, 4))
    if timing_series.sum() == 0:
        ax.text(0.5, 0.5, "완료된 작업이 아직 없습니다.", ha="center", va="center")
        ax.set_axis_off()
    else:
        timing_series.plot(kind="bar", ax=ax, color=["#54A24B", "#4C78A8", "#E45756"])
        ax.set_xlabel("완료 시점")
        ax.set_ylabel("단계 수")
        ax.set_title("마감일 대비 완료 시간")
        ax.tick_params(axis="x", rotation=0)
    st.pyplot(fig)


def render_reference_page():
    """페이지 4: 디자인 이미지 레퍼런스를 플랫폼별로 탐색합니다."""
    st.header(PAGE_REFERENCE)

    col1, col2 = st.columns(2)
    with col1:
        categories = ["전체"] + REFERENCE_CATEGORIES
        selected_category = st.selectbox("카테고리 필터", categories)
    with col2:
        keyword = st.text_input("키워드 검색", placeholder="예: 타이포그래피, 패키지, 포트폴리오")

    query = build_design_reference_query(selected_category, keyword)
    st.caption(f"검색어: {query}")

    st.subheader("플랫폼별 검색")
    platform_links = get_platform_search_links(query)
    render_platform_link_cards(platform_links)

    st.subheader("이미지 레퍼런스 미리보기")
    cache_key = f"{selected_category}|{keyword.strip()}"
    if "image_reference_cache" not in st.session_state:
        st.session_state["image_reference_cache"] = {}

    if st.button("이미지 레퍼런스 검색", type="primary"):
        with st.spinner("Pinterest, Are.na, Behance 관련 이미지 결과를 찾는 중입니다."):
            st.session_state["image_reference_cache"][cache_key] = fetch_platform_image_references(query)

    if cache_key in st.session_state["image_reference_cache"]:
        render_image_reference_cards(st.session_state["image_reference_cache"][cache_key])
    else:
        st.info("검색 버튼을 누르면 선택한 카테고리와 키워드에 맞는 이미지 미리보기를 모아 보여줍니다.")


def render_sidebar():
    """사이드바 페이지 이동 UI입니다."""
    st.sidebar.title("STEP")
    st.sidebar.caption("단계적으로 계획하고, 완료하고, 회고하기")

    if is_firebase_enabled():
        st.sidebar.text_input(
            "개인 접속 코드",
            key="user_code",
            type="password",
            help="같은 코드를 다시 입력하면 이전 캘린더 데이터를 불러옵니다.",
        )
        if get_active_user_code():
            st.sidebar.success("Firebase 저장소 연결됨")
        else:
            st.sidebar.warning("개인 접속 코드를 입력해주세요.")
    else:
        st.sidebar.info("로컬 tasks.json 저장 모드")

    if "pending_page" in st.session_state:
        st.session_state["page_radio"] = st.session_state.pop("pending_page")
    if st.session_state.get("page_radio") not in PAGE_OPTIONS:
        st.session_state["page_radio"] = PAGE_CALENDAR

    return st.sidebar.radio("페이지 이동", PAGE_OPTIONS, key="page_radio")


def run_streamlit_app():
    """Streamlit 앱 실행부입니다."""
    global st, plt
    import streamlit as streamlit

    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
    except Exception:
        get_script_run_ctx = None

    if get_script_run_ctx is not None and get_script_run_ctx(suppress_warning=True) is None:
        print("\n[STEP 실행 안내]")
        print("이 앱은 일반 python 명령이 아니라 Streamlit 명령으로 실행해야 합니다.")
        print("현재 폴더에서 아래 명령을 입력하세요:\n")
        print("    streamlit run step_app.py\n")
        print("만약 'streamlit' 명령을 찾을 수 없다고 나오면 아래처럼 실행하세요:\n")
        print("    python -m streamlit run step_app.py\n")
        print("레퍼런스 크롤링은 다음 명령으로 따로 실행합니다:\n")
        print("    python step_app.py --crawl\n")
        return

    import matplotlib.pyplot as matplotlib_pyplot

    st = streamlit
    plt = matplotlib_pyplot

    st.set_page_config(page_title=APP_TITLE, layout="wide")
    plt.rcParams["font.family"] = ["AppleGothic", "Malgun Gothic", "NanumGothic", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    st.title(APP_TITLE)

    references_created = not REFERENCES_FILE.exists()
    tasks_created = not TASKS_FILE.exists()
    load_references()
    load_tasks()

    if references_created:
        st.warning("references.csv가 없어 fallback 샘플 데이터로 자동 생성했습니다. 실제 수집은 `python step_app.py --crawl` 명령으로 실행할 수 있습니다.")
    if tasks_created:
        st.info("tasks.json이 없어 빈 작업 목록 파일을 자동 생성했습니다.")

    page = render_sidebar()
    if page == PAGE_HOME:
        render_home_page()
    elif page == PAGE_PLAN:
        render_plan_page()
    elif page == PAGE_CALENDAR:
        render_calendar_page()
    elif page == PAGE_REVIEW:
        render_review_page()
    elif page == PAGE_REFERENCE:
        render_reference_page()


# ============================================================
# 10. main 실행부
# ============================================================

def main():
    """명령행 인자에 따라 크롤링 모드 또는 Streamlit 앱 모드로 실행합니다."""
    if "--crawl" in sys.argv:
        crawl_references_with_beautifulsoup()
        return

    run_streamlit_app()


if __name__ == "__main__":
    main()
