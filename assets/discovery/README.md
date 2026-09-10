# 메뉴 탐색 사진

- `aglio-olio.jpg`: OpenAI 내장 ImageGen으로 생성한 알리오 올리오 참고 사진. 특정 영상이나 요리사의 완성 사진이 아니다.
- 나머지 17장(양식 5·일식 6·중식 6, 2026-09-09): `D:/클로드/gen_image.py`(Cloudflare FLUX.1 schnell, `--n 2 --steps 8`)로 뽑아 한 장씩 고른 것. 900px·JPEG q82, 장당 65~131KB. 원본과 프롬프트는 `_design/discovery-src/`와 스크래치 `gen.py`(공통 꼬리: off-white ceramic · pale stone tabletop · linen napkin · overhead three-quarter · natural side daylight). 앱의 `MENU_PHOTO` 맵이 요리 이름 → 파일명을 잇고 크레딧은 `FLUX.1 schnell`로 자동 표기된다.
- 생성 원본 PNG는 로컬 제작 기록에 보관하며, 배포에는 아래 최종 JPEG를 사용한다.
- 프로젝트용 최종 파일은 JPEG quality 85로 인코딩(크기/구도 변경 없음), 357,665 bytes. 내장 도구 사용, CLI fallback 사용 안 함.
- 나머지 사진은 기존 `PHOTO`/`D.photos` 출처를 사용한다. 메뉴 탐색 하단에 라이선스/AI 참고 이미지 정보를 표시한다. 150px짜리 김치볶음밥/닭꼬치 사진은 큰 탐색 사진에 사용하지 않는다.

## 생성 프롬프트

Create one premium editorial food photograph for a mobile Korean recipe discovery app. Single dish: authentic spaghetti aglio e olio, thin golden spaghetti glistening with olive oil, visible gently toasted sliced garlic, very few red chili flakes and finely chopped flat-leaf parsley. NO tomato sauce, NO cream, NO meat. On a warm off-white ceramic shallow plate, softly lit pale neutral stone tabletop, a small folded unbleached linen napkin partly visible. Tight appetizing overhead three-quarter close-up, beautiful natural side daylight, subtle real grain, tactile imperfect handmade ceramic, beautifully tangled pasta, considered magazine food styling. Square composition, plate mostly fills frame, no text, no branding, no collage, no illustrations. Subject must remain clear in a small mobile recipe photo crop. This is an illustrative menu reference photo, not a specific creator's recipe.
