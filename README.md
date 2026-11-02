# vda5050-spec

VDA 5050(모바일 로봇과 플릿 컨트롤 사이의 MQTT 인터페이스) 질문에 Claude Code가 기억 대신 공식 원문으로 답하게 만드는 참조 스킬 플러그인이다.

## 구성

| 경로 | 내용 |
|---|---|
| `skills/vda5050-spec/SKILL.md` | 조회 규칙, 3.0 핵심 사실, 2.1→3.0 차이, 원문과 스키마 충돌의 PDF 판정 |
| `skills/vda5050-spec/spec/` | 공식 원문 markdown. 3.0.0은 GitHub `main` @ `0b2ae43`, 2.1.0은 tag `2.1.0` |
| `skills/vda5050-spec/schemas/` | 공식 JSON 스키마. 2.1.0 6개, 3.0.0 8개 |
| `skills/vda5050-spec/scripts/validate.py` | 메시지 검증: 스키마, order/state 의미 검사, 스키마에 없는 필드 경고 |
| `skills/vda5050-spec/scripts/schema_diff.py` | 2.1↔3.0 필드 diff 재생성 |
| `skills/vda5050-spec/schema-diff-2.1.0-to-3.0.0.txt` | diff 결과 |
| `tests/test_validate.py` | `validate.py` 동작 테스트 |

## 불러오기

이 폴더를 그대로 불러온다. `~/.claude/settings.json`의 `env.CLAUDE_CODE_PLUGIN_DIRS`에 이 폴더 경로를 넣고 Claude Code를 다시 시작한다. 경로가 여러 개면 `:`로 구분한다.

```json
{
  "env": {
    "CLAUDE_CODE_PLUGIN_DIRS": "/Users/bmcho/Documents/git/plan-dev-relay:/Users/bmcho/Documents/git/vda5050-spec"
  }
}
```

다시 시작하면 스킬이 `vda5050-spec:vda5050-spec`로 보인다. 한 세션에서만 쓰려면 `claude --plugin-dir <이 폴더>`로 실행한다.

마켓플레이스로 설치할 수도 있다: `claude plugin marketplace add <이 폴더>` 다음 `claude plugin install vda5050-spec@vda5050-spec`. 폴더 불러오기와 마켓플레이스 설치를 함께 쓰면 스킬이 두 번 뜨므로 하나만 쓴다.

## 메시지 검증

```bash
pip install jsonschema
python3 skills/vda5050-spec/scripts/validate.py order msg.json              # 버전은 메시지 "version"으로 판별
python3 skills/vda5050-spec/scripts/validate.py state msg.json --spec 2.1.0
```

발견한 문제마다 `error:` 또는 `warning:` 한 줄을 출력하고, 마지막에 `OK` 또는 `FAIL`을 출력한다. 각 오류에는 근거가 된 스펙 절 번호가 붙는다. 종료 코드는 0(오류 없음), 1(오류 있음), 2(버전을 알 수 없거나 토픽 스키마가 없어 검사할 수 없음)이다.

`warning:` 줄은 실패로 치지 않는다. 스키마에 없는 필드가 여기에 나오므로 2.x 이름이 섞였는지 반드시 읽는다.

## 테스트

`validate.py`를 고치면 repo 루트에서 테스트를 돌린다. jsonschema가 설치된 Python이 필요하다.

```bash
python3 -m unittest discover -s tests
```

## 스펙 갱신

`SKILL.md`의 "Refresh when upstream changes" 절차를 따른다. 갱신하면 `plugin.json`과 `marketplace.json`의 `version`을 올리고 테스트를 다시 돌린다. 2.1 스키마의 `PAUSED` 누락이 고쳐지면 해당 특성 테스트가 실패하므로, 그때 `SKILL.md`의 충돌 표도 함께 고친다.

## 출처와 라이선스

- 원문과 스키마: [VDA5050/VDA5050](https://github.com/VDA5050/VDA5050), MIT (`skills/vda5050-spec/LICENSE-VDA5050.txt`)
- `validate.py`, `schema_diff.py`, 테스트: 이 repo에서 스펙 원문 규칙을 보고 직접 작성
- VDA PDF는 저작권 때문에 넣지 않았다. 링크, 해시, 대조 결과는 `SKILL.md`에 있다.
