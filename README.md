# Kunminzzang — portfolio

사이트는 `content/`(글·이미지)와 `src/`(디자인 코드)로 나뉘어 있어요.
`main`에 올리면 GitHub Actions가 `build.py`를 돌려서 자동으로 배포합니다.

## 프로젝트 추가하기
1. `content/projects/` 안에 `번호-영문이름` 폴더를 만듭니다. 번호가 클수록 Work 맨 위에 와요. 예: `077-new-brand`
2. 폴더에 넣을 것
   - `project.md` — 아래 형식
   - `cover.jpg` — 썸네일 (Work에선 정사각형으로, Featured에선 1:1.1로 잘려 보여요). 움직이는 썸네일은 `cover.gif` 또는 `cover.mp4`도 함께
   - `01.jpg`, `02.png`, `03.gif` … — 상세 이미지. 파일 이름 순서대로 나와요. 원본 그대로 넣어도 자동으로 웹용(최대 2000px, WebP)으로 변환돼요. GIF는 영상으로 바뀝니다.
3. 커밋하고 올리면 1~2분 뒤 반영돼요.

```md
---
title: New Brand
year: 2026
tags: [Branding, Package]
client: 클라이언트명
role: 브랜드 아이덴티티, 패키지 디자인
period: 2026.01 – 2026.03
featured:            # 홈 Featured work에 올릴 때만
  order: 2           # 몇 번째 카드인지
  meta: 2026 · Brand Identity
  text: + 버튼을 누르면 나오는 한두 문장 소개
  color: hsl(30 45% 97.4%)   # 설명 칸 배경 미색
---
상세페이지 Overview에 들어갈 소개글. 빈 줄로 문단을 나눠요.
```

- `work: false` 를 넣으면 Work 목록에는 안 나오고 Featured에만 나와요 (예: `900-dingbat-font`). 이때 `links:`로 외부 링크를 달아요.

## 홈 문구 고치기
`src/index.html`에서 소개 문구, Information, Experience, Projects, Socials를 직접 고치면 돼요.

## 로컬에서 미리 보기
```
pip install pillow pyyaml   # ffmpeg도 필요
python3 build.py
cd dist && python3 -m http.server
```
